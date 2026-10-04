"""Preview, apply and undo report revisions without silently replacing edits."""
import tkinter as tk
from dataclasses import replace
from tkinter import ttk, messagebox
from src.reporting.revisions import SECTIONS, propose_revision, apply_proposal, section_text
from src.ui.wording import REVISION_MODES, service_message
from src.ui.theme import WHITE, INK, MUTED


class RevisionUI:
    def build_revision_ui(self):
        self.pending_revision = None
        self.revision_history = []
        self.revision_poll = None
        outer = tk.Frame(self.report_tabs, bg=WHITE)
        self.report_tabs.add(outer, text='Feedback & revisions')

        self.revision_canvas = tk.Canvas(
            outer,
            bg=WHITE,
            highlightthickness=0
        )

        scrollbar = ttk.Scrollbar(
            outer,
            orient='vertical',
            command=self.revision_canvas.yview
        )

        self.revision_canvas.configure(
            yscrollcommand=scrollbar.set
        )

        self.revision_canvas.pack(
            side='left',
            fill='both',
            expand=True
        )

        scrollbar.pack(
            side='right',
            fill='y'
        )

        page = tk.Frame(
            self.revision_canvas,
            bg=WHITE,
            padx=10,
            pady=10
        )

        self.revision_window = self.revision_canvas.create_window(
            (0, 0),
            window=page,
            anchor='nw'
        )
        tk.Label(page, text='Choose a section and how to change it, describe the change, then preview it before applying.', bg=WHITE, fg=INK, anchor='w', wraplength=680).pack(fill='x', pady=(0, 2))
        tk.Label(page, text='Ask Gemini: rewrites the section from your request, e.g. "write a three-sentence summary for a busy manager". '
                 'It sees the masked section text, your request and the calculated facts only.\n'
                 'Edit from feedback: offline rules only (make it shorter, use bullet points, use plain language, Replace X with Y, Add: text).\n'
                 'Manual replacement: paste or write the wording yourself.',
                 bg=WHITE, fg=MUTED, anchor='w', justify='left', wraplength=680).pack(fill='x', pady=(0, 8))
        options = tk.Frame(page, bg=WHITE)
        options.pack(fill='x')
        self.revision_section = ttk.Combobox(options, values=SECTIONS, state='readonly', width=23)
        self.revision_section.set(SECTIONS[0])
        self.revision_section.pack(side='left', padx=(0, 8))
        self.revision_provider = ttk.Combobox(options, values=list(REVISION_MODES), state='readonly', width=26)
        self.revision_provider.set('Ask Gemini')
        self.revision_provider.pack(side='left')
        tk.Label(page, text='Feedback / instruction', bg=WHITE, fg=MUTED, anchor='w').pack(fill='x', pady=(8, 2))
        self.feedback = self.text(page, height=2, editable=True)
        self.feedback.pack(fill='x')
        tk.Label(page, text='Replacement section (paste or write your preferred wording)', bg=WHITE, fg=MUTED, anchor='w').pack(fill='x', pady=(8, 2))
        self.replacement = self.text(page, height=5, editable=True)
        self.replacement.pack(fill='x')
        actions = tk.Frame(page, bg=WHITE)
        actions.pack(fill='x', pady=(0, 8))
        self.propose_button = self.action(actions, 'Preview revision', self.propose_feedback, True)
        self.propose_button.pack(side='left')
        self.apply_button = self.action(actions, 'Apply', self.apply_feedback)
        self.apply_button.pack(side='left', padx=6)
        self.undo_button = self.action(actions, 'Undo revision', self.undo_revision)
        self.undo_button.pack(side='left')
        self.revision_preview = self.text(page, height=1)
        self.revision_preview.pack(fill='both', expand=True)
        self.show(self.revision_preview, 'Your original draft stays unchanged until you click Apply.')
        self.resize_revision_preview()
        self.feedback.bind('<<Modified>>', self.feedback_changed)
        self.replacement.bind('<<Modified>>', self.feedback_changed)
        for widget in (self.revision_section, self.revision_provider):
            widget.bind('<<ComboboxSelected>>', lambda event: self.invalidate_revision())

        def update_scroll_region(event=None):
            self.revision_canvas.configure(
                scrollregion=self.revision_canvas.bbox('all')
            )

        page.bind(
            '<Configure>',
            update_scroll_region
        )

        def resize_inner_frame(event):
            self.revision_canvas.itemconfigure(
                self.revision_window,
                width=event.width
            )

        self.revision_canvas.bind(
            '<Configure>',
            resize_inner_frame
        )
        def on_mousewheel(event):
            widget = event.widget

            # Let text boxes use their own scrolling.
            if widget.winfo_class() == 'Text':
                return

            if event.delta > 0:
                self.revision_canvas.yview_scroll(-1, 'units')
            elif event.delta < 0:
                self.revision_canvas.yview_scroll(1, 'units')
        def enable_mousewheel(event=None):
            self.revision_canvas.bind_all(
                '<MouseWheel>',
                on_mousewheel
            )

        def disable_mousewheel(event=None):
            self.revision_canvas.unbind_all(
                '<MouseWheel>'
            )

        outer.bind(
            '<Enter>',
            enable_mousewheel
        )

        outer.bind(
            '<Leave>',
            disable_mousewheel
        )

    def resize_revision_preview(self):
        """Resize the read-only revision preview to fit its content."""
        self.revision_preview.update_idletasks()

        content = self.revision_preview.get('1.0', 'end-1c')
        if not content.strip():
            self.revision_preview.configure(height=3)
            return

        try:
            display_lines = int(
                self.revision_preview.count(
                    '1.0',
                    'end-1c',
                    'displaylines'
                )[0]
            )
        except Exception:
            display_lines = content.count('\n') + 1

        new_height = max(3, min(display_lines + 1, 18))
        self.revision_preview.configure(height=new_height)


    def sync_revision_controls(self):
        ready = bool(self.report) and not self.busy
        self.propose_button.configure(state='normal' if ready else 'disabled')
        self.apply_button.configure(state='normal' if ready and self.pending_revision else 'disabled')
        self.undo_button.configure(state='normal' if ready and self.revision_history else 'disabled')
        self.feedback.configure(state='normal' if ready else 'disabled')
        self.replacement.configure(state='normal' if ready else 'disabled')
        for widget in (self.revision_section, self.revision_provider):
            widget.configure(state='readonly' if ready else 'disabled')

    def feedback_changed(self, event=None):
        if self.feedback.edit_modified() or self.replacement.edit_modified():
            self.feedback.edit_modified(False)
            self.replacement.edit_modified(False)
            self.invalidate_revision()

    def invalidate_revision(self):
        if self.pending_revision:
            self.pending_revision = None
            self.show(self.revision_preview, 'The draft or feedback changed. Preview a new revision before applying.')
            self.resize_revision_preview()
        self.sync_revision_controls()

    def reset_revisions(self):
        self.pending_revision = None
        self.revision_history.clear()
        self.feedback.configure(state='normal')
        self.feedback.delete('1.0', 'end')
        self.feedback.edit_modified(False)
        self.replacement.configure(state='normal')
        self.replacement.delete('1.0', 'end')
        self.replacement.edit_modified(False)
        self.show(self.revision_preview, 'Your original draft stays unchanged until you click Apply.')
        self.resize_revision_preview()

    def propose_feedback(self):
        if not self.report or self.busy:
            return
        content = self.editor.get('1.0', 'end-1c')
        feedback = self.feedback.get('1.0', 'end-1c')
        replacement = self.replacement.get('1.0', 'end-1c')
        section, mode_label = self.revision_section.get(), self.revision_provider.get()
        provider = REVISION_MODES.get(mode_label, mode_label)
        consent = False  # Visible revision modes only edit or replace text on-device.
        self.pending_revision = None
        self.busy = True
        self.status.set('Preparing revision preview…')
        self.sync_controls()
        if provider == 'Gemini':
            self.status.set('Asking Gemini to revise the section…')
        future = self.pool.submit(propose_revision, self.report, content, self.review_context(), section, feedback, provider, consent, None, replacement)
        def finish():
            if not future.done():
                self.revision_poll = self.root.after(80, finish)
                return
            self.revision_poll = None
            self.busy = False
            try:
                proposal = future.result()
            except Exception as exc:
                self.status.set('Revision failed. The original draft is unchanged.')
                self.sync_controls()
                messagebox.showerror('Could not revise draft', service_message(exc), parent=self.root)
                return
            self.pending_revision = proposal
            preview = (f'## Original — {section}\n{section_text(content, section)}\n\n'
                       f'## Proposed — {mode_label}\n{section_text(proposal.revised, section)}')
            if proposal.evidence:
                preview += '\n\n## Evidence Gemini cited\n' + '\n'.join(f'- {fact}' for fact in proposal.evidence)
            if proposal.note:
                preview += f'\n\n## Note from Gemini\n{proposal.note}'
            if proposal.provider == 'Gemini':
                preview += ('\n\nThe new wording will appear as AI-written in Review claims and must be accepted '
                            'claim by claim before the report can be submitted.')
            self.render(self.revision_preview, preview)
            self.resize_revision_preview()
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
        self.revision_history.append(replace(self.report, content=current))
        section = self.pending_revision.section
        self.report = updated
        self.pending_revision = None
        self.replace_revision_text(updated.content)
        self.record('Revision applied', self.author_entry.get().strip(), section=section, method=updated.mode)
        self.show(self.revision_preview, 'Revision applied. You can restore the preceding draft with Undo revision.')
        self.resize_revision_preview()
        self.status.set('Feedback applied. Review approval has been reset.')
        self.report_tabs.select(0)

    def replace_revision_text(self, content):
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', content)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.dirty = True
        self.draft_changed()
        self.sync_controls()

    def undo_revision(self):
        if not self.revision_history or self.busy:
            return
        if not messagebox.askyesno('Restore previous draft?', 'Restore the draft saved before the last applied revision? Any later manual edits will be replaced.', parent=self.root):
            return
        previous = self.revision_history.pop()
        content = previous.content.replace('HUMAN REVIEWED', 'DRAFT — REQUIRES HUMAN REVIEW')
        self.report = replace(previous, content=content, status='DRAFT — REQUIRES HUMAN REVIEW')
        self.pending_revision = None
        self.replace_revision_text(content)
        self.record('Revision undone', self.author_entry.get().strip())
        self.show(self.revision_preview, 'Previous draft restored. All approval checks must be repeated.')
        self.resize_revision_preview()

