"""Self-service accounts: sign-up with approval, Google sign-in, profile settings, admin tools."""
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request

import pytest

pytest.importorskip('fastapi')
from test_server import api, database_url, live_server, sign_in  # noqa: F401  (shared fixtures)
from test_login import tk_runtime  # noqa: F401

from src.storage.database import Database, UserStore


def fake_google(token):
    """Stand-in for Google's verification: 'sub|email|verified|name'."""
    sub, email, verified, name = token.split('|')
    if sub == 'bad':
        raise ValueError('Google sign-in could not be verified. Please try again.')
    return {'sub': sub, 'email': email, 'email_verified': verified == 'yes', 'name': name}


@pytest.fixture
def admin(api):
    api.services.verify_google = fake_google
    return sign_in(api, 'lisa', 'admin-pass')


def register(api, name='gopi', email='gopi@gmail.com', password='gopi-pass-1'):
    return api.post('/auth/register', json={'username': name, 'password': password, 'email': email,
                                            'display_name': 'Gopi R'})


def test_sign_up_waits_for_admin_approval(api, admin):
    response = register(api)
    assert response.status_code == 200 and response.json()['pending'] is True
    pending = api.post('/auth/login', json={'username': 'gopi', 'password': 'gopi-pass-1'})
    assert pending.status_code == 403 and 'waiting for administrator approval' in pending.json()['detail']
    assert api.post('/auth/login', json={'username': 'gopi', 'password': 'wrong'}).status_code == 401
    assert register(api).status_code == 400                                    # username taken
    assert register(api, name='gopi2').json()['detail'].startswith('An account already uses')
    assert register(api, name='x', email='not-an-email').status_code == 400
    listed = {u['username']: u for u in api.get('/users', headers=admin).json()}
    assert listed['gopi']['approved'] == 0 and listed['gopi']['email'] == 'gopi@gmail.com'
    assert 'password_hash' not in listed['gopi']
    assert api.post('/users/gopi/approve', headers=admin).status_code == 200
    gopi = sign_in(api, 'gopi', 'gopi-pass-1')
    assert api.get('/auth/me', headers=gopi).json()['display_name'] == 'Gopi R'
    # Members cannot approve anyone, and approved accounts cannot be "rejected".
    register(api, name='eve', email='eve@gmail.com')
    assert api.post('/users/eve/approve', headers=gopi).status_code == 403
    assert api.post('/users/gopi/reject', headers=admin).status_code == 400
    assert api.post('/users/eve/reject', headers=admin).status_code == 200
    assert 'eve' not in {u['username'] for u in api.get('/users', headers=admin).json()}


def test_profile_email_and_password_changes(api, admin):
    register(api)
    api.post('/users/gopi/approve', headers=admin)
    gopi = sign_in(api, 'gopi', 'gopi-pass-1')
    assert api.patch('/auth/me', headers=gopi, json={'display_name': '  Gopi   Ravula '}).json()['display_name'] == 'Gopi Ravula'
    no_password = api.patch('/auth/me', headers=gopi, json={'email': 'new@gmail.com'})
    assert no_password.status_code == 400 and 'current password' in no_password.json()['detail']
    changed = api.patch('/auth/me', headers=gopi, json={'email': 'New@Gmail.com', 'current_password': 'gopi-pass-1'})
    assert changed.json()['email'] == 'new@gmail.com'
    assert api.post('/auth/password', headers=gopi, json={'current_password': 'nope', 'new_password': 'x' * 9}).status_code == 400
    assert api.post('/auth/password', headers=gopi, json={'current_password': 'gopi-pass-1', 'new_password': 'brand-new-pw'}).status_code == 200
    assert api.post('/auth/login', json={'username': 'gopi', 'password': 'gopi-pass-1'}).status_code == 401
    sign_in(api, 'gopi', 'brand-new-pw')
    # Admin password reset, role change and self-protection.
    assert api.post('/users/gopi/password', headers=admin, json={'new_password': 'reset-pass-9'}).status_code == 200
    sign_in(api, 'gopi', 'reset-pass-9')
    assert api.post('/users/gopi/role', headers=admin, json={'role': 'admin'}).status_code == 200
    assert api.post('/users/lisa/role', headers=admin, json={'role': 'member'}).status_code == 400
    assert api.post('/users/lisa/active?active=false', headers=admin).status_code == 400


