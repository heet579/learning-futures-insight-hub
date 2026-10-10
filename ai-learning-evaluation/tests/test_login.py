"""Real Tk sign-in interaction and startup gate regressions."""
import os
import sys
import time
import tkinter as tk

import pytest

from src.auth import add_user
from src.ui.login import LoginScreen
from src.ui.runtime import _setup_environment, launch


@pytest.fixture(scope='module')
def tk_runtime():
    _setup_environment()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if sys.platform == 'win32' or os.getenv('REQUIRE_DESKTOP_TESTS') == '1':
            raise
        pytest.skip(f'Tk display unavailable: {exc}')
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def screen(tk_runtime, tmp_path):
    path = tmp_path / 'users.txt'
    add_user('admin', 'test password', path)
    root = tk.Toplevel(tk_runtime)
    root.withdraw()
    unlocked = []
    screen = LoginScreen(root, unlocked.append, path)
    screen.unlocked = unlocked
    yield screen
    if not screen.closed:
        screen.dispose()
    root.destroy()


def wait_for_login(screen):
    deadline = time.monotonic() + 10
    while screen.future is not None and time.monotonic() < deadline:
        screen.root.update()
        time.sleep(.01)
    assert screen.future is None, 'Authentication timed out'


def test_wrong_password_blocks_workspace_then_retry_succeeds(screen):
    assert screen.unlocked == []
    assert not screen.progress.winfo_manager()
    screen.username.set('admin')
    screen.password.set('wrong password')
    screen.submit()
    assert screen.button.cget('state') == 'disabled'
    assert screen.progress.winfo_manager() == 'pack'
    screen.submit()  # Repeated clicks must not start another task.
    wait_for_login(screen)
    assert screen.unlocked == []
    assert 'incorrect' in screen.status.get()
    assert screen.password.get() == ''
    assert not screen.progress.winfo_manager()
    screen.password.set('test password')
    screen.submit()
    wait_for_login(screen)
    assert screen.unlocked == ['admin']
    assert screen.closed
    assert not screen.frame.winfo_exists()


def test_missing_input_and_configuration_are_visible(screen):
    screen.submit()
    assert 'Enter' in screen.status.get()
    assert screen.future is None
    screen.account_path.unlink()
    screen.username.set('admin')
    screen.password.set('test password')
    screen.submit()
    wait_for_login(screen)
    assert 'Account file unavailable' in screen.status.get()
    assert screen.unlocked == []
    assert screen.button.cget('state') == 'normal'


def test_dispose_during_check_cancels_ui_callback(screen):
    screen.username.set('admin')
    screen.password.set('test password')
    screen.submit()
    poll_id = screen.poll_id
    screen.dispose()
    screen.dispose()  # Cleanup is safe if called again during window shutdown.
    pending = screen.root.tk.call('after', 'info')
    assert poll_id not in pending
    assert screen.unlocked == []


def test_runtime_requires_login_before_constructing_workspace(monkeypatch, tk_runtime, tmp_path):
    from src.ui import desktop, login
    path = tmp_path / 'users.txt'
    add_user('admin', 'test password', path)
    monkeypatch.setenv('LOGIN_USERS_FILE', str(path))
    root = tk.Toplevel(tk_runtime)
    monkeypatch.setattr(tk, 'Tk', lambda: root)
    opened, captured = [], []
    real_login = LoginScreen

    def capture_login(root, on_success):
        screen = real_login(root, on_success)
        captured.append(screen)
        return screen

    class Workspace:
        def __init__(self, root):
            opened.append(self)

    def interaction():
        assert opened == []
        screen = captured[0]
        screen.username.set('admin')
        screen.password.set('wrong password')
        screen.submit()
        wait_for_login(screen)
        assert opened == []
        screen.password.set('test password')
        screen.submit()
        wait_for_login(screen)
        assert len(opened) == 1
        assert opened[0].username == 'admin'
        root.destroy()

    monkeypatch.setattr(login, 'LoginScreen', capture_login)
    monkeypatch.setattr(desktop, 'DesktopApp', Workspace)
    monkeypatch.setattr(root, 'mainloop', interaction)
    assert launch() == 0
