"""Negative API contracts: rejected requests must leave saved reports unchanged."""
import base64
import json

import pytest

from test_server import api, database_url, sign_in  # noqa: F401
from server import security


@pytest.fixture
def member(api):
    api.services.users.create('author', 'author-pass')
    return sign_in(api, 'author', 'author-pass')


@pytest.fixture
def survey_report(api, member, golden_df):
    result = api.post('/api/reports', headers=member, data={'title': 'Boundary checks'},
                      files={'files': ('survey.csv', golden_df.to_csv(index=False).encode(), 'text/csv')})
    assert result.status_code == 200, result.text
    return result.json()['report']


@pytest.mark.parametrize('token', ['', 'broken', 'a.b.c', 'nonascii-é.invalid', 'a.é', None])
def test_malformed_tokens_are_rejected_without_exceptions(token):
    assert security.read_token(token) is None


def test_token_expires_at_the_exact_boundary(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-expiry-secret')
    clock = [1000.0]
    monkeypatch.setattr(security.time, 'time', lambda: clock[0])
    token = security.issue_token('author', 'member', hours=1)
    clock[0] = 4599.9
    assert security.read_token(token)['u'] == 'author'
    clock[0] = 4600.0
    assert security.read_token(token) is None


def test_editing_signed_identity_invalidates_the_token(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test-signature-secret')
    token = security.issue_token('author', 'member')
    body, signature = token.split('.')
    claims = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
    claims.update(u='lisa', r='admin')
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=') + '.' + signature
    assert security.read_token(forged) is None


def test_signed_role_cannot_override_the_current_account_role(api, member):
    forged_role = {'Authorization': 'Bearer ' + security.issue_token('author', 'admin')}
    assert api.get('/users', headers=forged_role).status_code == 403
    assert api.get('/auth/me', headers=forged_role).json()['role'] == 'member'
    profile = api.get('/auth/me', headers=member).json()
    assert not {'password', 'password_hash', 'google_sub'} & profile.keys()


@pytest.mark.parametrize('filename, content', [
    ('notes.txt', b'not a survey'), ('survey.csv', b'OtherColumn\n1\n'), ('empty.csv', b''),
])
def test_bad_uploads_leave_no_report(api, member, filename, content):
    response = api.post('/api/reports', headers=member, files={'files': (filename, content, 'text/plain')})
    assert response.status_code == 400
    assert api.get('/reports', headers=member).json() == []


def test_combined_upload_limit_is_enforced_before_saving(api, member, golden_df, monkeypatch):
    from server import web_api
    csv = golden_df.to_csv(index=False).encode()
    monkeypatch.setattr(web_api, 'MAX_UPLOAD_BYTES', len(csv) + 1)
    response = api.post('/api/reports', headers=member,
                        files=[('files', ('one.csv', csv, 'text/csv')), ('files', ('two.csv', csv, 'text/csv'))])
    assert response.status_code == 400 and 'maximum' in response.json()['detail']
    assert api.get('/reports', headers=member).json() == []


@pytest.mark.parametrize('endpoint, payload', [
    ('draft', {'audience': 'unknown'}),
    ('themes', {'name': 'anything', 'status': 'pending'}),
    ('ask', {'question': ''}),
    ('ask', {'question': 'x' * 2001}),
    ('revisions', {'sections': [], 'method': 'unknown'}),
])
def test_invalid_requests_do_not_change_the_saved_version(api, member, survey_report, endpoint, payload):
    rid = survey_report['id']
    response = api.post(f'/api/reports/{rid}/{endpoint}', headers=member, json=payload)
    assert response.status_code == 422
    current = api.get(f'/api/reports/{rid}', headers=member).json()
    assert current['report']['version'] == survey_report['version']
    assert current['workspace']['content'] == ''


def test_other_member_cannot_read_rows_export_rename_or_delete(api, member, survey_report):
    api.services.users.create('outsider', 'outsider-pass')
    outsider = sign_in(api, 'outsider', 'outsider-pass')
    rid, version = survey_report['id'], survey_report['version']
    for suffix in ('', '/rows', '/export?format=md'):
        assert api.get(f'/api/reports/{rid}{suffix}', headers=outsider).status_code == 400
    assert api.post(f'/reports/{rid}/rename', headers=outsider, json={'title': 'stolen', 'version': version}).status_code == 400
    assert api.delete(f'/reports/{rid}?version={version}', headers=outsider).status_code == 400
    assert api.get(f'/api/reports/{rid}', headers=member).json()['report']['title'] == 'Boundary checks'


def test_stale_versions_cannot_rename_or_delete_a_newer_draft(api, member, survey_report):
    rid, version = survey_report['id'], survey_report['version']
    renamed = api.post(f'/reports/{rid}/rename', headers=member, json={'title': 'Latest title', 'version': version})
    assert renamed.status_code == 200
    assert api.post(f'/reports/{rid}/rename', headers=member, json={'title': 'Stale title', 'version': version}).status_code == 400
    assert api.delete(f'/reports/{rid}?version={version}', headers=member).status_code == 400
    current = api.get(f'/api/reports/{rid}', headers=member).json()['report']
    assert current['title'] == 'Latest title' and current['version'] == version + 1


def test_export_before_drafting_and_submission_before_review_are_blocked(api, member, survey_report):
    rid, version = survey_report['id'], survey_report['version']
    assert api.get(f'/api/reports/{rid}/export?format=md', headers=member).status_code == 400
    submit = api.post(f'/reports/{rid}/transition', headers=member, json={'version': version, 'action': 'submit'})
    assert submit.status_code == 400
    current = api.get(f'/api/reports/{rid}', headers=member).json()
    assert current['workspace']['workflow']['status'] == 'DRAFT'
    assert current['report']['version'] == version
