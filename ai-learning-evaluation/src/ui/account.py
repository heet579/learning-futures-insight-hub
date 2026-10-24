"""Account menu and workspace lifecycle, independent of report persistence."""
import tkinter as tk
from tkinter import messagebox, ttk

from src.ui.theme import BG, WHITE, INK, MUTED, TEAL, BORDER


class AccountUI:
    def schedule(self, delay, callback):
        """Keep every workspace callback cancellable when the session ends."""
        def run():
            self.session_jobs.discard(job)
            if not self.disposed:
                callback()
        job = self.root.after(delay, run)
        self.session_jobs.add(job)
        return job

    def schedule_idle(self, callback):
        def run():
            self.session_jobs.discard(job)
            if not self.disposed:
                callback()
        job = self.root.after_idle(run)
        self.session_jobs.add(job)
        return job

    def build_account_menu(self, parent):
        self.account_trigger = tk.Frame(parent, bg=BG)
        self.account_trigger.pack(side='right', anchor='ne', padx=(16, 0))
        avatar = tk.Canvas(self.account_trigger, width=36, height=36, bg=BG,
                           highlightthickness=0, cursor='hand2')
        avatar.pack(side='left', padx=(0, 6))
        avatar.create_oval(2, 2, 34, 34, fill=TEAL, outline=TEAL)
        avatar.create_text(18, 18, text=(self.username[:1] or '?').upper(), fill=WHITE,
                           font=(self.font_family, 12, 'bold'))
        avatar.bind('<Button-1>', self.toggle_account_menu)
        display_name = self.username if len(self.username) <= 22 else self.username[:21] + '…'
        self.account_button = ttk.Button(self.account_trigger,
            text=f'{display_name or "Workspace"}  ▾', command=self.toggle_account_menu)
        self.account_button.pack(side='left', pady=3)
        self.account_menu = tk.Frame(self.root, bg=WHITE, padx=14, pady=12,
                                     highlightbackground=BORDER, highlightthickness=1)
        tk.Label(self.account_menu, text='SIGNED IN AS', bg=WHITE, fg=MUTED,
                 font=(self.font_family, 8, 'bold')).pack(anchor='w')
        tk.Label(self.account_menu, text=self.username or 'No signed-in account', bg=WHITE,
                 fg=INK, wraplength=240, justify='left',
                 font=(self.font_family, 11, 'bold')).pack(anchor='w', pady=(4, 12))
        self.account_actions = []
        from src import remote
        if remote.server_url() and remote.session.username == self.username:
            # Shared-server accounts: self-service profile, and account management for admins.
            items = [('Profile settings', self.open_profile)]
            if remote.session.role == 'admin':
                items.append(('Manage accounts', self.open_accounts))
            for caption, command in items:
                button = ttk.Button(self.account_menu, text=caption, command=command)
                button.pack(fill='x', pady=3)
                self.account_actions.append(button)
            ttk.Separator(self.account_menu).pack(fill='x', pady=6)
        for caption, switching in [('Switch account', True), ('Sign out', False)]:
            button = ttk.Button(self.account_menu, text=caption,
                                command=lambda switch=switching: self.sign_out(switch))
            button.pack(fill='x', pady=3)
            self.account_actions.append(button)
        self.account_bindings = {
            '<Button-1>': self.root.bind('<Button-1>', self.dismiss_account_menu, add='+'),
            '<Escape>': self.root.bind('<Escape>', self.hide_account_menu, add='+'),
        }

    def toggle_account_menu(self, event=None):
        if self.disposed:
            return
        if self.account_menu.winfo_manager():
            self.hide_account_menu()
            return
        state = 'disabled' if self.busy or self.on_logout is None else 'normal'
        for button in self.account_actions:
            button.configure(state=state)
        self.root.update_idletasks()
        right = self.account_trigger.winfo_rootx() + self.account_trigger.winfo_width() - self.root.winfo_rootx()
        bottom = self.account_trigger.winfo_rooty() + self.account_trigger.winfo_height() - self.root.winfo_rooty()
        self.account_menu.place(x=right, y=bottom + 6, anchor='ne')
        self.account_menu.lift()
        self.account_actions[0].focus_set()

    def hide_account_menu(self, event=None):
        self.account_menu.place_forget()

    def dismiss_account_menu(self, event):
        widget = event.widget
        while widget is not None:
            if widget in (self.account_trigger, self.account_menu):
                return
            widget = getattr(widget, 'master', None)
        self.hide_account_menu()

    def open_profile(self):
        self.hide_account_menu()
        from src.ui.accounts import ProfileDialog
        return ProfileDialog(self.root)

    def open_accounts(self):
        self.hide_account_menu()
        from src.ui.accounts import AccountsDialog
        return AccountsDialog(self.root)

    def sign_out(self, switching=False):
        if self.disposed or self.busy or self.on_logout is None:
            return False
        self.hide_account_menu()
        action = 'Switch account' if switching else 'Sign out'
        if (self.report or self.context is not None) and self.library_unsaved():
            choice = messagebox.askyesnocancel(action,
                'Save your draft before leaving?\n\n'
                'Yes: save to Report library, then return to sign-in.\n'
                'No: discard unsaved work and return to sign-in.\n'
                'Cancel: stay in this workspace.\n\n'
                'Saved drafts can be reopened by your account from Report library.',
                parent=self.root, default='cancel')
            if choice is None or (choice and not self.save_library_draft()):
                return False
        elif self.context is not None and not self.library_id:
            if not messagebox.askyesno(action,
                'Return to sign-in and clear this workspace?\n\n'
                'This workspace has not been saved to Report library. '
                'Any documents already exported will remain on disk.',
                parent=self.root, default='no'):
                return False
        callback = self.on_logout
        from src.remote import logout
        logout()
        self.dispose_workspace()
        callback()
        return True

    def dispose_workspace(self):
        if self.disposed:
            return
        self.disposed = True
        self.progress.stop()
        for job in self.session_jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.session_jobs.clear()
        for sequence, binding in self.library_bindings.items():
            self.root.unbind(sequence, binding)
        for sequence, binding in self.account_bindings.items():
            self.root.unbind(sequence, binding)
        self.root.unbind('<Control-o>')
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.root.unbind_all(sequence)
        self.pool.shutdown(wait=False, cancel_futures=True)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.username = ''
        self.context = self.raw = self.report = self.frame = None
        self.insights_cache.clear()
        self.question_cache.clear()
        self.pending_revision = None
        self.revision_history.clear()
        self.init_review_state()
        self.on_logout = None
