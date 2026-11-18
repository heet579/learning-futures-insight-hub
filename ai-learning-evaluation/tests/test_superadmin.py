"""Role and user-management boundaries shared by both interfaces."""
from src.roles import ROLES, can_manage_users, can_review_reports
from test_server import api, database_url, sign_in  # noqa: F401
import pytest


def test_role_capabilities():
    assert ROLES == ('member', 'admin', 'facilitator', 'client', 'superadmin')
    assert can_manage_users('superadmin')
    assert not can_manage_users('admin') and not can_manage_users('member')
    assert can_review_reports('superadmin') and can_review_reports('admin')
    assert not can_review_reports('member')
    for role in ('facilitator', 'client'):
        assert not can_manage_users(role)
        assert not can_review_reports(role)


def test_bootstrap_superadmin_preserves_existing_accounts(tmp_path, monkeypatch):
    from src.storage.database import Database, UserStore
    from server.app import bootstrap_admin
    users = UserStore(Database(str(tmp_path / 'users.sqlite3')))
    monkeypatch.setenv('SUPERADMIN_USERNAME', 'owner')
    monkeypatch.setenv('SUPERADMIN_PASSWORD', 'initial-secret')
    monkeypatch.delenv('ADMIN_USERNAME', raising=False)
    bootstrap_admin(users)
    assert users.authenticate('owner', 'initial-secret')['role'] == 'superadmin'
    monkeypatch.setenv('SUPERADMIN_PASSWORD', 'changed-environment')
    bootstrap_admin(users)
    assert users.authenticate('owner', 'initial-secret')
    assert users.authenticate('owner', 'changed-environment') is None
    users.create('existing', 'existing-secret', 'member')
    monkeypatch.setenv('SUPERADMIN_USERNAME', 'existing')
    bootstrap_admin(users)
    assert users.get('existing')['role'] == 'member'


def test_removed_account_is_reserved_and_cannot_sign_in(tmp_path):
    import pytest
    from src.storage.database import Database, UserStore
    users = UserStore(Database(str(tmp_path / 'users.sqlite3')))
    users.create('owner', 'owner-password', 'superadmin')
    users.create('person', 'person-password', 'member')
    users.manage_account('owner', 'person', remove=True)
    assert users.get('person')['deleted'] == 1
    assert users.authenticate('person', 'person-password') is None
    assert 'person' not in {u['username'] for u in users.list()}
    with pytest.raises(ValueError, match='removed account'):
        users.create('person', 'replacement', replace=True)


def test_account_changes_enforce_permissions_and_self_protection(tmp_path):
    import pytest
    from src.storage.database import Database, UserStore
    users = UserStore(Database(str(tmp_path / 'users.sqlite3')))
    users.create('owner', 'owner-password', 'superadmin')
    users.create('reviewer', 'reviewer-password', 'admin')
    with pytest.raises(ValueError, match='Only a signed-in superadmin'):
        users.manage_account('reviewer', 'owner', role='member')
    for change in ({'remove': True}, {'active': False}, {'role': 'member'}):
        with pytest.raises(ValueError, match='your own account'):
            users.manage_account('owner', 'owner', **change)
    users.manage_account('owner', 'reviewer', role='superadmin', display_name=' New  Name ')
    assert users.get('reviewer')['role'] == 'superadmin'
    assert users.get('reviewer')['display_name'] == 'New Name'


