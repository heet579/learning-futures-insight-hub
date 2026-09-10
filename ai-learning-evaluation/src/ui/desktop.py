"""Presentation interface for the native desktop workflow."""
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from src.ui.runtime import _setup_environment
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog
from src.config import DATA_DIR
from src.ingestion.validator import validate_dataframe
from src.privacy.pii_masker import mask_dataframe
from src.analytics.quantitative import calculate_metrics
from src.analytics.qualitative import collect_comments
from src.analytics.themes import extract_themes
from src.models import AnalysisContext

BG, WHITE, INK, MUTED = '#F3F6FA', '#FFFFFF', '#172B43', '#63758B'
FONT = 'TkDefaultFont'
NAVY, TEAL, BORDER = '#11273E', '#087F8C', '#DFE7EF'


def label(parent, text='', size=10, color=INK, bold=False, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, 'bold' if bold else 'normal'), bg=parent.cget('bg'), fg=color, anchor='w', **kwargs)


def panel(parent, **kwargs):
    return tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1, **kwargs)


def analyse(frame, name, scope):
    validation = validate_dataframe(frame)
    if not validation.valid:
        raise ValueError("\n".join(validation.errors))
    masked, count = mask_dataframe(frame)
    courses = sorted(masked['CourseName'].dropna().astype(str).unique()) if 'CourseName' in masked else []
    if scope != 'All courses (aggregate)':
        masked = masked[masked['CourseName'].astype(str) == scope].copy()
    if masked.empty:
        raise ValueError('No responses in this course. Select another scope.')
    context = AnalysisContext(calculate_metrics(masked), extract_themes(collect_comments(masked)), name, scope, validation.warnings)
    return masked, context, count, courses


