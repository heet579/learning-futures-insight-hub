"""Self-service account windows for shared-server mode: create account, profile, admin accounts.

Every server call runs off the Tk thread so a sleeping server never freezes the window.
"""
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from src import remote
from src.google_signin import GoogleSignInError
from src.ui.theme import BG, WHITE, INK, MUTED, TEAL, BORDER
from src.roles import ROLES, can_manage_users

ERROR = '#9F254B'
FONT = 'TkDefaultFont'


def run_in_background(widget, work, done):
    """Run work() on a thread, then done(result, error) back on the Tk thread."""
    box = {}

    def target():
        try:
            box['result'] = work()
        except Exception as exc:          # shown to the user by `done`
            box['error'] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    def poll():
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if thread.is_alive():
            widget.after(60, poll)
        else:
            done(box.get('result'), box.get('error'))
    widget.after(60, poll)
    return thread


def error_text(exc):
    if isinstance(exc, (GoogleSignInError, remote.ServerError, remote.ServerUnavailable, ValueError)):
        return str(exc)
    import traceback
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return 'Something went wrong. Please try again.'


class Dialog:
    """A small modal window with a white card, labelled fields and a status line."""

    def __init__(self, parent, title, heading, subheading='', wrap=380):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.configure(bg=BG)
        self.window.transient(parent.winfo_toplevel())
        self.window.resizable(False, False)
        self.card = tk.Frame(self.window, bg=WHITE, padx=26, pady=22, highlightbackground=BORDER, highlightthickness=1)
        self.card.pack(fill='both', expand=True, padx=18, pady=18)
        tk.Label(self.card, text=heading, font=(FONT, 17, 'bold'), bg=WHITE, fg=INK).pack(anchor='w')
        if subheading:
            tk.Label(self.card, text=subheading, font=(FONT, 10), bg=WHITE, fg=MUTED, wraplength=wrap,
                     justify='left').pack(anchor='w', pady=(4, 12))
        self.fields = {}
        self.status = tk.StringVar(self.window, value='')
        self.busy = False
        self.window.protocol('WM_DELETE_WINDOW', self.close)

    def section(self, text):
        tk.Label(self.card, text=text.upper(), font=(FONT, 8, 'bold'), bg=WHITE, fg=MUTED).pack(anchor='w', pady=(14, 4))

    def field(self, key, caption, value='', masked=False, readonly=False):
        tk.Label(self.card, text=caption, font=(FONT, 10, 'bold'), bg=WHITE, fg=INK).pack(anchor='w', pady=(0, 4))
        variable = tk.StringVar(self.window, value=value)
        entry = tk.Entry(self.card, textvariable=variable, show='•' if masked else '', font=(FONT, 11), width=36,
                         bg=BG, fg=INK, insertbackground=TEAL, relief='flat', highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=TEAL, readonlybackground=WHITE,
                         state='readonly' if readonly else 'normal')
        entry.pack(fill='x', ipady=6, pady=(0, 10))
        self.fields[key] = variable
        return entry

    def button(self, parent, text, command, primary=True):
        return tk.Button(parent, text=text, command=command, font=(FONT, 10, 'bold'),
                         bg=TEAL if primary else WHITE, fg=WHITE if primary else TEAL,
                         activebackground='#6B2FD4' if primary else BG, activeforeground=WHITE if primary else TEAL,
                         relief='flat' if primary else 'solid', borderwidth=0 if primary else 1,
                         cursor='hand2', padx=14, pady=7)

    def status_line(self):
        self.status_label = tk.Label(self.card, textvariable=self.status, font=(FONT, 10), bg=WHITE, fg=ERROR,
                                     wraplength=380, justify='left', anchor='w')
        self.status_label.pack(fill='x', pady=(8, 0))

    def value(self, key):
        return self.fields[key].get()

    def say(self, text, ok=False):
        self.status_label.configure(fg=TEAL if ok else ERROR)
        self.status.set(text)

    def call(self, work, done, waiting='Working…'):
        if self.busy:
            return
        self.busy = True
        self.busy_changed()
        self.say(waiting, ok=True)

        def finish(result, error):
            self.busy = False
            self.busy_changed()
            if error is not None:
                self.say(error_text(error))
            else:
                done(result)
        run_in_background(self.window, work, finish)

    def busy_changed(self):
        """Allow account controls to reflect requests that are still running."""
        pass

    def close(self):
        self.window.destroy()
        # Release Tcl variables while still on the UI thread. Closed editor cycles
        # may otherwise be collected later by a background HTTP worker.
        self.fields.clear()
        self.status = None


