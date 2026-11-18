"""Real desktop controls against the isolated HTTP server, with no hosted accounts."""
import tkinter as tk
import pytest

from test_server import database_url, live_server  # noqa: F401
from test_accounts import wait_for
from src import remote
from src.ui.accounts import AccountsDialog
from src.ui.desktop import DesktopApp


@pytest.fixture(autouse=True)
def collect_tk_objects_on_main_thread():
    # Closed Tk windows can leave reference cycles. Collect before another HTTP
    # worker starts so Tcl variables are not finalised on a background thread.
    import gc
    gc.collect()
    yield
    gc.collect()


@pytest.mark.parametrize('role', ['member', 'admin', 'facilitator', 'client', ''])
def test_dashboard_constructor_rejects_other_roles(monkeypatch, role):
    monkeypatch.setattr(remote.session, 'role', role)
    with pytest.raises(ValueError, match='Only a superadmin'):
        AccountsDialog(None)


@pytest.fixture
def super_dashboard(live_server, tk_runtime, monkeypatch):
    live_server.users.set_role('sam', 'superadmin')
    assert remote.login('sam', 'sam-pass') == 'sam'
    root = tk.Toplevel(tk_runtime)
    app = DesktopApp(root, username='sam', on_logout=lambda: None)
    dashboard = app.open_accounts()
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    wait_for(root, lambda: bool(dashboard.users) and not dashboard.busy)
    yield app, dashboard, live_server.users
    if dashboard.window.winfo_exists():
        wait_for(root, lambda: not dashboard.busy)
        dashboard.close()
    app.dispose_workspace()
    root.update()
    root.destroy()


def select(dashboard, username):
    dashboard.search.set('')
    dashboard.tree.selection_set(username)
    dashboard.sync()


def test_desktop_dashboard_create_edit_password_and_remove(super_dashboard, monkeypatch):
    app, dashboard, users = super_dashboard
    assert hasattr(app, 'superadmin_button')
    assert 'Superadmin dashboard' in [b.cget('text') for b in app.account_actions]
    editor = dashboard.create_user()
    for key, value in {'username': 'desktop-person', 'display_name': 'Desktop Person', 'email': 'desktop@example.invalid',
                       'role': 'admin', 'password': 'desktop-password', 'confirm': 'different-password'}.items():
        editor.fields[key].set(value)
    editor.submit()
    assert 'do not match' in editor.status.get()
    assert users.get('desktop-person') is None
    editor.fields['confirm'].set('desktop-password')
    editor.submit()
    wait_for(app.root, lambda: 'desktop-person' in dashboard.users and not dashboard.busy)
    assert users.authenticate('desktop-person', 'desktop-password')['role'] == 'admin'
    select(dashboard, 'desktop-person')
    editor = dashboard.edit_user()
    editor.fields['display_name'].set('Updated Desktop Person')
    editor.fields['role'].set('member')
    editor.submit()
    wait_for(app.root, lambda: dashboard.users['desktop-person']['display_name'] == 'Updated Desktop Person' and not dashboard.busy)
    assert users.get('desktop-person')['role'] == 'member'
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'replacement-password')
    dashboard.reset_password()
    wait_for(app.root, lambda: 'reset' in dashboard.status.get() and not dashboard.busy)
    assert users.authenticate('desktop-person', 'replacement-password')
    assert users.authenticate('desktop-person', 'desktop-password') is None
    dashboard.toggle_active()
    wait_for(app.root, lambda: not dashboard.users['desktop-person']['active'] and not dashboard.busy)
    dashboard.toggle_active()
    wait_for(app.root, lambda: dashboard.users['desktop-person']['active'] and not dashboard.busy)
    dashboard.remove_user()
    wait_for(app.root, lambda: 'desktop-person' not in dashboard.users and not dashboard.busy)
    assert users.get('desktop-person')['deleted'] and not users.authenticate('desktop-person', 'replacement-password')


def test_desktop_search_pending_approval_and_self_protection(super_dashboard):
    app, dashboard, users = super_dashboard
    users.create('waiting-person', 'waiting-password', approved=False)
    dashboard.refresh()
    wait_for(app.root, lambda: 'waiting-person' in dashboard.users and not dashboard.busy)
    dashboard.search.set('waiting-person')
    assert dashboard.tree.get_children() == ('waiting-person',)
    dashboard.tree.selection_set('waiting-person')
    dashboard.sync()
    dashboard.approve()
    wait_for(app.root, lambda: dashboard.users['waiting-person']['approved'] and not dashboard.busy)
    assert users.authenticate('waiting-person', 'waiting-password')['approved']
    select(dashboard, 'sam')
    assert str(dashboard.actions['remove'].cget('state')) == 'disabled'
    assert str(dashboard.actions['active'].cget('state')) == 'disabled'
    editor = dashboard.edit_user()
    assert str(editor.role_entry.cget('state')) == 'disabled'
    editor.close()


def test_admin_desktop_has_no_user_management(live_server, tk_runtime, monkeypatch):
    assert remote.login('sam', 'sam-pass') == 'sam'
    root = tk.Toplevel(tk_runtime)
    app = DesktopApp(root, username='sam', on_logout=lambda: None)
    try:
        assert not hasattr(app, 'superadmin_button')
        assert 'Superadmin dashboard' not in [b.cget('text') for b in app.account_actions]
        errors = []
        monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: errors.append(a))
        assert app.open_accounts() is None
        assert errors and 'Only a superadmin' in errors[0][1]
    finally:
        app.dispose_workspace()
        root.update()
        root.destroy()