def test_google_sign_up_link_and_unlink(api, admin):
    assert api.get('/auth/google/config').json()['enabled'] is False
    # A new Google user becomes a pending request with a username taken from the address.
    first = api.post('/auth/google', json={'id_token': 'g-1|zhongyi.li@gmail.com|yes|Zhongyi Li'})
    assert first.status_code == 202 and first.json() == {'username': 'zhongyi.li', 'pending': True,
                                                          'detail': first.json()['detail']}
    assert api.post('/auth/google', json={'id_token': 'g-1|zhongyi.li@gmail.com|yes|Zhongyi Li'}).status_code == 403
    api.post('/users/zhongyi.li/approve', headers=admin)
    signed_in = api.post('/auth/google', json={'id_token': 'g-1|zhongyi.li@gmail.com|yes|Zhongyi Li'})
    assert signed_in.status_code == 200 and signed_in.json()['username'] == 'zhongyi.li'
    google_user = {'Authorization': 'Bearer ' + signed_in.json()['token']}
    me = api.get('/auth/me', headers=google_user).json()
    assert me['google'] is True and me['has_password'] is False and me['display_name'] == 'Zhongyi Li'
    # No password yet: cannot disconnect Google; setting one needs no current password.
    assert api.delete('/auth/google/link', headers=google_user).status_code == 400
    assert api.post('/auth/password', headers=google_user, json={'new_password': 'own-pass-12'}).status_code == 200
    assert api.delete('/auth/google/link', headers=google_user).json()['google'] is False
    sign_in(api, 'zhongyi.li', 'own-pass-12')
    # An existing password account is connected when Google proves its email address.
    register(api)
    api.post('/users/gopi/approve', headers=admin)
    linked = api.post('/auth/google', json={'id_token': 'g-2|gopi@gmail.com|yes|Gopi'})
    assert linked.status_code == 200 and linked.json()['username'] == 'gopi'
    # One Google account cannot be attached to two Insight Hub accounts.
    gopi = sign_in(api, 'gopi', 'gopi-pass-1')
    assert api.post('/auth/google/link', headers=google_user, json={'id_token': 'g-2|x@gmail.com|yes|X'}).status_code == 400
    assert api.get('/auth/me', headers=gopi).json()['google'] is True
    # Unverified addresses and forged tokens are refused.
    assert api.post('/auth/google', json={'id_token': 'g-3|a@b.com|no|A'}).status_code == 400
    assert api.post('/auth/google', json={'id_token': 'bad|a@b.com|yes|A'}).status_code == 400


def test_existing_users_table_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL, '
                   'active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL)')
        from src.storage.database import password_hash
        db.execute('INSERT INTO users VALUES (?,?,?,?,?)', ('heet', password_hash('pw'), 'admin', 1, 'then'))
    users = UserStore(Database(str(path)))
    user = users.authenticate('heet', 'pw')
    assert user['approved'] == 1 and user['email'] == '' and user['google_sub'] == ''


def test_google_browser_flow_uses_pkce_and_loopback(monkeypatch):
    from src import google_signin
    seen = {}

    def fake_browser(url):
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        seen.update(query)
        redirect = f"{query['redirect_uri']}/?code=abc&state={query['state']}"
        threading.Thread(target=lambda: urllib.request.urlopen(redirect, timeout=5).read(), daemon=True).start()
        return True

    class TokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id_token": "the-id-token"}'

    real_urlopen = urllib.request.urlopen

    def fake_urlopen(request, timeout=None):
        if getattr(request, 'full_url', '') == google_signin.TOKEN_URL:
            body = dict(urllib.parse.parse_qsl(request.data.decode()))
            assert body['code'] == 'abc' and body['code_verifier'] and body['client_secret'] == 'secret'
            return TokenResponse()
        return real_urlopen(request, timeout=timeout)

    monkeypatch.setattr(google_signin.urllib.request, 'urlopen', fake_urlopen)
    assert google_signin.get_id_token('client.apps.googleusercontent.com', 'secret', open_browser=fake_browser) == 'the-id-token'
    assert seen['redirect_uri'].startswith('http://127.0.0.1:') and seen['code_challenge_method'] == 'S256'
    assert seen['scope'] == 'openid email profile'
    with pytest.raises(google_signin.GoogleSignInError, match='not set up'):
        google_signin.get_id_token('', '')


