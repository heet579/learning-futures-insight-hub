"""Authenticated, persistent two-person review and repeatable approved export."""
from pathlib import Path
import os
from tkinter import messagebox, filedialog


from src.ui.review_experience import ReviewExperienceUI


class HandoffUI(ReviewExperienceUI):
    def can_edit_workspace(self):
        if not self.username:
            return True  # Legacy direct DesktopApp callers; production always signs in.
        return (not self.library_owner or self.library_owner == self.username) and self.workflow.status in ('DRAFT', 'CHANGES REQUESTED')

    def can_review_workspace(self):
        return bool(self.username and self.library_id and self.library_owner != self.username
                    and self.workflow.status == 'AWAITING HUMAN REVIEW')

    def submit_persistent(self):
        if self.busy or not self.report or not self.can_edit_workspace():
            return False
        self.refresh_claims()
        blockers = self.review_blockers()
        if blockers:
            messagebox.showinfo('Not ready to submit', '\n'.join(blockers), parent=self.root)
            return False
        if not self.save_library_draft():
            return False
        if not self.persist_review_action('submit'):
            return False
        self.status.set('Submitted and saved. Switch accounts; the second reviewer can open Pending review in Library.')
        return True

    def persist_review_action(self, action, **kwargs):
        try:
            version, state = self.repository.transition(actor=self.username, report_id=self.library_id,
                version=self.library_version, action=action, audit=self.audit, **kwargs)
        except Exception as exc:
            messagebox.showerror('Could not update review', str(exc), parent=self.root)
            return False
        self.handoff_success = action in ('submit', 'approve')
        self.library_version = version
        self.workflow = state['workflow']
        self.approved_export = state.get('approved_export', '')
        self.dirty = False
        self.saved_snapshot = self.workspace_snapshot()
        self.record('Review state saved', self.username, report_id=self.library_id,
                    action_taken=action, version=version, status=self.workflow.status)
        self.sync_controls()
        self.update_audit_status()
        self.refresh_preview()
        self.select_report_tab(1)
        return True

    def approve_persistent(self):
        if self.busy or not self.can_review_workspace():
            return False
        if not self.persist_review_action('approve', role=self.approver_role.get(), confirmed=self.confirmed.get()):
            return False
        self.status.set('Approval saved. Export approved to download the report; it also remains in Library → Approved.')
        return True

    def return_persistent(self):
        from tkinter import simpledialog
        if self.busy or not self.can_review_workspace():
            return False
        notes = simpledialog.askstring('Return for changes', 'What must the first reviewer change?', parent=self.root)
        if not notes or not notes.strip():
            return False
        owner = self.library_owner
        if not self.persist_review_action('return', notes=notes.strip()):
            return False
        self.reset_library_workspace(3)
        self.select_library_view('pending')
        self.status.set(f'Returned to {owner}. They can read your notes in My reports, edit and submit again.')
        return True

    def export_approved(self):
        if self.busy or self.workflow.status != 'HUMAN REVIEWED' or not self.library_id:
            return False
        from src.storage.snapshot import unpack
        from src.reporting.designed_report import export_bytes
        try:
            # Export the immutable saved approval, never whatever is in the editor.
            state = unpack(self.repository.load(self.library_id, self.username)['snapshot'])
            final = state.get('approved_export')
            if state['workflow'].status != 'HUMAN REVIEWED' or not final:
                raise ValueError('No approved export is stored. Reopen the report from Library.')
        except Exception as exc:
            messagebox.showerror('Cannot export report', str(exc), parent=self.root)
            return False
        path = filedialog.asksaveasfilename(parent=self.root, title='Export approved report',
            initialdir=str(Path.cwd()),
            initialfile=f'learning_evaluation_{state["report"].audience}_reviewed.docx',
            defaultextension='.docx', filetypes=[('Word document', '*.docx'), ('PDF', '*.pdf'), ('Markdown', '*.md')])
        if not path:
            return False
        try:
            suffix = Path(path).suffix.lower()
            if suffix not in ('.docx', '.pdf', '.md'):
                raise ValueError('Choose a .docx, .pdf or .md filename.')
            data = export_bytes(state, final, suffix[1:])
            Path(path).write_bytes(data)
        except Exception as exc:
            messagebox.showerror('Export failed', f'{exc}\n\nThe approval is saved. You can try exporting again.', parent=self.root)
            return False
        self.record('Approved report exported', self.username, report_id=self.library_id, file=Path(path).name)
        self.status.set(f'Approved report exported · {Path(path).name}')
        return True

    def sync_handoff_controls(self):
        if not self.username or not hasattr(self, 'approver_entry'):
            return
        editable = self.can_edit_workspace() and not self.busy
        reviewing = self.can_review_workspace() and not self.busy
        approved = self.workflow.status == 'HUMAN REVIEWED' and bool(self.library_id) and not self.busy
        self.library_save_button.configure(state='normal' if editable and self.context else 'disabled')
        self.submit_button.configure(text='Submit for review', state='normal' if editable and self.report else 'disabled')
        self.export_button.configure(text='Export approved' if approved else 'Approve report',
                                     state='normal' if reviewing or approved else 'disabled')
        self.return_button.configure(state='normal' if reviewing else 'disabled')
        self.review_check.configure(state='normal' if reviewing else 'disabled')
        self.approver_role.configure(state='readonly' if reviewing else 'disabled')
        for entry, value in ((self.author_entry, self.library_owner or self.username),
                             (self.approver_entry, self.workflow.approver or (self.username if reviewing else ''))):
            entry.configure(state='normal')
            entry.delete(0, 'end')
            entry.insert(0, value)
            entry.configure(state='readonly')
        self.editor.configure(state='normal' if editable and self.report else 'disabled')
        self.audience.configure(state='readonly' if editable else 'disabled')
        self.generate_button.configure(state='normal' if editable and self.context and self.theme_review.complete else 'disabled')
        for button in (self.accept_claim_button, self.reject_claim_button):
            button.configure(state='normal' if editable and self.report and self.ledger.claims else 'disabled')
        for button in (self.confirm_theme_button, self.reject_theme_button):
            button.configure(state='normal' if editable and self.context and self.theme_review.total else 'disabled')
        self.theme_category.configure(state='readonly' if editable else 'disabled')
        if not editable:
            for widget in (self.propose_button, self.undo_button, self.apply_section_button,
                           self.keep_original_button, self.feedback, self.replacement, self.revision_provider):
                widget.configure(state='disabled')
            for button in self.revision_section_buttons.values():
                button.configure(state='disabled')

        self.update_handoff_surface()
        self.update_progress_drawer()
        self.sync_report_tabs()