def test_user_management_api_is_superadmin_only(api):
    api.services.users.create('owner', 'owner-password', 'superadmin')
    owner = sign_in(api, 'owner', 'owner-password')
    admin = sign_in(api, 'lisa', 'admin-pass')
    body = {'username': 'new-person', 'password': 'person-password', 'role': 'admin', 'display_name': 'New Person'}
    assert api.post('/users', headers=admin, json=body).status_code == 403
    assert api.get('/users', headers=admin).status_code == 403
    assert api.post('/users', headers=owner, json=body).status_code == 200
    assert api.patch('/users/new-person', headers=owner,
                     json={'display_name': 'Updated Person', 'role': 'member'}).status_code == 200
    assert api.services.users.get('new-person')['display_name'] == 'Updated Person'
    person = sign_in(api, 'new-person', 'person-password')
    assert api.delete('/users/new-person', headers=admin).status_code == 403
    assert api.delete('/users/new-person', headers=owner).status_code == 200
    assert api.get('/auth/me', headers=person).status_code == 401
    assert api.delete('/users/owner', headers=owner).status_code == 400


def test_superadmin_keeps_review_and_oversight_access(api):
    api.services.users.create('owner', 'owner-password', 'superadmin')
    owner = sign_in(api, 'owner', 'owner-password')
    admin = sign_in(api, 'lisa', 'admin-pass')
    api.services.users.create('person', 'person-password', 'member')
    person = sign_in(api, 'person', 'person-password')
    reviewers = api.get('/api/reviewers', headers=person).json()
    assert {u['username'] for u in reviewers} == {'owner', 'lisa'}
    assert api.get('/api/oversight', headers=owner).status_code == 200
    assert api.get('/api/oversight', headers=admin).status_code == 200
    assert api.get('/api/oversight', headers=person).status_code == 403


def test_remote_account_operations_encode_names_and_limit_fields(monkeypatch):
    from src import remote
    calls = []
    monkeypatch.setattr(remote, 'request', lambda *args: calls.append(args) or {'ok': True})
    remote.create_user(username=' person ', password='private-password', role='admin', display_name=' Person ')
    remote.update_user('person@example.com', display_name='Changed')
    remote.remove_user('person@example.com')
    assert calls[0] == ('POST', '/users', {'username': 'person', 'password': 'private-password',
                                         'role': 'admin', 'display_name': 'Person', 'email': ''})
    assert calls[1] == ('PATCH', '/users/person%40example.com', {'display_name': 'Changed'})
    assert calls[2] == ('DELETE', '/users/person%40example.com')


@pytest.mark.parametrize('role', ['member', 'admin', 'facilitator', 'client'])
def test_every_management_route_rejects_non_superadmins(api, role):
    api.services.users.create('operator', 'operator-password', role)
    api.services.users.create('target', 'target-password')
    headers = sign_in(api, 'operator', 'operator-password')
    actions = [('GET', '/users', None), ('POST', '/users', {'username': 'extra', 'password': 'extra-pass'}),
               ('PATCH', '/users/target', {'display_name': 'Changed'}), ('DELETE', '/users/target', None),
               ('POST', '/users/target/role', {'role': 'superadmin'}),
               ('POST', '/users/target/active?active=false', None),
               ('POST', '/users/target/password', {'new_password': 'replacement-pass'}),
               ('POST', '/users/target/approve', None), ('POST', '/users/target/reject', None)]
    for method, path, body in actions:
        result = api.request(method, path, headers=headers, **({'json': body} if body else {}))
        assert result.status_code == 403, (method, path, result.text)
    target = api.services.users.get('target')
    assert target['role'] == 'member' and target['active'] and not target['deleted']
    assert api.services.users.authenticate('target', 'target-password')


def test_demoted_superadmin_token_loses_management_access(api):
    from server.security import issue_token
    users = api.services.users
    users.create('owner', 'owner-password', 'superadmin')
    users.create('other', 'other-password', 'superadmin')
    owner = sign_in(api, 'owner', 'owner-password')
    other = sign_in(api, 'other', 'other-password')
    assert api.patch('/users/other', headers=owner, json={'role': 'admin'}).status_code == 200
    assert api.get('/users', headers=other).status_code == 403
    assert api.get('/api/oversight', headers=other).status_code == 200
    forged = {'Authorization': 'Bearer ' + issue_token('lisa', 'superadmin')}
    assert api.get('/users', headers=forged).status_code == 403