# ---- create account ----------------------------------------------------------------------
class RegisterDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, 'Create account', 'Create account',
                         'A superadmin approves new accounts before they can sign in.')
        self.field('display_name', 'Full name')
        self.field('username', 'Username')
        self.field('email', 'Email (Gmail)')
        self.field('password', 'Password', masked=True)
        self.field('confirm', 'Confirm password', masked=True)
        row = tk.Frame(self.card, bg=WHITE)
        row.pack(fill='x', pady=(6, 0))
        self.submit_button = self.button(row, 'Request account', self.submit)
        self.submit_button.pack(side='left')
        self.button(row, 'Cancel', self.close, primary=False).pack(side='left', padx=(8, 0))
        self.status_line()

    def submit(self):
        name, username, email = self.value('display_name').strip(), self.value('username').strip(), self.value('email').strip()
        password = self.value('password')
        if not (name and username and email and password):
            return self.say('Fill in every field.')
        if password != self.value('confirm'):
            return self.say('The passwords do not match.')
        if len(password) < 8:
            return self.say('Use a password of at least 8 characters.')

        def done(result):
            self.submit_button.configure(state='disabled')
            self.say(f'Request sent for “{result["username"]}”. You can sign in after a superadmin approves it.', ok=True)
        self.call(lambda: remote.register(username=username, password=password, email=email, display_name=name),
                  done, 'Sending request…')


# ---- profile -----------------------------------------------------------------------------
class ProfileDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, 'Profile settings', 'Profile settings')
        self.profile = None
        self.loading = tk.Label(self.card, text='Loading…', font=(FONT, 10), bg=WHITE, fg=MUTED)
        self.loading.pack(anchor='w')
        self.status_line()
        self.call(remote.me, self.build, 'Loading your profile…')

    def build(self, profile):
        self.profile = profile
        self.loading.destroy()
        self.status_label.pack_forget()
        self.section('Details')
        self.field('username', 'Username (used to sign in; cannot be changed)', profile['username'], readonly=True)
        self.field('display_name', 'Full name', profile['display_name'])
        self.field('email', 'Email', profile['email'])
        if profile['has_password']:
            self.field('email_password', 'Current password (only needed to change email)', masked=True)
        self.button(self.card, 'Save details', self.save_details).pack(anchor='w')

        self.section('Password')
        if profile['has_password']:
            self.field('current', 'Current password', masked=True)
        self.field('new', 'New password', masked=True)
        self.field('confirm', 'Confirm new password', masked=True)
        self.button(self.card, 'Change password' if profile['has_password'] else 'Set a password',
                    self.save_password).pack(anchor='w')

        self.section('Google')
        self.google_label = tk.Label(self.card, font=(FONT, 10), bg=WHITE, fg=INK)
        self.google_label.pack(anchor='w', pady=(0, 6))
        self.google_button = self.button(self.card, '', self.toggle_google, primary=False)
        self.google_button.pack(anchor='w')
        self.show_google()
        self.status_label.pack(fill='x', pady=(10, 0))
        self.status.set('')

    def show_google(self):
        linked = self.profile['google']
        self.google_label.configure(text='Connected: you can use “Continue with Google” to sign in.' if linked
                                    else 'Not connected.')
        self.google_button.configure(text='Disconnect Google' if linked else 'Connect Google account')

    def save_details(self):
        email, name = self.value('email').strip(), self.value('display_name')
        password = self.value('email_password') if 'email_password' in self.fields else ''

        def done(profile):
            self.profile = profile
            self.say('Details saved.', ok=True)
        self.call(lambda: remote.update_profile(display_name=name, email=email,
                                                current_password=password), done, 'Saving…')

    def save_password(self):
        new = self.value('new')
        if new != self.value('confirm'):
            return self.say('The new passwords do not match.')
        if len(new) < 8:
            return self.say('Use a password of at least 8 characters.')
        current = self.value('current') if 'current' in self.fields else ''

        def done(result):
            for key in ('current', 'new', 'confirm'):
                if key in self.fields:
                    self.fields[key].set('')
            self.say('Password changed.', ok=True)
        self.call(lambda: remote.change_password(current, new), done, 'Changing password…')

    def toggle_google(self):
        def done(profile):
            self.profile = profile
            self.show_google()
            self.say('Google account connected.' if profile['google'] else 'Google account disconnected.', ok=True)
        if self.profile['google']:
            self.call(remote.unlink_google, done, 'Disconnecting…')
        else:
            self.call(lambda: remote.link_google(remote.google_id_token()), done,
                      'Finish signing in to Google in your browser…')


