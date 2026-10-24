"""Shared storage for the API server: Postgres (Neon) in production, SQLite for tests.

The report rules live in ReportRepository; this module only swaps the connection,
so the server enforces exactly the same ownership, versioning and review checks
as the local app.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.audit.logger import GENESIS, _digest
from src.storage.reports import ReportRepository

REPORTS_TABLE = '''CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
    course TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL,
    version INTEGER NOT NULL, snapshot TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT '')'''
USERS_TABLE = '''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL)'''
AUDIT_TABLE_PG = 'CREATE TABLE IF NOT EXISTS audit_log (seq BIGSERIAL PRIMARY KEY, line TEXT NOT NULL)'
AUDIT_TABLE_SQLITE = 'CREATE TABLE IF NOT EXISTS audit_log (seq INTEGER PRIMARY KEY AUTOINCREMENT, line TEXT NOT NULL)'


def normalise_url(url):
    """Accept Neon's postgres:// or postgresql:// URL and always require TLS for remote hosts."""
    url = url.strip()
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    if parts.hostname not in ('localhost', '127.0.0.1', '::1'):
        query.setdefault('sslmode', 'require')
    return urlunsplit(parts._replace(query=urlencode(query)))


class Row:
    """Row usable as row['col'], row[0] and dict(row), like sqlite3.Row."""
    __slots__ = ('_names', '_values')

    def __init__(self, names, values):
        self._names, self._values = names, tuple(values)

    def keys(self):
        return list(self._names)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        return self._values[self._names.index(key)]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _Cursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.rowcount = cursor.rowcount
        self._names = [c.name for c in cursor.description] if cursor.description else []

    def fetchone(self):
        row = self._cursor.fetchone()
        return None if row is None else Row(self._names, row)

    def fetchall(self):
        return [Row(self._names, row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class PostgresConnection:
    """Translate the SQLite dialect used by ReportRepository to Postgres."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        stripped = sql.strip()
        if stripped.upper() == 'BEGIN IMMEDIATE':
            # Serialise review transitions exactly like SQLite's write lock did.
            sql = 'LOCK TABLE reports IN SHARE ROW EXCLUSIVE MODE'
        elif stripped.upper().startswith('PRAGMA'):
            return _EmptyCursor()
        cursor = self._connection.cursor()
        cursor.execute(sql.replace('?', '%s'), tuple(params))
        return _Cursor(cursor)

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        return False


class _EmptyCursor:
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def __iter__(self):
        return iter(())


class Database:
    """One storage location: a postgresql:// URL, or a SQLite file path for tests and local runs."""

    def __init__(self, url):
        if not url:
            raise ValueError('DATABASE_URL is not set.')
        self.is_postgres = url.startswith(('postgres://', 'postgresql://'))
        self.url = normalise_url(url) if self.is_postgres else str(Path(url).expanduser())
        self._ready = False

    def describe(self):
        if not self.is_postgres:
            return f'SQLite {self.url}'
        parts = urlsplit(self.url)
        return f'Postgres {parts.hostname}{parts.path}'

    @contextmanager
    def connect(self):
        if self.is_postgres:
            import psycopg
            raw = psycopg.connect(self.url, connect_timeout=20)
            db = PostgresConnection(raw)
        else:
            Path(self.url).parent.mkdir(parents=True, exist_ok=True)
            raw = db = sqlite3.connect(self.url, timeout=30)
            raw.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            raw.close()

    def initialise(self):
        if self._ready:
            return
        with self.connect() as db:
            with db:
                db.execute(REPORTS_TABLE)
                db.execute(USERS_TABLE)
                db.execute(AUDIT_TABLE_PG if self.is_postgres else AUDIT_TABLE_SQLITE)
        self._ready = True


class DatabaseReportRepository(ReportRepository):
    """ReportRepository whose rows live in the shared server database."""

    def __init__(self, database):
        self.database = database
        self.path = database.describe()

    @contextmanager
    def connect(self):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                yield db


class DatabaseAuditTrail:
    """The same SHA-256 hash chain as AuditTrail, stored as rows instead of file lines."""

    def __init__(self, database):
        self.database = database
        self.path = database.describe()

    def append(self, action, actor='', **details):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                if self.database.is_postgres:
                    db.execute('LOCK TABLE audit_log IN EXCLUSIVE MODE')
                else:
                    db.execute('BEGIN IMMEDIATE')
                last = db.execute('SELECT line FROM audit_log ORDER BY seq DESC LIMIT 1').fetchone()
                event = {'timestamp': datetime.now(timezone.utc).isoformat(), 'action': action,
                         'actor': actor, 'details': details,
                         'prev_hash': json.loads(last[0])['hash'] if last else GENESIS}
                event['hash'] = _digest(event)
                db.execute('INSERT INTO audit_log (line) VALUES (?)', (json.dumps(event, ensure_ascii=False),))
        return event

    def verify(self):
        self.database.initialise()
        with self.database.connect() as db:
            rows = db.execute('SELECT seq, line FROM audit_log ORDER BY seq').fetchall()
        previous, count = GENESIS, 0
        for row in rows:
            try:
                event = json.loads(row[1])
            except ValueError:
                return {'ok': False, 'entries': count, 'head': previous, 'broken_at': count + 1}
            if event.get('prev_hash') != previous or event.get('hash') != _digest(event):
                return {'ok': False, 'entries': count, 'head': previous, 'broken_at': count + 1}
            previous, count = event['hash'], count + 1
        return {'ok': True, 'entries': count, 'head': previous, 'broken_at': None}


def password_hash(password, *, salt=None, iterations=310_000):
    import os
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), iterations).hex()
    return f'pbkdf2_sha256${iterations}${salt}${digest}'


