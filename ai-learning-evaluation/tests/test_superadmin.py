"""Role and user-management boundaries shared by both interfaces."""
from src.roles import ROLES, can_manage_users, can_review_reports
from test_server import api, database_url, sign_in  # noqa: F401


def test_role_capabilities():
    assert ROLES == ('member', 'admin', 'superadmin')
    assert can_manage_users('superadmin')
    assert not can_manage_users('admin') and not can_manage_users('member')
    assert can_review_reports('superadmin') and can_review_reports('admin')
    assert not can_review_reports('member')


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
