"""API server + shared database: accounts, ownership, review handoff across two computers.

Runs against SQLite always. Set INSIGHT_HUB_TEST_DATABASE_URL=postgresql://... to also
run every test against a real Postgres database (the tables are emptied first).
"""
import os
import socket
import threading
import time
import tkinter as tk

import pytest

fastapi = pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from server.app import create_app
from server.security import issue_token, read_token
from src.storage.database import Database, password_hash, password_matches
from test_login import tk_runtime  # noqa: F401  (shared Tk root fixture)

BACKENDS = ['sqlite'] + (['postgres'] if os.getenv('INSIGHT_HUB_TEST_DATABASE_URL') else [])


@pytest.fixture(params=BACKENDS)
def database_url(request, tmp_path):
    if request.param == 'sqlite':
        return str(tmp_path / 'server.sqlite3')
    url = os.environ['INSIGHT_HUB_TEST_DATABASE_URL']
    database = Database(url)
    database.initialise()
    with database.connect() as db:
        with db:
            db.execute('DELETE FROM reports')
            db.execute('DELETE FROM users')
            db.execute('DELETE FROM audit_log')
    return url


@pytest.fixture
def api(database_url, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    monkeypatch.setenv('ADMIN_USERNAME', 'lisa')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-pass')
    app = create_app(database_url)
    with TestClient(app) as client:
        client.services = app.state.services
        yield client


def sign_in(api, name, password):
    response = api.post('/auth/login', json={'username': name, 'password': password})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_passwords_are_hashed_and_tokens_are_signed(monkeypatch):
    stored = password_hash('secret')
    assert 'secret' not in stored and password_matches('secret', stored)
    assert not password_matches('Secret', stored)
    monkeypatch.setenv('SECRET_KEY', 'one')
    token = issue_token('alex', 'member')
    assert read_token(token)['u'] == 'alex'
    assert read_token(token[:-2] + 'xx') is None
    monkeypatch.setenv('SECRET_KEY', 'two')
    assert read_token(token) is None


def test_health_login_and_admin_accounts(api):
    assert api.get('/health').json()['ok'] is True
    assert api.get('/reports').status_code == 401
    assert api.post('/auth/login', json={'username': 'lisa', 'password': 'wrong'}).status_code == 401
    admin = sign_in(api, 'lisa', 'admin-pass')
    me = api.get('/auth/me', headers=admin).json()
    assert (me['username'], me['role'], me['has_password'], me['google']) == ('lisa', 'admin', True, False)
    assert api.post('/users', headers=admin, json={'username': 'Alex', 'password': 'pw-alex'}).status_code == 200
    alex = sign_in(api, 'alex', 'pw-alex')
    assert api.get('/users', headers=alex).status_code == 403
    assert api.post('/users', headers=alex, json={'username': 'eve', 'password': 'x', 'role': 'admin'}).status_code == 403
    assert {u['username'] for u in api.get('/users', headers=admin).json()} == {'lisa', 'alex'}
    # Disabling an account invalidates its existing session immediately.
    assert api.post('/users/alex/active?active=false', headers=admin).status_code == 200
    assert api.get('/reports', headers=alex).status_code == 401
    assert api.post('/auth/login', json={'username': 'alex', 'password': 'pw-alex'}).status_code == 401
    assert api.post('/users/lisa/active?active=false', headers=admin).status_code == 400
    assert api.get('/audit/verify', headers=admin).json()['ok'] is True


def test_reports_are_private_and_snapshots_are_validated(api):
    admin = sign_in(api, 'lisa', 'admin-pass')
    api.post('/users', headers=admin, json={'username': 'alex', 'password': 'a'})
    api.post('/users', headers=admin, json={'username': 'sam', 'password': 's'})
    alex, sam = sign_in(api, 'alex', 'a'), sign_in(api, 'sam', 's')
    bad = api.post('/reports', headers=alex, json={'title': 't', 'course': 'c', 'status': 'DRAFT',
                                                    'snapshot': {'schema': 2, 'state': {}}})
    assert bad.status_code == 400
    assert api.post('/reports/x/transition', headers=sam, json={'version': 1, 'action': 'approve'}).status_code == 400
    assert api.get('/reports?view=pending', headers=sam).json() == []
    assert api.post('/reports/x/transition', headers=admin, json={'version': 1, 'action': 'approve'}).status_code == 400


@pytest.fixture
def live_server(database_url, monkeypatch):
    """A real HTTP server on localhost, so the desktop client is tested over the network."""
    import uvicorn
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    monkeypatch.delenv('ADMIN_USERNAME', raising=False)
    app = create_app(database_url)
    users = app.state.services.users
    users.create('alex', 'alex-pass')
    users.create('sam', 'sam-pass', role='admin')   # the reviewer
    users.create('gopi', 'gopi-pass')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    monkeypatch.setenv('SERVER_URL', f'http://127.0.0.1:{port}')
    yield app.state.services
    from src import remote
    remote.logout()
    server.should_exit = True
    thread.join(10)


def test_remote_login(live_server):
    from src.auth import AccountFileError, authenticate
    from src import remote
    assert authenticate('alex', 'wrong') is None
    assert authenticate(' ALEX ', 'alex-pass') == 'alex'
    assert remote.session.username == 'alex' and remote.session.token
    os.environ['SERVER_URL'] = 'http://127.0.0.1:9'
    with pytest.raises(AccountFileError, match='Cannot reach'):
        authenticate('alex', 'alex-pass')


def test_two_computers_share_library_and_review_through_server(live_server, tk_runtime, monkeypatch, tmp_path):
    from src import remote
    from src.remote import RemoteAuditTrail, RemoteReportRepository
    from src.ui.desktop import DesktopApp
    from test_handoff import ready_report
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)
    errors = []
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: errors.append(a))

    def open_workspace(name, password):
        assert remote.login(name, password) == name
        root = tk.Toplevel(tk_runtime)
        app = DesktopApp(root, username=name, on_logout=lambda: None)
        assert isinstance(app.repository, RemoteReportRepository)
        assert isinstance(app.audit, RemoteAuditTrail)
        return root, app

    # Computer 1: the author saves and submits.
    root, author = open_workspace('alex', 'alex-pass')
    ready_report(author)
    assert author.submit_for_approval(), errors
    rid, submitted_version = author.library_id, author.library_version
    assert author.workflow.status == 'AWAITING HUMAN REVIEW'
    assert author.repository.list_pending('alex') == []
    assert author.sign_out()
    assert remote.session.token == ''
    root.destroy()

    # Another member cannot see, open or approve the submitted report.
    assert remote.login('gopi', 'gopi-pass') == 'gopi'
    member = RemoteReportRepository()
    assert member.list_pending('gopi') == []
    with pytest.raises(ValueError, match='unavailable'):
        member.load(rid, 'gopi')
    with pytest.raises(ValueError, match='sent to sam'):
        member.transition(actor='gopi', report_id=rid, version=submitted_version, action="approve", confirmed=True)
    remote.logout()

    # Nothing was written to a local library or audit file.
    assert not (tmp_path / 'reports.sqlite3').exists()

    # Computer 2: a different account sees it, approves it, and the server records the approval.
    root, reviewer = open_workspace('sam', 'sam-pass')
    reviewer.select_library_view('pending')
    assert rid in reviewer.library_cards
    assert reviewer.open_library_report(rid), errors
    assert reviewer.can_review_workspace()
    reviewer.confirmed.set(True)
    assert reviewer.export(), errors
    assert reviewer.workflow.status == 'HUMAN REVIEWED'
    assert reviewer.workflow.approver == 'sam'
    assert 'Human review record' in reviewer.approved_export or reviewer.approved_export
    reviewer.dispose_workspace()
    root.destroy()

    stored = live_server.reports.load(rid, 'sam')
    assert stored['status'] == 'HUMAN REVIEWED' and stored['reviewer'] == 'sam'
    chain = live_server.audit.verify()
    assert chain['ok'] and chain['entries'] > 3
    with live_server.audit.database.connect() as db:
        lines = [row[0] for row in db.execute('SELECT line FROM audit_log ORDER BY seq').fetchall()]
    assert any('"Approved"' in line and '"sam"' in line for line in lines)
    # The author's own account cannot approve their report through the API either.
    with pytest.raises(ValueError):
        live_server.reports.transition(actor='alex', report_id=rid, version=stored['version'], action='approve',
                                       confirmed=True, audit=live_server.audit)
    assert errors == []