def password_matches(password, stored):
    import hmac
    try:
        scheme, iterations, salt, _ = stored.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        return hmac.compare_digest(password_hash(password, salt=salt, iterations=int(iterations)), stored)
    except (ValueError, AttributeError):
        return False


ROLES = ('member', 'admin')


class UserStore:
    """Accounts held in the server database. Passwords are stored only as PBKDF2 hashes."""

    def __init__(self, database):
        self.database = database

    def create(self, username, password, role='member', replace=False):
        from src.auth import normalize_username, validate_password
        username = normalize_username(username)
        validate_password(password)
        if role not in ROLES:
            raise ValueError(f'Role must be one of: {", ".join(ROLES)}.')
        self.database.initialise()
        now = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as db:
            with db:
                exists = db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
                if exists and not replace:
                    raise ValueError('That account exists. Use --replace to change its password or role.')
                if exists:
                    db.execute('UPDATE users SET password_hash=?, role=?, active=1 WHERE username=?',
                               (password_hash(password), role, username))
                else:
                    db.execute('INSERT INTO users (username, password_hash, role, active, created) VALUES (?,?,?,?,?)',
                               (username, password_hash(password), role, 1, now))
        return username

    def set_active(self, username, active):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                count = db.execute('UPDATE users SET active=? WHERE username=?',
                                   (1 if active else 0, username.strip().lower())).rowcount
        if not count:
            raise ValueError('No such account.')

    def get(self, username):
        self.database.initialise()
        with self.database.connect() as db:
            row = db.execute('SELECT username, password_hash, role, active, created FROM users WHERE username=?',
                             (username.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def list(self):
        self.database.initialise()
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT username, role, active, created FROM users ORDER BY username')]

    def authenticate(self, username, password):
        if not password or len(password) > 1024:
            return None
        user = self.get(username or '')
        # Hash even for unknown users so timing does not reveal which names exist.
        stored = user['password_hash'] if user else password_hash('x', salt='0' * 32)
        if password_matches(password, stored) and user and user['active']:
            return user
        return None
