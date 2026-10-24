"""Saved drafts, isolated from the SQLite implementation."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from src.remote import report_repository
from src.storage.snapshot import pack, unpack
from src.ui.theme import BG, WHITE, INK, MUTED, TEAL, BORDER


class LibraryUI:
    def init_library(self):
        self.repository = report_repository()
        self.library_id = self.library_version = self.saved_snapshot = None
        self.library_title = ''
        self.library_owner = ''
        self.approved_export = ''
        self.handoff_success = False
        self.feedback_expanded = False
        self.library_view = 'mine'
        self.library_action_buttons = []
        self.library_cards = {}
        self.library_open_actions = None
        self.library_bindings = {}

    def build_library(self):
        page = self.pages[3]
        heading = tk.Frame(page, bg=BG)
        heading.pack(fill='x', pady=(0, 6))
        tk.Label(heading, text='Reports & reviews', bg=BG, fg=INK,
                 font=(self.font_family, 16, 'bold')).pack(side='left')
        self.library_count = tk.Label(heading, text='', bg=BG, fg=MUTED,
                                      font=(self.font_family, 10))
        self.library_count.pack(side='left', padx=12)
        tk.Label(page, text='Continue your work, review a colleague’s submission, or export an approved report.',
                 bg=BG, fg=MUTED, anchor='w').pack(fill='x', pady=(0, 16))
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill='x', pady=(0, 16))
        self.create_report_button = self.action(bar, '+ Create report', self.create_report, True)
        self.create_report_button.configure(style='Create.Library.Primary.TButton')
        self.create_report_button.pack(side='left', padx=(0, 10))
        ttk.Button(bar, text='Refresh', style='Library.TButton', command=self.refresh_library).pack(side='left')
        tk.Label(bar, text='Shared review library · this computer', bg=BG, fg=MUTED,
                 font=(self.font_family, 9)).pack(side='right')
        views = tk.Frame(page, bg=BG)
        views.pack(fill='x', pady=(0, 12))
        self.library_view_buttons = {}
        for key, caption in [('mine', 'My reports'), ('pending', 'Pending review'), ('approved', 'Approved')]:
            button = ttk.Button(views, text=caption, style='Tab.Library.TButton',
                                command=lambda view=key: self.select_library_view(view))
            button.pack(side='left', padx=(0, 8))
            self.library_view_buttons[key] = button
        self.library_attention = tk.Label(page, bg='#FFF3DA', fg='#805400', anchor='w',
            justify='left', padx=12, pady=8, width=1, wraplength=740)
        self.library_attention.bind('<Configure>', lambda e: self.library_attention.configure(wraplength=max(200, e.width - 24)))
        self.library_rows = tk.Frame(page, bg=BG)
        self.library_rows.pack(fill='both', expand=True)
        self.library_bindings = {
            '<Button-1>': self.root.bind('<Button-1>', self.dismiss_library_actions, add='+'),
            '<Escape>': self.root.bind('<Escape>', lambda e: self.close_library_actions(restore_focus=True), add='+'),
        }

    def select_library_view(self, view):
        self.library_view = view
        self.refresh_library()

    def close_library_actions(self, restore_focus=False):
        item = self.library_open_actions
        if item:
            item['panel'].grid_remove()
            item['trigger'].configure(text='More ▾')
            if restore_focus:
                item['trigger'].focus_set()
        self.library_open_actions = None

    def toggle_library_actions(self, report_id):
        if self.busy:
            return
        item = self.library_cards[report_id]
        if not item['editable']:
            return
        already_open = self.library_open_actions is item
        self.close_library_actions()
        if not already_open:
            item['panel'].grid()
            item['trigger'].configure(text='More ▴')
            self.library_open_actions = item
            item['rename'].focus_set()

    def dismiss_library_actions(self, event):
        if not self.library_open_actions:
            return
        widget = event.widget
        while widget is not None:
            if widget in (self.library_open_actions['panel'], self.library_open_actions['trigger']):
                return
            widget = getattr(widget, 'master', None)
        self.close_library_actions()

    def run_library_action(self, action, row):
        self.close_library_actions()
        return action(row)

    def refresh_library(self):
        self.close_library_actions()
        self.library_action_buttons = []
        self.library_cards = {}
        for widget in self.library_rows.winfo_children():
            widget.destroy()
        self.library_count.configure(text='')
        self.library_attention.pack_forget()
        try:
            groups = {
                'mine': self.repository.list_owned(self.username) if self.username else [],
                'pending': self.repository.list_pending(self.username) if self.username else [],
                'approved': self.repository.list_approved(self.username) if self.username else [],
            }
            for key, caption in [('mine', 'My reports'), ('pending', 'Pending review'), ('approved', 'Approved')]:
                self.library_view_buttons[key].configure(text=f'{caption} ({len(groups[key])})',
                    style='Selected.Tab.Library.TButton' if key == self.library_view else 'Tab.Library.TButton')
            needs_changes = sum(r['status'] == 'CHANGES REQUESTED' for r in groups['mine'])
            notices = []
            if needs_changes:
                notices.append(f'{needs_changes} returned report(s): open My reports to read feedback and make changes.')
            if groups['pending']:
                notices.append(f'{len(groups["pending"])} report(s) need your second review: open Pending review above.')
            if notices:
                self.library_attention.configure(text='\n'.join(notices))
                self.library_attention.pack(fill='x', before=self.library_rows, pady=(0, 12))
            rows = groups[self.library_view]
            if self.library_view == 'mine':
                rows.sort(key=lambda row: row['status'] != 'CHANGES REQUESTED')
        except Exception as exc:
            tk.Label(self.library_rows, text=f'Could not open report library: {exc}', bg=BG, wraplength=700).pack(pady=20)
            return
        self.library_count.configure(text=f'{len(rows)} saved')
        if not rows:
            empty = tk.Frame(self.library_rows, bg=WHITE, highlightbackground=BORDER, highlightthickness=1,
                             padx=24, pady=32)
            empty.pack(fill='x')
            tk.Label(empty, text={'mine': 'Your next report starts here', 'pending': 'No reports waiting for your review', 'approved': 'No approved reports yet'}[self.library_view], bg=WHITE, fg=INK,
                     font=(self.font_family, 14, 'bold')).pack(anchor='w')
            tk.Label(empty, text={'mine': 'Create a report to begin. Reports you save stay here; submit them when ready for a second reviewer.',
                           'pending': 'A different account must choose Complete & submit first. Saving a personal draft does not submit it.',
                           'approved': 'Reports approved by you, or approved reports you created, will appear here for export.'}[self.library_view],
                     bg=WHITE, fg=MUTED, justify='left', wraplength=700).pack(anchor='w', pady=(10, 0))
            return
        canvas = tk.Canvas(self.library_rows, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.library_rows, orient='vertical', command=canvas.yview)
        def scroll_region(first, last):
            scrollbar.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()
        self.library_rows.columnconfigure(0, weight=1)
        self.library_rows.rowconfigure(0, weight=1)
        scrollbar.grid(row=0, column=1, sticky='ns', padx=(8, 0))
        canvas.grid(row=0, column=0, sticky='nsew')
        canvas.configure(yscrollcommand=scroll_region)
        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window(0, 0, window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        for row in rows:
            self.build_library_card(inner, row)

    def build_library_card(self, parent, row):
        from datetime import datetime
        card = tk.Frame(parent, bg=WHITE, padx=18, pady=16,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', pady=(0, 12))
        card.columnconfigure(0, weight=1)
        info = tk.Frame(card, bg=WHITE)
        info.grid(row=0, column=0, sticky='nsew', padx=(18, 20))
        tk.Frame(card, bg=TEAL, width=3).place(x=0, y=0, relheight=1)
        state_text = {'DRAFT': 'Draft', 'CHANGES REQUESTED': 'Changes requested', 'AWAITING HUMAN REVIEW': 'Awaiting second reviewer', 'HUMAN REVIEWED': 'Approved'}.get(row['status'], row['status'])
        tk.Label(info, text=state_text, bg='#FFF3DA' if row['status'] == 'CHANGES REQUESTED' else '#F0E9FC',
                 fg='#805400' if row['status'] == 'CHANGES REQUESTED' else '#6530B3', padx=9, pady=3,
                 font=(self.font_family, 9, 'bold')).pack(anchor='w', pady=(0, 9))
        title = tk.Label(info, text=row['title'], bg=WHITE, fg=INK, anchor='w', justify='left',
                         font=(self.font_family, 14, 'bold'), width=1, wraplength=420)
        title.pack(fill='x')
        title.bind('<Configure>', lambda e: title.configure(wraplength=max(100, e.width)))
        scope = tk.Label(info, text=row['course'], bg=WHITE, fg=MUTED, anchor='w', justify='left',
                         font=(self.font_family, 10), width=1, wraplength=420)
        scope.pack(fill='x', pady=(5, 14))
        scope.bind('<Configure>', lambda e: scope.configure(wraplength=max(100, e.width)))
        updated = datetime.fromisoformat(row['updated']).astimezone().strftime('%d %b %Y · %H:%M')
        details = tk.Label(info, text=f"First reviewer: {row['owner']}\nSecond reviewer: {row.get('reviewer') or 'Not yet reviewed'}\nLast saved: {updated}",
                           bg=WHITE, fg=MUTED, anchor='w', justify='left', width=1, wraplength=420,
                           font=(self.font_family, 9))
        details.pack(fill='x')
        details.bind('<Configure>', lambda e: details.configure(wraplength=max(100, e.width)))
        feedback = None
        if row.get('return_notes'):
            summary = ' '.join(row['return_notes'].split())
            if len(summary) > 160:
                summary = summary[:157] + '…'
            feedback = tk.Label(info, text=f'Returned by {row["returned_by"]}: {summary}',
                bg='#FFF3DA', fg='#805400', anchor='w', justify='left', width=1,
                padx=8, pady=7, wraplength=420, font=(self.font_family, 10))
            feedback.pack(fill='x', pady=(10, 0))
            feedback.bind('<Configure>', lambda e: feedback.configure(wraplength=max(100, e.width - 16)))
        actions = tk.Frame(card, bg=WHITE)
        actions.grid(row=0, column=1, sticky='ne')
        state = 'disabled' if self.busy else 'normal'
        editable = row['owner'] == self.username and row['status'] in ('DRAFT', 'CHANGES REQUESTED')
        caption = 'Continue editing →' if editable else ('Review report →' if row['status'] == 'AWAITING HUMAN REVIEW' and row['owner'] != self.username else 'View report →')
        if editable and row['status'] == 'CHANGES REQUESTED':
            caption = 'Read feedback →'
        resume = ttk.Button(actions, text=caption, style='Library.TButton', state=state,
                            command=lambda: self.open_library_report(row['id']))
        resume.pack(side='left', padx=(0, 8))
        trigger = ttk.Button(actions, text='More ▾', style='More.Library.TButton', state=state,
                             command=lambda: self.toggle_library_actions(row['id']))
        if editable:
            trigger.pack(side='left')
        panel = tk.Frame(card, bg='#FAF8FD', padx=12, pady=10,
                         highlightbackground=BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(14, 0))
        tk.Label(panel, text='Manage draft', bg='#FAF8FD', fg=MUTED,
                 font=(self.font_family, 9)).pack(side='left')
        delete = ttk.Button(panel, text='Delete draft', style='Danger.Library.TButton', state=state,
                            command=lambda: self.run_library_action(self.delete_library_report, row))
        delete.pack(side='right', padx=(8, 0))
        rename = ttk.Button(panel, text='Rename', style='Library.TButton', state=state,
                            command=lambda: self.run_library_action(self.rename_library_report, row))
        rename.pack(side='right')
        panel.grid_remove()
        self.library_action_buttons.extend((resume, trigger, rename, delete))
        self.library_cards[row['id']] = dict(panel=panel, trigger=trigger, rename=rename,
                                             delete=delete, resume=resume, card=card, details=details, feedback=feedback, editable=editable)

    def create_report(self):
        if self.busy or not self.may_replace():
            return False
        self.reset_library_workspace(0)
        self.status.set('New report · import survey files to begin. Name it when you save your first draft.')
        return True

    def reset_library_workspace(self, page):
        # Rebuild the workspace just as on account switching. This also cancels
        # queued callbacks so an old dataset cannot leak into a new report.
        root, username, callback, repository = self.root, self.username, self.on_logout, self.repository
        self.dispose_workspace()
        self.__dict__.clear()
        self.__init__(root, username=username, on_logout=callback)
        self.repository = repository
        self.navigate(page)

    def rename_library_report(self, row):
        if self.busy:
            return False
        current = row['id'] == self.library_id
        title = simpledialog.askstring('Rename draft', 'Report name:',
                                      initialvalue=self.library_title if current else row['title'],
                                      parent=self.root)
        if title is None:
            return False
        title = title.strip()
        if not title:
            messagebox.showinfo('Report name required', 'Enter a name for this draft.', parent=self.root)
            return False
        try:
            version = self.repository.rename(actor=self.username, report_id=row['id'],
                version=self.library_version if current else row['version'], title=title)
        except Exception as exc:
            messagebox.showerror('Could not rename draft', str(exc), parent=self.root)
            return False
        if current:
            self.library_title, self.library_version = title, version
            # Renaming never saves or discards any unsaved content.
            self.update_journey()
        self.record('Library draft renamed', self.username, report_id=row['id'], version=version)
        self.refresh_library()
        self.status.set(f'Renamed · {title}')
        return True

    def delete_library_report(self, row):
        if self.busy:
            return False
        current = row['id'] == self.library_id
        title = self.library_title if current else row['title']
        extra = ('\n\nThis draft is open. Its workspace will also close and any unsaved changes will be discarded.'
                 if current else '')
        if not messagebox.askyesno('Delete draft?',
                f'Delete “{title}” from Report library?\n\n'
                'Its saved data and review progress will be permanently removed. This cannot be undone. '
                'Original survey files and exported documents will remain.' + extra,
                parent=self.root, icon='warning', default='no'):
            return False
        try:
            self.repository.delete(actor=self.username, report_id=row['id'],
                                   version=self.library_version if current else row['version'])
        except Exception as exc:
            messagebox.showerror('Could not delete draft', str(exc), parent=self.root)
            return False
        self.record('Library draft deleted', self.username, report_id=row['id'])
        if current:
            self.reset_library_workspace(3)
        else:
            self.refresh_library()
        self.status.set(f'Deleted · {title}')
        return True

    def continue_report(self):
        if self.busy:
            return
        if self.current_page == 2 and self.username and not self.can_edit_workspace():
            if self.workflow.status == 'HUMAN REVIEWED':
                self.export_approved()
            elif self.can_review_workspace():
                self.review_check.focus_set()
            else:
                self.navigate(3)
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
            elif self.username:
                self.submit_persistent()
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
        if page == 2 and self.username and not self.can_edit_workspace():
            if self.workflow.status == 'HUMAN REVIEWED':
                hint, text = f'Approved by {self.workflow.approver}. This saved version is ready to export.', 'Export approved →'
            elif self.can_review_workspace():
                hint, text = f'Submitted by {self.library_owner}. Read the report and evidence, then approve or return it.', 'Review decision →'
            else:
                hint, text = 'Submitted and saved. Switch accounts to review this report in Pending review.', 'Return to library →'
        elif page == 2 and self.workflow.status == 'CHANGES REQUESTED':
            hint = 'Changes requested. Read the feedback above, edit and submit again.'
        if page == 2 and self.username and self.can_edit_workspace() and self.report and not self.review_blockers():
            text = 'Resubmit for review →' if self.workflow.times_returned() else 'Complete & submit →'
            hint = 'Ready to hand over. Submission saves this version and makes it available to a second reviewer.'
        self.journey_hint.configure(text=hint)
        self.next_button.configure(text=text, state='normal' if enabled and not self.busy else 'disabled')
        if hasattr(self, 'generate_button'):
            self.generate_button.configure(state='normal' if self.context and self.theme_review.complete and not self.busy and self.can_edit_workspace() else 'disabled',
                                           text='Regenerate draft' if self.report else 'Generate draft',
                                           style='TButton' if self.report else 'Primary.TButton')
        if self.username and page == 2:
            self.update_handoff_surface()

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
                     audience=self.audience.get(), approved_export=self.approved_export)
        return pack(state)

    def library_unsaved(self):
        if self.username and not self.can_edit_workspace():
            return False
        if self.context is None or not self.username:
            return self.dirty
        return self.saved_snapshot != self.workspace_snapshot()

    def save_library_draft(self):
        if self.busy or self.context is None or not self.can_edit_workspace():
            return False
        if not self.username:
            messagebox.showinfo('Sign in required', 'Sign in before saving to the library.', parent=self.root)
            return False
        if self.workflow.status not in ('DRAFT', 'CHANGES REQUESTED'):
            messagebox.showinfo('Editable drafts only', 'Submitted and approved reports are locked. Use their review or export actions.', parent=self.root)
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
        self.library_owner = self.username
        self.library_title, self.saved_snapshot = title.strip(), snapshot
        self.dirty = False
        self.update_journey()
        self.record('Library draft saved', self.username, report_id=rid, version=version)
        self.update_handoff_surface()
        self.status.set(f'Draft saved · {self.library_title} · only visible to you. Submit when ready for a second reviewer.')
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
        self.handoff_success = False
        self.feedback_expanded = False
        # The entire snapshot is decoded before replacing the current workspace.
        self.raw, self.source, self.loaded_file_label = state['raw'], state['source'], state['loaded_file_label']
        self.apply_analysis((state['frame'], state['context'], state['masked_count'], []))
        self.library_owner = row['owner']
        self.approved_export = state.get('approved_export', '')
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
        self.status.set(f'Opened · {row["title"]} · {self.workflow.status}')
        return True
