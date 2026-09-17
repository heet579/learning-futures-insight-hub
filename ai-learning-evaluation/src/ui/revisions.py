"""Preview, apply and undo report revisions without silently replacing edits."""
import tkinter as tk
from tkinter import ttk, messagebox
from src.reporting.revisions import SECTIONS, propose_revision, apply_proposal, section_text


class RevisionUI:
    def build_revision_ui(self):
        self.pending_revision = None
        self.revision_history = []
        self.revision_poll = None
        page = tk.Frame(self.report_tabs, bg='#FFFFFF', padx=10, pady=10)
        self.report_tabs.add(page, text='Feedback & revisions')
        tk.Label(page, text='Describe what should change, preview the revision, then apply it.', bg='#FFFFFF', fg='#172B43', anchor='w', wraplength=500).pack(fill='x', pady=(0, 8))
        options = tk.Frame(page, bg='#FFFFFF')
        options.pack(fill='x')
        self.revision_section = ttk.Combobox(options, values=SECTIONS, state='readonly', width=23)
        self.revision_section.set(SECTIONS[0])
        self.revision_section.pack(side='left', padx=(0, 8))
        self.revision_provider = ttk.Combobox(options, values=['Offline edits', 'Azure AI'], state='readonly', width=15)
        self.revision_provider.set('Offline edits')
        self.revision_provider.pack(side='left')
        tk.Label(page, text='Offline: make it shorter / use bullet points / use plain language.\nAzure AI: free-form feedback; requires your configured Azure deployment.', bg='#FFFFFF', fg='#63758B', anchor='w', justify='left', wraplength=540).pack(fill='x', pady=8)
        self.feedback = self.text(page, height=3, editable=True)
        self.feedback.pack(fill='x')
        self.external_consent = tk.BooleanVar(master=self.root, value=False)
        self.consent_check = ttk.Checkbutton(page, text='I approve sending the masked section, feedback and evidence\nto the configured Azure AI service.', variable=self.external_consent)
        self.consent_check.pack(anchor='w', pady=6)
        actions = tk.Frame(page, bg='#FFFFFF')
        actions.pack(fill='x', pady=(0, 8))
        self.propose_button = self.action(actions, 'Preview revision', self.propose_feedback, True)
        self.propose_button.pack(side='left')
        self.apply_button = self.action(actions, 'Apply', self.apply_feedback)
        self.apply_button.pack(side='left', padx=6)
        self.undo_button = self.action(actions, 'Undo revision', self.undo_revision)
        self.undo_button.pack(side='left')
        self.revision_preview = self.text(page, height=6)
        self.revision_preview.pack(fill='both', expand=True)
        self.show(self.revision_preview, 'Your original draft stays unchanged until you click Apply.')
        self.feedback.bind('<<Modified>>', self.feedback_changed)
        for widget in (self.revision_section, self.revision_provider):
            widget.bind('<<ComboboxSelected>>', lambda event: self.invalidate_revision())

    def sync_revision_controls(self):
        ready = bool(self.report) and not self.busy
        self.propose_button.configure(state='normal' if ready else 'disabled')
        self.apply_button.configure(state='normal' if ready and self.pending_revision else 'disabled')
        self.undo_button.configure(state='normal' if ready and self.revision_history else 'disabled')
        self.feedback.configure(state='normal' if ready else 'disabled')
        for widget in (self.revision_section, self.revision_provider):
            widget.configure(state='readonly' if ready else 'disabled')
        self.consent_check.configure(state='normal' if ready else 'disabled')

    def feedback_changed(self, event=None):
        if self.feedback.edit_modified():
            self.feedback.edit_modified(False)
            self.invalidate_revision()

    def invalidate_revision(self):
        if self.pending_revision:
            self.pending_revision = None
            self.show(self.revision_preview, 'The draft or feedback changed. Preview a new revision before applying.')
        self.sync_revision_controls()

    def reset_revisions(self):
        self.pending_revision = None
        self.revision_history.clear()
        self.external_consent.set(False)
        self.feedback.configure(state='normal')
        self.feedback.delete('1.0', 'end')
        self.feedback.edit_modified(False)
        self.show(self.revision_preview, 'Your original draft stays unchanged until you click Apply.')

    def propose_feedback(self):
        if not self.report or self.busy:
            return
        content = self.editor.get('1.0', 'end-1c')
        feedback = self.feedback.get('1.0', 'end-1c')
        section, provider = self.revision_section.get(), self.revision_provider.get()
        consent = self.external_consent.get()
        self.pending_revision = None
        self.busy = True
        self.progress.start(12)
        self.status.set('Preparing revision preview…')
        self.sync_controls()
        future = self.pool.submit(propose_revision, self.report, content, self.context, section, feedback, provider, consent)
        def finish():
            if not future.done():
                self.revision_poll = self.root.after(80, finish)
                return
            self.revision_poll = None
            self.busy = False
            self.progress.stop()
            self.progress.configure(value=0)
            try:
                proposal = future.result()
            except Exception as exc:
                self.status.set('Revision failed. The original draft is unchanged.')
                self.sync_controls()
                messagebox.showerror('Could not revise draft', str(exc), parent=self.root)
                return
            self.pending_revision = proposal
            self.render(self.revision_preview, f'## Original — {section}\n{section_text(content, section)}\n\n## Proposed — {provider}\n{section_text(proposal.revised, section)}')
            self.status.set('Revision preview ready. Review the wording and click Apply to use it.')
            self.sync_controls()
        self.revision_poll = self.root.after(80, finish)

    def apply_feedback(self):
        if not self.pending_revision or self.busy:
            return
        current = self.editor.get('1.0', 'end-1c')
        try:
            updated = apply_proposal(self.report, current, self.pending_revision)
        except ValueError as exc:
            messagebox.showerror('Preview is out of date', str(exc), parent=self.root)
            self.invalidate_revision()
            return
        from src.models import ReportDraft
        self.revision_history.append(ReportDraft(self.report.audience, current, self.report.status, self.report.mode))
        self.report = updated
        self.pending_revision = None
        self.replace_revision_text(updated.content)
        self.report_status.set(f'Revision applied • {len(self.revision_history)} change(s) • review required')
        self.show(self.revision_preview, 'Revision applied. You can restore the preceding draft with Undo revision.')
        self.status.set('Feedback applied. Review approval has been reset.')
        self.report_tabs.select(1)

    def replace_revision_text(self, content):
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', content)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.confirmed.set(False)
        self.dirty = True
        self.refresh_preview()
        self.sync_controls()

    def undo_revision(self):
        if not self.revision_history or self.busy:
            return
        if not messagebox.askyesno('Restore previous draft?', 'Restore the draft saved before the last applied revision? Any later manual edits will be replaced.', parent=self.root):
            return
        from src.models import ReportDraft
        previous = self.revision_history.pop()
        content = previous.content.replace('HUMAN REVIEWED', 'DRAFT — REQUIRES HUMAN REVIEW')
        self.report = ReportDraft(previous.audience, content, 'DRAFT — REQUIRES HUMAN REVIEW', previous.mode)
        self.pending_revision = None
        self.replace_revision_text(content)
        self.report_status.set('Previous draft restored • review required')
        self.show(self.revision_preview, 'Previous draft restored. All approval checks must be repeated.')
