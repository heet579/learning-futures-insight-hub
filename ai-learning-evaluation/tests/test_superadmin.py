"""Role and user-management boundaries shared by both interfaces."""
from src.roles import ROLES, can_manage_users, can_review_reports


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