def test_user_edits_are_atomic_and_passwords_never_returned(api):
    users = api.services.users
    users.create('owner', 'owner-password', 'superadmin')
    users.create('person', 'person-password', email='person@example.invalid')
    users.create('taken', 'taken-password', email='taken@example.invalid')
    owner = sign_in(api, 'owner', 'owner-password')
    response = api.patch('/users/person', headers=owner,
                         json={'role': 'admin', 'display_name': 'Changed', 'email': 'taken@example.invalid'})
    assert response.status_code == 400
    assert users.get('person')['role'] == 'member' and users.get('person')['display_name'] == ''
    assert api.post('/users', headers=owner, json={'username': 'person', 'password': 'overwrite', 'replace': True}).status_code == 400
    assert users.authenticate('person', 'person-password')
    assert api.post('/users/person/password', headers=owner, json={'new_password': 'new-private-password'}).status_code == 200
    assert users.authenticate('person', 'person-password') is None
    assert users.authenticate('person', 'new-private-password')
    listed = api.get('/users', headers=owner).json()
    assert all(not {'password', 'password_hash', 'google_sub'} & row.keys() for row in listed)
    events = list(api.services.audit.events({'Password reset', 'Account updated'}))
    assert 'new-private-password' not in str(events)


def test_removed_user_keeps_reports_and_cannot_return_through_google(api, golden_df):
    users = api.services.users
    users.create('owner', 'owner-password', 'superadmin')
    users.create('person', 'person-password', email='person@example.invalid', google_sub='google-person')
    owner, person = sign_in(api, 'owner', 'owner-password'), sign_in(api, 'person', 'person-password')
    response = api.post('/api/reports', headers=person, files={'files': ('survey.csv', golden_df.to_csv(index=False).encode(), 'text/csv')})
    assert response.status_code == 200
    report_id = response.json()['report']['id']
    assert api.delete('/users/person', headers=owner).status_code == 200
    assert api.get('/auth/me', headers=person).status_code == 401
    assert api.services.reports.list_owned('person')[0]['id'] == report_id
    api.services.verify_google = lambda token: {'sub': 'google-person', 'email': 'person@example.invalid', 'email_verified': True}
    assert api.post('/auth/google', json={'id_token': 'test-token'}).status_code == 401
    assert api.post('/users', headers=owner, json={'username': 'person', 'password': 'reuse-password'}).status_code == 400


def test_registration_cannot_request_privileged_role(api):
    response = api.post('/auth/register', json={'username': 'requester', 'password': 'requester-password',
                                               'email': 'requester@example.invalid', 'role': 'superadmin'})
    assert response.status_code == 200
    assert api.services.users.get('requester')['role'] == 'member'
    assert not api.services.users.get('requester')['approved']


def test_concurrent_demotions_keep_an_active_superadmin(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.storage.database import Database, UserStore
    users = UserStore(Database(str(tmp_path / 'concurrent.sqlite3')))
    users.create('left', 'left-password', 'superadmin')
    users.create('right', 'right-password', 'superadmin')
    def demote(actor, target):
        try:
            users.manage_account(actor, target, role='member')
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(demote, 'left', 'right')
        second = executor.submit(demote, 'right', 'left')
    assert sorted([first.result(), second.result()]) == [False, True]
    assert sum(u['role'] == 'superadmin' and u['active'] for u in users.list()) == 1


def test_operator_can_promote_without_resetting_password(tmp_path, monkeypatch, capsys):
    from server.manage import main
    from src.storage.database import Database, UserStore
    url = str(tmp_path / 'cli.sqlite3')
    users = UserStore(Database(url))
    users.create('existing', 'unchanged-password')
    monkeypatch.setenv('DATABASE_URL', url)
    main(['promote-superadmin', 'existing'])
    assert users.authenticate('existing', 'unchanged-password')['role'] == 'superadmin'
    assert 'unchanged-password' not in capsys.readouterr().out