class DesktopApp:
    TITLES = [('Evaluation overview', 'A clear view of learner experience, grounded in your survey data.'),
              ('Survey workspace', 'Search masked responses and inspect the source behind every insight.'),
              ('Themes & evidence', 'Explore recurring feedback and the comments supporting it.'),
              ('Report studio', 'Turn evidence into a draft, refine it, then review and export.'),
              ('Data assistant', 'Quick, local answers based on the current analysis scope.')]

    def __init__(self, root, auto_demo=True):
        global FONT
        FONT = tkfont.nametofont('TkDefaultFont', root=root).actual('family')
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.context = self.raw = self.report = self.frame = None
        self.source = ''
        self.busy = self.dirty = False
        self.controls = []
        self.nav_buttons = []
        self.metric_values = []
        self.search_id = None
        self.status = tk.StringVar(value='Ready • Open a CSV or load the included demonstration.')
        self.report_status = tk.StringVar(value='No draft yet')
        self.confirmed = tk.BooleanVar(value=False)
        self.search = tk.StringVar()
        root.title('Learning Futures | Insight Hub')
        root.geometry(f'{min(1360, root.winfo_screenwidth()-70)}x{min(900, root.winfo_screenheight()-80)}+25+25')
        root.minsize(min(1080, root.winfo_screenwidth()-70), min(740, root.winfo_screenheight()-80))
        root.configure(bg=BG)
        self.styles()
        self.shell()
        self.build_overview()
        self.build_data()
        self.build_themes()
        self.build_report()
        self.build_assistant()
        self.navigate(0)
        self.sync_controls()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-o>', lambda e: self.open_file() if not self.busy else None)
        if auto_demo:
            self.startup_id = root.after(150, self.load_demo)

    @staticmethod
    def show(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')

    def open_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title='Open evaluation data', filetypes=[('CSV files', '*.csv')])
        if path:
            self.load(Path(path), Path(path).name)

    def load_demo(self):
        self.startup_id = None
        path = DATA_DIR / 'synthetic_qualtrics_evaluation.csv'
        self.load(path, path.name)

    def styles(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.', font=(FONT, 10))
        s.configure('Nav.TButton', background=NAVY, foreground='#C1D0DC', anchor='w', padding=(15, 14), borderwidth=0, relief='flat')
        s.map('Nav.TButton', background=[('active', '#25485F')], foreground=[('active', WHITE)])
        s.configure('Selected.Nav.TButton', background='#25485F', foreground=WHITE)
        s.map('Selected.Nav.TButton', background=[('active', '#25485F')], foreground=[('active', WHITE)])
        s.configure('TButton', background=WHITE, foreground=INK, bordercolor=BORDER, padding=(14, 9), relief='flat')
        s.map('TButton', background=[('active', '#E8F0F5')], foreground=[('disabled', '#93A1B2')])
        s.configure('Primary.TButton', background=TEAL, foreground=WHITE, bordercolor=TEAL)
        s.map('Primary.TButton', background=[('disabled', '#CCDEE1'), ('active', '#096B77')], foreground=[('disabled', '#718B91')])
        s.configure('TCombobox', padding=7, fieldbackground=WHITE, foreground=INK, bordercolor=BORDER)
        s.map('TCombobox', fieldbackground=[('readonly', WHITE)], selectbackground=[('readonly', WHITE)], selectforeground=[('readonly', INK)])
        s.configure('TEntry', padding=8, fieldbackground=WHITE, bordercolor=BORDER)
        s.configure('TCheckbutton', background=WHITE, foreground=INK, padding=5)
        s.map('TCheckbutton', background=[('active', WHITE)])
        s.configure('Treeview', background=WHITE, fieldbackground=WHITE, foreground=INK, rowheight=34, borderwidth=0)
        s.configure('Treeview.Heading', background='#EAF0F6', foreground=MUTED, font=(FONT, 9, 'bold'), padding=10, relief='flat')
        s.map('Treeview', background=[('selected', '#D7EFF0')], foreground=[('selected', INK)])
        s.configure('TNotebook', background=WHITE, borderwidth=0)
        s.configure('TNotebook.Tab', padding=(18, 10), background='#EDF2F7')
        s.map('TNotebook.Tab', background=[('selected', WHITE)], foreground=[('selected', TEAL)])
        s.configure('Horizontal.TProgressbar', background=TEAL, troughcolor=BG, borderwidth=0, thickness=3)

    def action(self, parent, text, command, primary=False):
        b = ttk.Button(parent, text=text, command=command, style='Primary.TButton' if primary else 'TButton')
        self.controls.append(b)
        return b

    def shell(self):
        sidebar = tk.Frame(self.root, bg=NAVY, width=206)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        label(sidebar, 'LF / INSIGHT HUB', 13, WHITE, True).pack(anchor='w', padx=20, pady=(30, 5))
        label(sidebar, 'LEARNING FUTURES', 8, '#90ACBE').pack(anchor='w', padx=20)
        tk.Frame(sidebar, bg='#294056', height=1).pack(fill='x', padx=20, pady=26)
        label(sidebar, 'WORKSPACE', 8, '#90ACBE', True).pack(anchor='w', padx=20, pady=(0, 12))
        for i, name in enumerate(['Overview', 'Survey data', 'Themes & evidence', 'Report studio', 'Data assistant']):
            b = ttk.Button(sidebar, text=f'{i+1:02}   {name}', style='Nav.TButton',
                           cursor='hand2', command=lambda index=i: self.navigate(index))
            b.pack(fill='x', padx=10, pady=3)
            self.nav_buttons.append(b)
        bottom = tk.Frame(sidebar, bg=NAVY)
        bottom.pack(side='bottom', fill='x', padx=20, pady=24)
        label(bottom, '●  LOCAL WORKSPACE', 9, '#6AD4C8', True).pack(anchor='w')
        label(bottom, 'Your data stays on this device.\nReports require human review.', 9, '#A8BECB', justify='left', wraplength=168).pack(anchor='w', pady=(8, 0))
        main = tk.Frame(self.root, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        head = tk.Frame(main, bg=BG)
        head.pack(fill='x', padx=24, pady=(24, 16))
        label(head, 'DEMO EDITION', 9, TEAL, True).pack(anchor='w', pady=(0, 8))
        self.page_title = label(head, '', 25, INK, True)
        self.page_title.pack(anchor='w')
        self.page_subtitle = label(head, '', 10, MUTED)
        self.page_subtitle.pack(anchor='w', pady=(4, 0))
        toolbar = panel(main, padx=12, pady=12)
        toolbar.pack(fill='x', padx=24, pady=(0, 18))
        self.action(toolbar, '+ Open CSV', self.open_file, True).pack(side='left', padx=(0, 8))
        self.action(toolbar, 'Load demo', self.load_demo).pack(side='left', padx=(0, 8))
        self.action(toolbar, 'New sample', self.synthetic).pack(side='left')
        self.scope = ttk.Combobox(toolbar, state='disabled', width=28, values=['All courses (aggregate)'])
        self.scope.set('All courses (aggregate)')
        self.scope.pack(side='right')
        self.scope.bind('<<ComboboxSelected>>', lambda e: self.load(self.raw, self.source, self.scope.get()))
        label(toolbar, 'SCOPE', 8, MUTED, True).pack(side='right', padx=10)
        footer = tk.Frame(main, bg=BG)
        footer.pack(side='bottom', fill='x', padx=24, pady=10)
        status = label(footer, size=9, color=MUTED, wraplength=800)
        status.configure(textvariable=self.status)
        status.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(side='bottom', fill='x', padx=24)
        content = tk.Frame(main, bg=BG)
        content.pack(fill='both', expand=True, padx=24, pady=(0, 6))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        self.pages = []
        for _ in self.TITLES:
            p = tk.Frame(content, bg=BG)
            p.grid(row=0, column=0, sticky='nsew')
            self.pages.append(p)

    def text(self, parent, height=10, editable=False):
        from tkinter.scrolledtext import ScrolledText
        w = ScrolledText(parent, wrap='word', font=(FONT, 11), bg=WHITE, fg=INK, relief='flat', bd=0,
                         padx=10, pady=10, spacing1=3, spacing3=7, insertbackground=TEAL,
                         selectbackground='#C9E8EA', height=height, width=20, undo=editable)
        w.tag_configure('title', font=(FONT, 19, 'bold'), foreground=INK, spacing1=12, spacing3=12)
        w.tag_configure('heading', font=(FONT, 12, 'bold'), foreground=TEAL, spacing1=12)
        w.configure(state='normal' if editable else 'disabled')
        return w

    def build_overview(self):
        p = self.pages[0]
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        self.dataset_label = label(p, 'Open a dataset to begin.', 10, MUTED)
        self.dataset_label.grid(row=0, column=0, sticky='w', pady=(0, 12))
        cards = tk.Frame(p, bg=BG)
        cards.grid(row=1, column=0, sticky='ew', pady=(0, 16))
        specs = [('TOTAL RESPONSES', 'Selected analysis scope'), ('SATISFACTION', 'Mean rating · out of 5'), ('WOULD RECOMMEND', 'Recognised answers'), ('COMPLETENESS', 'Required fields populated')]
        for i, (title, note) in enumerate(specs):
            cards.columnconfigure(i, weight=1, uniform='card')
            card = panel(cards, padx=14, pady=16)
            card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            label(card, title, 8, MUTED, True).pack(anchor='w')
            value = label(card, '—', 28, TEAL if i == 1 else INK, True)
            value.pack(anchor='w', pady=(9, 5))
            label(card, note, 8, MUTED).pack(anchor='w')
            self.metric_values.append(value)
        body = tk.Frame(p, bg=BG)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        chart = panel(body, padx=18, pady=16)
        chart.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        label(chart, 'Learning experience', 14, INK, True).pack(anchor='w')
        label(chart, 'Average ratings on a 1–5 scale', 9, MUTED).pack(anchor='w', pady=(4, 8))
        self.chart = tk.Canvas(chart, bg=WHITE, highlightthickness=0, height=225, width=360)
        self.chart.pack(fill='both', expand=True)
        self.chart.bind('<Configure>', lambda e: self.draw_chart())
        side = panel(body, padx=18, pady=16)
        side.grid(row=0, column=1, sticky='nsew')
        label(side, 'At a glance', 14, INK, True).pack(anchor='w')
        self.highlights = self.text(side, height=8)
        self.highlights.pack(fill='both', expand=True, pady=(10, 6))
        self.highlights.configure(font=(FONT, 10), spacing3=3)
        self.highlights.tag_configure('heading', font=(FONT, 11, 'bold'), spacing1=6)
        self.show(self.highlights, 'Load a dataset to see strengths and opportunities.')
        self.action(side, 'Explore evidence →', lambda: self.navigate(2)).pack(fill='x')
        quality = panel(p, padx=16, pady=12)
        quality.grid(row=3, column=0, sticky='ew', pady=(14, 0))
        self.quality_label = label(quality, 'Data quality checks will appear here.', 9, MUTED, wraplength=630)
        self.quality_label.pack(side='left', fill='x', expand=True)
        self.action(quality, 'Inspect data', lambda: self.navigate(1)).pack(side='right', padx=(12, 0))

    def build_data(self):
        p = self.pages[1]
        tools = tk.Frame(p, bg=BG)
        tools.pack(fill='x', pady=(0, 12))
        label(tools, 'SEARCH RESPONSES', 8, MUTED, True).pack(side='left', padx=(0, 12))
        ttk.Entry(tools, textvariable=self.search, width=26).pack(side='left')
        self.search.trace_add('write', self.queue_search)
        self.action(tools, 'Clear', lambda: self.search.set('')).pack(side='left', padx=8)
        self.row_label = label(tools, 'No responses loaded', 9, MUTED)
        self.row_label.pack(side='right')
        box = panel(p)
        box.pack(fill='both', expand=True)
        self.table = ttk.Treeview(box, show='headings', selectmode='browse', height=5)
        vs = ttk.Scrollbar(box, orient='vertical', command=self.table.yview)
        hs = ttk.Scrollbar(box, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side='right', fill='y')
        hs.pack(side='bottom', fill='x')
        self.table.pack(fill='both', expand=True)
        self.table.tag_configure('alternate', background='#F6F9FC')
        self.table.bind('<<TreeviewSelect>>', self.inspect_row)
        self.row_detail = self.text(p, height=4)
        self.row_detail.pack(fill='x', pady=(12, 0))
        self.show(self.row_detail, 'Select a response to inspect its full masked contents.')
        self.validation_text = self.text(p, height=2)
        self.validation_text.pack(fill='x', pady=(8, 0))
        self.show(self.validation_text, 'Quality checks run automatically when a file is opened.')

    def build_themes(self):
        p = self.pages[2]
        label(p, 'Select a theme to inspect the supporting learner comments.', 10, MUTED).pack(anchor='w', pady=(0, 12))
        panes = tk.PanedWindow(p, orient='horizontal', bg=BG, bd=0, sashwidth=12)
        panes.pack(fill='both', expand=True)
        left, right = panel(panes), panel(panes, padx=16, pady=12)
        panes.add(left, minsize=260, width=330)
        panes.add(right, minsize=300)
        self.theme_table = ttk.Treeview(left, columns=('theme', 'count'), show='headings', selectmode='browse', height=5)
        self.theme_table.heading('theme', text='RECURRING THEME')
        self.theme_table.heading('count', text='MENTIONS')
        self.theme_table.column('theme', width=235)
        self.theme_table.column('count', width=75, stretch=False, anchor='center')
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.theme_table.yview)
        scroll.pack(side='right', fill='y')
        self.theme_table.configure(yscrollcommand=scroll.set)
        self.theme_table.pack(fill='both', expand=True)
        self.theme_table.bind('<<TreeviewSelect>>', self.inspect_theme)
        self.theme_detail = self.text(right)
        self.theme_detail.pack(fill='both', expand=True)
        self.show(self.theme_detail, 'Load a dataset to explore its themes.')
        label(p, 'Categories are indicators. Mentions may overlap across themes; inspect evidence before acting.', 9, MUTED, wraplength=800).pack(anchor='w', pady=(12, 0))

    def build_report(self):
        p = self.pages[3]
        p.columnconfigure(0, weight=1)
        p.columnconfigure(1, minsize=242)
        p.rowconfigure(0, weight=1)
        workspace = panel(p, padx=14, pady=12)
        workspace.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        actions = tk.Frame(workspace, bg=WHITE)
        actions.pack(fill='x', pady=(0, 10))
        self.audience = ttk.Combobox(actions, values=['facilitator', 'client'], state='readonly', width=13)
        self.audience.set('facilitator')
        self.audience.pack(side='left')
        self.audience.bind('<<ComboboxSelected>>', self.audience_changed)
        self.generate_button = self.action(actions, 'Generate draft', self.generate, True)
        self.generate_button.pack(side='right')
        self.report_tabs = ttk.Notebook(workspace)
        self.report_tabs.pack(fill='both', expand=True)
        edit, preview = tk.Frame(self.report_tabs, bg=WHITE), tk.Frame(self.report_tabs, bg=WHITE)
        self.report_tabs.add(edit, text='Edit draft')
        self.report_tabs.add(preview, text='Reading preview')
        self.editor = self.text(edit, editable=True)
        self.editor.pack(fill='both', expand=True)
        self.editor.bind('<<Modified>>', self.edited)
        self.preview = self.text(preview)
        self.preview.pack(fill='both', expand=True)
        self.report_tabs.bind('<<NotebookTabChanged>>', lambda e: self.refresh_preview())
        self.show(self.preview, 'Generate a draft to see a formatted reading preview.')
        self.report_tabs.select(1)
        review = panel(p, padx=16, pady=18)
        review.grid(row=0, column=1, sticky='nsew')
        label(review, 'Human review', 14, INK, True).pack(anchor='w')
        state = label(review, size=9, color=TEAL, bold=True, wraplength=205)
        state.configure(textvariable=self.report_status)
        state.pack(anchor='w', pady=(8, 20))
        label(review, '1   Verify the evidence', 10, INK, True).pack(anchor='w')
        label(review, 'Check ratings, themes and source\ncomments before approving.', 9, MUTED, justify='left').pack(anchor='w', pady=(6, 16))
        label(review, '2   Identify the reviewer', 10, INK, True).pack(anchor='w')
        self.reviewer = ttk.Entry(review, width=22)
        self.reviewer.pack(fill='x', pady=(8, 16))
        label(review, '3   Confirm your review', 10, INK, True).pack(anchor='w')
        self.review_check = ttk.Checkbutton(review, text='I checked the evidence,\nprivacy and final wording.', variable=self.confirmed, command=self.review_changed)
        self.review_check.pack(anchor='w', pady=(8, 18))
        self.export_button = self.action(review, 'Approve & export', self.export, True)
        self.export_button.pack(fill='x', pady=(0, 8))
        self.save_button = self.action(review, 'Save draft', lambda: self.export(False))
        self.save_button.pack(fill='x')
        label(review, 'Word (.docx) or Markdown (.md)\nDrafts remain marked for review.', 9, MUTED, justify='left').pack(anchor='w', pady=(12, 0))

    def build_assistant(self):
        box = panel(self.pages[4], padx=22, pady=18)
        box.pack(fill='both', expand=True)
        label(box, 'What would you like to understand?', 17, INK, True).pack(anchor='w')
        label(box, 'Answers from the selected data. Local, rule-based demonstration.', 9, MUTED).pack(anchor='w', pady=(6, 16))
        suggestions = tk.Frame(box, bg=WHITE)
        suggestions.pack(fill='x', pady=(0, 16))
        for caption, question in [('Performance', 'How are the ratings performing?'), ('Key themes', 'What are the main feedback themes?'), ('Next steps', 'What should we improve next?')]:
            self.action(suggestions, caption, lambda q=question: self.ask(q)).pack(side='left', padx=(0, 8))
        entry = tk.Frame(box, bg=WHITE)
        entry.pack(fill='x')
        self.question = ttk.Entry(entry)
        self.question.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.question.bind('<Return>', lambda e: self.ask())
        self.action(entry, 'Ask →', self.ask, True).pack(side='right')
        self.answer = self.text(box)
        self.answer.pack(fill='both', expand=True, pady=(18, 0))
        self.show(self.answer, 'Choose a suggestion or ask about ratings, participation, themes, recommendations or limitations.')

    def navigate(self, index):
        for page in self.pages:
            page.grid_remove()
        self.pages[index].grid()
        self.pages[index].tkraise()
        title, subtitle = self.TITLES[index]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        for i, b in enumerate(self.nav_buttons):
            b.configure(style='Selected.Nav.TButton' if i == index else 'Nav.TButton')
        if index == 0:
            self.root.after_idle(self.draw_chart)

    def render(self, widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        for line in content.splitlines():
            tag = 'title' if line.startswith('# ') else 'heading' if line.startswith('## ') else ''
            line = line.removeprefix('## ').removeprefix('# ').replace('**', '')
            if line.startswith('- '):
                line = '•  ' + line[2:]
            widget.insert('end', line + '\n', tag)
        widget.configure(state='disabled')

    def sync_controls(self):
        for b in self.controls:
            b.configure(state='disabled' if self.busy else 'normal')
        self.generate_button.configure(state='normal' if self.context and not self.busy else 'disabled')
        for b in (self.export_button, self.save_button):
            b.configure(state='normal' if self.report and not self.busy else 'disabled')
        self.scope.configure(state='readonly' if self.context and not self.busy else 'disabled')
        self.audience.configure(state='disabled' if self.busy else 'readonly')
        self.editor.configure(state='normal' if self.report and not self.busy else 'disabled')
        self.review_check.configure(state='normal' if self.report and not self.busy else 'disabled')

    def draw_chart(self):
        c = self.chart
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50:
            return
        if not self.context:
            c.create_text(w/2, h/2, text='Your rating chart will appear here', fill=MUTED, font=(FONT, 11))
            return
        ratings = list(self.context.metrics['ratings'].values())
        step = max(40, min(66, (h-28)/len(ratings)))
        for i, rating in enumerate(ratings):
            y = 8 + i*step
            c.create_text(2, y, anchor='nw', text=rating['label'], fill=INK, font=(FONT, 10))
            mean = rating['mean']
            c.create_text(w-4, y, anchor='ne', text=f'{mean:.2f} / 5' if mean is not None else 'N/A', fill=TEAL, font=(FONT, 10, 'bold'))
            c.create_rectangle(2, y+25, w-4, y+34, fill='#EAF0F5', width=0)
            if mean is not None:
                c.create_rectangle(2, y+25, 2+(w-6)*mean/5, y+34, fill=TEAL, width=0)
        c.create_text(2, h-6, anchor='sw', text='0', fill=MUTED, font=(FONT, 8))
        c.create_text(w-4, h-6, anchor='se', text='5', fill=MUTED, font=(FONT, 8))

    def edited(self, event=None):
        if self.editor.edit_modified():
            self.confirmed.set(False)
            self.dirty = self.report is not None
            self.report_status.set('Draft • requires review' if self.report else 'No draft yet')
            self.editor.edit_modified(False)

    def review_changed(self):
        self.report_status.set('Ready for named approval' if self.confirmed.get() else 'Draft • requires review')

    def refresh_preview(self):
        if self.report:
            self.render(self.preview, self.editor.get('1.0', 'end-1c'))

    def may_replace(self):
        return not self.dirty or messagebox.askyesno('Unsaved report', 'Continue and discard the unsaved report? Use Save draft to keep a copy.', parent=self.root)

    def load(self, source, name, scope='All courses (aggregate)'):
        from pathlib import Path
        from src.ingestion.qualtrics_loader import load_csv
        if self.busy or source is None:
            return
        if not self.may_replace():
            self.scope.set(self.context.course_name if self.context else 'All courses (aggregate)')
            return
        self.busy = True
        self.status.set('Reading, validating and analysing data…')
        self.progress.start(12)
        self.sync_controls()
        def work():
            raw = source() if callable(source) else load_csv(source) if isinstance(source, (str, Path)) else source
            return raw, analyse(raw, name, scope)
        future = self.pool.submit(work)
        def finish():
            if not future.done():
                self.load_poll = self.root.after(80, finish)
                return
            self.load_poll = None
            self.busy = False
            self.progress.stop()
            self.progress.configure(value=0)
            try:
                raw, result = future.result()
            except Exception as exc:
                self.scope.set(self.context.course_name if self.context else 'All courses (aggregate)')
                self.status.set('Could not load this file. Your previous workspace is unchanged.')
                self.sync_controls()
                messagebox.showerror('Cannot analyse file', str(exc), parent=self.root)
                return
            self.raw, self.source = raw, name
            self.apply_analysis(result)
            self.status.set(f'Ready • {len(self.frame):,} responses analysed • All processing is local')
            self.sync_controls()
        self.load_poll = self.root.after(80, finish)

    def synthetic(self):
        from src.synthetic import build_synthetic_responses
        self.load(lambda: build_synthetic_responses(500, 208), 'synthetic_500_seed_208.csv')

    def apply_analysis(self, result):
        self.frame, self.context, count, courses = result
        self.scope.configure(values=['All courses (aggregate)', *courses])
        self.scope.set(self.context.course_name)
        self.report, self.dirty = None, False
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.confirmed.set(False)
        self.report_status.set('No draft yet')
        self.show(self.preview, 'Generate a draft to see a formatted reading preview.')
        self.show(self.answer, 'Ask about this dataset or choose a suggestion above.')
        self.question.delete(0, 'end')
        self.search.set('')
        self.filter_rows()
        m = self.context.metrics
        mean, rec = m['ratings']['OverallSatisfaction']['mean'], m['recommendation_percent']
        values = [f"{m['response_count']:,}", f'{mean:.2f}' if mean is not None else 'N/A', f'{rec:.0f}%' if rec is not None else 'N/A', f"{m['response_completeness']:.1f}%"]
        for widget, value in zip(self.metric_values, values):
            widget.configure(text=value)
        self.dataset_label.configure(text=f'{self.source}  /  {self.context.course_name}')
        strongest = m['ratings'].get(m['strongest_area'], {}).get('label', 'Insufficient rating data')
        improvement = next((t.name for t in self.context.themes if t.category == 'Improvement'), 'No recurring improvement theme')
        self.render(self.highlights, f'## Strongest rated area\n{strongest}\n## Opportunity to explore\n{improvement}\n## Feedback coverage\n{len(self.context.themes)} recurring themes identified')
        warnings = self.context.warnings
        summary = f'{len(warnings)} quality warning(s)' if warnings else 'Required columns validated'
        self.quality_label.configure(text=f'{summary}  •  {count} patterns masked in source file\nBasic masking still requires human inspection.', fg='#92600D' if warnings else TEAL)
        self.show(self.validation_text, 'SOURCE FILE QUALITY\n' + ('\n'.join(warnings) if warnings else 'No validation warnings.') + f'\n{count} patterns masked. Preview capped at 1,000 rows; all selected rows are analysed.')
        self.theme_table.delete(*self.theme_table.get_children())
        for i, theme in enumerate(self.context.themes):
            self.theme_table.insert('', 'end', iid=str(i), values=(theme.name, theme.frequency))
        if self.context.themes:
            self.theme_table.selection_set('0')
            self.inspect_theme()
        else:
            self.show(self.theme_detail, 'No recurring themes met the evidence threshold.')
        self.draw_chart()

    def queue_search(self, *args):
        if self.search_id:
            self.root.after_cancel(self.search_id)
        self.search_id = self.root.after(180, self.filter_rows)

    def filter_rows(self):
        if self.search_id:
            self.root.after_cancel(self.search_id)
        self.search_id = None
        if self.frame is None:
            return
        frame = self.frame.fillna('').astype(str)
        query = self.search.get().strip().casefold()
        if query:
            frame = frame[frame.apply(lambda col: col.str.casefold().str.contains(query, regex=False)).any(axis=1)]
        self.table.delete(*self.table.get_children())
        self.table['columns'] = list(frame.columns)
        for col in frame.columns:
            self.table.heading(col, text=col)
            self.table.column(col, width=210 if col in ('CourseName', 'MostValuableAspect', 'WhatCouldImprove', 'AdditionalComments') else 150, stretch=False)
        for i, row in enumerate(frame.head(1000).itertuples(index=False, name=None)):
            self.table.insert('', 'end', values=row, tags=('alternate',) if i % 2 else ())
        self.row_label.configure(text=f'{min(1000, len(frame)):,} shown / {len(frame):,} matching')
        self.show(self.row_detail, 'Select a response to inspect its full contents.' if len(frame) else 'No matching responses. Clear the search to see all data.')

    def inspect_row(self, event=None):
        selected = self.table.selection()
        if selected:
            values = self.table.item(selected[0], 'values')
            self.show(self.row_detail, '\n'.join(f'{col}: {value}' for col, value in zip(self.table['columns'], values)))

    def inspect_theme(self, event=None):
        selected = self.theme_table.selection()
        if selected and self.context:
            theme = self.context.themes[int(selected[0])]
            text = f'# {theme.name}\n{theme.category}  •  {theme.frequency} related comment(s)\n\n## Keywords\n{", ".join(theme.keywords) or "Emerging topic"}\n\n## Supporting learner feedback\n'
            text += '\n\n'.join(f'“{comment}”' for comment in theme.evidence) or 'No example comments available.'
            self.render(self.theme_detail, text)

    def audience_changed(self, event=None):
        if self.report and self.audience.get() != self.report.audience:
            self.status.set(f'Current draft is for {self.report.audience}. Generate a new draft to change audience.')

    def generate(self):
        from src.reporting.report_generator import generate_report
        from src.ai.local_provider import LocalDemoProvider
        if not self.context or self.busy or (self.report and not self.may_replace()):
            return
        self.report = generate_report(self.context, self.audience.get(), LocalDemoProvider())
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', self.report.content)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.dirty = True
        self.confirmed.set(False)
        self.report_status.set(f'{self.report.audience.title()} draft • requires review')
        self.refresh_preview()
        self.report_tabs.select(1)
        self.status.set('Draft ready • Read the preview, edit the wording, then complete human review.')
        self.sync_controls()

    def export(self, reviewed=True):
        from pathlib import Path
        from datetime import datetime
        from tkinter import filedialog
        from src.reporting.exporter import docx_bytes, markdown_bytes
        from src.reporting.report_generator import approve_report
        if not self.report or self.busy:
            return False
        if reviewed and (not self.reviewer.get().strip() or not self.confirmed.get()):
            messagebox.showinfo('Review required', 'Enter the reviewer name and confirm the evidence, privacy and wording checks.', parent=self.root)
            return False
        content = self.editor.get('1.0', 'end-1c').strip()
        if not content:
            messagebox.showerror('Empty report', 'Add report content before exporting.', parent=self.root)
            return False
        path = filedialog.asksaveasfilename(parent=self.root, title='Export reviewed report' if reviewed else 'Save draft report',
            initialfile=f'learning_evaluation_{self.report.audience}_{"reviewed" if reviewed else "draft"}.docx',
            defaultextension='.docx', filetypes=[('Word document', '*.docx'), ('Markdown', '*.md')])
        if not path:
            return False
        if Path(path).suffix.lower() not in ('.docx', '.md'):
            messagebox.showerror('Unsupported format', 'Choose a .docx or .md filename.', parent=self.root)
            return False
        final = approve_report(self.report, content).content if reviewed else '**DRAFT — REQUIRES HUMAN REVIEW**\n\n' + content
        if reviewed:
            final += f'\n\nReviewed by: {self.reviewer.get().strip()}\nReviewed at: {datetime.now().astimezone().isoformat(timespec="minutes")}\n'
        try:
            Path(path).write_bytes(docx_bytes(final) if Path(path).suffix.lower() == '.docx' else markdown_bytes(final))
        except Exception as exc:
            messagebox.showerror('Export failed', str(exc), parent=self.root)
            return False
        self.dirty = False
        self.report_status.set('Reviewed copy exported' if reviewed else 'Draft saved • requires review')
        self.status.set(f'{"Reviewed report" if reviewed else "Draft"} saved • {path}')
        return True

    def ask(self, question=None):
        from src.ai.copilot import answer_question
        if not self.context or self.busy:
            self.show(self.answer, 'Load a dataset first, then choose a question.')
            return
        text = question if question is not None else self.question.get().strip()
        if question is not None:
            self.question.delete(0, 'end')
            self.question.insert(0, question)
        if not text:
            self.show(self.answer, 'Enter a question or choose a suggestion above.')
            return
        self.render(self.answer, f'## {text}\n\n{answer_question(text, self.context)}\n\n## Analysis scope\n{self.context.course_name} • {self.context.metrics["response_count"]:,} responses')

    def close(self):
        if not self.may_replace():
            return
        for pending in (getattr(self, 'load_poll', None), getattr(self, 'startup_id', None), self.search_id):
            if pending:
                self.root.after_cancel(pending)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main():
    from src.ui.runtime import main as start
    return start()
