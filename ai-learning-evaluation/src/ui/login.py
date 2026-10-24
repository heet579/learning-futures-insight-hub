"""Sign-in screen displayed before any workspace controls are constructed."""
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk

from src.auth import AccountFileError, authenticate
from src.ui.theme import BG, WHITE, INK, MUTED, NAVY, TEAL, BORDER


class LoginScreen:
    def __init__(self, root, on_success, account_path=None):
        self.root, self.on_success, self.account_path = root, on_success, account_path
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.future = self.poll_id = None
        self.closed = False
        root.title('Learning Futures | Sign in')
        root.configure(bg=BG)
        from src.remote import server_url
        self.shared = bool(server_url())
        width, height = min(680, root.winfo_screenwidth()), min(720 if self.shared else 610, root.winfo_screenheight())
        root.geometry(f'{width}x{height}+{max(0, (root.winfo_screenwidth()-width)//2)}+{max(0, (root.winfo_screenheight()-height)//2)}')
        root.minsize(min(440, width), min(520, height))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.frame = tk.Frame(root, bg=BG)
        self.frame.pack(fill='both', expand=True)
        tk.Label(self.frame, text='LF / INSIGHT HUB', font=('TkDefaultFont', 16, 'bold'), bg=BG, fg=NAVY).pack(pady=(36, 6))
        tk.Label(self.frame, text='LEARNING FUTURES', font=('TkDefaultFont', 9), bg=BG, fg=MUTED).pack()
        card = tk.Frame(self.frame, bg=WHITE, padx=30, pady=28, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill='x', padx=45, pady=25)
        tk.Label(card, text='Welcome back', font=('TkDefaultFont', 23, 'bold'), bg=WHITE, fg=INK).pack(anchor='w')
        tk.Label(card, text='Sign in to your evaluation workspace.', font=('TkDefaultFont', 10), bg=WHITE, fg=MUTED).pack(anchor='w', pady=(6, 22))
        self.username, self.password = tk.StringVar(root), tk.StringVar(root)
        self.entries = []
        for caption, variable, masked in [('Username', self.username, False), ('Password', self.password, True)]:
            tk.Label(card, text=caption, font=('TkDefaultFont', 10, 'bold'), bg=WHITE, fg=INK).pack(anchor='w', pady=(0, 6))
            entry = tk.Entry(card, textvariable=variable, show='•' if masked else '', font=('TkDefaultFont', 12),
                             bg=BG, fg=INK, insertbackground=TEAL, relief='flat', highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=TEAL)
            entry.pack(fill='x', ipady=9, pady=(0, 16))
            entry.bind('<Return>', lambda event: self.submit())
            self.entries.append(entry)
        self.button = tk.Button(card, text='Sign in', command=self.submit, font=('TkDefaultFont', 11, 'bold'),
                                bg=TEAL, fg=WHITE, activebackground='#6B2FD4', activeforeground=WHITE,
                                relief='flat', borderwidth=0, cursor='hand2', pady=10)
        self.button.pack(fill='x')
        self.google_button = None
        if self.shared:
            # Shared-server mode: Google sign-in and self-service account requests.
            tk.Label(card, text='or', font=('TkDefaultFont', 9), bg=WHITE, fg=MUTED).pack(pady=(8, 4))
            self.google_button = tk.Button(card, text='G   Continue with Google', command=self.google,
                font=('TkDefaultFont', 11, 'bold'), bg=WHITE, fg=INK, activebackground=BG, activeforeground=INK,
                relief='solid', borderwidth=1, cursor='hand2', pady=8)
            self.google_button.pack(fill='x')
        self.progress = ttk.Progressbar(card, mode='indeterminate')
        self.status = tk.StringVar(root, value='')
        tk.Label(card, textvariable=self.status, font=('TkDefaultFont', 10), bg=WHITE, fg='#9F254B',
                 wraplength=420, justify='left', anchor='w').pack(fill='x', pady=(12, 0))
        if self.shared:
            footer = tk.Frame(self.frame, bg=BG)
            footer.pack()
            tk.Label(footer, text='New to Insight Hub?', font=('TkDefaultFont', 10), bg=BG, fg=MUTED).pack(side='left')
            self.register_link = tk.Label(footer, text='Create account', font=('TkDefaultFont', 10, 'underline'),
                                          bg=BG, fg=TEAL, cursor='hand2')
            self.register_link.pack(side='left', padx=(6, 0))
            self.register_link.bind('<Button-1>', lambda event: self.create_account())
        else:
            tk.Label(self.frame, text='For account access, contact your administrator.', font=('TkDefaultFont', 10), bg=BG, fg=MUTED).pack()
        self.entries[0].focus_set()

    def submit(self):
        if self.closed or self.future is not None:
            return
        if not self.username.get().strip() or not self.password.get():
            self.status.set('Enter your username and password.')
            return
        from src.remote import server_url
        self.status.set('Connecting to the Insight Hub server… the first sign-in of the day can take up to a minute.'
                        if server_url() else 'Signing in…')
        self.button.configure(state='disabled')
        for entry in self.entries:
            entry.configure(state='disabled')
        self.progress.pack(fill='x', pady=(8, 0), before=self.button)
        self.progress.start(12)
        self.future = self.pool.submit(authenticate, self.username.get(), self.password.get(), self.account_path)
        self.poll_id = self.root.after(40, self._poll)

    def _poll(self):
        self.poll_id = None
        if not self.future.done():
            self.poll_id = self.root.after(40, self._poll)
            return
        try:
            username = self.future.result()
            error = 'Username or password is incorrect.' if username is None else ''
        except AccountFileError as exc:
            username, error = None, str(exc)
        except Exception:
            username, error = None, 'Unable to sign in. Please try again.'
        self.future = None
        self.password.set('')
        self.progress.stop()
        self.progress.pack_forget()
        if username is not None:
            self.dispose()
            self.on_success(username)
            return
        self.status.set(error)
        self.button.configure(state='normal')
        for entry in self.entries:
            entry.configure(state='normal')
        self.entries[1].focus_set()

    def set_busy(self, busy):
        state = 'disabled' if busy else 'normal'
        for widget in [self.button, *self.entries] + ([self.google_button] if self.google_button else []):
            widget.configure(state=state)
        if busy:
            self.progress.pack(fill='x', pady=(8, 0), before=self.button)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def create_account(self):
        if self.closed or self.future is not None:
            return None
        from src.ui.accounts import RegisterDialog
        return RegisterDialog(self.root)

    def google(self):
        if self.closed or self.future is not None:
            return
        from src import remote
        self.status.set('Finish signing in to Google in your browser…')
        self.set_busy(True)
        self.future = self.pool.submit(lambda: remote.google_login(remote.google_id_token()))
        self.poll_id = self.root.after(60, self._poll_google)

    def _poll_google(self):
        self.poll_id = None
        if not self.future.done():
            self.poll_id = self.root.after(60, self._poll_google)
            return
        from src.ui.accounts import error_text
        try:
            outcome, value = self.future.result()
        except Exception as exc:
            outcome, value = 'error', error_text(exc)
        self.future = None
        self.set_busy(False)
        if outcome == 'signed_in':
            self.dispose()
            self.on_success(value)
            return
        self.status.set(value)

    def dispose(self):
        if self.closed:
            return
        self.closed = True
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        self.progress.stop()
        self.password.set('')
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.frame.destroy()

    def close(self):
        self.dispose()
        self.root.destroy()
