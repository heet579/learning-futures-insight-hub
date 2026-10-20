"""Saved drafts, isolated from the SQLite implementation."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from src.storage.reports import ReportRepository
from src.storage.snapshot import pack, unpack
from src.ui.theme import WHITE, INK, MUTED


class LibraryUI:
    def init_library(self):
        self.repository = ReportRepository()
        self.library_id = self.library_version = self.saved_snapshot = None
        self.library_title = ''

    def build_library(self):
        page = self.pages[3]
        tk.Label(page, text='Your reports', bg=page.cget('bg'), fg=INK,
                 font=(self.font_family, 16, 'bold')).pack(anchor='w')
        tk.Label(page, text='Create a report or continue a saved draft. This library currently shows drafts saved by your account on this computer.',
                 bg=page.cget('bg'), fg=MUTED, wraplength=750, justify='left').pack(anchor='w', pady=(6, 14))
        bar = ttk.Frame(page)
        bar.pack(fill='x', pady=(0, 12))
        self.create_report_button = self.action(bar, '+ Create report', self.create_report, True)
        self.create_report_button.pack(side='left', padx=(0, 8))
        ttk.Button(bar, text='Refresh', command=self.refresh_library).pack(side='left')
        self.library_rows = tk.Frame(page, bg=WHITE)
        self.library_rows.pack(fill='both', expand=True)

    def refresh_library(self):
        for widget in self.library_rows.winfo_children():
            widget.destroy()
        try:
            rows = self.repository.list_owned(self.username) if self.username else []
        except Exception as exc:
            tk.Label(self.library_rows, text=f'Could not open report library: {exc}', bg=WHITE, wraplength=700).pack(pady=20)
            return
        if not rows:
            tk.Label(self.library_rows, text='No saved reports yet.\n\nChoose Create report to start with your survey files.\nYou will name your report when you first save a draft.',
                     bg=WHITE, fg=MUTED, wraplength=700).pack(padx=20, pady=30)
            return
        canvas = tk.Canvas(self.library_rows, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.library_rows, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        inner = tk.Frame(canvas, bg=WHITE)
        window = canvas.create_window(0, 0, window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        for row in rows:
            line = tk.Frame(inner, bg=WHITE, padx=16, pady=12)
            line.pack(fill='x')
            ttk.Button(line, text='Continue editing', command=lambda rid=row['id']: self.open_library_report(rid)).pack(side='right', padx=(12, 0))
            tk.Label(line, text=row['title'], bg=WHITE, fg=INK, anchor='w', wraplength=520,
                     font=(self.font_family, 11, 'bold')).pack(fill='x')
            from datetime import datetime
            updated = datetime.fromisoformat(row['updated']).astimezone().strftime('%d %b %Y %H:%M')
            tk.Label(line, text=f"{row['course']} · {row['owner']} · {row['status']} · {updated}",
                     bg=WHITE, fg=MUTED, anchor='w', wraplength=520).pack(fill='x', pady=(4, 0))

    def create_report(self):
        if self.busy or not self.may_replace():
            return False
        # Rebuild the workspace just as on account switching. This also cancels
        # queued callbacks so an old dataset cannot leak into a new report.
        root, username, callback, repository = self.root, self.username, self.on_logout, self.repository
        self.dispose_workspace()
        self.__dict__.clear()
        self.__init__(root, username=username, on_logout=callback)
        self.repository = repository
        self.navigate(0)
        self.status.set('New report · import survey files to begin. Name it when you save your first draft.')
        return True

    def continue_report(self):
        if self.busy:
            return
        if self.current_page == 0 and self.context:
            self.navigate(1)
        elif self.current_page == 1 and self.context and self.theme_review.complete:
            self.navigate(2)
        elif self.current_page == 2 and self.report:
            if not self.theme_review.complete or self.themes_changed_since_draft:
                self.navigate(1)
            elif self.ledger.pending or self.update_evidence_check():
                self.select_report_tab(3)
            else:
                self.review_drawer_pinned = True
                self.open_review_drawer()

    def update_journey(self):
        if not hasattr(self, 'next_button') or not hasattr(self, 'feedback'):
            return
        if self.report:
            self.report_tabbar.pack(fill='x', before=self.report_tabs)
        else:
            self.report_tabbar.pack_forget()
            self.report_tabs.select(1)
        title = self.library_title or 'Untitled report'
        state = 'Unsaved changes' if self.library_unsaved() else ('Saved' if self.library_id else 'Not saved yet')
        self.workspace_caption.configure(text=f'{title[:55]} · {state}')
        page = getattr(self, 'current_page', 3)
        enabled = bool(self.context)
        if page == 0:
            text = 'Continue to themes →'
            hint = 'Review the data, then check its themes.' if self.context else 'Import CSV or Excel to begin. Name your report when you save.'
        elif page == 1:
            remaining = self.theme_review.total - self.theme_review.reviewed
            text = 'Continue to report →'
            enabled = enabled and self.theme_review.complete
            hint = f'{remaining} themes still need a decision.' if remaining else 'Themes checked. Continue to generate your report.'
        else:
            enabled = bool(self.report)
            text = 'Check facts & quotes →'
            if not self.context:
                hint = 'Start with survey files in Explore data.'
            elif not self.theme_review.complete:
                hint, text = 'Review all themes before generating a draft.', 'Review themes →'
            elif not self.report:
                hint = 'Choose your report type, then Generate draft.'
            elif self.themes_changed_since_draft:
                hint, text = 'Theme decisions changed. Regenerate the draft before checking it.', 'Review themes →'
            elif self.ledger.pending:
                hint = f'{len(self.ledger.pending)} claims still need checking. Read the preview, then check facts & quotes.'
            elif self.update_evidence_check():
                hint = 'Fix unmatched figures or quotes before submission.'
            else:
                text = 'Review & export →'
                if self.workflow.status == 'AWAITING HUMAN REVIEW':
                    hint = 'Submitted. A second person must complete the approval controls before export.'
                elif self.workflow.status == 'HUMAN REVIEWED':
                    hint = 'Approved and exported. Open review details to inspect the approval record.'
                    text = 'Review details →'
                else:
                    hint = 'Checks complete. Open approval controls for submission and export.'
        self.journey_hint.configure(text=hint)
        self.next_button.configure(text=text, state='normal' if enabled and not self.busy else 'disabled')
        if hasattr(self, 'generate_button'):
            self.generate_button.configure(state='normal' if self.context and self.theme_review.complete and not self.busy else 'disabled',
                                           text='Regenerate draft' if self.report else 'Generate draft',
                                           style='TButton' if self.report else 'Primary.TButton')

    def workspace_snapshot(self):
        state = {name: getattr(self, name) for name in (
            'raw', 'frame', 'context', 'source', 'loaded_file_label', 'masked_count', 'report', 'workflow',
            'themes_changed_since_draft', 'pending_revision', 'revision_history',
            'revision_section_decisions', 'revision_section_snapshots')}
        state.update(content=self.editor.get('1.0', 'end-1c'),
                     theme_decisions=self.theme_review.decisions,
                     claim_decisions=self.ledger.decisions, claim_history=self.ledger.history,
                     revision_input=self.feedback.get('1.0', 'end-1c'),
                     revision_method=self.revision_provider.get(),
                     replacement_input=self.replacement.get('1.0', 'end-1c'),
                     revision_selection=self.selected_revision_sections(),
                     audience=self.audience.get())
        return pack(state)

    def library_unsaved(self):
        if self.context is None or not self.username:
            return self.dirty
        return self.saved_snapshot != self.workspace_snapshot()

    def save_library_draft(self):
        if self.busy or self.context is None:
            return False
        if not self.username:
            messagebox.showinfo('Sign in required', 'Sign in before saving to the library.', parent=self.root)
            return False
        if self.workflow.status not in ('DRAFT', 'CHANGES REQUESTED'):
            messagebox.showinfo('Editable drafts only', 'This release saves editable drafts. Submitted or approved reports can still be exported.', parent=self.root)
            return False
        title = self.library_title
        if not title:
            title = simpledialog.askstring('Save draft', 'Report name:', initialvalue=f'{self.context.course_name} — {self.audience.get()}', parent=self.root)
            if not title or not title.strip():
                return False
        try:
            self.refresh_claims()
            snapshot = self.workspace_snapshot()
            rid, version = self.repository.save(actor=self.username, title=title,
                course=self.context.course_name, status=self.workflow.status,
                snapshot=snapshot, report_id=self.library_id, version=self.library_version)
        except Exception as exc:
            messagebox.showerror('Could not save draft', str(exc), parent=self.root)
            return False
        self.library_id, self.library_version = rid, version
        self.library_title, self.saved_snapshot = title.strip(), snapshot
        self.dirty = False
        self.update_journey()
        self.record('Library draft saved', self.username, report_id=rid, version=version)
        self.status.set(f'Saved · {self.library_title} · available in Report library')
        return True

    def open_library_report(self, report_id):
        if self.busy:
            return False
        try:
            row = self.repository.load(report_id, self.username)
            state = unpack(row['snapshot'])
        except Exception as exc:
            messagebox.showerror('Cannot open draft', str(exc), parent=self.root)
            return False
        if not self.may_replace():
            return False
        # The entire snapshot is decoded before replacing the current workspace.
        self.raw, self.source, self.loaded_file_label = state['raw'], state['source'], state['loaded_file_label']
        self.apply_analysis((state['frame'], state['context'], state['masked_count'], []))
        for name in ('report', 'workflow', 'themes_changed_since_draft'):
            setattr(self, name, state[name])
        self.theme_review.decisions = state['theme_decisions']
        self.refresh_theme_rows()
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', state['content'])
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.ledger.decisions = state['claim_decisions']
        self.ledger.history = state['claim_history']
        self.refresh_claims()
        self.revision_provider.set(state['revision_method'])
        for name, variable in self.revision_section_vars.items():
            variable.set(name in state['revision_selection'])
        self.update_revision_mode_ui()
        self.feedback.configure(state='normal')
        self.feedback.delete('1.0', 'end')
        self.feedback.insert('1.0', state['revision_input'])
        self.feedback.edit_modified(False)
        self.replacement.configure(state='normal')
        self.replacement.delete('1.0', 'end')
        self.replacement.insert('1.0', state.get('replacement_input', ''))
        self.replacement.edit_modified(False)
        for name in ('pending_revision', 'revision_history', 'revision_section_decisions', 'revision_section_snapshots'):
            setattr(self, name, state[name])
        if self.pending_revision:
            self._build_revision_preview_tabs(self.pending_revision.sections)
            self.show_revision_comparison(self.pending_revision.sections[0])
        self.audience.set(state.get('audience', self.report.audience if self.report else 'facilitator'))
        self.confirmed.set(False)
        self.file_name.configure(text=self.loaded_file_label or self.source)
        self.file_state.configure(text='LOADED FILE')
        self.insights_cache.clear()
        self.question_cache.clear()
        self.library_id, self.library_version = row['id'], row['version']
        self.library_title = row['title']
        self.dirty = False
        self.saved_snapshot = self.workspace_snapshot()
        self.refresh_preview()
        self.update_evidence_check()
        self.sync_controls()
        self.report_tabs.select(1)
        self.navigate(2 if self.report or self.theme_review.complete else 1)
        self.record('Library draft opened', self.username, report_id=row['id'], version=row['version'])
        self.status.set(f'Opened · {row["title"]} · saved review progress restored')
        return True
