"""Presentation interface for the native desktop workflow."""
import os
import tkinter as tk
from src.ui.revisions import RevisionUI
from src.ui.review import ReviewUI
from src.ui.insights import InsightsUI
from src.ui.questions import QuestionsUI
from src.ui.wording import service_message
from tkinter import ttk, messagebox, font as tkfont
from src.ui.runtime import _setup_environment  # noqa: F401 -- re-exported for tests
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
from src.ui.theme import BG, WHITE, INK, MUTED, NAVY, TEAL, BORDER

FONT = 'TkDefaultFont'


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


class DesktopApp(ReviewUI, RevisionUI, InsightsUI, QuestionsUI):
    TITLES = [('Explore data', 'A clear view of learner experience, grounded in your survey data.'),
              ('Themes & evidence', 'Explore recurring feedback and the comments supporting it, or ask a question.'),
              ('Report studio', 'Turn evidence into a draft, refine it, then review and export.')]

    def __init__(self, root, auto_load=False):
        global FONT
        FONT = tkfont.nametofont('TkDefaultFont', root=root).actual('family')
        self.root = root
        self.font_family = FONT
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.context = self.raw = self.report = self.frame = None
        self.source = ''
        self.loaded_file_label = ''
        self.busy = self.dirty = False
        self.controls = []
        self.nav_buttons = []
        self.metric_values = []
        self.search_id = None
        self.sort_column = None
        self.sort_reverse = False
        self.status = tk.StringVar(value='Awaiting import. Choose a CSV or Excel file to begin.')
        self.report_status = tk.StringVar(value='No draft yet')
        self.evidence_status = tk.StringVar(value='Evidence check: get a draft first.')
        self.confirmed = tk.BooleanVar(value=False)
        self.search = tk.StringVar()
        root.title('Learning Futures | Insight Hub')
        root.geometry(f'{min(1360, root.winfo_screenwidth()-70)}x{min(900, root.winfo_screenheight()-80)}+25+25')
        root.minsize(min(1080, root.winfo_screenwidth()-70), min(740, root.winfo_screenheight()-80))
        root.configure(bg=BG)
        self.init_review_state()
        self.styles()
        self.shell()
        self.build_data_page()
        self.build_themes_page()
        self.build_report()
        self.build_revision_ui()
        self.build_claims_tab()
        self.refresh_report_tab_bar()
        self.navigate(0)
        self.sync_controls()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-o>', lambda e: self.open_file() if not self.busy else None)
        if auto_load:
            self.startup_id = root.after(150, self.load_startup_data)

    @staticmethod
    def show(widget, content):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')

    def open_file(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title='Open evaluation data', initialdir=os.getenv('DEMO_SHARED_DIR', str(DATA_DIR)), filetypes=[('Survey files', '*.csv *.xlsx *.xls')])
        if paths:
            import pandas as pd
            from src.ingestion.qualtrics_loader import load_survey

            def load_selected_files():
                frames = []
                for path in paths:
                    frame = load_survey(path).copy()
                    frame['SourceFile'] = Path(path).name
                    frames.append(frame)
                return pd.concat(frames, ignore_index=True)

            raw_display = Path(paths[0]).stem.replace('+', ' ').replace('_', ' ')
            first_display = ' '.join(raw_display.split())
            if len(first_display) > 64:
                first_display = first_display[:61].rstrip() + '…'
            display_label = (
                first_display
                if len(paths) == 1
                else f'{len(paths)} survey files loaded  ·  {first_display}  +{len(paths)-1} more'
            )

            self.load(
                load_selected_files,
                Path(paths[0]).name if len(paths) == 1 else f'{len(paths)} survey files',
                file_label=display_label
            )

    def load_startup_data(self):
        self.startup_id = None
        env_path = os.getenv('EVALUATION_DATA_PATH')
        if env_path:
            path = Path(env_path).expanduser()
            if not path.is_absolute():
                path = DATA_DIR.parent / path
        else:
            client_dir = DATA_DIR / 'client'
            path = client_dir if client_dir.is_dir() and any(client_dir.glob('*.csv')) else DATA_DIR / 'synthetic_qualtrics_evaluation.csv'
        if path.is_dir():
            from src.ingestion.qualtrics_loader import load_qualtrics_folder
            self.load(lambda p=path: load_qualtrics_folder(p), 'Learning Futures Qualtrics Data Set')
        else:
            self.load(path, path.name)

    def styles(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.', font=(FONT, 10))
        s.configure('Nav.TButton', background=NAVY, foreground='#C7BEE0', anchor='w', padding=(15, 14), borderwidth=0, relief='flat')
        s.map('Nav.TButton', background=[('active', '#4A3574')], foreground=[('active', WHITE)])
        s.configure('Selected.Nav.TButton', background='#4A3574', foreground=WHITE)
        s.map('Selected.Nav.TButton', background=[('active', '#4A3574')], foreground=[('active', WHITE)])
        s.configure('TButton', background=WHITE, foreground=INK, bordercolor='#E4DDF0',
                    padding=(14, 9), relief='flat')
        s.map('TButton', background=[('active', '#F6F2FB')], foreground=[('disabled', '#A79BC4')])
        s.configure('Primary.TButton', background=TEAL, foreground=WHITE, bordercolor=TEAL,
                    padding=(15, 9))
        s.map('Primary.TButton', background=[('disabled', '#DCCFF7'), ('active', '#6B2FD4')],
              foreground=[('disabled', '#8E7FB0')])
        s.configure('TCombobox', padding=7, fieldbackground=WHITE, foreground=INK, bordercolor=BORDER)
        s.map('TCombobox', fieldbackground=[('readonly', WHITE)], selectbackground=[('readonly', WHITE)], selectforeground=[('readonly', INK)])
        s.configure('TEntry', padding=8, fieldbackground=WHITE, bordercolor=BORDER)
        s.configure('TCheckbutton', background=WHITE, foreground=INK, padding=5)
        s.map('TCheckbutton', background=[('active', WHITE)])
        s.configure('Treeview', background=WHITE, fieldbackground=WHITE, foreground=INK,
                    rowheight=36, borderwidth=0)
        s.configure('Treeview.Heading', background='#F4F0FA', foreground=MUTED,
                    font=(FONT, 9, 'bold'), padding=(10, 11), relief='flat')
        s.map('Treeview', background=[('selected', '#EDE4FB')], foreground=[('selected', INK)])
        s.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure('TNotebook.Tab', padding=(18, 11), background='#F2EDF8',
                    foreground=MUTED, borderwidth=0)
        s.map('TNotebook.Tab',
              background=[('selected', WHITE), ('active', '#F8F5FC')],
              foreground=[('selected', TEAL), ('active', INK)])

        # Explore data uses a custom flat tab bar. Hide only that notebook's
        # native tabs so the active item never appears recessed/pressed.
        try:
            s.layout('Explore.TNotebook.Tab', [])
            s.layout('Flat.TNotebook.Tab', [])
        except tk.TclError:
            pass
        s.configure('Explore.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure('Flat.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
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
        label(sidebar, 'LEARNING FUTURES', 8, '#A9A0C9').pack(anchor='w', padx=20)
        tk.Frame(sidebar, bg='#3D2B63', height=1).pack(fill='x', padx=20, pady=26)
        label(sidebar, 'WORKSPACE', 8, '#A9A0C9', True).pack(anchor='w', padx=20, pady=(0, 12))
        for i, name in enumerate(['Explore data', 'Themes & evidence', 'Report studio']):
            b = ttk.Button(sidebar, text=f'{i+1:02}   {name}', style='Nav.TButton',
                           cursor='hand2', command=lambda index=i: self.navigate(index))
            b.pack(fill='x', padx=10, pady=3)
            self.nav_buttons.append(b)
        bottom = tk.Frame(sidebar, bg=NAVY)
        bottom.pack(side='bottom', fill='x', padx=20, pady=24)
        label(bottom, '●  WORKSPACE', 9, '#5EEAD4', True).pack(anchor='w')
        self.action(bottom, 'Data use', lambda: messagebox.showinfo(
            'Data use', 'Insights, answers, report drafts and "Ask Gemini" revisions use an external processing service. '
            'Only calculated metrics, fixed theme counts, your question or request and (for revisions) the masked text of the '
            'selected report section are submitted; raw survey comments stay on this device. '
            'Submitted summaries may be used by the service to improve its products. Avoid personal details in questions.\n\n'
            'Review actions (theme and claim decisions, submissions, approvals, exports) are recorded in a tamper-evident '
            'audit log on this computer: ' + str(self.audit.path),
            parent=self.root)).pack(anchor='w', pady=(8, 0))
        label(bottom, 'Explore feedback.\nTurn insights into action.\nReports require human review.', 9, '#B8AED9', justify='left', wraplength=168).pack(anchor='w', pady=(8, 0))
        main = tk.Frame(self.root, bg=BG)
        main.pack(side='left', fill='both', expand=True)
        head = tk.Frame(main, bg=BG)
        head.pack(fill='x', padx=24, pady=(24, 16))
        label(head, 'EVALUATION WORKSPACE', 9, TEAL, True).pack(anchor='w', pady=(0, 8))
        self.page_title = label(head, '', 25, INK, True)
        self.page_title.pack(anchor='w')
        self.page_subtitle = label(head, '', 10, MUTED)
        self.page_subtitle.pack(anchor='w', pady=(4, 0))
        toolbar = panel(main, padx=12, pady=12)
        self.toolbar = toolbar
        toolbar.pack(fill='x', padx=24, pady=(0, 18))
        toolbar.columnconfigure(1, weight=1)
        self.action(toolbar, '+ Import CSV / Excel', self.open_file, True).grid(row=0, column=0, padx=(0, 12), sticky='w')
        file_badge = tk.Frame(toolbar, bg='#F4EFFA', padx=14, pady=9,
                              highlightbackground='#E6DFF1', highlightthickness=1)
        file_badge.grid(row=0, column=1, sticky='nsew')
        self.file_state = label(file_badge, 'AWAITING IMPORT', 8, MUTED, True)
        self.file_state.pack(anchor='w')
        self.file_name = label(file_badge, 'No file selected', 10, INK, True,
                               width=1, wraplength=620, justify='left')
        self.file_name.pack(fill='x', pady=(3, 0))
        file_badge.bind('<Configure>', lambda event: self.file_name.configure(wraplength=max(160, event.width-28)))
        footer = tk.Frame(main, bg=BG)
        footer.pack(side='bottom', fill='x', padx=24, pady=10)
        status = label(footer, size=9, color=MUTED, wraplength=800)
        status.configure(textvariable=self.status)
        status.pack(side='left')
        self.progress = ttk.Progressbar(main, mode='indeterminate')
        content = tk.Frame(main, bg=BG)
        self.content_frame = content
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
                         padx=12, pady=12, spacing1=3, spacing3=7, insertbackground=TEAL,
                         selectbackground='#E6DBFB', height=height, width=20, undo=editable,
                         highlightthickness=1, highlightbackground='#E4DDF0',
                         highlightcolor='#B89BE8')
        w.tag_configure('title', font=(FONT, 19, 'bold'), foreground=INK, spacing1=12, spacing3=12)
        w.tag_configure('heading', font=(FONT, 12, 'bold'), foreground=TEAL, spacing1=12)
        w.configure(state='normal' if editable else 'disabled')
        return w

    def build_data_page(self):
        container = self.pages[0]

        # Flat custom tab bar: active tab is indicated by colour + underline,
        # not by a recessed ttk tab.
        tabbar = tk.Frame(container, bg=BG)
        tabbar.pack(fill='x', pady=(0, 0))

        self.explore_tab_buttons = []
        tab_specs = ['Overview', 'Survey data', 'Insights & suggestions']

        for index, caption in enumerate(tab_specs):
            holder = tk.Frame(tabbar, bg=BG)
            holder.pack(side='left', padx=(0, 4))

            button = tk.Button(
                holder,
                text=caption,
                command=lambda i=index: self.select_explore_tab(i),
                font=(FONT, 10, 'normal'),
                fg=MUTED,
                bg='#F5F1FA',
                activeforeground=TEAL,
                activebackground='#F5F1FA',
                relief='flat',
                bd=0,
                highlightthickness=0,
                padx=18,
                pady=10,
                cursor='hand2'
            )
            button.pack(fill='x')

            underline = tk.Frame(holder, bg='#F5F1FA', height=3)
            underline.pack(fill='x')

            self.explore_tab_buttons.append((button, underline))

        notebook = ttk.Notebook(container, style='Explore.TNotebook')
        notebook.pack(fill='both', expand=True)

        overview_tab = tk.Frame(notebook, bg=BG)
        data_tab = tk.Frame(notebook, bg=BG)
        insights_tab = tk.Frame(notebook, bg=BG)

        notebook.add(overview_tab, text='Overview')
        notebook.add(data_tab, text='Survey data')
        notebook.add(insights_tab, text='Insights & suggestions')

        self.explore_notebook = notebook
        self.explore_notebook.bind('<<NotebookTabChanged>>', lambda e: self.sync_explore_tabs())

        self.build_overview(overview_tab)
        self.build_data(data_tab)
        self.build_insights(insights_tab)

        self.select_explore_tab(0)

    def select_explore_tab(self, index):
        self.explore_notebook.select(index)
        self.sync_explore_tabs()

    def sync_explore_tabs(self):
        if not hasattr(self, 'explore_tab_buttons'):
            return
        try:
            selected = self.explore_notebook.index(self.explore_notebook.select())
        except tk.TclError:
            return

        for index, (button, underline) in enumerate(self.explore_tab_buttons):
            active = index == selected
            button.configure(
                bg=WHITE if active else '#F5F1FA',
                activebackground=WHITE if active else '#F5F1FA',
                fg=TEAL if active else MUTED,
                font=(FONT, 10, 'bold' if active else 'normal')
            )
            underline.configure(bg=TEAL if active else '#F5F1FA')

    def show_survey_data(self):
        self.navigate(0)
        self.select_explore_tab(1)

    def build_themes_page(self):
        container = self.pages[1]

        tabbar = tk.Frame(container, bg=BG)
        tabbar.pack(fill='x')

        self.themes_tab_buttons = []
        tab_specs = ['Themes & evidence', 'Ask a question']

        for index, caption in enumerate(tab_specs):
            holder = tk.Frame(tabbar, bg=BG)
            holder.pack(side='left', padx=(0, 4))

            button = tk.Button(
                holder,
                text=caption,
                command=lambda i=index: self.select_themes_tab(i),
                font=(FONT, 10, 'normal'),
                fg=MUTED,
                bg='#F5F1FA',
                activeforeground=TEAL,
                activebackground='#F5F1FA',
                relief='flat',
                bd=0,
                highlightthickness=0,
                padx=18,
                pady=10,
                cursor='hand2'
            )
            button.pack(fill='x')

            underline = tk.Frame(holder, bg='#F5F1FA', height=3)
            underline.pack(fill='x')
            self.themes_tab_buttons.append((button, underline))

        notebook = ttk.Notebook(container, style='Flat.TNotebook')
        notebook.pack(fill='both', expand=True)

        themes_tab = tk.Frame(notebook, bg=BG)
        assistant_tab = tk.Frame(notebook, bg=BG)
        notebook.add(themes_tab, text='Themes & evidence')
        notebook.add(assistant_tab, text='Ask a question')

        self.themes_notebook = notebook
        self.themes_notebook.bind(
            '<<NotebookTabChanged>>',
            lambda e: self.sync_themes_tabs()
        )

        self.build_themes(themes_tab)
        self.build_assistant(assistant_tab)
        self.select_themes_tab(0)

    def select_themes_tab(self, index):
        self.themes_notebook.select(index)
        self.sync_themes_tabs()

    def sync_themes_tabs(self):
        if not hasattr(self, 'themes_tab_buttons'):
            return
        try:
            selected = self.themes_notebook.index(self.themes_notebook.select())
        except tk.TclError:
            return

        for index, (button, underline) in enumerate(self.themes_tab_buttons):
            active = index == selected
            button.configure(
                bg=WHITE if active else '#F5F1FA',
                activebackground=WHITE if active else '#F5F1FA',
                fg=TEAL if active else MUTED,
                font=(FONT, 10, 'bold' if active else 'normal')
            )
            underline.configure(bg=TEAL if active else '#F5F1FA')

    def build_overview(self, p):
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)
        self.dataset_label = label(p, 'Open a dataset to begin.', 9, MUTED)
        self.dataset_label.grid(row=0, column=0, sticky='w', pady=(2, 14))
        cards = tk.Frame(p, bg=BG)
        cards.grid(row=1, column=0, sticky='ew', pady=(0, 16))
        specs = [('TOTAL RESPONSES', 'Selected analysis scope'), ('OVERALL RATING', 'Mean of valid answers · out of 5'), ('WOULD RECOMMEND', 'Recognised answers'), ('COMPLETENESS', 'Of fields the survey collected')]
        for i, (title, note) in enumerate(specs):
            cards.columnconfigure(i, weight=1, uniform='card')
            card = panel(cards, padx=14, pady=16)
            card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            label(card, title, 8, MUTED, True).pack(anchor='w')
            value = label(card, 'PENDING', 18, MUTED, True)
            value.pack(anchor='w', pady=(9, 5))
            label(card, note, 8, MUTED).pack(anchor='w')
            self.metric_values.append(value)
        body = tk.Frame(p, bg=BG)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        chart = panel(body, padx=20, pady=18)
        chart.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        label(chart, 'Learning experience', 14, INK, True).pack(anchor='w')
        label(chart, 'Average ratings on a 1–5 scale', 9, MUTED).pack(anchor='w', pady=(4, 8))
        self.chart = tk.Canvas(chart, bg=WHITE, highlightthickness=0, height=225, width=360)
        self.chart.pack(fill='both', expand=True)
        self.chart.bind('<Configure>', lambda e: self.draw_chart())
        side = panel(body, padx=20, pady=18)
        side.grid(row=0, column=1, sticky='nsew')
        label(side, 'At a glance', 14, INK, True).pack(anchor='w')
        self.highlights = self.text(side, height=8)
        self.highlights.pack(fill='both', expand=True, pady=(10, 6))
        self.highlights.configure(font=(FONT, 10), spacing3=3)
        self.highlights.tag_configure('heading', font=(FONT, 11, 'bold'), spacing1=6)
        self.show(self.highlights, 'Load a dataset to see strengths and opportunities.')
        self.action(side, 'Explore evidence →', lambda: self.navigate(1)).pack(fill='x')
        quality = panel(p, padx=16, pady=12)
        quality.grid(row=3, column=0, sticky='ew', pady=(14, 0))
        self.quality_label = label(quality, 'Data quality checks will appear here.', 9, MUTED, wraplength=630)
        self.quality_label.pack(side='left', fill='x', expand=True)
        self.action(quality, 'Inspect data', self.show_survey_data).pack(side='right', padx=(12, 0))

    def build_data(self, p):
        tools = tk.Frame(p, bg=BG)
        tools.pack(fill='x', pady=(0, 8))
        label(tools, 'SEARCH RESPONSES', 8, MUTED, True).pack(side='left', padx=(0, 12))
        ttk.Entry(tools, textvariable=self.search, width=26).pack(side='left')
        self.search.trace_add('write', self.queue_search)
        self.action(tools, 'Clear', lambda: self.search.set('')).pack(side='left', padx=8)
        self.row_label = label(tools, 'No responses loaded', 9, MUTED)
        self.row_label.pack(side='right')

        filters = tk.Frame(p, bg=BG)
        filters.pack(fill='x', pady=(0, 12))

        label(filters, 'FILTER', 8, MUTED, True).pack(side='left', padx=(0, 10))

        self.source_filter = ttk.Combobox(filters, state='readonly', width=18, values=['All files'])
        self.source_filter.set('All files')
        self.source_filter.pack(side='left', padx=(0, 8))
        self.source_filter.bind('<<ComboboxSelected>>', lambda e: self.filter_rows())

        self.course_filter = ttk.Combobox(filters, state='readonly', width=20, values=['All courses'])
        self.course_filter.set('All courses')
        self.course_filter.pack(side='left', padx=(0, 8))
        self.course_filter.bind('<<ComboboxSelected>>', lambda e: self.filter_rows())

        self.month_filter = ttk.Combobox(filters, state='readonly', width=11, values=['All dates'])
        self.month_filter.set('All dates')
        self.month_filter.pack(side='left', padx=(0, 8))
        self.month_filter.bind('<<ComboboxSelected>>', lambda e: self.filter_rows())

        self.rating_filter = ttk.Combobox(filters, state='readonly', width=10, values=['All ratings'])
        self.rating_filter.set('All ratings')
        self.rating_filter.pack(side='left', padx=(0, 8))
        self.rating_filter.bind('<<ComboboxSelected>>', lambda e: self.filter_rows())

        self.recommend_filter = ttk.Combobox(filters, state='readonly', width=13, values=['All recommendations'])
        self.recommend_filter.set('All recommendations')
        self.recommend_filter.pack(side='left', padx=(0, 8))
        self.recommend_filter.bind('<<ComboboxSelected>>', lambda e: self.filter_rows())

        self.action(filters, 'Reset view', self.reset_data_view).pack(side='left')

        box = panel(p)
        box.pack(fill='both', expand=True)
        self.table = ttk.Treeview(box, show='headings', selectmode='browse', height=5)
        vs = ttk.Scrollbar(box, orient='vertical', command=self.table.yview)
        hs = ttk.Scrollbar(box, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side='right', fill='y')
        hs.pack(side='bottom', fill='x')
        self.table.pack(fill='both', expand=True)
        self.table.tag_configure('alternate', background='#FAF8FD')
        self.table.bind('<<TreeviewSelect>>', self.inspect_row)

        # Keep detail and data-quality information visible without stacking
        # two large text areas vertically.
        details = tk.Frame(p, bg=BG, height=142)
        details.pack(fill='x', pady=(10, 0))
        details.pack_propagate(False)
        details.columnconfigure(0, weight=3)
        details.columnconfigure(1, weight=2)
        details.rowconfigure(0, weight=1)

        response_card = panel(details, padx=12, pady=10)
        response_card.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        label(response_card, 'SELECTED RESPONSE', 8, MUTED, True).pack(anchor='w', pady=(0, 6))
        self.row_detail = self.text(response_card, height=4)
        self.row_detail.pack(fill='both', expand=True)
        self.show(self.row_detail, 'Select a response to inspect its full masked contents.')

        quality_card = panel(details, padx=12, pady=10)
        quality_card.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
        label(quality_card, 'SOURCE FILE QUALITY', 8, MUTED, True).pack(anchor='w', pady=(0, 6))
        self.validation_text = self.text(quality_card, height=4)
        self.validation_text.pack(fill='both', expand=True)
        self.show(self.validation_text, 'Quality checks run automatically when a file is opened.')

    def build_themes(self, p):
        intro = tk.Frame(p, bg='#F6F2FB', padx=12, pady=9,
                         highlightbackground='#E5DEEF', highlightthickness=1)
        intro.pack(fill='x', pady=(0, 12))
        label(intro, 'STEP 1 · HUMAN REVIEW', 8, TEAL, True).pack(anchor='w')
        label(intro, 'Read the supporting comments, then confirm, re-categorise or reject each recurring theme.',
              9, MUTED, wraplength=900).pack(anchor='w', pady=(2, 0))

        panes = tk.PanedWindow(p, orient='horizontal', bg=BG, bd=0, sashwidth=8,
                              sashrelief='flat', showhandle=False)
        panes.pack(fill='both', expand=True)
        left = panel(panes, padx=0, pady=0)
        right = panel(panes, padx=18, pady=14)
        panes.add(left, minsize=330, width=370)
        panes.add(right, minsize=480)

        left_head = tk.Frame(left, bg=WHITE, padx=14, pady=11)
        left_head.pack(fill='x')
        label(left_head, 'Theme review', 12, INK, True).pack(side='left')
        self.show_pending_themes = tk.BooleanVar(master=self.root, value=False)
        ttk.Checkbutton(
            left_head,
            text='Pending only',
            variable=self.show_pending_themes,
            command=self.refresh_theme_rows
        ).pack(side='right')

        tk.Frame(left, bg='#E7E0F1', height=1).pack(fill='x')

        self.theme_table = ttk.Treeview(
            left,
            columns=('theme', 'count', 'decision'),
            show='headings',
            selectmode='browse',
            height=5
        )
        self.theme_table.heading('theme', text='RECURRING THEME')
        self.theme_table.heading('count', text='MENTIONS')
        self.theme_table.heading('decision', text='DECISION')
        self.theme_table.column('theme', width=195)
        self.theme_table.column('count', width=82, stretch=False, anchor='center')
        self.theme_table.column('decision', width=105, stretch=False, anchor='center')
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.theme_table.yview)
        scroll.pack(side='right', fill='y')
        self.theme_table.configure(yscrollcommand=scroll.set)
        self.theme_table.pack(fill='both', expand=True)
        self.theme_table.bind('<<TreeviewSelect>>', self.inspect_theme)

        label(right, 'Selected theme', 8, MUTED, True).pack(anchor='w', pady=(0, 6))
        controls = tk.Frame(right, bg=WHITE)
        controls.pack(side='bottom', fill='x', pady=(10, 0))
        self.build_theme_review_controls(controls)

        self.theme_detail = self.text(right)
        self.theme_detail.pack(fill='both', expand=True)
        self.show(self.theme_detail, 'Load a dataset to explore its themes.')

        label(p, 'Categories are indicators. Mentions may overlap across themes; inspect evidence before acting.',
              9, MUTED, wraplength=900).pack(anchor='w', pady=(10, 0))

    def build_report(self):
        p = self.pages[2]
        p.columnconfigure(0, weight=1)
        p.rowconfigure(0, weight=1)

        workspace = panel(p, padx=18, pady=14)
        workspace.grid(row=0, column=0, sticky='nsew')

        actions = tk.Frame(workspace, bg=WHITE)
        actions.pack(fill='x', pady=(0, 8))

        audience_box = tk.Frame(actions, bg=WHITE)
        audience_box.pack(side='left')
        label(audience_box, 'REPORT TYPE', 8, MUTED, True).pack(anchor='w', pady=(0, 4))
        self.audience = ttk.Combobox(audience_box, values=['facilitator', 'client'],
                                     state='readonly', width=16)
        self.audience.set('facilitator')
        self.audience.pack(anchor='w')
        self.audience.bind('<<ComboboxSelected>>', self.audience_changed)

        # Human review becomes a contextual drawer instead of a permanently
        # visible right rail. Hover previews it; click pins it open.
        self.review_drawer_pinned = False
        self.review_drawer_visible = False
        self.review_drawer_width = 360
        self.review_drawer_x = self.review_drawer_width
        self.review_drawer_anim = None
        self.review_drawer_open_job = None
        self.review_drawer_close_job = None

        self.review_drawer_text = tk.StringVar(value='Human review · Start')
        self.review_drawer_button = tk.Button(
            actions,
            textvariable=self.review_drawer_text,
            command=self.toggle_review_drawer_pin,
            font=(FONT, 9, 'bold'),
            fg=TEAL,
            bg='#F3ECFB',
            activeforeground=TEAL,
            activebackground='#EADDF8',
            relief='flat',
            bd=0,
            highlightthickness=1,
            highlightbackground='#D8C8ED',
            padx=14,
            pady=9,
            cursor='hand2'
        )
        self.review_drawer_button.pack(side='right', anchor='s', pady=(18, 0))
        self.review_drawer_button.bind('<Enter>', self.schedule_review_drawer_open)
        self.review_drawer_button.bind('<Leave>', self.schedule_review_drawer_close)

        self.generate_button = self.action(actions, 'Get Gemini draft', self.generate, True)
        self.generate_button.pack(side='right', anchor='s', padx=(0, 8), pady=(18, 0))

        label(workspace, 'Drafts are grounded in the selected survey summaries and must pass human review before export.',
              9, MUTED, wraplength=820).pack(anchor='w', pady=(0, 10))

        self.report_tabbar = tk.Frame(workspace, bg=WHITE)
        self.report_tabbar.pack(fill='x')
        self.report_tab_buttons = []

        self.report_tabs = ttk.Notebook(workspace, style='Flat.TNotebook')
        self.report_tabs.pack(fill='both', expand=True)
        edit, preview = tk.Frame(self.report_tabs, bg=WHITE), tk.Frame(self.report_tabs, bg=WHITE)
        self.report_tabs.add(edit, text='Edit draft')
        self.report_tabs.add(preview, text='Reading preview')

        self.editor = self.text(edit, editable=True)
        self.editor.pack(fill='both', expand=True, padx=1, pady=1)
        self.editor.bind('<<Modified>>', self.edited)

        self.preview_meta = label(preview, 'No report available yet', 9, MUTED)
        self.preview_meta.pack(fill='x', padx=12, pady=(10, 4))

        self.preview = self.text(preview)
        self.preview.pack(fill='both', expand=True, padx=1, pady=(0, 1))
        self.report_tabs.bind('<<NotebookTabChanged>>', self.on_report_tab_changed)
        self.show(self.preview, 'Get a draft to see a formatted reading preview.')
        self.report_tabs.select(0)

        # Overlay drawer. It is placed over the report instead of resizing it.
        self.review_drawer = tk.Frame(
            p,
            bg=WHITE,
            highlightbackground='#D8C8ED',
            highlightthickness=1
        )
        self.review_drawer.bind('<Enter>', self.cancel_review_drawer_close)
        self.review_drawer.bind('<Leave>', self.schedule_review_drawer_close)

        review_inner = tk.Frame(self.review_drawer, bg=WHITE, padx=8, pady=8)
        review_inner.pack(fill='both', expand=True)
        self.build_review_panel(review_inner)

        close_button = tk.Button(
            self.review_drawer,
            text='×',
            command=self.close_review_drawer,
            font=(FONT, 15, 'normal'),
            fg=MUTED,
            bg=WHITE,
            activeforeground=INK,
            activebackground=WHITE,
            relief='flat',
            bd=0,
            highlightthickness=0,
            cursor='hand2'
        )
        close_button.place(relx=1.0, x=-8, y=7, anchor='ne')

        self.update_review_drawer_badge()

    def _cancel_review_job(self, attr):
        job = getattr(self, attr, None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
            setattr(self, attr, None)

    def _pointer_inside(self, widget):
        if not widget or not widget.winfo_exists() or not widget.winfo_ismapped():
            return False
        x, y = self.root.winfo_pointerxy()
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        return left <= x <= left + widget.winfo_width() and top <= y <= top + widget.winfo_height()

    def schedule_review_drawer_open(self, event=None):
        self._cancel_review_job('review_drawer_close_job')
        if self.review_drawer_visible:
            return
        self._cancel_review_job('review_drawer_open_job')
        self.review_drawer_open_job = self.root.after(350, self.open_review_drawer)

    def cancel_review_drawer_close(self, event=None):
        self._cancel_review_job('review_drawer_close_job')

    def schedule_review_drawer_close(self, event=None):
        self._cancel_review_job('review_drawer_open_job')
        if self.review_drawer_pinned:
            return
        self._cancel_review_job('review_drawer_close_job')
        self.review_drawer_close_job = self.root.after(450, self._close_review_drawer_if_outside)

    def _close_review_drawer_if_outside(self):
        self.review_drawer_close_job = None
        if self.review_drawer_pinned:
            return
        if self._pointer_inside(self.review_drawer_button) or self._pointer_inside(self.review_drawer):
            return
        self.hide_review_drawer()

    def toggle_review_drawer_pin(self):
        self._cancel_review_job('review_drawer_open_job')
        self._cancel_review_job('review_drawer_close_job')
        if self.review_drawer_visible and self.review_drawer_pinned:
            self.review_drawer_pinned = False
            self.hide_review_drawer()
        else:
            self.review_drawer_pinned = True
            self.open_review_drawer()

    def close_review_drawer(self):
        self.review_drawer_pinned = False
        self._cancel_review_job('review_drawer_open_job')
        self._cancel_review_job('review_drawer_close_job')
        self.hide_review_drawer()

    def open_review_drawer(self):
        self.review_drawer_open_job = None
        if self.review_drawer_visible:
            self.review_drawer.lift()
            return
        self.review_drawer_visible = True
        self.review_drawer_x = self.review_drawer_width
        self.review_drawer.place(
            relx=1.0,
            x=self.review_drawer_x,
            y=0,
            anchor='ne',
            relheight=1.0,
            width=self.review_drawer_width
        )
        self.review_drawer.lift()
        self._animate_review_drawer(opening=True)

    def hide_review_drawer(self):
        if not self.review_drawer_visible:
            return
        self._animate_review_drawer(opening=False)

    def _animate_review_drawer(self, opening):
        if self.review_drawer_anim:
            try:
                self.root.after_cancel(self.review_drawer_anim)
            except tk.TclError:
                pass
            self.review_drawer_anim = None

        target = 0 if opening else self.review_drawer_width
        step = max(28, self.review_drawer_width // 9)

        if opening:
            self.review_drawer_x = max(target, self.review_drawer_x - step)
        else:
            self.review_drawer_x = min(target, self.review_drawer_x + step)

        self.review_drawer.place_configure(x=self.review_drawer_x)
        self.review_drawer.lift()

        if self.review_drawer_x == target:
            self.review_drawer_anim = None
            if not opening:
                self.review_drawer.place_forget()
                self.review_drawer_visible = False
            return

        self.review_drawer_anim = self.root.after(
            16,
            lambda: self._animate_review_drawer(opening)
        )

    def update_review_drawer_badge(self):
        if not hasattr(self, 'review_drawer_text'):
            return

        if not self.context:
            text = 'Human review · Start'
        elif not self.theme_review.complete:
            text = f'Human review · Themes {self.theme_review.reviewed}/{self.theme_review.total}'
        elif not self.report:
            text = 'Human review · Themes ready ✓'
        elif self.workflow.status == 'AWAITING HUMAN REVIEW':
            text = 'Human review · Awaiting approval'
        elif self.workflow.status == 'CHANGES REQUESTED':
            text = 'Human review · Changes requested'
        elif self.workflow.status == 'HUMAN REVIEWED':
            text = 'Human review · Ready ✓'
        else:
            counts = self.ledger.counts()
            text = f'Human review · {counts["decided"]}/{counts["total"]} claims'

        self.review_drawer_text.set(text)

    def refresh_report_tab_bar(self):
        """Rebuild the flat Report Studio tab bar from the notebook tabs."""
        if not hasattr(self, 'report_tabbar') or not hasattr(self, 'report_tabs'):
            return

        for child in self.report_tabbar.winfo_children():
            child.destroy()

        self.report_tab_buttons = []

        for index, tab_id in enumerate(self.report_tabs.tabs()):
            caption = self.report_tabs.tab(tab_id, 'text')

            holder = tk.Frame(self.report_tabbar, bg=WHITE)
            holder.pack(side='left', padx=(0, 3))

            button = tk.Button(
                holder,
                text=caption,
                command=lambda i=index: self.select_report_tab(i),
                font=(FONT, 9, 'normal'),
                fg=MUTED,
                bg='#F5F1FA',
                activeforeground=TEAL,
                activebackground='#F5F1FA',
                relief='flat',
                bd=0,
                highlightthickness=0,
                padx=14,
                pady=9,
                cursor='hand2'
            )
            button.pack(fill='x')

            underline = tk.Frame(holder, bg='#F5F1FA', height=3)
            underline.pack(fill='x')

            self.report_tab_buttons.append((button, underline))

        self.sync_report_tabs()

    def select_report_tab(self, index):
        self.report_tabs.select(index)
        self.sync_report_tabs()

    def sync_report_tabs(self):
        if not hasattr(self, 'report_tab_buttons') or not self.report_tab_buttons:
            return
        try:
            selected = self.report_tabs.index(self.report_tabs.select())
        except tk.TclError:
            return

        for index, (button, underline) in enumerate(self.report_tab_buttons):
            active = index == selected
            button.configure(
                bg=WHITE if active else '#F5F1FA',
                activebackground=WHITE if active else '#F5F1FA',
                fg=TEAL if active else MUTED,
                font=(FONT, 9, 'bold' if active else 'normal')
            )
            underline.configure(bg=TEAL if active else '#F5F1FA')

    def on_report_tab_changed(self, event=None):
        self.sync_report_tabs()
        self.refresh_preview()

    def build_assistant(self, p):
        self.question_cache = {}
        self.question_poll = None
        box = panel(p, padx=22, pady=18)
        box.pack(fill='both', expand=True)
        label(box, 'What would you like to understand?', 17, INK, True).pack(anchor='w')
        label(box, 'Explore the selected survey metrics and themes. Each question is independent.', 9, MUTED, wraplength=780).pack(anchor='w', pady=(6, 8))
        suggestions = tk.Frame(box, bg=WHITE)
        suggestions.pack(fill='x', pady=(0, 16))
        for caption, question in [('Performance', 'How are the ratings performing?'), ('Key themes', 'What are the main feedback themes?'), ('Next steps', 'What should we improve next?'), ('Participation', 'How many responses do we have?'), ('Limitations', 'What are the risks or limitations of this data?')]:
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

        # Importing/replacing survey files belongs to Explore data.
        # Hide the repeated import/file banner on later workflow pages
        # to reduce duplication and give review/report content more room.
        if index == 0:
            if not self.toolbar.winfo_manager():
                self.toolbar.pack(
                    fill='x',
                    padx=24,
                    pady=(0, 18),
                    before=self.content_frame
                )
        else:
            self.toolbar.pack_forget()

        for i, b in enumerate(self.nav_buttons):
            b.configure(style='Selected.Nav.TButton' if i == index else 'Nav.TButton')

        if hasattr(self, 'review_drawer'):
            if index != 2:
                self.review_drawer_pinned = False
                if self.review_drawer_visible:
                    self.hide_review_drawer()
            else:
                self.update_review_drawer_badge()

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
        if self.busy:
            if not self.progress.winfo_manager():
                self.progress.pack(side='bottom', fill='x', padx=24, before=self.content_frame)
                self.progress.start(20)
        else:
            self.progress.stop()
            self.progress.configure(value=0)
            self.progress.pack_forget()
        for b in self.controls:
            b.configure(state='disabled' if self.busy else 'normal')
        self.generate_button.configure(state='normal' if self.context and not self.busy else 'disabled')
        self.insights_button.configure(state='normal' if self.context and not self.busy else 'disabled')
        self.question.configure(state='disabled' if self.busy else 'normal')
        self.audience.configure(state='disabled' if self.busy else 'readonly')
        self.editor.configure(state='normal' if self.report and not self.busy else 'disabled')
        self.sync_revision_controls()
        self.update_review_panel()

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
            c.create_rectangle(2, y+25, w-4, y+34, fill='#EFE9FA', width=0)
            if mean is not None:
                c.create_rectangle(2, y+25, 2+(w-6)*mean/5, y+34, fill=TEAL, width=0)
        c.create_text(2, h-6, anchor='sw', text='0', fill=MUTED, font=(FONT, 8))
        c.create_text(w-4, h-6, anchor='se', text='5', fill=MUTED, font=(FONT, 8))

    def edited(self, event=None):
        if self.editor.edit_modified():
            self.invalidate_revision()
            self.dirty = self.report is not None
            self.editor.edit_modified(False)
            if self.report:
                self.draft_changed()

    def review_changed(self):
        if self.confirmed.get():
            self.status.set('Checks confirmed. Approve & export records your name and role as the approver.')

    def update_evidence_check(self):
        if not self.report or not self.context:
            self.evidence_status.set('Evidence check: get a draft first.')
            return []
        from src.reporting.grounding import unsupported_claims
        unsupported = unsupported_claims(self.editor.get('1.0', 'end-1c'), self.review_context())
        if unsupported:
            kinds = ', '.join(sorted({c.kind for c in unsupported}))
            self.evidence_status.set(f'Evidence check: {len(unsupported)} figure(s) or quote(s) not found in the data ({kinds}). Cannot submit.')
        else:
            self.evidence_status.set('Evidence check: all numbers and quotes match the data.')
        return unsupported

    def refresh_preview(self):
        if self.report:
            audience = self.report.audience.title()
            scope = self.context.course_name if self.context else 'Unknown scope'
            self.preview_meta.configure(text=f'{audience} report • {scope}')
            self.render(self.preview, self.editor.get('1.0', 'end-1c'))
        else:
            self.preview_meta.configure(text='No report available yet')

    def may_replace(self):
        return not self.dirty or messagebox.askyesno('Unsaved report', 'Continue and discard the unsaved report? Use Save draft to keep a copy.', parent=self.root)

    def load(self, source, name, scope='All courses (aggregate)', file_label=None):
        from pathlib import Path
        from src.ingestion.qualtrics_loader import load_survey
        if self.busy or source is None:
            return
        if not self.may_replace():
            return
        self.busy = True
        pending_label = file_label or (self.loaded_file_label if source is self.raw else name) or name
        self.file_state.configure(text='PROCESSING FILE', fg=TEAL)
        self.file_name.configure(text=pending_label)
        self.status.set('Reading, validating and analysing data…')
        self.sync_controls()
        def work():
            if callable(source):
                raw = source()
            elif isinstance(source, (str, Path)):
                raw = load_survey(source)
            else:
                raw = source
            return raw, analyse(raw, name, scope)
        future = self.pool.submit(work)
        def finish():
            if not future.done():
                self.load_poll = self.root.after(80, finish)
                return
            self.load_poll = None
            self.busy = False
            try:
                raw, result = future.result()
            except Exception as exc:
                self.file_state.configure(text='LOADED FILE' if self.context else 'AWAITING IMPORT', fg=MUTED)
                self.file_name.configure(text=self.loaded_file_label if self.context else 'No file selected')
                self.status.set('Could not load this file. Your previous workspace is unchanged.')
                self.sync_controls()
                messagebox.showerror('Cannot analyse file', str(exc), parent=self.root)
                return
            self.raw, self.source = raw, name
            self.loaded_file_label = pending_label
            self.file_state.configure(text='LOADED FILE', fg=TEAL)
            self.file_name.configure(text=pending_label)
            self.apply_analysis(result)
            self.status.set(f'Ready • {len(self.frame):,} responses analysed')
            self.sync_controls()
        self.load_poll = self.root.after(80, finish)

    def apply_analysis(self, result):
        self.frame, self.context, count, courses = result
        self.show_local_insights()
        self.report, self.dirty = None, False
        self.reset_revisions()
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.confirmed.set(False)
        self.report_status.set('No draft yet')
        self.ledger.reset()
        self.workflow = type(self.workflow)()
        self.preview_meta.configure(text='No report available yet')
        self.show(self.preview, 'Get a draft to see a formatted reading preview.')
        self.show(self.answer, 'Ask about this dataset or choose a suggestion above.')
        self.question.configure(state='normal')
        self.question.delete(0, 'end')
        self.sort_column = None
        self.sort_reverse = False
        self.search.set('')
        self.update_data_filters()
        self.filter_rows()
        m = self.context.metrics
        mean, rec = m['ratings']['OverallSatisfaction']['mean'], m['recommendation_percent']
        values = [f"{m['response_count']:,}", f'{mean:.2f}' if mean is not None else 'N/A', f'{rec:.0f}%' if rec is not None else 'N/A', f"{m['response_completeness']:.1f}%"]
        for widget, value in zip(self.metric_values, values):
            widget.configure(text=value, font=(FONT, 28, 'bold'), fg=TEAL if widget is self.metric_values[1] else INK)
        self.dataset_label.configure(text=f'{self.source}  /  {self.context.course_name}')
        strongest = m['ratings'].get(m['strongest_area'], {}).get('label', 'Insufficient rating data')
        improvement = next((t.name for t in self.context.themes if t.category == 'Improvement'), 'No recurring improvement theme')
        self.render(self.highlights, f'## Strongest rated area\n{strongest}\n## Opportunity to explore\n{improvement}\n## Feedback coverage\n{len(self.context.themes)} recurring themes identified')
        warnings = self.context.warnings
        summary = f'{len(warnings)} quality warning(s)' if warnings else 'Required columns validated'
        self.quality_label.configure(text=f'{summary}  •  {count} patterns masked in source file\nBasic masking still requires human inspection.', fg='#92600D' if warnings else TEAL)
        self.show(
            self.validation_text,
            ('\n'.join(warnings) if warnings else 'No validation warnings.')
            + f'\n\n{count} patterns masked. Preview capped at 1,000 rows; all selected rows are analysed.'
        )
        self.theme_table.delete(*self.theme_table.get_children())
        for i, theme in enumerate(self.context.themes):
            self.theme_table.insert('', 'end', iid=str(i), values=(theme.name, theme.frequency, 'Pending'))
        self.reset_theme_review()
        self.refresh_claims()
        self.record('Data imported', '', source=self.source, responses=m['response_count'], themes=len(self.context.themes))
        self.update_audit_status()
        if self.context.themes:
            self.theme_table.selection_set('0')
            self.inspect_theme()
        else:
            self.show(self.theme_detail, 'No recurring themes met the evidence threshold.')
        self.draw_chart()

    def update_data_filters(self):
        """Refresh Survey data filter choices from the loaded dataset."""
        if self.frame is None:
            return

        frame = self.frame.fillna('').astype(str)

        sources = ['All files']
        if 'SourceFile' in frame.columns:
            sources += sorted(
                value for value in frame['SourceFile'].str.strip().unique()
                if value
            )
        self.source_filter.configure(values=sources)
        self.source_filter.set('All files')

        courses = ['All courses']
        if 'CourseName' in frame.columns:
            courses += sorted(
                value for value in frame['CourseName'].str.strip().unique()
                if value
            )
        self.course_filter.configure(values=courses)
        self.course_filter.set('All courses')

        months = ['All dates']
        if 'RecordedDate' in frame.columns:
            import pandas as pd
            parsed = pd.to_datetime(frame['RecordedDate'], errors='coerce')
            months += sorted(
                value for value in parsed.dt.strftime('%Y-%m').dropna().unique()
                if value
            )
        self.month_filter.configure(values=months)
        self.month_filter.set('All dates')

        ratings = ['All ratings']
        if 'OverallSatisfaction' in frame.columns:
            import pandas as pd
            numeric = pd.to_numeric(frame['OverallSatisfaction'], errors='coerce').dropna()
            ratings += [
                f'{value:g}'
                for value in sorted(numeric.unique(), reverse=True)
            ]
        self.rating_filter.configure(values=ratings)
        self.rating_filter.set('All ratings')

        recommendations = ['All recommendations']
        if 'WouldRecommend' in frame.columns:
            values = sorted(
                value for value in frame['WouldRecommend'].str.strip().unique()
                if value
            )
            recommendations += values
        self.recommend_filter.configure(values=recommendations)
        self.recommend_filter.set('All recommendations')

    def reset_data_view(self):
        """Restore Survey data to its default search, filter and sort state."""
        self.search.set('')
        self.source_filter.set('All files')
        self.course_filter.set('All courses')
        self.month_filter.set('All dates')
        self.rating_filter.set('All ratings')
        self.recommend_filter.set('All recommendations')
        self.sort_column = None
        self.sort_reverse = False
        self.filter_rows()

    def queue_search(self, *args):
        if self.search_id:
            self.root.after_cancel(self.search_id)
        self.search_id = self.root.after(180, self.filter_rows)

    def sort_rows(self, column):
        """Sort the currently visible survey results by a table column."""
        non_sortable = {'No.', 'MostValuableAspect', 'WhatCouldImprove', 'AdditionalComments'}
        if column in non_sortable:
            return

        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        self.filter_rows()

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

        source_file = self.source_filter.get() if hasattr(self, 'source_filter') else 'All files'
        if source_file != 'All files' and 'SourceFile' in frame.columns:
            frame = frame[frame['SourceFile'].str.strip() == source_file]

        course = self.course_filter.get() if hasattr(self, 'course_filter') else 'All courses'
        if course != 'All courses' and 'CourseName' in frame.columns:
            frame = frame[frame['CourseName'].str.strip() == course]

        month = self.month_filter.get() if hasattr(self, 'month_filter') else 'All dates'
        if month != 'All dates' and 'RecordedDate' in frame.columns:
            import pandas as pd
            recorded_month = pd.to_datetime(frame['RecordedDate'], errors='coerce').dt.strftime('%Y-%m')
            frame = frame[recorded_month == month]

        rating = self.rating_filter.get() if hasattr(self, 'rating_filter') else 'All ratings'
        if rating != 'All ratings' and 'OverallSatisfaction' in frame.columns:
            import pandas as pd
            numeric_rating = pd.to_numeric(frame['OverallSatisfaction'], errors='coerce')
            frame = frame[numeric_rating == float(rating)]

        recommendation = self.recommend_filter.get() if hasattr(self, 'recommend_filter') else 'All recommendations'
        if recommendation != 'All recommendations' and 'WouldRecommend' in frame.columns:
            frame = frame[
                frame['WouldRecommend'].str.strip().str.casefold()
                == recommendation.casefold()
            ]

        # Sort only the filtered display results. The source DataFrame is never changed.
        if self.sort_column and self.sort_column in frame.columns:
            import pandas as pd

            numeric_columns = {
                'OverallSatisfaction',
                'ContentQuality',
                'FacilitatorEffectiveness',
                'CourseRelevance',
            }

            if self.sort_column in numeric_columns:
                sort_key = pd.to_numeric(frame[self.sort_column], errors='coerce')
            elif self.sort_column == 'RecordedDate':
                sort_key = pd.to_datetime(frame[self.sort_column], errors='coerce')
            else:
                sort_key = frame[self.sort_column].astype(str).str.casefold()

            frame = (
                frame.assign(__sort_key=sort_key)
                .sort_values(
                    '__sort_key',
                    ascending=not self.sort_reverse,
                    na_position='last',
                    kind='mergesort'
                )
                .drop(columns='__sort_key')
            )

        # Keep the source data unchanged and only simplify values for table display.
        display_frame = frame.copy()
        if 'RecordedDate' in display_frame.columns:
            display_frame['RecordedDate'] = display_frame['RecordedDate'].str.slice(0, 10)

        data_columns = list(display_frame.columns)
        if 'SourceFile' in data_columns:
            data_columns.remove('SourceFile')
            display_columns = ['No.', 'SourceFile'] + data_columns
        else:
            display_columns = ['No.'] + data_columns

        centered_columns = {
            'No.',
            'ResponseID',
            'RecordedDate',
            'CourseCode',
            'DeliveryMode',
            'ClientType',
            'FacilitatorCode',
            'OverallSatisfaction',
            'ContentQuality',
            'FacilitatorEffectiveness',
            'CourseRelevance',
            'WouldRecommend',
        }

        column_widths = {
            'No.': 55,
            'SourceFile': 220,
            'ResponseID': 95,
            'RecordedDate': 120,
            'CourseCode': 90,
            'CourseName': 220,
            'DeliveryMode': 110,
            'ClientType': 110,
            'FacilitatorCode': 110,
            'OverallSatisfaction': 145,
            'ContentQuality': 130,
            'FacilitatorEffectiveness': 160,
            'CourseRelevance': 130,
            'WouldRecommend': 120,
            'MostValuableAspect': 240,
            'WhatCouldImprove': 240,
            'AdditionalComments': 260,
        }

        self.table.delete(*self.table.get_children())
        self.table['columns'] = display_columns

        non_sortable = {'No.', 'MostValuableAspect', 'WhatCouldImprove', 'AdditionalComments'}

        for col in display_columns:
            anchor = 'center' if col in centered_columns else 'w'
            width = column_widths.get(col, 140)

            heading_text = col
            if col == self.sort_column:
                heading_text += ' ▼' if self.sort_reverse else ' ▲'

            if col in non_sortable:
                self.table.heading(col, text=heading_text, anchor=anchor)
            else:
                self.table.heading(
                    col,
                    text=heading_text,
                    anchor=anchor,
                    command=lambda c=col: self.sort_rows(c)
                )

            self.table.column(
                col,
                width=width,
                minwidth=width,
                stretch=False,
                anchor=anchor
            )

        for i, (_, row) in enumerate(
            display_frame.head(1000).iterrows(),
            start=1
        ):
            values = tuple(row[col] for col in display_columns if col != 'No.')
            self.table.insert(
                '',
                'end',
                values=(i,) + values,
                tags=('alternate',) if i % 2 == 0 else ()
            )

        self.row_label.configure(text=f'{min(1000, len(frame)):,} shown / {len(frame):,} matching')
        self.show(
            self.row_detail,
            'Select a response to inspect its full contents.'
            if len(frame)
            else 'No matching responses. Clear the search to see all data.'
        )

    def inspect_row(self, event=None):
        selected = self.table.selection()
        if selected:
            values = list(self.table.item(selected[0], 'values'))
            columns = list(self.table['columns'])

            # "No." is only a display index and is not part of the survey source data.
            if columns and columns[0] == 'No.':
                columns = columns[1:]
                values = values[1:]

            self.show(
                self.row_detail,
                '\n'.join(
                    f'{col}: {value}'
                    for col, value in zip(columns, values)
                )
            )

    def inspect_theme(self, event=None):
        theme = self.selected_theme()
        if theme:
            decision = self.theme_review.decisions.get(theme.name)
            self.theme_category.set(decision.category if decision else theme.category)
            self.render(self.theme_detail, self.theme_detail_text(theme))

    def audience_changed(self, event=None):
        if self.report and self.audience.get() != self.report.audience:
            self.status.set(f'Current draft is for {self.report.audience}. Get a new draft to change audience.')

    def generate(self):
        from src.reporting.report_generator import generate_report
        if not self.context or self.busy:
            return
        if not self.theme_review.complete:
            tr = self.theme_review
            messagebox.showinfo('Review themes first',
                f'Confirm or reject every theme before drafting ({tr.reviewed} of {tr.total} done). '
                'Only themes a person has confirmed are used in the report.', parent=self.root)
            self.navigate(1)
            return
        if self.report and not self.may_replace():
            return
        self.busy = True
        self.status.set('Preparing report draft…')
        self.sync_controls()
        context, audience = self.review_context(), self.audience.get()

        def work():
            from src.ai.gemini_provider import GeminiAIProvider
            from src.ai.local_provider import LocalAnalysisProvider
            try:
                provider = GeminiAIProvider()
            except ValueError:
                # Gemini is not set up on this computer: draft locally and say so.
                return generate_report(context, audience, LocalAnalysisProvider()), 'not configured'
            return generate_report(context, audience, provider), None

        future = self.pool.submit(work)

        def finish():
            if not future.done():
                self.generate_poll = self.root.after(80, finish)
                return
            self.generate_poll = None
            self.busy = False
            try:
                report, fallback = future.result()
            except Exception as exc:
                self.status.set('Gemini could not prepare a draft.')
                self.sync_controls()
                if messagebox.askyesno('Gemini draft unavailable',
                        f'{service_message(exc)}\n\nCreate a local draft from the calculated results instead? '
                        'It uses fixed wording rather than AI interpretation.', parent=self.root):
                    from src.ai.local_provider import LocalAnalysisProvider
                    self._apply_generated_report(generate_report(context, audience, LocalAnalysisProvider()))
                    self.status.set('Local draft ready (Gemini was unavailable). Review every claim before submitting.')
                return
            self._apply_generated_report(report)
            if fallback:
                self.status.set('Gemini is not set up on this computer, so this draft uses local fixed wording. '
                                'Review every claim before submitting.')
        self.generate_poll = self.root.after(80, finish)

    def _apply_generated_report(self, report):
        self.report = report
        self.reset_revisions()
        self.editor.configure(state='normal')
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', self.report.content)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.dirty = True
        self.confirmed.set(False)
        self.ledger.reset()
        self.workflow = type(self.workflow)()
        self.themes_changed_since_draft = False
        self.update_evidence_check()
        self.refresh_preview()
        self.refresh_claims()
        self.record('Draft generated', self.author_entry.get().strip(), audience=report.audience, written_by=report.source_mode,
                    claims=len(self.ledger.claims))
        self.update_audit_status()
        self.report_tabs.select(0)
        self.editor.focus_set()
        self.status.set(f'Draft ready ({report.source_mode}). Next: decide every claim in the Review claims tab, '
                        'then submit for approval.')
        self.sync_controls()

    def export(self, reviewed=True):
        from pathlib import Path
        from src.reporting.exporter import docx_bytes, markdown_bytes
        from src.reporting.report_generator import approve_report
        from src.review.record import build_review_record, content_hash
        if not self.report or self.busy:
            return False
        if reviewed:
            problems = self.approval_problems()
            if problems:
                messagebox.showinfo('Cannot approve yet', '\n'.join('• ' + p for p in problems), parent=self.root)
                return False
        content = self.editor.get('1.0', 'end-1c').strip()
        if not content:
            messagebox.showerror('Empty report', 'Add report content before exporting.', parent=self.root)
            return False
        path = filedialog.asksaveasfilename(parent=self.root, initialdir=os.getenv('DEMO_SHARED_DIR', str(Path.cwd())), title='Export reviewed report' if reviewed else 'Save draft report',
            initialfile=f'learning_evaluation_{self.report.audience}_{"reviewed" if reviewed else "draft"}.docx',
            defaultextension='.docx', filetypes=[('Word document', '*.docx'), ('Markdown', '*.md')])
        if not path:
            return False
        if Path(path).suffix.lower() not in ('.docx', '.md'):
            messagebox.showerror('Unsupported format', 'Choose a .docx or .md filename.', parent=self.root)
            return False
        if reviewed:
            approver, role = self.approver_entry.get().strip(), self.approver_role.get()
            approved_text = approve_report(self.report, content).content
            # Approval must be on record before the file exists.
            event = self.record('Approved', approver, role=role, audience=self.report.audience,
                                author=self.workflow.reviewer, report_sha256=content_hash(approved_text))
            if event is None:
                messagebox.showerror('Audit log unavailable',
                    f'The review audit log could not be written ({self.audit.path}). Approval is blocked so that '
                    'every approval stays on record.', parent=self.root)
                return False
            self.workflow.approve(approver, role=role, audience=self.report.audience)
            summary = self.review_summary()
            chain = self.audit.verify()
            final = approved_text + '\n\n' + build_review_record(
                workflow=self.workflow, theme_counts=summary['themes'], claim_counts=summary['claims'],
                pace=summary['pace'], ai_retained=summary['ai_retained'], source_mode=self.report.source_mode,
                report_hash=content_hash(approved_text), approval_hash=event['hash'], audit_entries=chain['entries'])
        else:
            final = '**DRAFT — REQUIRES HUMAN REVIEW**\n\n' + content
        data = docx_bytes(final, os.getenv('UNIVERSITY_LOGO_PATH')) if Path(path).suffix.lower() == '.docx' else markdown_bytes(final)
        try:
            Path(path).write_bytes(data)
        except Exception as exc:
            if reviewed:
                self.workflow.status = 'AWAITING HUMAN REVIEW'
                self.record('Export failed', self.approver_entry.get().strip(), error=type(exc).__name__)
                self.update_review_panel()
            messagebox.showerror('Export failed', str(exc), parent=self.root)
            return False
        import hashlib
        self.record('Exported' if reviewed else 'Draft saved', self.approver_entry.get().strip() if reviewed else self.author_entry.get().strip(),
                    file=Path(path).name, file_sha256=hashlib.sha256(data).hexdigest())
        self.update_audit_status()
        self.dirty = False
        self.update_review_panel()
        self.status.set(f'{"Approved report" if reviewed else "Draft"} saved • {path}')
        return True

    def close(self):
        if not self.may_replace():
            return
        for pending in (self.claims_refresh_id, getattr(self, 'load_poll', None), getattr(self, 'startup_id', None), getattr(self, 'generate_poll', None), self.insights_poll, self.question_poll, self.search_id, self.revision_poll):
            if pending:
                self.root.after_cancel(pending)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main():
    from src.ui.runtime import main as start
    return start()
