"""Human-in-the-loop review screens: theme validation, claim ledger, submit/approve."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from src.audit.logger import AuditTrail
from src.review.claims import ClaimLedger, extract_claims, remove_claim, ai_text_retained
from src.review.themes import ThemeReview, CATEGORIES, matched_keywords
from src.workflow import ReviewWorkflow, APPROVER_ROLES
from src.ui.theme import WHITE, INK, MUTED, TEAL

WARN = '#B4372B'
OK = '#1F7A55'


class ReviewUI:
    # ------------------------------------------------------------------ state
    def init_review_state(self):
        self.theme_review = ThemeReview([])
        self.ledger = ClaimLedger()
        self.workflow = ReviewWorkflow()
        self.audit = AuditTrail()
        self.themes_changed_since_draft = False
        self.claims_refresh_id = None

    def record(self, action, actor='', **details):
        """Write to the audit trail. Returns the event, or None if the log cannot be written."""
        try:
            return self.audit.append(action, actor, **details)
        except OSError as exc:
            self.status.set(f'Audit log could not be written: {exc}')
            return None

    # ------------------------------------------------------------------ Gate 1: themes
    def build_theme_review_controls(self, parent):
        filter_bar = tk.Frame(parent, bg=WHITE)
        filter_bar.pack(fill='x', pady=(8, 0))
        self.show_pending_themes = tk.BooleanVar(master=self.root, value=False)
        ttk.Checkbutton(
            filter_bar,
            text='Show pending only',
            variable=self.show_pending_themes,
            command=self.refresh_theme_rows
        ).pack(side='left')

        bar = tk.Frame(parent, bg=WHITE)
        bar.pack(fill='x', pady=(10, 0))
        tk.Label(bar, text='Category', bg=WHITE, fg=MUTED).pack(side='left')
        self.theme_category = ttk.Combobox(bar, values=list(CATEGORIES), state='readonly', width=12)
        self.theme_category.pack(side='left', padx=(6, 10))
        self.confirm_theme_button = self.action(bar, 'Confirm theme', self.confirm_theme, True)
        self.confirm_theme_button.pack(side='left')
        self.reject_theme_button = self.action(bar, 'Reject theme', self.reject_theme)
        self.reject_theme_button.pack(side='left', padx=6)
        self.theme_progress = tk.StringVar(value='Import data to review its themes.')
        tk.Label(parent, textvariable=self.theme_progress, bg=WHITE, fg=MUTED, anchor='w',
                 justify='left', wraplength=520).pack(fill='x', pady=(8, 0))

    def reset_theme_review(self):
        self.theme_review = ThemeReview(self.context.themes if self.context else [])
        self.themes_changed_since_draft = False
        self.refresh_theme_rows()

    def refresh_theme_rows(self):
        selected = self.theme_table.selection()
        selected_iid = selected[0] if selected else None
        pending_only = (
            hasattr(self, 'show_pending_themes')
            and self.show_pending_themes.get()
        )

        self.theme_table.delete(*self.theme_table.get_children())

        for i, theme in enumerate(self.theme_review.themes):
            decision = self.theme_review.status_of(theme.name)
            if pending_only and str(decision).casefold() != 'pending':
                continue
            self.theme_table.insert(
                '',
                'end',
                iid=str(i),
                values=(theme.name, theme.frequency, decision)
            )

        if selected_iid and self.theme_table.exists(selected_iid):
            self.theme_table.selection_set(selected_iid)
            self.theme_table.see(selected_iid)
        elif self.theme_table.get_children():
            first = self.theme_table.get_children()[0]
            self.theme_table.selection_set(first)
            self.theme_table.see(first)

        done, total = self.theme_review.reviewed, self.theme_review.total
        pending = max(0, total - done)
        filter_note = f' Showing {pending} pending.' if pending_only and total else ''

        if not total:
            text = 'No recurring themes to review.' if self.context else 'Import data to review its themes.'
        elif done < total:
            text = (f'{done} of {total} themes reviewed. Read the comments, then confirm or reject each theme. '
                    f'Only confirmed themes go into the report.{filter_note}')
        else:
            c = self.theme_review.counts()
            text = (f'All {total} themes reviewed: {c["confirmed"]} confirmed, {c["rejected"]} rejected. '
                    f'You can get a draft.{filter_note}')
        self.theme_progress.set(text)

        if self.theme_table.selection():
            self.inspect_theme()
        elif pending_only and total:
            self.show(self.theme_detail, 'No pending themes remain. Turn off “Show pending only” to review completed decisions.')

        self.update_review_panel()

    def selected_theme(self):
        selected = self.theme_table.selection()
        if selected and self.context and int(selected[0]) < len(self.theme_review.themes):
            return self.theme_review.themes[int(selected[0])]
        return None

    def theme_detail_text(self, theme):
        decision = self.theme_review.status_of(theme.name)
        text = (f'# {theme.name}\n{theme.category}  •  {theme.frequency} related comment(s)  •  Decision: {decision}\n\n'
                f'## Keywords\n{", ".join(theme.keywords) or "Emerging topic"}\n\n## Supporting learner feedback\n')
        rows = []
        for comment in theme.evidence:
            hits = matched_keywords(comment, theme)
            rows.append(f'“{comment}”\n- Matched: {", ".join(hits) if hits else "no exact keyword (statistical topic)"}')
        text += '\n\n'.join(rows) or 'No example comments available.'
        text += ('\n\n## Your decision\nConfirm if these comments really are about this theme. Change the category '
                 'if the sentiment is wrong. Reject it if the keyword matched by accident.')
        return text

    def reviewer_name(self):
        """Every theme and claim decision is recorded under a named person. Ask once, then reuse
        the name (it also pre-fills the author box in the Human review panel)."""
        name = self.author_entry.get().strip()
        if name:
            return name
        name = simpledialog.askstring('Who is reviewing?', 'Enter your name. Your theme and claim decisions are '
                                      'recorded under it in the audit log.', parent=self.root)
        if not name or not name.strip():
            return None
        self.author_entry.insert(0, name.strip())
        return name.strip()

    def _decide_theme(self, status):
        theme = self.selected_theme()
        if not theme or self.busy:
            return
        actor = self.reviewer_name()
        if not actor:
            return
        category = self.theme_category.get() or theme.category
        self.theme_review.decide(theme.name, status, category)
        self.record(f'Theme {status}', actor, theme=theme.name, category=category, original_category=theme.category)
        if self.report:
            self.themes_changed_since_draft = True
        self.refresh_theme_rows()
        nxt = next((i for i, t in enumerate(self.theme_review.themes)
                    if t.name not in self.theme_review.decisions), None)
        if nxt is not None:
            self.theme_table.selection_set(str(nxt))
            self.theme_table.see(str(nxt))
        self.inspect_theme()

    def confirm_theme(self):
        self._decide_theme('confirmed')

    def reject_theme(self):
        self._decide_theme('rejected')

    def review_context(self):
        return self.theme_review.reviewed_context(self.context) if self.context else None

    # ------------------------------------------------------------------ Gate 2/3: claims
    def build_claims_tab(self):
        page = tk.Frame(self.report_tabs, bg=WHITE, padx=10, pady=8)
        self.report_tabs.add(page, text='Review claims')
        self.claims_progress = tk.StringVar(value='Get a draft to review its claims.')
        tk.Label(page, textvariable=self.claims_progress, bg=WHITE, fg=INK, anchor='w', justify='left',
                 wraplength=760).pack(side='top', fill='x')
        tk.Label(page, text='Accept or reject every sentence and bullet; clear or remove every learner quote. '
                 'Rejecting removes the text from the draft.', bg=WHITE, fg=MUTED, anchor='w', justify='left',
                 wraplength=760).pack(side='top', fill='x', pady=(0, 6))

        filter_bar = tk.Frame(page, bg=WHITE)
        filter_bar.pack(side='top', fill='x', pady=(0, 6))
        self.show_undecided_only = tk.BooleanVar(master=self.root, value=False)
        ttk.Checkbutton(
            filter_bar,
            text='Show undecided only',
            variable=self.show_undecided_only,
            command=self.refresh_claims
        ).pack(side='left')

        # Bottom area first, so the table (not the buttons) shrinks on short screens.
        self.claim_detail = self.text(page, height=3)
        self.claim_detail.pack(side='bottom', fill='x')
        self.show(self.claim_detail, 'Select a claim to see its source and evidence.')
        actions = tk.Frame(page, bg=WHITE)
        actions.pack(side='bottom', fill='x', pady=6)
        self.accept_claim_button = self.action(actions, 'Accept', self.accept_claim, True)
        self.accept_claim_button.pack(side='left')
        self.reject_claim_button = self.action(actions, 'Reject and remove', self.reject_claim)
        self.reject_claim_button.pack(side='left', padx=6)
        self.locate_claim_button = self.action(actions, 'Show in draft', self.locate_claim)
        self.locate_claim_button.pack(side='left')
        box = tk.Frame(page, bg=WHITE)
        box.pack(side='top', fill='both', expand=True)
        ttk.Style(self.root).configure('Claims.Treeview', rowheight=26)
        columns = ('section', 'claim', 'origin', 'check', 'decision')
        self.claims_table = ttk.Treeview(box, columns=columns, show='headings', selectmode='browse', height=5,
                                         style='Claims.Treeview')
        for col, title, width in (('section', 'SECTION', 145), ('claim', 'CLAIM', 280), ('origin', 'SOURCE', 95),
                                  ('check', 'CHECK', 105), ('decision', 'DECISION', 85)):
            self.claims_table.heading(col, text=title)
            self.claims_table.column(col, width=width, minwidth=60, stretch=col == 'claim')
        scroll = ttk.Scrollbar(box, orient='vertical', command=self.claims_table.yview)
        self.claims_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.claims_table.pack(fill='both', expand=True)
        self.claims_table.tag_configure('attention', foreground=WARN)
        self.claims_table.tag_configure('done', foreground=MUTED)
        self.claims_table.bind('<<TreeviewSelect>>', lambda e: self.inspect_claim())

    def queue_claims_refresh(self):
        if self.claims_refresh_id:
            self.root.after_cancel(self.claims_refresh_id)
        self.claims_refresh_id = self.root.after(250, self.refresh_claims)

    def refresh_claims(self):
        self.claims_refresh_id = None
        if not self.report or not self.context:
            self.ledger.reset()
            self.claims_table.delete(*self.claims_table.get_children())
            self.claims_progress.set('Get a draft to review its claims.')
            self.update_review_panel()
            return
        selected = self.claims_table.selection()
        content = self.editor.get('1.0', 'end-1c')
        self.ledger.sync(extract_claims(content, self.report, self.review_context()))
        self.claims_table.delete(*self.claims_table.get_children())
        undecided_only = (
            hasattr(self, 'show_undecided_only')
            and self.show_undecided_only.get()
        )

        for claim in self.ledger.claims:
            decision = self.ledger.status_of(claim.key)

            if undecided_only and decision != 'pending':
                continue

            check = ('Fix needed' if any(p.startswith(('Unsupported', 'Quote does not')) for p in claim.problems)
                     else 'Possible name' if claim.possible_names
                     else 'Check wording' if claim.problems
                     else 'Matches data' if claim.checks or claim.kind == 'quote' else '—')
            label = 'Quote' if claim.kind == 'quote' else claim.origin
            tags = ('done',) if decision != 'pending' else ('attention',) if claim.needs_attention else ()
            self.claims_table.insert('', 'end', iid=claim.key, tags=tags,
                                     values=(claim.section, claim.text, label, check, decision.title()))
        if selected and self.claims_table.exists(selected[0]):
            self.claims_table.selection_set(selected[0])
        c = self.ledger.counts()
        filter_note = f'  •  showing {len(self.ledger.pending)} undecided' if undecided_only else ''
        self.claims_progress.set(f'{c["decided"]} of {c["total"]} claims decided  •  {c["ai_written"]} AI-written  •  '
                                 f'{c["human_edited"]} edited by a person  •  {c["attention"]} need attention'
                                 f'{filter_note}')
        self.inspect_claim()
        self.update_review_panel()

    def selected_claim(self):
        selected = self.claims_table.selection()
        if not selected:
            return None
        try:
            return self.ledger.get(selected[0])
        except ValueError:
            return None

    def inspect_claim(self):
        claim = self.selected_claim()
        if not claim:
            self.show(self.claim_detail, 'Select a claim to see its source and evidence.')
            self.accept_claim_button.configure(text='Accept')
            self.reject_claim_button.configure(text='Reject and remove')
            return
        quote = claim.kind == 'quote'
        self.accept_claim_button.configure(text='Clear quote' if quote else 'Accept')
        self.reject_claim_button.configure(text='Remove quote' if quote else 'Reject and remove')
        lines = [f'{claim.section}  •  {"Learner quote" if quote else claim.origin}  •  '
                 f'{self.ledger.status_of(claim.key).title()}', claim.text, '']
        if claim.checks:
            lines.append('Figures: ' + '; '.join(f'{c.text} {"matches the data" if c.supported else "NOT FOUND in the data"}'
                                                 for c in claim.checks))
        if claim.evidence:
            lines.append('Evidence the AI cited:')
            lines += [f'- {fact}' for fact in claim.evidence]
        if claim.possible_names:
            lines.append('Possible names: ' + ', '.join(claim.possible_names)
                         + '. Remove or reword if they could identify someone.')
        lines += [f'Warning: {p}' for p in claim.problems]
        if quote:
            lines.append('Clear this quote only if it contains nothing that could identify a learner or staff member.')
        self.show(self.claim_detail, '\n'.join(lines))

    def _after_claim_decision(self, claim):
        nxt = next((c.key for c in self.ledger.pending), None)
        self.refresh_claims()
        if nxt and self.claims_table.exists(nxt):
            self.claims_table.selection_set(nxt)
            self.claims_table.see(nxt)
            self.inspect_claim()

    def accept_claim(self):
        claim = self.selected_claim()
        if not claim or self.busy:
            return
        actor = self.reviewer_name()
        if not actor:
            return
        try:
            decision = self.ledger.accept(claim.key)
        except ValueError as exc:
            messagebox.showinfo('Fix this claim first', str(exc), parent=self.root)
            return
        self.record(f'Claim {decision}', actor, claim=claim.key, section=claim.section, source=claim.origin, kind=claim.kind)
        self._after_claim_decision(claim)

    def reject_claim(self):
        claim = self.selected_claim()
        if not claim or self.busy:
            return
        actor = self.reviewer_name()
        if not actor:
            return
        content = self.editor.get('1.0', 'end-1c')
        try:
            updated = remove_claim(content, claim)
        except ValueError as exc:
            messagebox.showinfo('Claim not found', str(exc), parent=self.root)
            self.refresh_claims()
            return
        decision = self.ledger.reject(claim.key)
        self.record(f'Claim {decision}', actor, claim=claim.key, section=claim.section, source=claim.origin, kind=claim.kind)
        self.set_editor_text(updated)
        self._after_claim_decision(claim)

    def locate_claim(self):
        claim = self.selected_claim()
        if not claim:
            return
        index = self.editor.search(claim.text[:60], '1.0', 'end')
        self.report_tabs.select(0)
        if index:
            end = f'{index}+{len(claim.text[:60])}c'
            self.editor.tag_remove('sel', '1.0', 'end')
            self.editor.tag_add('sel', index, end)
            self.editor.see(index)
            self.editor.focus_set()

    def set_editor_text(self, content):
        """Programmatic draft change: keeps review state consistent with a manual edit."""
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', content)
        self.editor.edit_modified(False)
        self.dirty = True
        self.draft_changed()

    def draft_changed(self):
        """Any change to the draft text: approval checks must be redone."""
        self.confirmed.set(False)
        if self.workflow.reopen('Draft edited after submission.'):
            self.record('Reopened after edit', self.author_entry.get().strip())
            self.status.set('The draft changed after submission, so it is back in Draft. Submit it again when ready.')
        self.update_evidence_check()
        self.refresh_preview()
        self.queue_claims_refresh()

    # ------------------------------------------------------------------ Gate 4/5/6: panel
    def scrollable(self, parent):
        """A vertically scrollable frame, so the review steps stay reachable on short screens."""
        canvas = tk.Canvas(parent, bg=WHITE, highlightthickness=0, width=230)
        bar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=WHITE)
        window = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))

        def wheel(event):
            if canvas.winfo_height() < inner.winfo_reqheight():
                canvas.yview_scroll(-1 if (event.delta > 0 or getattr(event, 'num', 0) == 4) else 1, 'units')
        for widget in (canvas, inner):
            widget.bind('<Enter>', lambda e: (canvas.bind_all('<MouseWheel>', wheel),
                                              canvas.bind_all('<Button-4>', wheel), canvas.bind_all('<Button-5>', wheel)))
            widget.bind('<Leave>', lambda e: (canvas.unbind_all('<MouseWheel>'),
                                              canvas.unbind_all('<Button-4>'), canvas.unbind_all('<Button-5>')))
        self.review_canvas = canvas
        return inner

    def build_review_panel(self, outer):
        review = self.scrollable(outer)
        tk.Label(review, text='Human review', font=(self.font_family, 14, 'bold'), bg=WHITE, fg=INK).pack(anchor='w')
        tk.Label(review, textvariable=self.report_status, font=(self.font_family, 9, 'bold'), bg=WHITE, fg=TEAL,
                 wraplength=210, justify='left').pack(anchor='w', pady=(2, 6))

        def step(title):
            tk.Label(review, text=title, font=(self.font_family, 10, 'bold'), bg=WHITE, fg=INK).pack(anchor='w', pady=(8, 0))

        def note(var, color=MUTED):
            label = tk.Label(review, textvariable=var, font=(self.font_family, 9), bg=WHITE, fg=color,
                             wraplength=210, justify='left')
            label.pack(anchor='w')
            return label

        self.themes_status = tk.StringVar(value='Themes: import data first.')
        self.claims_status = tk.StringVar(value='Claims: get a draft first.')
        self.pace_status = tk.StringVar(value='')
        self.audit_status = tk.StringVar(value='')
        step('1  Validate themes')
        self.themes_status_label = note(self.themes_status)
        step('2  Decide every claim')
        self.claims_status_label = note(self.claims_status)
        note(self.evidence_status, INK)
        note(self.pace_status, WARN)
        step('3  Author submits')
        self.author_entry = ttk.Entry(review, width=22)
        self.author_entry.pack(fill='x', pady=(4, 4))
        self.submit_button = self.action(review, 'Submit for approval', self.submit_for_approval)
        self.submit_button.pack(fill='x')
        step('4  A second person approves')
        self.approver_entry = ttk.Entry(review, width=22)
        self.approver_entry.pack(fill='x', pady=(4, 4))
        self.approver_role = ttk.Combobox(review, values=list(APPROVER_ROLES), state='readonly', width=22)
        self.approver_role.set(APPROVER_ROLES[0])
        self.approver_role.pack(fill='x')
        self.review_check = ttk.Checkbutton(review, text='I checked the evidence,\nprivacy and final wording.',
                                            variable=self.confirmed, command=self.review_changed)
        self.review_check.pack(anchor='w', pady=(6, 6))
        self.export_button = self.action(review, 'Approve & export', self.export, True)
        self.export_button.pack(fill='x', pady=(0, 4))
        self.return_button = self.action(review, 'Return for changes', self.return_for_changes)
        self.return_button.pack(fill='x', pady=(0, 4))
        self.save_button = self.action(review, 'Save draft', lambda: self.export(False))
        self.save_button.pack(fill='x')
        note(self.audit_status)
        self.update_audit_status()

    def update_audit_status(self):
        try:
            result = self.audit.verify()
        except OSError:
            self.audit_status.set('Audit log unavailable.')
            return
        state = 'chain verified' if result['ok'] else f'CHAIN BROKEN at line {result["broken_at"]}'
        self.audit_status.set(f'Audit log: {result["entries"]} entries, {state}.')

    def review_blockers(self):
        blockers = []
        if not self.report:
            return ['Get a draft first.']
        if not self.theme_review.complete:
            blockers.append(f'Review all themes ({self.theme_review.reviewed} of {self.theme_review.total} done).')
        if self.themes_changed_since_draft:
            blockers.append('Theme decisions changed after this draft. Get a new draft.')
        if self.ledger.pending:
            blockers.append(f'Decide every claim ({len(self.ledger.pending)} still pending).')
        if self.update_evidence_check():
            blockers.append('Fix or remove numbers and quotes that do not match the data.')
        return blockers

    def update_review_panel(self):
        if not hasattr(self, 'themes_status'):
            return
        tr = self.theme_review
        if not self.context:
            self.themes_status.set('Import data first.')
        else:
            mark = ' ✓' if tr.complete and not self.themes_changed_since_draft else ''
            extra = ' Changed after the draft: get a new draft.' if self.themes_changed_since_draft else ''
            self.themes_status.set(f'{tr.reviewed} of {tr.total} themes reviewed{mark}.{extra}')
        if self.report:
            c = self.ledger.counts()
            mark = ' ✓' if self.ledger.complete else ''
            self.claims_status.set(f'{c["decided"]} of {c["total"]} claims decided{mark}. Use the Review claims tab.')
            self.pace_status.set(self.ledger.pace()['message'])
            state = self.workflow.status
            if state == 'AWAITING HUMAN REVIEW':
                self.report_status.set(f'Submitted by {self.workflow.reviewer} • awaiting a second person')
            elif state == 'CHANGES REQUESTED':
                self.report_status.set('Returned for changes • edit, then submit again')
            elif state == 'HUMAN REVIEWED':
                self.report_status.set(f'Approved by {self.workflow.approver} • exported')
            else:
                self.report_status.set(f'{self.report.audience.title()} draft • requires review')
        else:
            self.claims_status.set('Get a draft first.')
            self.pace_status.set('')
        self.sync_review_buttons()

    def sync_review_buttons(self):
        if not hasattr(self, 'submit_button') or not hasattr(self, 'accept_claim_button'):
            return
        has = bool(self.report) and not self.busy
        state = self.workflow.status
        self.submit_button.configure(state='normal' if has and state in ('DRAFT', 'CHANGES REQUESTED') else 'disabled')
        awaiting = has and state == 'AWAITING HUMAN REVIEW'
        self.export_button.configure(state='normal' if awaiting else 'disabled')
        self.return_button.configure(state='normal' if awaiting else 'disabled')
        self.review_check.configure(state='normal' if awaiting else 'disabled')
        self.save_button.configure(state='normal' if has else 'disabled')
        for widget in (self.accept_claim_button, self.reject_claim_button, self.locate_claim_button):
            widget.configure(state='normal' if has and self.ledger.claims else 'disabled')
        for widget in (self.confirm_theme_button, self.reject_theme_button):
            widget.configure(state='normal' if self.context and self.theme_review.total and not self.busy else 'disabled')

    def submit_for_approval(self):
        if not self.report or self.busy:
            return False
        blockers = self.review_blockers()
        author = self.author_entry.get().strip()
        if not author:
            blockers.append('Enter your name as the author.')
        if blockers:
            messagebox.showinfo('Not ready to submit', '\n'.join('• ' + b for b in blockers), parent=self.root)
            return False
        try:
            self.workflow.submit(author)
        except ValueError as exc:
            messagebox.showerror('Cannot submit', str(exc), parent=self.root)
            return False
        self.record('Submitted for approval', author, audience=self.report.audience, claims=self.ledger.counts()['total'])
        self.status.set('Submitted. A second person must now enter their name, confirm the checks and approve.')
        self.update_review_panel()
        self.update_audit_status()
        return True

    def return_for_changes(self):
        if self.workflow.status != 'AWAITING HUMAN REVIEW' or self.busy:
            return False
        approver = self.approver_entry.get().strip()
        if not approver:
            messagebox.showinfo('Approver name needed', 'Enter your name as the approver before returning the report.',
                                parent=self.root)
            return False
        notes = simpledialog.askstring('Return for changes', 'What needs to change?', parent=self.root)
        if not notes or not notes.strip():
            return False
        self.workflow.return_for_changes(approver, notes)
        self.record('Returned for changes', approver, notes=notes.strip())
        self.confirmed.set(False)
        self.status.set(f'Returned to {self.workflow.reviewer} with notes: {notes.strip()}')
        self.update_review_panel()
        self.update_audit_status()
        return True

    def approval_problems(self):
        """Checks that must pass before approval; nothing is changed."""
        if self.workflow.status != 'AWAITING HUMAN REVIEW':
            return ['Submit the report for approval first (step 3).']
        problems = list(self.review_blockers())
        approver = self.approver_entry.get().strip()
        if not approver:
            problems.append('Enter the approver name.')
        if not self.confirmed.get():
            problems.append('Tick the confirmation that you checked the evidence, privacy and wording.')
        if approver:
            trial = copy.deepcopy(self.workflow)
            try:
                trial.approve(approver, role=self.approver_role.get(), audience=self.report.audience)
            except ValueError as exc:
                problems.append(str(exc))
        return problems

    def review_summary(self):
        return {
            'themes': self.theme_review.counts(),
            'claims': self.ledger.counts(),
            'pace': self.ledger.pace(),
            'ai_retained': ai_text_retained(self.report, self.editor.get('1.0', 'end-1c')),
        }