# ---- superadmin dashboard ---------------------------------------------------------------
class UserEditorDialog(Dialog):
    def __init__(self, parent, on_saved, user=None):
        if not can_manage_users(remote.session.role):
            raise ValueError('Only a superadmin can manage users.')
        self.user, self.on_saved = user, on_saved
        super().__init__(parent, 'Edit user' if user else 'Create user',
                         'Edit user' if user else 'Create user',
                         'Usernames stay fixed so report ownership and review history remain intact.')
        values = user or {}
        self.field('username', 'Username', values.get('username', ''), readonly=bool(user))
        self.field('display_name', 'Full name', values.get('display_name', ''))
        self.field('email', 'Email (optional)', values.get('email', ''))
        tk.Label(self.card, text='Role', font=(FONT, 10, 'bold'), bg=WHITE, fg=INK).pack(anchor='w')
        self.fields['role'] = tk.StringVar(self.window, value=values.get('role', 'member'))
        self.role_entry = ttk.Combobox(self.card, textvariable=self.fields['role'], values=ROLES,
                                       state='disabled' if user and user['username'] == remote.session.username else 'readonly')
        self.role_entry.pack(fill='x', pady=(4, 12))
        if not user:
            self.field('password', 'Password (at least 8 characters)', masked=True)
            self.field('confirm', 'Confirm password', masked=True)
        row = tk.Frame(self.card, bg=WHITE)
        row.pack(fill='x', pady=(6, 0))
        self.save_button = self.button(row, 'Save changes' if user else 'Create user', self.submit)
        self.save_button.pack(side='left')
        self.cancel_button = self.button(row, 'Cancel', self.close, primary=False)
        self.cancel_button.pack(side='left', padx=(8, 0))
        self.status_line()

    def busy_changed(self):
        for button in (self.save_button, self.cancel_button):
            button.configure(state='disabled' if self.busy else 'normal')

    def close(self):
        if not self.busy:
            super().close()

    def submit(self):
        if self.busy:
            return
        data = {key: self.value(key).strip() for key in ('username', 'display_name', 'email', 'role')}
        if not data['username']:
            return self.say('Enter a username.')
        if not self.user:
            password = self.value('password')
            if len(password) < 8:
                return self.say('Use a password of at least 8 characters.')
            if password != self.value('confirm'):
                return self.say('The passwords do not match.')
            work = lambda: remote.create_user(password=password, **data)
        else:
            username = data.pop('username')
            work = lambda: remote.update_user(username, **data)

        def done(result):
            self.on_saved('User updated.' if self.user else 'User created. They can sign in now.')
            self.close()
        self.call(work, done, 'Saving user…')


