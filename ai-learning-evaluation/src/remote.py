"""Desktop client for the Insight Hub API server.

When SERVER_URL is set (for example https://insight-hub.onrender.com), sign-in, the report
library, review handoff and the audit chain all go through the server, so every computer
shares one library. No database credentials ever live on the desktop. Without SERVER_URL the
app keeps using its local SQLite library and audit file. Uses only the standard library.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

# The free Render plan sleeps when idle; the first request can take about a minute.
TIMEOUT = float(os.getenv('SERVER_TIMEOUT', '90'))


def server_url():
    return os.getenv('SERVER_URL', '').strip().rstrip('/')


class ServerError(ValueError):
    """The server refused the request; the message is safe to show to the user."""


class ServerUnavailable(ConnectionError):
    """The server could not be reached."""


class Session:
    token = ''
    username = ''
    role = ''


session = Session()


def request(method, path, body=None, *, token=None, base=None):
    base = base or server_url()
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
    headers = {'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    token = session.token if token is None else token
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8') or 'null')
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('detail')
        except Exception:
            detail = None
        if isinstance(detail, list):   # FastAPI validation errors
            detail = 'The server rejected this request: ' + '; '.join(str(d.get('msg', d)) for d in detail)
        raise ServerError(detail or f'Server error ({exc.code}). Please try again.') from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        raise ServerUnavailable(f'Cannot reach the Insight Hub server at {base} ({reason}). '
                                'Check your internet connection and try again.') from None


def login(username, password):
    """Return the username on success, None for a wrong password. Stores the session token."""
    try:
        result = request('POST', '/auth/login', {'username': username.strip(), 'password': password}, token='')
    except ServerError as exc:
        if 'incorrect' in str(exc).lower():
            return None
        raise
    session.token, session.username, session.role = result['token'], result['username'], result['role']
    return result['username']


def logout():
    session.token = session.username = session.role = ''


class RemoteReportRepository:
    """Same operations as ReportRepository; the server applies the same rules for every computer."""

    def __init__(self, base=None):
        self.base = base or server_url()
        self.path = self.base

    def _call(self, method, path, body=None):
        return request(method, path, body, base=self.base)

    def _check(self, actor):
        if actor and session.username and actor != session.username:
            raise ValueError('This workspace belongs to a different signed-in account. Sign in again.')

    def list_owned(self, actor):
        self._check(actor)
        return self._call('GET', '/reports?view=mine')

    def list_pending(self, actor):
        self._check(actor)
        return self._call('GET', '/reports?view=pending')

    def list_approved(self, actor):
        self._check(actor)
        return self._call('GET', '/reports?view=approved')

    def load(self, report_id, actor):
        self._check(actor)
        return self._call('GET', f'/reports/{urllib.parse.quote(report_id, safe="")}')

    def save(self, *, actor, title, course, status, snapshot, report_id=None, version=None):
        self._check(actor)
        result = self._call('POST', '/reports', {'title': title, 'course': course, 'status': status,
            'snapshot': snapshot, 'report_id': report_id, 'version': version})
        return result['id'], result['version']

    def rename(self, *, actor, report_id, version, title):
        self._check(actor)
        return self._call('POST', f'/reports/{urllib.parse.quote(report_id, safe="")}/rename',
                          {'version': version, 'title': title})['version']

    def delete(self, *, actor, report_id, version):
        self._check(actor)
        self._call('DELETE', f'/reports/{urllib.parse.quote(report_id, safe="")}?version={int(version)}')

    def transition(self, *, actor, report_id, version, action, notes='', role='', confirmed=False, audit=None):
        # The server writes the approval to its own audit chain; `audit` is ignored here.
        from src.storage.snapshot import unpack
        self._check(actor)
        result = self._call('POST', f'/reports/{urllib.parse.quote(report_id, safe="")}/transition',
            {'version': version, 'action': action, 'notes': notes, 'role': role, 'confirmed': bool(confirmed)})
        return result['version'], unpack(result['snapshot'])


class RemoteAuditTrail:
    """Same interface as AuditTrail; events join the server's shared hash chain."""

    def __init__(self, base=None):
        self.base = base or server_url()
        self.path = f'{self.base} (shared server audit chain)'

    def append(self, action, actor='', **details):
        try:
            return request('POST', '/audit', {'action': action, 'actor': actor,
                                              'details': json.loads(json.dumps(details, default=str))}, base=self.base)
        except ServerError as exc:
            # Callers treat OSError as "audit log could not be written".
            raise OSError(str(exc)) from None

    def verify(self):
        try:
            return request('GET', '/audit/verify', base=self.base)
        except ServerError as exc:
            raise OSError(str(exc)) from None


def report_repository():
    if server_url():
        return RemoteReportRepository()
    from src.storage.reports import ReportRepository
    return ReportRepository()


def audit_trail():
    if server_url():
        return RemoteAuditTrail()
    from src.audit.logger import AuditTrail
    return AuditTrail()
