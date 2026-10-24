"""Authenticated identity, account menu and safe workspace disposal."""
import json
import tkinter as tk
from types import SimpleNamespace

import pytest

from test_login import wait_for_login
from test_desktop import load_sample
from src.ui.desktop import DesktopApp


@pytest.fixture
def session(tk_runtime, monkeypatch, tmp_path):
    monkeypatch.setenv('AUDIT_LOG_PATH', str(tmp_path / 'audit.jsonl'))
    root = tk.Toplevel(tk_runtime)
    signed_out = []
    app = DesktopApp(root, username='alex', on_logout=lambda: signed_out.append(True))
    app.signed_out = signed_out
    errors = []
    monkeypatch.setattr(tk_runtime, 'report_callback_exception', lambda *args: errors.append(args))
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)
    yield app
    if not app.disposed:
        app.dispose_workspace()
    root.update()
    root.destroy()
    assert errors == []


def test_signed_in_account_owns_theme_and_submission(session, monkeypatch):
    def unexpected_prompt(*args, **kwargs):
        pytest.fail('An authenticated reviewer must not be asked to type a name')
    monkeypatch.setattr('tkinter.simpledialog.askstring', unexpected_prompt)
    assert session.author_entry.get() == 'alex'
    assert str(session.author_entry.cget('state')) == 'readonly'
    load_sample(session, count=12)
    events = [json.loads(line) for line in session.audit.path.read_text().splitlines()]
    assert any(event['actor'] == 'alex' for event in events)
    # Even a programmatic change to the display cannot change the audit identity.
    session.author_entry.configure(state='normal')
    session.author_entry.delete(0, 'end')
    session.author_entry.insert(0, 'another-person')
    assert session.reviewer_name() == 'alex'
    from src.ai.local_provider import LocalAnalysisProvider
    from src.reporting.report_generator import generate_report
    from test_desktop import decide_all_claims
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    decide_all_claims(session)
    session.library_title = 'Identity test'
    assert session.submit_for_approval()
    assert session.workflow.reviewer == 'alex'
    assert json.loads(session.audit.path.read_text().splitlines()[-1])['actor'] == 'alex'


def test_menu_dismissal_and_busy_guard(session):
    session.toggle_account_menu()
    assert session.account_menu.winfo_manager() == 'place'
    session.dismiss_account_menu(SimpleNamespace(widget=session.account_button))
    assert session.account_menu.winfo_manager() == 'place'
    session.dismiss_account_menu(SimpleNamespace(widget=session.editor))
    assert session.account_menu.winfo_manager() == ''
    session.busy = True
    session.sync_controls()
    assert all(str(button.cget('state')) == 'disabled' for button in session.account_actions)
    assert session.sign_out(True) is False
    assert session.signed_out == []
    session.busy = False


@pytest.mark.parametrize('choice', [None, True])
def test_cancel_or_failed_export_keeps_workspace(session, monkeypatch, choice):
    session.report = object()
    monkeypatch.setattr(session, 'library_unsaved', lambda: True)
    session.dirty = True
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: choice)
    monkeypatch.setattr(session, 'save_library_draft', lambda: False)
    assert session.sign_out() is False
    assert not session.disposed
    assert session.report is not None
    assert session.signed_out == []


def test_export_then_switch_clears_session_and_callbacks(session, monkeypatch):
    session.context = object()
    session.report = object()
    monkeypatch.setattr(session, 'library_unsaved', lambda: True)
    session.dirty = True
    session.question_cache['old'] = 'private answer'
    calls = []
    session.schedule(100, lambda: calls.append('old timer'))
    session.schedule_idle(lambda: calls.append('old idle'))
    session.schedule_review_drawer_open()
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: True)
    monkeypatch.setattr(session, 'save_library_draft', lambda: calls.append(('save', False)) or True)
    assert session.sign_out(True)
    assert calls == [('save', False)]
    assert session.signed_out == [True]
    session.root.update()
    assert calls == [('save', False)]
    assert session.context is session.report is session.raw is None
    assert session.username == ''
    assert session.workflow.reviewer == ''
    assert session.question_cache == {}
    assert session.root.bind('<Control-o>') == ''
    assert session.root.winfo_children() == []
    assert session.session_jobs == set()
    assert not session.sign_out()


def test_loaded_workspace_requires_discard_confirmation(session, monkeypatch):
    load_sample(session, count=12, review=False)
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: None)
    assert not session.sign_out()
    assert not session.disposed
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: False)
    assert session.sign_out()


def test_runtime_switches_between_real_accounts(monkeypatch, tk_runtime, tmp_path):
    from src.auth import add_user
    from src.ui import desktop, login, runtime
    path = tmp_path / 'users.txt'
    add_user('alex', 'first password', path)
    add_user('sam', 'second password', path)
    monkeypatch.setenv('LOGIN_USERS_FILE', str(path))
    monkeypatch.setenv('AUDIT_LOG_PATH', str(tmp_path / 'audit.jsonl'))
    monkeypatch.setattr('dotenv.load_dotenv', lambda *a, **k: None)
    root = tk.Toplevel(tk_runtime)
    monkeypatch.setattr(tk, 'Tk', lambda: root)
    screens, workspaces, errors = [], [], []
    real_login = login.LoginScreen
    real_workspace = desktop.DesktopApp
    def capture_login(*args, **kwargs):
        screen = real_login(*args, **kwargs)
        screens.append(screen)
        return screen
    def capture_workspace(*args, **kwargs):
        app = real_workspace(*args, **kwargs)
        workspaces.append(app)
        return app
    monkeypatch.setattr(login, 'LoginScreen', capture_login)
    monkeypatch.setattr(desktop, 'DesktopApp', capture_workspace)
    def interaction():
        root.report_callback_exception = lambda *args: errors.append(args)
        for name, password in [('alex', 'first password'), ('sam', 'second password'), ('alex', 'first password')]:
            screen = screens[-1]
            assert screen.username.get() == screen.password.get() == ''
            screen.username.set(name)
            screen.password.set(password)
            screen.submit()
            wait_for_login(screen)
            app = workspaces[-1]
            assert app.username == app.author_entry.get() == name
            assert app.context is app.report is None
            assert app.sign_out(True)
            root.update()
        screens[-1].dispose()
        root.destroy()
    monkeypatch.setattr(root, 'mainloop', interaction)
    assert runtime.launch() == 0
    assert len(workspaces) == 3
    assert errors == []