class AccountsDialog(Dialog):
    COLUMNS = (('username', 'Username', 120), ('display_name', 'Name', 150), ('email', 'Email', 200),
               ('role', 'Role', 105), ('state', 'Status', 155))

    def __init__(self, parent):
        if not can_manage_users(remote.session.role):
            raise ValueError('Only a superadmin can manage users.')
        super().__init__(parent, 'Superadmin dashboard', 'Superadmin dashboard',
                         'Create users, assign roles, update details and manage access.', wrap=850)
        self.window.resizable(True, True)
        self.window.geometry('1080x680')
        self.window.minsize(900, 560)
        self.summary = tk.StringVar(self.window, value='Loading account summary…')
        tk.Label(self.card, textvariable=self.summary, font=(FONT, 11, 'bold'), bg=WHITE, fg=INK).pack(anchor='w', pady=(4, 14))
        toolbar = tk.Frame(self.card, bg=WHITE)
        toolbar.pack(fill='x', pady=(0, 12))
        self.create_button = self.button(toolbar, '+ Create user', self.create_user)
        self.create_button.pack(side='left')
        tk.Label(toolbar, text='Search users', bg=WHITE, fg=MUTED).pack(side='left', padx=(20, 8))
        self.search = tk.StringVar(self.window)
        ttk.Entry(toolbar, textvariable=self.search, width=32).pack(side='left', fill='x', expand=True)
        self.search.trace_add('write', lambda *args: self.render_users())
        self.refresh_button = self.button(toolbar, 'Refresh', lambda: self.refresh(), primary=False)
        self.refresh_button.pack(side='right', padx=(10, 0))
        self.tree = ttk.Treeview(self.card, columns=[c[0] for c in self.COLUMNS], show='headings', height=10)
        for key, caption, width in self.COLUMNS:
            self.tree.heading(key, text=caption)
            self.tree.column(key, width=width, anchor='w')
        scroll = ttk.Scrollbar(self.card, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda event: self.sync())
        self.tree.bind('<Double-1>', lambda event: self.edit_user())
        row = tk.Frame(self.card, bg=WHITE)
        row.pack(fill='x', pady=(10, 0))
        self.actions = {}
        for key, text, command in [('approve', 'Approve', self.approve), ('reject', 'Reject request', self.reject),
                                   ('edit', 'Edit user', self.edit_user), ('active', 'Disable', self.toggle_active),
                                   ('password', 'Reset password', self.reset_password),
                                   ('remove', 'Remove user', self.remove_user)]:
            button = self.button(row, text, command, primary=key == 'approve')
            button.pack(side='left', padx=(0, 6))
            self.actions[key] = button
        self.status_line()
        self.users = {}
        self.editor = None
        self.refresh()

    @staticmethod
    def state(user):
        if not user['approved']:
            return 'Waiting for approval'
        return 'Active' if user['active'] else 'Disabled'

    def refresh(self, message=None):
        def done(users):
            self.users = {u['username']: u for u in users}
            waiting = sum(not u['approved'] for u in users)
            self.summary.set(f'{len(users)} users   ·   {sum(bool(u["active"] and u["approved"]) for u in users)} active   ·   '
                             f'{waiting} waiting   ·   {sum(u["role"] == "superadmin" for u in users)} superadmins')
            self.render_users()
            self.say(message or f'{len(users)} accounts · {waiting} waiting for approval.', ok=True)
            self.sync()
        self.call(remote.list_users, done, 'Loading accounts…')

    def render_users(self):
        if not hasattr(self, 'users'):
            return
        selected = self.selected_name()
        query = self.search.get().strip().casefold()
        self.tree.delete(*self.tree.get_children())
        for user in self.users.values():
            if query and query not in ' '.join(str(user.get(k, '')) for k in ('username', 'display_name', 'email', 'role')).casefold():
                continue
            self.tree.insert('', 'end', iid=user['username'], values=(user['username'], user['display_name'],
                             user['email'], user['role'], self.state(user)))
        if selected in self.tree.get_children():
            self.tree.selection_set(selected)
        self.sync()

    def selected_name(self):
        selection = self.tree.selection() if hasattr(self, 'tree') else ()
        return selection[0] if selection else None

    def sync(self):
        user = self.users.get(self.selected_name())
        for button in (self.create_button, self.refresh_button):
            button.configure(state='disabled' if self.busy else 'normal')
        for button in self.actions.values():
            button.configure(state='normal' if user and not self.busy else 'disabled')
        if not user:
            self.actions['active'].configure(text='Disable')
            return
        self.actions['active'].configure(text='Disable' if user['active'] else 'Enable')
        if self.busy:
            return
        pending = not user['approved']
        self.actions['approve'].configure(state='normal' if pending else 'disabled')
        self.actions['reject'].configure(state='normal' if pending else 'disabled')
        self.actions['active'].configure(text='Disable' if user['active'] else 'Enable',
                                         state='disabled' if pending or user['username'] == remote.session.username else 'normal')
        self.actions['remove'].configure(state='disabled' if user['username'] == remote.session.username else 'normal')

    def busy_changed(self):
        self.sync()

    def act(self, work, message):
        name = self.selected_name()
        if name:
            self.call(lambda: work(name), lambda result: self.refresh(message.format(name)))

    def approve(self):
        self.act(remote.approve_user, '{} approved.')

    def reject(self):
        name = self.selected_name()
        if name and messagebox.askyesno('Reject request', f'Reject and remove the account request from “{name}”?',
                                        parent=self.window):
            self.act(remote.reject_user, 'Request from {} rejected.')

    def create_user(self):
        self.editor = UserEditorDialog(self.window, self.refresh)
        return self.editor

    def edit_user(self):
        user = self.users.get(self.selected_name())
        if user:
            self.editor = UserEditorDialog(self.window, self.refresh, user)
            return self.editor

    def remove_user(self):
        name = self.selected_name()
        if name and name != remote.session.username and messagebox.askyesno(
                'Remove user', f'Remove “{name}”? They will lose access. Reports and review history will be preserved.',
                parent=self.window):
            self.act(remote.remove_user, '{} removed. Report history preserved.')

    def toggle_active(self):
        user = self.users.get(self.selected_name())
        if user:
            active = not user['active']
            self.act(lambda name: remote.set_user_active(name, active), '{} ' + ('enabled.' if active else 'disabled.'))

    def reset_password(self):
        name = self.selected_name()
        if not name:
            return
        password = simpledialog.askstring('Reset password', f'New password for {name} (at least 8 characters):',
                                          show='•', parent=self.window)
        if password is None:
            return
        if len(password) < 8:
            return self.say('Use a password of at least 8 characters.')
        self.act(lambda user: remote.reset_user_password(user, password), 'Password for {} reset. Tell them the new password.')

    def close(self):
        if self.editor is not None and self.editor.window.winfo_exists():
            self.editor.close()
        self.editor = None
        super().close()
        self.search = self.summary = None