def wait_for(widget, condition, seconds=15):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        widget.update()
        time.sleep(.02)
    assert condition()


def test_desktop_sign_up_profile_and_admin_windows(live_server, tk_runtime, monkeypatch):
    from src import remote
    from src.ui.login import LoginScreen
    from src.ui.accounts import AccountsDialog, ProfileDialog
    from src.ui.desktop import DesktopApp
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    live_server.users.set_role('sam', 'admin')

    # Sign-in screen in shared mode offers Google and Create account.
    root = tk.Toplevel(tk_runtime)
    signed_in = []
    screen = LoginScreen(root, signed_in.append)
    assert screen.google_button is not None and screen.register_link.cget('text') == 'Create account'
    dialog = screen.create_account()
    for key, value in [('display_name', 'Esrat J'), ('username', 'esrat'), ('email', 'esrat@gmail.com'),
                       ('password', 'esrat-pass-1'), ('confirm', 'esrat-pass-2')]:
        dialog.fields[key].set(value)
    dialog.submit()
    assert 'do not match' in dialog.status.get()
    dialog.fields['confirm'].set('esrat-pass-1')
    dialog.submit()
    wait_for(root, lambda: 'Request sent' in dialog.status.get())
    assert live_server.users.get('esrat')['approved'] == 0
    dialog.close()
    screen.dispose()
    root.destroy()

    # Admin approves in Manage accounts.
    assert remote.login('sam', 'sam-pass') == 'sam'
    root = tk.Toplevel(tk_runtime)
    app = DesktopApp(root, username='sam', on_logout=lambda: None)
    captions = [str(b.cget('text')) for b in app.account_actions]
    assert captions[:2] == ['Profile settings', 'Manage accounts']
    accounts = app.open_accounts()
    assert isinstance(accounts, AccountsDialog)
    wait_for(root, lambda: 'esrat' in accounts.users)
    accounts.tree.selection_set('esrat')
    accounts.sync()
    assert str(accounts.actions['approve'].cget('state')) == 'normal'
    accounts.approve()
    wait_for(root, lambda: accounts.users['esrat']['approved'] == 1)
    accounts.close()
    app.dispose_workspace()
    root.destroy()

    # The member's profile: rename, change password; no Manage accounts.
    assert remote.login('esrat', 'esrat-pass-1') == 'esrat'
    root = tk.Toplevel(tk_runtime)
    app = DesktopApp(root, username='esrat', on_logout=lambda: None)
    assert [str(b.cget('text')) for b in app.account_actions][:1] == ['Profile settings']
    assert 'Manage accounts' not in [str(b.cget('text')) for b in app.account_actions]
    profile = app.open_profile()
    assert isinstance(profile, ProfileDialog)
    wait_for(root, lambda: profile.profile is not None and 'display_name' in profile.fields)
    profile.fields['display_name'].set('Esrat Jahan')
    profile.save_details()
    wait_for(root, lambda: not profile.busy)
    assert profile.status.get() == 'Details saved.', profile.status.get()
    profile.fields['current'].set('esrat-pass-1')
    profile.fields['new'].set('esrat-new-pass')
    profile.fields['confirm'].set('esrat-new-pass')
    profile.save_password()
    wait_for(root, lambda: profile.status.get() == 'Password changed.')
    profile.close()
    app.dispose_workspace()
    root.destroy()
    assert live_server.users.get('esrat')['display_name'] == 'Esrat Jahan'
    assert live_server.users.authenticate('esrat', 'esrat-new-pass') is not None
    remote.logout()
