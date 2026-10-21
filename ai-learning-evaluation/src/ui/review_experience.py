"""Visible review handoff, durable outcomes and returned feedback."""
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from src.ui.theme import WHITE, INK, MUTED, BORDER


def event_time(value):
    return datetime.fromisoformat(value).astimezone().strftime('%d %b %Y · %H:%M') if value else ''


class ReviewExperienceUI:
    def build_handoff_surface(self, parent):
        self.handoff_panel = tk.Frame(parent, bg='#FAF8FD', padx=10, pady=8,
                                      highlightbackground=BORDER, highlightthickness=1)
        head = tk.Frame(self.handoff_panel, bg='#FAF8FD')
        head.pack(fill='x')
        self.handoff_actions = tk.Frame(head, bg='#FAF8FD')
        self.handoff_actions.pack(side='right', padx=(10, 0))
        self.handoff_title = tk.Label(head, bg='#FAF8FD', fg=INK, anchor='w', justify='left',
            width=1, wraplength=400, font=(self.font_family, 11, 'bold'))
        self.handoff_title.pack(side='left', fill='x', expand=True)
        self.handoff_title.bind('<Configure>', lambda e: self.handoff_title.configure(wraplength=max(100, e.width)))
        self.handoff_message = tk.Label(self.handoff_panel, bg='#FAF8FD', fg=MUTED,
            anchor='w', justify='left', width=1, wraplength=700, font=(self.font_family, 9))
        self.handoff_message.pack(fill='x', pady=(3, 0))
        self.handoff_message.bind('<Configure>', lambda e: self.handoff_message.configure(wraplength=max(200, e.width)))
        self.handoff_notice = tk.Frame(self.handoff_panel, bg='#EDF8F0', padx=8, pady=5)
        ttk.Button(self.handoff_notice, text='Continue reading', style='More.Library.TButton',
                   command=self.dismiss_handoff_success).pack(side='right')
        self.handoff_notice_text = tk.Label(self.handoff_notice, bg='#EDF8F0', fg='#1F7A55',
            width=1, wraplength=500, justify='left', anchor='w', font=(self.font_family, 9))
        self.handoff_notice_text.pack(side='left', fill='x', expand=True)
        self.handoff_notice_text.bind('<Configure>', lambda e: self.handoff_notice_text.configure(wraplength=max(100, e.width)))
        self.handoff_feedback_bar = tk.Frame(self.handoff_panel, bg='#FFF3DA', padx=6, pady=4)
        self.handoff_feedback_toggle = ttk.Button(self.handoff_feedback_bar, text='Read feedback ▾',
            style='More.Library.TButton', command=self.toggle_return_feedback)
        self.handoff_feedback_toggle.pack(side='right')
        self.handoff_feedback_summary = tk.Label(self.handoff_feedback_bar, bg='#FFF3DA', fg='#805400',
            width=1, anchor='w', justify='left', wraplength=500, font=(self.font_family, 9))
        self.handoff_feedback_summary.pack(side='left', fill='x', expand=True)
        self.handoff_feedback_summary.bind('<Configure>', lambda e: self.handoff_feedback_summary.configure(wraplength=max(100, e.width)))
        self.handoff_notes = ScrolledText(self.handoff_panel, height=3, wrap='word',
            bg=WHITE, fg=INK, relief='solid', borderwidth=1, font=(self.font_family, 10))
        self.handoff_options = tk.Frame(self.handoff_panel, bg='#FAF8FD')
        self.studio_save_button = ttk.Button(self.handoff_actions, text='Save draft',
            style='Library.TButton', command=self.save_library_draft)
        self.handoff_library = ttk.Button(self.handoff_actions, text='Library',
            style='Library.TButton', command=lambda: self.navigate(3))
        self.handoff_switch = ttk.Button(self.handoff_actions, text='Switch account',
            style='Library.TButton', command=lambda: self.sign_out(True))
        self.handoff_edit = ttk.Button(self.handoff_feedback_bar, text='Edit report',
            style='More.Library.TButton', command=lambda: self.select_report_tab(0))

    def dismiss_handoff_success(self):
        self.handoff_success = False
        self.update_handoff_surface()

    def toggle_return_feedback(self):
        self.feedback_expanded = not self.feedback_expanded
        self.update_handoff_surface()

    def update_handoff_surface(self):
        if not self.username or not hasattr(self, 'return_button'):
            return
        self.handoff_panel.pack(fill='x', pady=(0, 8), before=self.report_actions)
        for button in (self.submit_button, self.export_button, self.return_button, self.studio_save_button,
                       self.handoff_library, self.handoff_switch, self.handoff_edit):
            button.pack_forget()
        for widget in (self.handoff_options, self.handoff_notes, self.handoff_notice, self.handoff_feedback_bar):
            widget.pack_forget()
        state = self.workflow.status
        owner = self.library_owner or self.username
        name = self.library_title or 'Untitled report'
        metadata = f'First reviewer: {owner}'
        editable = self.can_edit_workspace()
        if editable:
            self.audience_summary.pack_forget()
            self.audience.pack(side='left')
            self.generate_button.pack(side='right', padx=(0, 8))
            self.studio_save_button.pack(side='left', padx=(0, 8))
        else:
            self.audience.pack_forget()
            self.audience_summary.configure(text=(self.report.audience if self.report else self.audience.get()).title())
            self.audience_summary.pack(side='left')
            self.generate_button.pack_forget()
        self.studio_save_button.configure(state='normal' if editable and self.context and not self.busy else 'disabled')
        if state == 'AWAITING HUMAN REVIEW':
            submitted = next(e for e in reversed(self.workflow.events) if e.action == 'Submitted for review')
            metadata += f' · Submitted: {event_time(submitted.timestamp)}'
            if self.can_review_workspace():
                title = f'{name[:40]} · Awaiting your review'
                message = metadata + f' · Reviewing as: {self.username}'
                self.handoff_options.pack(fill='x', pady=(5, 0))
                self.export_button.pack(side='left', padx=(0, 8))
                self.return_button.pack(side='left')
            else:
                title = f'{name[:40]} · Submitted and saved'
                message = metadata + ' · Awaiting second reviewer'
                self.handoff_library.pack(side='left', padx=(0, 8))
                self.handoff_switch.pack(side='left')
                if self.handoff_success:
                    self.handoff_notice_text.configure(text='Your review is complete. The second reviewer can open Library → Pending review. You can safely leave.')
        elif state == 'HUMAN REVIEWED':
            approved = next((e for e in reversed(self.workflow.events) if e.action == 'Approved'), None)
            title = f'{name[:40]} · Approved and saved'
            message = metadata + f' · Approved by: {self.workflow.approver} · {event_time(approved.timestamp) if approved else ""}'
            self.export_button.pack(side='left')
            self.handoff_notice_text.configure(text='Review complete — approval saved. Export now or reopen from Library → Approved later.')
        else:
            blockers = self.review_blockers() if self.report else []
            returned = next((e for e in reversed(self.workflow.events) if e.action == 'Returned for changes'), None)
            saved = 'Unsaved changes' if self.library_unsaved() else ('Draft saved' if self.library_id else 'Not saved yet')
            title = f'{name[:40]} · {saved}'
            if not self.report:
                message = 'Generate a report after checking all themes.' if self.context else 'Import survey data in Explore data to begin.'
            else:
                message = ('Still to do: ' + ' '.join(blockers)) if blockers else 'Checks complete. Submit to hand this version to a second reviewer.'
            message += ' · Private draft, not submitted.'
            if returned and state == 'CHANGES REQUESTED':
                title = f'{name[:40]} · Changes requested'
                summary = ' '.join(returned.notes.split())
                self.handoff_feedback_summary.configure(text=f'{returned.actor}: {summary[:115]}' + ('…' if len(summary) > 115 else ''))
                self.handoff_feedback_bar.pack(fill='x', pady=(5, 0))
                self.handoff_feedback_toggle.configure(text='Hide feedback ▴' if self.feedback_expanded else 'Read feedback ▾')
                self.handoff_notes.configure(state='normal')
                text = f'{returned.actor} · {event_time(returned.timestamp)}\n{returned.notes}'
                if self.handoff_notes.get('1.0', 'end-1c') != text:
                    self.handoff_notes.delete('1.0', 'end')
                    self.handoff_notes.insert('1.0', text)
                self.handoff_notes.configure(state='disabled')
                if self.feedback_expanded:
                    self.handoff_edit.pack(side='right', padx=(0, 5))
                    self.handoff_notes.pack(fill='x', pady=(5, 0))
            self.submit_button.configure(text='Resubmit for review' if returned else 'Complete & submit',
                state='normal' if self.report and not self.busy and not blockers and editable else 'disabled')
            if self.report:
                self.submit_button.pack(side='left')
        if self.handoff_success and state in ('AWAITING HUMAN REVIEW', 'HUMAN REVIEWED'):
            self.handoff_notice.pack(fill='x', pady=(5, 0))
        self.handoff_title.configure(text=title)
        self.handoff_message.configure(text=message)
        for button in (self.handoff_library, self.handoff_edit, self.handoff_feedback_toggle):
            button.configure(state='disabled' if self.busy else 'normal')
        self.handoff_switch.configure(state='normal' if not self.busy and self.on_logout else 'disabled')

    def build_progress_drawer(self, parent):
        tk.Label(parent, text='Review progress', bg=WHITE, fg=INK,
                 font=(self.font_family, 15, 'bold')).pack(anchor='w', padx=4, pady=(2, 8))
        self.progress_rows = []
        for index, title in enumerate(('Import data', 'Check themes', 'Check report & quotes',
                                       'First reviewer submits', 'Second reviewer decides')):
            box = tk.Frame(parent, bg='#F7F5FC', padx=10, pady=8,
                           highlightbackground=BORDER, highlightthickness=1)
            box.pack(fill='x', padx=3, pady=(0, 7))
            heading = tk.Label(box, text=title, anchor='w', justify='left', wraplength=270,
                               font=(self.font_family, 10, 'bold'))
            heading.pack(fill='x')
            detail = tk.Label(box, anchor='w', justify='left', wraplength=270, font=(self.font_family, 9))
            detail.pack(fill='x', pady=(3, 4))
            button = ttk.Button(box, text='Open step →', style='More.Library.TButton',
                                command=lambda i=index: self.open_progress_step(i))
            button.pack(anchor='w')
            self.progress_rows.append((box, heading, detail, button))
        ttk.Button(parent, text='Review history', style='Library.TButton',
                   command=self.show_review_history).pack(fill='x', padx=4, pady=(3, 6))
        tk.Label(parent, textvariable=self.evidence_status, bg=WHITE, fg=MUTED,
                 wraplength=280, justify='left', anchor='w', font=(self.font_family, 9)).pack(fill='x', padx=4)
        tk.Label(parent, textvariable=self.pace_status, bg=WHITE, fg='#805400',
                 wraplength=280, justify='left', anchor='w', font=(self.font_family, 9)).pack(fill='x', padx=4)

    def review_progress_steps(self):
        state = self.workflow.status
        themes_done = bool(self.context and self.theme_review.complete)
        checks_done = bool(self.report and not self.review_blockers())
        submitted = state in ('AWAITING HUMAN REVIEW', 'HUMAN REVIEWED')
        returned = state == 'CHANGES REQUESTED'
        last_submit = next((e for e in reversed(self.workflow.events) if e.action == 'Submitted for review'), None)
        last_return = next((e for e in reversed(self.workflow.events) if e.action == 'Returned for changes'), None)
        steps = [
            ('done' if self.context else 'active', 'Import data',
             (self.loaded_file_label or 'Survey data imported') if self.context else 'Choose CSV or Excel files to begin.'),
            ('done' if themes_done else ('active' if self.context else 'pending'), 'Check themes',
             f'{self.theme_review.reviewed} of {self.theme_review.total} themes checked.' if self.context else 'Waiting for survey data.'),
            ('done' if checks_done else ('attention' if self.themes_changed_since_draft else 'active' if themes_done else 'pending'),
             'Check report & quotes', 'Checks complete.' if checks_done else
             ('Regenerate after theme changes, then check the new report.' if self.themes_changed_since_draft else
              f'{len(self.ledger.pending)} claims still need a decision. Check figures and quotes.' if self.report else 'Generate a draft, then check every claim and quote.')),
            ('done' if submitted else 'attention' if returned else 'active' if checks_done else 'pending', 'First reviewer submits',
             f'{last_submit.actor} · {event_time(last_submit.timestamp)}' if submitted and last_submit else
             'Changes requested. Edit, check and resubmit.' if returned else 'Save draft is private. Submit when your checks are complete.'),
            ('done' if state == 'HUMAN REVIEWED' else 'attention' if returned else 'active' if submitted else 'pending',
             'Second reviewer decides', f'Approved by {self.workflow.approver}.' if state == 'HUMAN REVIEWED' else
             f'Returned by {last_return.actor}. Read feedback above the report.' if returned and last_return else
             'Awaiting a different reviewer.' if submitted else 'Available after the first reviewer submits.')]
        return steps

    def update_progress_drawer(self):
        if not self.username or not hasattr(self, 'progress_rows'):
            return
        steps = self.review_progress_steps()
        self.review_drawer_text.set(f'Review progress · {sum(state == "done" for state, _, _ in steps)}/5')
        colors = {'done': ('#EDF8F0', '#1F7A55', '✓', 'Complete'),
                  'active': ('#F0E9FC', '#6530B3', '●', 'In progress'),
                  'pending': ('#F5F4F7', MUTED, '○', 'Not started'),
                  'attention': ('#FFF3DA', '#805400', '!', 'Needs attention')}
        for (box, heading, detail, button), (state, title, text) in zip(self.progress_rows, steps):
            bg, fg, mark, caption = colors[state]
            box.configure(bg=bg)
            heading.configure(text=f'{mark} {title}', bg=bg, fg=fg)
            detail.configure(text=f'{caption} · {text}', bg=bg, fg=fg)
            button.configure(state='disabled' if self.busy else 'normal')

    def open_progress_step(self, index):
        if self.busy:
            return
        self.close_review_drawer()
        self.navigate(0 if index == 0 else 1 if index == 1 else 2)
        if index == 2 and self.report:
            self.select_report_tab(3)
        elif index == 4:
            if self.workflow.status == 'CHANGES REQUESTED':
                self.feedback_expanded = True
                self.update_handoff_surface()
            elif self.can_review_workspace():
                self.review_check.focus_set()
        elif index == 3 and self.can_edit_workspace():
            self.submit_button.focus_set()

    def review_history_text(self):
        return '\n\n'.join(f'{event_time(e.timestamp)} · {e.action}\n{e.actor}\n{e.notes}'
                           for e in self.workflow.events) or 'No review events yet.'

    def show_review_history(self):
        window = tk.Toplevel(self.root)
        window.title('Review history')
        window.geometry('620x420')
        window.transient(self.root)
        text = ScrolledText(window, wrap='word', padx=14, pady=14, font=(self.font_family, 11))
        text.pack(fill='both', expand=True)
        text.insert('1.0', self.review_history_text())
        text.configure(state='disabled')
        ttk.Button(window, text='Close', command=window.destroy).pack(pady=10)
