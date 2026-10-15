"""Preview, apply and undo report revisions without silently replacing edits."""
import tkinter as tk
from dataclasses import replace
from tkinter import ttk, messagebox
from src.reporting.revisions import (
    SECTIONS,
    propose_revisions,
    apply_batch_proposal,
    apply_section_proposal,
    revert_section_proposal,
    section_text,
)
from src.ui.wording import REVISION_MODES, service_message
from src.ui.theme import WHITE, INK, MUTED, TEAL, BORDER, BG


class RevisionUI:
    def build_revision_ui(self):
        self.pending_revision = None
        self.revision_history = []
        self.revision_poll = None
        self.revision_preview_section = None
        self.revision_section_decisions = {}
        self.revision_section_snapshots = {}
        self.revision_evidence_expanded = False

        outer = tk.Frame(self.report_tabs, bg=WHITE)
        self.report_tabs.add(outer, text='Feedback & revisions')

        # The revision workspace can become taller than the available window,
        # especially once the side-by-side preview is visible. Put the whole
        # page inside a vertically scrollable canvas so every control remains
        # reachable without shrinking the comparison area.
        scroll_canvas = tk.Canvas(
            outer,
            bg=WHITE,
            highlightthickness=0,
            bd=0,
        )
        page_scrollbar = ttk.Scrollbar(
            outer,
            orient='vertical',
            command=scroll_canvas.yview,
        )
        scroll_canvas.configure(yscrollcommand=page_scrollbar.set)

        page_scrollbar.pack(side='right', fill='y')
        scroll_canvas.pack(side='left', fill='both', expand=True)

        page = tk.Frame(scroll_canvas, bg=WHITE, padx=14, pady=12)
        page_window = scroll_canvas.create_window(
            (0, 0),
            window=page,
            anchor='nw',
        )

        def _sync_revision_scroll_region(event=None):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))

        def _sync_revision_page_width(event):
            scroll_canvas.itemconfigure(page_window, width=event.width)

        page.bind('<Configure>', _sync_revision_scroll_region)
        scroll_canvas.bind('<Configure>', _sync_revision_page_width)

        # Mouse-wheel scrolling applies to the page background/buttons/labels.
        # Text, Treeview and Combobox widgets keep their own native scrolling.
        def _revision_mousewheel(event):
            widget_class = event.widget.winfo_class()
            if widget_class in {'Text', 'Treeview', 'TCombobox', 'Listbox'}:
                return

            delta = getattr(event, 'delta', 0)
            if delta:
                units = -1 if delta > 0 else 1
                scroll_canvas.yview_scroll(units * 3, 'units')
                return 'break'

        def _bind_revision_mousewheel(widget):
            if widget.winfo_class() not in {'Text', 'Treeview', 'TCombobox', 'Listbox'}:
                widget.bind('<MouseWheel>', _revision_mousewheel, add='+')
            for child in widget.winfo_children():
                _bind_revision_mousewheel(child)

        self.revision_scroll_canvas = scroll_canvas
        self.revision_page_scrollbar = page_scrollbar

        page.columnconfigure(0, weight=1)

        tk.Label(
            page,
            text='Revise one or more report sections, preview the changes side by side, then decide whether to apply them.',
            bg=WHITE,
            fg=INK,
            anchor='w',
            justify='left',
            font=(self.font_family, 10, 'bold'),
            wraplength=980,
        ).grid(row=0, column=0, sticky='ew', pady=(0, 8))

        # -------------------------------------------------------------
        # Step 1 + Step 2: section selection and revision method
        # -------------------------------------------------------------
        setup = tk.Frame(page, bg=WHITE)
        setup.grid(row=1, column=0, sticky='ew')
        setup.columnconfigure(0, weight=3)
        setup.columnconfigure(1, weight=2)

        section_card = tk.Frame(
            setup,
            bg='#FAF8FD',
            padx=12,
            pady=10,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        section_card.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        tk.Label(
            section_card,
            text='1  SECTIONS TO REVISE',
            bg='#FAF8FD',
            fg=TEAL,
            font=(self.font_family, 8, 'bold'),
            anchor='w',
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 5))

        self.revision_section_vars = {}
        self.revision_section_buttons = {}
        for index, section in enumerate(SECTIONS):
            var = tk.BooleanVar(master=self.root, value=(index == 0))
            self.revision_section_vars[section] = var
            row = 1 + index // 2
            col = index % 2
            button = ttk.Checkbutton(
                section_card,
                text=section,
                variable=var,
                command=lambda s=section: self.revision_section_changed(s),
            )
            button.grid(row=row, column=col, sticky='w', padx=(0, 14), pady=2)
            self.revision_section_buttons[section] = button

        section_card.columnconfigure(0, weight=1)
        section_card.columnconfigure(1, weight=1)
        self.revision_selection_status = tk.StringVar(value='1 section selected')
        tk.Label(
            section_card,
            textvariable=self.revision_selection_status,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8),
            anchor='w',
        ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))

        method_card = tk.Frame(
            setup,
            bg='#FAF8FD',
            padx=12,
            pady=10,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        method_card.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        tk.Label(
            method_card,
            text='2  REVISION METHOD',
            bg='#FAF8FD',
            fg=TEAL,
            font=(self.font_family, 8, 'bold'),
            anchor='w',
        ).pack(fill='x', pady=(0, 7))

        self.revision_provider = ttk.Combobox(
            method_card,
            values=list(REVISION_MODES),
            state='readonly',
            width=27,
        )
        self.revision_provider.set('Ask Gemini')
        self.revision_provider.pack(fill='x')
        self.revision_provider.bind('<<ComboboxSelected>>', self.revision_mode_changed)

        self.revision_method_help = tk.StringVar()
        tk.Label(
            method_card,
            textvariable=self.revision_method_help,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8),
            anchor='w',
            justify='left',
            wraplength=330,
        ).pack(fill='x', pady=(7, 0))

        # -------------------------------------------------------------
        # Step 3: one dynamic input area. The label/help changes by mode.
        # -------------------------------------------------------------
        input_card = tk.Frame(
            page,
            bg=WHITE,
            padx=0,
            pady=0,
        )
        input_card.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        self.revision_input_label = tk.StringVar()
        self.revision_input_help = tk.StringVar()

        tk.Label(
            input_card,
            textvariable=self.revision_input_label,
            bg=WHITE,
            fg=INK,
            font=(self.font_family, 10, 'bold'),
            anchor='w',
        ).pack(fill='x')
        tk.Label(
            input_card,
            textvariable=self.revision_input_help,
            bg=WHITE,
            fg=MUTED,
            font=(self.font_family, 8),
            anchor='w',
            justify='left',
            wraplength=980,
        ).pack(fill='x', pady=(2, 5))

        self.revision_input = self.text(input_card, height=4, editable=True)
        self.revision_input.pack(fill='x')

        # Backward-compatible aliases used by existing tests and older code.
        self.feedback = self.revision_input
        self.replacement = self.text(outer, height=1, editable=True)  # intentionally not packed
        self.revision_preview = self.text(outer, height=1)  # compatibility summary; intentionally not packed

        self.feedback.bind('<<Modified>>', self.feedback_changed)
        self.replacement.bind('<<Modified>>', self.feedback_changed)

        actions = tk.Frame(page, bg=WHITE)
        actions.grid(row=3, column=0, sticky='ew', pady=(8, 10))
        self.propose_button = self.action(actions, 'Preview revisions', self.propose_feedback, True)
        self.propose_button.pack(side='left')
        self.undo_button = self.action(actions, 'Undo last revision', self.undo_revision)
        self.undo_button.pack(side='left', padx=(6, 0))

        # -------------------------------------------------------------
        # Step 4: large, side-by-side comparison area.
        # -------------------------------------------------------------
        preview_wrap = tk.Frame(
            page,
            bg='#FAF8FD',
            padx=10,
            pady=9,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        preview_wrap.grid(row=5, column=0, sticky='nsew')
        preview_wrap.columnconfigure(0, weight=1)
        preview_wrap.rowconfigure(2, weight=1)

        preview_head = tk.Frame(preview_wrap, bg='#FAF8FD')
        preview_head.grid(row=0, column=0, sticky='ew')
        tk.Label(
            preview_head,
            text='4  PREVIEW',
            bg='#FAF8FD',
            fg=TEAL,
            font=(self.font_family, 8, 'bold'),
        ).pack(side='left')
        self.revision_preview_status = tk.StringVar(value='Preview changes before applying them to the draft.')
        tk.Label(
            preview_head,
            textvariable=self.revision_preview_status,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8),
        ).pack(side='right')

        self.revision_preview_tabbar = tk.Frame(preview_wrap, bg='#FAF8FD')
        self.revision_preview_tabbar.grid(row=1, column=0, sticky='ew', pady=(7, 7))
        self.revision_preview_tab_buttons = []

        compare = tk.Frame(preview_wrap, bg='#FAF8FD')
        compare.grid(row=2, column=0, sticky='nsew')
        compare.columnconfigure(0, weight=1, uniform='revisioncompare')
        compare.columnconfigure(1, weight=1, uniform='revisioncompare')
        compare.rowconfigure(1, weight=1)

        self.revision_original_title = tk.StringVar(value='ORIGINAL')
        self.revision_proposed_title = tk.StringVar(value='PROPOSED')
        tk.Label(
            compare,
            textvariable=self.revision_original_title,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8, 'bold'),
            anchor='w',
        ).grid(row=0, column=0, sticky='ew', padx=(0, 5), pady=(0, 4))
        tk.Label(
            compare,
            textvariable=self.revision_proposed_title,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8, 'bold'),
            anchor='w',
        ).grid(row=0, column=1, sticky='ew', padx=(5, 0), pady=(0, 4))

        self.revision_original = self.text(compare, height=11)
        self.revision_original.grid(row=1, column=0, sticky='nsew', padx=(0, 5))
        self.revision_proposed = self.text(compare, height=11)
        self.revision_proposed.grid(row=1, column=1, sticky='nsew', padx=(5, 0))

        # Proposal-specific controls sit directly beneath the proposed wording,
        # making it visually obvious which text the decision belongs to.
        proposal_actions = tk.Frame(compare, bg='#FAF8FD')
        proposal_actions.grid(row=2, column=1, sticky='ew', padx=(5, 0), pady=(8, 0))
        proposal_actions.columnconfigure(0, weight=1)

        self.revision_section_decision_status = tk.StringVar(
            value='Compare the proposal, then apply or ignore it.'
        )
        tk.Label(
            proposal_actions,
            textvariable=self.revision_section_decision_status,
            bg='#FAF8FD',
            fg=MUTED,
            font=(self.font_family, 8),
            anchor='w',
            justify='left',
            wraplength=420,
        ).grid(row=0, column=0, sticky='w')

        decision_buttons = tk.Frame(proposal_actions, bg='#FAF8FD')
        decision_buttons.grid(row=1, column=0, sticky='e', pady=(6, 0))

        # Two-choice review control. Both choices stay visible at all times;
        # the selected choice receives a strong colour and the alternative fades.
        style = ttk.Style(self.root)

        style.configure(
            'RevisionApply.TButton',
            background=TEAL, foreground=WHITE, bordercolor=TEAL,
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionApply.TButton',
            background=[('active', '#6B2FD4')],
            foreground=[('active', WHITE)]
        )

        style.configure(
            'RevisionApplySelected.TButton',
            background='#2F8A57', foreground=WHITE, bordercolor='#2F8A57',
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionApplySelected.TButton',
            background=[('active', '#28784B')],
            foreground=[('active', WHITE)]
        )

        style.configure(
            'RevisionApplyMuted.TButton',
            background='#EEE8F5', foreground='#A59DAE', bordercolor='#E2DAEB',
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionApplyMuted.TButton',
            background=[('active', '#E6DDF0')],
            foreground=[('active', '#776E82')]
        )

        style.configure(
            'RevisionIgnore.TButton',
            background=WHITE, foreground=MUTED, bordercolor='#D9D1E5',
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionIgnore.TButton',
            background=[('active', '#F2EFF5')],
            foreground=[('active', INK)]
        )

        style.configure(
            'RevisionIgnoreSelected.TButton',
            background='#7B7882', foreground=WHITE, bordercolor='#7B7882',
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionIgnoreSelected.TButton',
            background=[('active', '#696671')],
            foreground=[('active', WHITE)]
        )

        style.configure(
            'RevisionIgnoreMuted.TButton',
            background='#F3F2F5', foreground='#B1ADB6', bordercolor='#E6E3E9',
            padding=(15, 9), relief='flat'
        )
        style.map(
            'RevisionIgnoreMuted.TButton',
            background=[('active', '#ECE9EF')],
            foreground=[('active', '#85808C')]
        )

        self.keep_original_button = ttk.Button(
            decision_buttons,
            text='✕  Ignore',
            command=self.keep_current_revision_section,
            style='RevisionIgnore.TButton',
            cursor='hand2',
        )
        self.keep_original_button.pack(side='left', padx=(0, 8))

        self.apply_section_button = ttk.Button(
            decision_buttons,
            text='✓  Apply',
            command=self.apply_current_revision_section,
            style='RevisionApply.TButton',
            cursor='hand2',
        )
        self.apply_section_button.pack(side='left')

        # Backward-compatible name used by older tests/callers.
        self.apply_button = self.apply_section_button

        # Evidence remains available for transparency, but no longer consumes
        # permanent screen space. It is collapsed by default.
        evidence_bar = tk.Frame(preview_wrap, bg='#FAF8FD')
        evidence_bar.grid(row=3, column=0, sticky='ew', pady=(7, 0))

        self.revision_evidence_toggle = tk.Button(
            evidence_bar,
            text='Evidence & notes ▸',
            command=self.toggle_revision_evidence,
            font=(self.font_family, 8, 'bold'),
            fg=TEAL,
            bg='#FAF8FD',
            activeforeground=TEAL,
            activebackground='#FAF8FD',
            relief='flat',
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=2,
            cursor='hand2',
        )
        self.revision_evidence_toggle.pack(anchor='w')

        self.revision_evidence = self.text(preview_wrap, height=4)
        self.revision_evidence.grid(row=4, column=0, sticky='ew', pady=(4, 0))
        self.revision_evidence.grid_remove()

        self.show(self.revision_original, 'Preview a revision to compare the current wording.')
        self.show(self.revision_proposed, 'The proposed wording will appear here.')
        self.show(self.revision_evidence, '')
        self.show(self.revision_preview, 'Your original draft stays unchanged until you apply an individual section.')

        # Bind wheel scrolling after the complete page has been constructed,
        # then calculate the initial scrollable extent.
        _bind_revision_mousewheel(page)
        self.schedule_idle(_sync_revision_scroll_region)

        self.update_revision_mode_ui()
        self.sync_revision_controls()

    def toggle_revision_evidence(self):
        self.revision_evidence_expanded = not self.revision_evidence_expanded
        if self.revision_evidence_expanded:
            self.revision_evidence.grid()
            self.revision_evidence_toggle.configure(text='Evidence & notes ▾')
        else:
            self.revision_evidence.grid_remove()
            self.revision_evidence_toggle.configure(text='Evidence & notes ▸')

        if hasattr(self, 'revision_scroll_canvas'):
            self.schedule_idle(
                lambda: self.revision_scroll_canvas.configure(
                    scrollregion=self.revision_scroll_canvas.bbox('all')
                )
            )

    def selected_revision_sections(self):
        return tuple(section for section in SECTIONS if self.revision_section_vars[section].get())

    def revision_section_changed(self, changed_section=None):
        mode_label = self.revision_provider.get()
        selected = list(self.selected_revision_sections())

        # Manual replacement intentionally behaves like a radio selection: one section only.
        if mode_label == 'Manual replacement' and changed_section and self.revision_section_vars[changed_section].get():
            for section, var in self.revision_section_vars.items():
                if section != changed_section:
                    var.set(False)
            selected = [changed_section]

        # Always keep at least one section selected.
        if not selected:
            fallback = changed_section if changed_section in SECTIONS else SECTIONS[0]
            self.revision_section_vars[fallback].set(True)
            selected = [fallback]

        count = len(selected)
        if mode_label == 'Manual replacement':
            self.revision_selection_status.set('1 section selected · manual replacement works one section at a time')
        else:
            self.revision_selection_status.set(f'{count} section{"s" if count != 1 else ""} selected')
        self.invalidate_revision()

    def revision_mode_changed(self, event=None):
        if self.revision_provider.get() == 'Manual replacement':
            selected = list(self.selected_revision_sections())
            keep = selected[0] if selected else SECTIONS[0]
            for section, var in self.revision_section_vars.items():
                var.set(section == keep)
        self.update_revision_mode_ui()
        self.revision_section_changed()

    def update_revision_mode_ui(self):
        mode = self.revision_provider.get()
        if mode == 'Ask Gemini':
            self.revision_input_label.set('Tell Gemini what you want to change')
            self.revision_input_help.set(
                'The same instruction is applied independently to each selected section. Gemini receives only that masked '
                'section, your request and calculated evidence; raw survey comments are not sent.'
            )
            self.revision_method_help.set('AI-assisted rewrite · supports one or multiple selected sections.')
        elif mode == 'Edit from feedback':
            self.revision_input_label.set('Describe the edit')
            self.revision_input_help.set(
                'Offline rules only: make it shorter, use bullet points, use plain language, Replace X with Y, or Add: text.'
            )
            self.revision_method_help.set('Local deterministic edits · no external AI request.')
        else:
            self.revision_input_label.set('Replacement text')
            self.revision_input_help.set(
                'Paste or write the final wording for the selected section. This mode works one section at a time.'
            )
            self.revision_method_help.set('Reviewer-supplied wording · one section only.')

    def resize_revision_preview(self):
        """Compatibility hook retained for older tests/callers."""
        return

    def sync_revision_controls(self):
        ready = bool(self.report) and not self.busy
        has_selection = bool(self.selected_revision_sections()) if hasattr(self, 'revision_section_vars') else False
        self.propose_button.configure(state='normal' if ready and has_selection else 'disabled')
        self.undo_button.configure(state='normal' if ready and self.revision_history else 'disabled')
        self.feedback.configure(state='normal' if ready else 'disabled')
        self.replacement.configure(state='normal' if ready else 'disabled')
        self.revision_provider.configure(state='readonly' if ready else 'disabled')
        for button in self.revision_section_buttons.values():
            button.configure(state='normal' if ready else 'disabled')

        current = getattr(self, 'revision_preview_section', None)
        decision = self.revision_section_decisions.get(current, 'pending') if current else None

        if not ready or self.pending_revision is None or current is None:
            self.keep_original_button.configure(state='disabled', style='RevisionIgnoreMuted.TButton')
            self.apply_section_button.configure(state='disabled', style='RevisionApplyMuted.TButton')
            return

        # The pair acts like a visual two-choice control:
        # green = accepted, grey = ignored, purple/white = not decided yet.
        if decision == 'applied':
            self.keep_original_button.configure(
                text='✕  Ignore instead',
                style='RevisionIgnoreMuted.TButton',
                state='normal'
            )
            self.apply_section_button.configure(
                text='✓  Applied',
                style='RevisionApplySelected.TButton',
                state='normal'
            )
        elif decision == 'kept':
            self.keep_original_button.configure(
                text='✕  Ignored',
                style='RevisionIgnoreSelected.TButton',
                state='normal'
            )
            self.apply_section_button.configure(
                text='✓  Apply instead',
                style='RevisionApplyMuted.TButton',
                state='normal'
            )
        else:
            self.keep_original_button.configure(
                text='✕  Ignore',
                style='RevisionIgnore.TButton',
                state='normal'
            )
            self.apply_section_button.configure(
                text='✓  Apply',
                style='RevisionApply.TButton',
                state='normal'
            )

    def clear_revision_preview(self, message='Preview changes before applying them to the draft.', reset_decisions=True):
        self.revision_preview_section = None
        if reset_decisions:
            self.revision_section_decisions = {}
            self.revision_section_snapshots = {}
        for child in self.revision_preview_tabbar.winfo_children():
            child.destroy()
        self.revision_preview_tab_buttons = []
        self.revision_preview_status.set(message)
        self.revision_original_title.set('ORIGINAL')
        self.revision_proposed_title.set('PROPOSED')
        self.show(self.revision_original, 'Preview a revision to compare the current wording.')
        self.show(self.revision_proposed, 'The proposed wording will appear here.')
        self.show(self.revision_evidence, '')
        if hasattr(self, 'revision_evidence'):
            self.revision_evidence.grid_remove()
        if hasattr(self, 'revision_evidence_toggle'):
            self.revision_evidence_toggle.configure(text='Evidence & notes ▸')
        self.revision_evidence_expanded = False

    def feedback_changed(self, event=None):
        """Invalidate an existing preview when the revision instruction changes."""
        feedback_modified = self.feedback.edit_modified()
        replacement_modified = self.replacement.edit_modified()

        if feedback_modified or replacement_modified:
            self.feedback.edit_modified(False)
            self.replacement.edit_modified(False)
            self.invalidate_revision()

    def invalidate_revision(self):
        if self.pending_revision:
            self.pending_revision = None
            self.show(self.revision_preview, 'The draft or feedback changed. Preview a new revision before applying.')
            self.clear_revision_preview('Draft, selection or instruction changed · preview again before applying.')
        self.sync_revision_controls()

    def reset_revisions(self):
        self.pending_revision = None
        self.revision_history.clear()
        self.revision_section_decisions = {}
        self.revision_section_snapshots = {}
        for index, section in enumerate(SECTIONS):
            self.revision_section_vars[section].set(index == 0)
        self.revision_provider.set('Ask Gemini')
        self.update_revision_mode_ui()
        self.revision_selection_status.set('1 section selected')

        self.feedback.configure(state='normal')
        self.feedback.delete('1.0', 'end')
        self.feedback.edit_modified(False)
        self.replacement.configure(state='normal')
        self.replacement.delete('1.0', 'end')
        self.replacement.edit_modified(False)
        self.show(self.revision_preview, 'Your original draft stays unchanged until you click Apply.')
        self.clear_revision_preview()
        self.sync_revision_controls()

    def _compatibility_preview_text(self, batch, mode_label):
        chunks = []
        for proposal in batch.proposals:
            section = proposal.section
            chunks.append(f'## Original — {section}\n{section_text(batch.original, section)}')
            chunks.append(f'## Proposed — {mode_label}\n{section_text(batch.revised, section)}')
            if proposal.evidence:
                chunks.append('## Evidence Gemini cited\n' + '\n'.join(f'- {fact}' for fact in proposal.evidence))
            if proposal.note:
                chunks.append(f'## Note from Gemini\n{proposal.note}')
        if batch.provider == 'Gemini':
            chunks.append('The new wording will appear as AI-written in Review claims and must be accepted claim by claim before the report can be submitted.')
        return '\n\n'.join(chunks)

    def _revision_tab_visual(self, decision, active=False):
        if decision == 'applied':
            return {
                'bg': '#E8F5EC',
                'fg': '#2E7D4F',
                'active_bg': '#DFF0E5',
                'underline': '#45A36A' if active else '#CDE8D5',
                'suffix': '  ✓',
            }
        if decision == 'kept':
            return {
                'bg': '#EFEFF2',
                'fg': '#77737E',
                'active_bg': '#E7E7EB',
                'underline': '#9C99A2' if active else '#DADADF',
                'suffix': '  ×',
            }
        return {
            'bg': WHITE if active else '#F3EEF9',
            'fg': TEAL if active else MUTED,
            'active_bg': WHITE if active else '#EEE7F7',
            'underline': TEAL if active else '#F3EEF9',
            'suffix': '',
        }

    def _build_revision_preview_tabs(self, sections):
        for child in self.revision_preview_tabbar.winfo_children():
            child.destroy()
        self.revision_preview_tab_buttons = []

        current = self.revision_preview_section

        for section in sections:
            decision = self.revision_section_decisions.get(section, 'pending')
            active = section == current
            visual = self._revision_tab_visual(decision, active)

            holder = tk.Frame(self.revision_preview_tabbar, bg='#FAF8FD')
            holder.pack(side='left', padx=(0, 4))

            button = tk.Button(
                holder,
                text=section + visual['suffix'],
                command=lambda s=section: self.show_revision_comparison(s),
                font=(self.font_family, 8, 'bold' if active else 'normal'),
                fg=visual['fg'],
                bg=visual['bg'],
                activeforeground=visual['fg'],
                activebackground=visual['active_bg'],
                relief='flat',
                bd=0,
                highlightthickness=0,
                padx=10,
                pady=6,
                cursor='hand2',
            )
            button.pack(fill='x')

            underline = tk.Frame(holder, bg=visual['underline'], height=3 if active else 2)
            underline.pack(fill='x')
            self.revision_preview_tab_buttons.append((section, button, underline))

    def _revision_decision_counts(self):
        decisions = self.revision_section_decisions
        return (
            sum(value == 'applied' for value in decisions.values()),
            sum(value == 'kept' for value in decisions.values()),
            sum(value == 'pending' for value in decisions.values()),
        )

    def _next_pending_revision_section(self, after=None):
        if not self.pending_revision:
            return None
        sections = list(self.pending_revision.sections)
        if after in sections:
            start = sections.index(after) + 1
            ordered = sections[start:] + sections[:start]
        else:
            ordered = sections
        return next(
            (section for section in ordered if self.revision_section_decisions.get(section) == 'pending'),
            None,
        )

    def _refresh_revision_decision_summary(self):
        if not self.pending_revision:
            self.revision_preview_status.set('Preview changes before applying them to the draft.')
            return
        applied, kept, pending = self._revision_decision_counts()
        self.revision_preview_status.set(
            f'{applied} applied · {kept} ignored · {pending} pending'
        )

    def show_revision_comparison(self, section):
        batch = self.pending_revision
        if not batch or section not in batch.sections:
            return
        self.revision_preview_section = section
        mode_label = self.revision_provider.get()
        proposal = next(item for item in batch.proposals if item.section == section)
        decision = self.revision_section_decisions.get(section, 'pending')

        self.revision_original_title.set(f'ORIGINAL · {section}')
        self.revision_proposed_title.set(f'PROPOSED · {mode_label}')
        self.show(self.revision_original, section_text(batch.original, section))
        self.show(self.revision_proposed, section_text(proposal.revised, section))

        details = []
        if proposal.evidence:
            details.append('EVIDENCE USED\n' + '\n'.join(f'• {fact}' for fact in proposal.evidence))
        if proposal.note:
            details.append('GEMINI NOTE\n' + proposal.note)
        if batch.provider == 'Gemini':
            details.append('Applied wording returns to Review claims as AI-written and requires human acceptance.')

        if details:
            self.show(self.revision_evidence, '\n\n'.join(details))
            self.revision_evidence_toggle.configure(state='normal')
        else:
            self.show(self.revision_evidence, '')
            self.revision_evidence_toggle.configure(state='disabled')
            if self.revision_evidence_expanded:
                self.revision_evidence_expanded = False
                self.revision_evidence.grid_remove()
                self.revision_evidence_toggle.configure(text='Evidence & notes ▸')

        if decision == 'applied':
            self.revision_section_decision_status.set(
                'Applied ✓  Choose Ignore instead if you change your mind.'
            )
        elif decision == 'kept':
            self.revision_section_decision_status.set(
                'Ignored ×  Choose Apply instead if you change your mind.'
            )
        else:
            self.revision_section_decision_status.set(
                'Choose whether to use this proposed wording'
            )

        for candidate, button, underline in self.revision_preview_tab_buttons:
            active = candidate == section
            candidate_decision = self.revision_section_decisions.get(candidate, 'pending')
            visual = self._revision_tab_visual(candidate_decision, active)
            button.configure(
                bg=visual['bg'],
                activebackground=visual['active_bg'],
                activeforeground=visual['fg'],
                fg=visual['fg'],
                font=(self.font_family, 8, 'bold' if active else 'normal'),
                text=candidate + visual['suffix'],
            )
            underline.configure(
                bg=visual['underline'],
                height=3 if active else 2,
            )

        self._refresh_revision_decision_summary()
        self.sync_revision_controls()

    def propose_feedback(self):
        if not self.report or self.busy:
            return

        content = self.editor.get('1.0', 'end-1c')
        sections = self.selected_revision_sections()
        mode_label = self.revision_provider.get()
        provider = REVISION_MODES.get(mode_label, mode_label)
        visible_input = self.feedback.get('1.0', 'end-1c').strip()
        compatibility_replacement = self.replacement.get('1.0', 'end-1c').strip()

        if not sections:
            messagebox.showinfo('Choose a section', 'Select at least one report section to revise.', parent=self.root)
            return

        # The new Manual replacement UI uses the one visible input as the replacement body.
        # Older automated tests can still set the legacy provider label and hidden replacement widget.
        if mode_label == 'Manual replacement':
            feedback = 'Manual replacement supplied by reviewer.'
            replacement = visible_input
        elif provider in ('Human / Copilot text', 'Human / Copilot replacement'):
            feedback = visible_input or 'Manual replacement supplied by reviewer.'
            replacement = compatibility_replacement
        else:
            feedback = visible_input
            replacement = ''

        if not visible_input and not replacement:
            messagebox.showinfo('Add revision input', 'Enter an instruction or replacement text before previewing.', parent=self.root)
            return

        consent = False  # Visible revision modes only edit or replace text on-device.
        self.pending_revision = None
        self.clear_revision_preview('Preparing preview…')
        self.busy = True
        count = len(sections)
        self.status.set('Preparing revision preview…')
        self.sync_controls()
        if provider == 'Gemini':
            self.status.set(f'Asking Gemini to revise {count} section{"s" if count != 1 else ""} independently…')

        future = self.pool.submit(
            propose_revisions,
            self.report,
            content,
            self.review_context(),
            sections,
            feedback,
            provider,
            consent,
            None,
            replacement,
        )

        def finish():
            if not future.done():
                self.revision_poll = self.schedule(80, finish)
                return
            self.revision_poll = None
            self.busy = False
            try:
                batch = future.result()
            except Exception as exc:
                self.status.set('Revision failed. The original draft is unchanged.')
                self.sync_controls()
                messagebox.showerror('Could not revise draft', service_message(exc), parent=self.root)
                return

            self.pending_revision = batch
            self.revision_section_decisions = {section: 'pending' for section in batch.sections}
            self.revision_section_snapshots = {}
            self._build_revision_preview_tabs(batch.sections)
            self.show_revision_comparison(batch.sections[0])
            self.revision_preview_status.set(
                f'{len(batch.sections)} section{"s" if len(batch.sections) != 1 else ""} ready to compare · draft unchanged'
            )
            self.render(self.revision_preview, self._compatibility_preview_text(batch, mode_label))
            self.status.set('Revision preview ready. Compare each section, then apply the revisions if appropriate.')
            self.sync_controls()

        self.revision_poll = self.schedule(80, finish)

    def apply_current_revision_section(self):
        if not self.pending_revision or self.busy:
            return

        section = self.revision_preview_section
        if not section:
            section = self._next_pending_revision_section()
        if not section:
            return
        if self.revision_section_decisions.get(section) not in ('pending', 'kept'):
            return

        current = self.editor.get('1.0', 'end-1c')
        batch = self.pending_revision

        try:
            updated = apply_section_proposal(self.report, current, batch, section)
        except ValueError as exc:
            messagebox.showerror('Preview is out of date', str(exc), parent=self.root)
            return

        # Save both a general history entry and a section-specific snapshot.
        # The latter enables a direct "Revert applied change" for this section.
        before_apply = replace(self.report, content=current)
        self.revision_history.append(before_apply)
        self.revision_section_snapshots[section] = before_apply
        self.report = updated
        self.revision_section_decisions[section] = 'applied'
        self.replace_revision_text(updated.content)

        self.record(
            'Revision applied',
            self.author_identity(),
            section=section,
            sections=[section],
            method=updated.mode,
        )

        self._build_revision_preview_tabs(batch.sections)

        applied, kept, pending = self._revision_decision_counts()
        next_section = self._next_pending_revision_section(after=section)

        if next_section:
            # Move straight to the next undecided proposal so the reviewer can
            # continue without scrolling back up to the preview tabs.
            self.show_revision_comparison(next_section)
            self.status.set(
                f'{section} applied ✓. Now reviewing {next_section}. '
                'You can return to the green tab and choose Ignore instead later.'
            )
        else:
            self.show_revision_comparison(section)
            self.status.set(
                f'Revision review complete: {applied} applied, {kept} ignored. '
                'Changed claims must be reviewed again.'
            )

        self.render(
            self.revision_preview,
            self._compatibility_preview_text(batch, self.revision_provider.get()),
        )
        self.sync_controls()

    def keep_current_revision_section(self):
        if not self.pending_revision or self.busy:
            return

        section = self.revision_preview_section
        if not section:
            section = self._next_pending_revision_section()
        if not section:
            return

        current_decision = self.revision_section_decisions.get(section, 'pending')
        if current_decision == 'kept':
            return

        # Switching from Applied -> Ignored automatically restores the original
        # wording. The reviewer does not need a separate Revert action.
        if current_decision == 'applied':
            current = self.editor.get('1.0', 'end-1c')
            snapshot = self.revision_section_snapshots.get(section)
            remaining_applied = max(
                0,
                sum(value == 'applied' for value in self.revision_section_decisions.values()) - 1,
            )

            try:
                updated = revert_section_proposal(
                    self.report,
                    current,
                    self.pending_revision,
                    section,
                    previous_report=snapshot,
                    remaining_applied=remaining_applied,
                )
            except ValueError as exc:
                messagebox.showerror('Cannot switch decision', str(exc), parent=self.root)
                return

            self.report = updated
            self.revision_section_snapshots.pop(section, None)
            self.replace_revision_text(updated.content)
            event_name = 'Revision changed to ignored'
        else:
            event_name = 'Revision proposal ignored'

        self.revision_section_decisions[section] = 'kept'
        self.record(
            event_name,
            self.author_identity(),
            section=section,
            method=self.pending_revision.provider,
        )

        self._build_revision_preview_tabs(self.pending_revision.sections)

        applied, kept, pending = self._revision_decision_counts()
        next_section = self._next_pending_revision_section(after=section)

        if next_section:
            self.show_revision_comparison(next_section)
            self.status.set(
                f'{section}: ignored ×. Now reviewing {next_section}. '
                'You can return to the grey tab and apply it instead later.'
            )
        else:
            self.show_revision_comparison(section)
            self.status.set(
                f'Revision review complete: {applied} applied, {kept} ignored.'
            )

        self.sync_revision_controls()

    def revert_current_revision_section(self):
        if not self.pending_revision or self.busy:
            return

        section = self.revision_preview_section
        if not section or self.revision_section_decisions.get(section) != 'applied':
            return

        current = self.editor.get('1.0', 'end-1c')
        snapshot = self.revision_section_snapshots.get(section)
        remaining_applied = max(
            0,
            sum(value == 'applied' for value in self.revision_section_decisions.values()) - 1,
        )

        try:
            updated = revert_section_proposal(
                self.report,
                current,
                self.pending_revision,
                section,
                previous_report=snapshot,
                remaining_applied=remaining_applied,
            )
        except ValueError as exc:
            messagebox.showerror('Cannot revert automatically', str(exc), parent=self.root)
            return

        # The section returns to an undecided state, so the reviewer can apply
        # the same proposal again or ignore it.
        self.report = updated
        self.revision_section_decisions[section] = 'pending'
        self.revision_section_snapshots.pop(section, None)
        self.replace_revision_text(updated.content)

        self.record(
            'Revision reverted',
            self.author_identity(),
            section=section,
            method=self.pending_revision.provider,
        )

        self._build_revision_preview_tabs(self.pending_revision.sections)
        self.show_revision_comparison(section)
        self.status.set(
            f'{section} restored to its original wording. Apply the proposal again or ignore it.'
        )
        self.sync_controls()

    def apply_feedback(self):
        """Backward-compatible entry point: apply only the section currently in preview."""
        return self.apply_current_revision_section()


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
        if not messagebox.askyesno(
            'Restore previous draft?',
            'Restore the draft saved before the last applied revision? Any later manual edits will be replaced.',
            parent=self.root,
        ):
            return
        previous = self.revision_history.pop()
        content = previous.content.replace('HUMAN REVIEWED', 'DRAFT — REQUIRES HUMAN REVIEW')
        self.report = replace(previous, content=content, status='DRAFT — REQUIRES HUMAN REVIEW')
        self.pending_revision = None
        self.revision_section_decisions = {}
        self.revision_section_snapshots = {}
        self.replace_revision_text(content)
        self.record('Revision undone', self.author_identity())
        self.show(self.revision_preview, 'Previous draft restored. All approval checks must be repeated.')
        self.clear_revision_preview('Previous draft restored · preview another revision when ready')
