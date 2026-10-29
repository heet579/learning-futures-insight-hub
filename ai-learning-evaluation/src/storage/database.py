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
CLEAR_DRAFTS_TABLE = '''CREATE TABLE IF NOT EXISTS clear_review_drafts (
    report_id TEXT NOT NULL, reviewer TEXT NOT NULL, report_version INTEGER NOT NULL,
    answers TEXT NOT NULL, updated TEXT NOT NULL,
    PRIMARY KEY (report_id, reviewer))'''


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


# Saved reports contain the whole survey dataset. Large values are stored zlib-compressed
# (about 25 times smaller) so each save and load moves little data to and from the database.
COMPRESSED = 'zlib:'
COMPRESS_FROM = 64 * 1024


def _pack_value(value):
    if isinstance(value, str) and len(value) >= COMPRESS_FROM and not value.startswith(COMPRESSED):
        import base64
        import zlib
        return COMPRESSED + base64.b64encode(zlib.compress(value.encode('utf-8'), 6)).decode('ascii')
    return value


def _unpack_value(value):
    if isinstance(value, str) and value.startswith(COMPRESSED):
        import base64
        import zlib
        return zlib.decompress(base64.b64decode(value[len(COMPRESSED):])).decode('utf-8')
    return value


class _Cursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.rowcount = cursor.rowcount
        self._names = [c.name for c in cursor.description] if cursor.description else []

    def fetchone(self):
        row = self._cursor.fetchone()
        return None if row is None else Row(self._names, [_unpack_value(v) for v in row])

    def fetchall(self):
        return [Row(self._names, [_unpack_value(v) for v in row]) for row in self._cursor.fetchall()]

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
        cursor.execute(sql.replace('?', '%s'), tuple(_pack_value(p) for p in params))
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


def _pool_available():
    try:
        import psycopg_pool  # noqa: F401
        return True
    except ImportError:
        return False


class Database:
    """One storage location: a postgresql:// URL, or a SQLite file path for tests and local runs."""

    def __init__(self, url, direct_url=None):
        """`url` carries the app's queries (Neon: the pooled -pooler URL). `direct_url`
        (Neon: DATABASE_URL_UNPOOLED) is used only to create tables, as Neon recommends
        for schema changes; without it the main URL is used."""
        if not url:
            raise ValueError('DATABASE_URL is not set.')
        self.is_postgres = url.startswith(('postgres://', 'postgresql://'))
        self.url = normalise_url(url) if self.is_postgres else str(Path(url).expanduser())
        self.direct_url = normalise_url(direct_url) if self.is_postgres and direct_url else self.url
        self._ready = False

    def describe(self):
        if not self.is_postgres:
            return f'SQLite {self.url}'
        parts = urlsplit(self.url)
        return f'Postgres {parts.hostname}{parts.path}'

    def _pool(self):
        """Reuse open connections instead of a new TLS handshake for every query."""
        if getattr(self, '_connection_pool', None) is None:
            import atexit
            from psycopg_pool import ConnectionPool
            # max_idle stays below Neon's 5-minute scale-to-zero; check() drops stale connections.
            self._connection_pool = ConnectionPool(
                self.url, min_size=0, max_size=6, max_idle=240, timeout=30, open=True,
                check=ConnectionPool.check_connection,
                kwargs={'connect_timeout': 20, 'prepare_threshold': None})
            atexit.register(self._connection_pool.close)
        return self._connection_pool

    @contextmanager
    def connect(self, direct=False):
        if self.is_postgres and not direct and _pool_available():
            with self._pool().connection() as raw:
                yield PostgresConnection(raw)
            return
        if self.is_postgres:
            import psycopg
            # prepare_threshold=None: no server-side prepared statements, which a
            # transaction-mode connection pooler (Neon's -pooler endpoint) cannot track.
            raw = psycopg.connect(self.direct_url if direct else self.url,
                                  connect_timeout=20, prepare_threshold=None)
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
        try:
            self._create_tables(direct=True)
        except Exception:
            if not self.is_postgres or self.direct_url == self.url:
                raise
            # The direct endpoint is unreachable (for example a DNS hiccup): the pooled
            # connection can create or check the tables too.
            self._create_tables(direct=False)
        self._ready = True

    def _create_tables(self, direct):
        with self.connect(direct=direct) as db:
            with db:
                db.execute(REPORTS_TABLE)
                db.execute(USERS_TABLE)
                db.execute(AUDIT_TABLE_PG if self.is_postgres else AUDIT_TABLE_SQLITE)
                db.execute(CLEAR_DRAFTS_TABLE)
                self._migrate_users(db)

    def _migrate_users(self, db):
        """Add the self-service account columns to databases created before them."""
        added = [('approved', "INTEGER NOT NULL DEFAULT 1"), ('email', "TEXT NOT NULL DEFAULT ''"),
                 ('display_name', "TEXT NOT NULL DEFAULT ''"), ('google_sub', "TEXT NOT NULL DEFAULT ''")]
        if self.is_postgres:
            for name, kind in added:
                db.execute(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {kind}')
        else:
            existing = {row[1] for row in db.execute('PRAGMA table_info(users)')}
            for name, kind in added:
                if name not in existing:
                    db.execute(f'ALTER TABLE users ADD COLUMN {name} {kind}')


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

    def assign_reviewer(self, report_id, version, reviewer):
        """Record who a submitted report was sent to (the reviewer column until a decision)."""
        with self.connect() as db:
            db.execute("UPDATE reports SET reviewer=? WHERE id=? AND version=? AND status='AWAITING HUMAN REVIEW'",
                       (reviewer, report_id, version))

    def save_clear_draft(self, report_id, reviewer, report_version, answers):
        """Save one reviewer's unfinished CLEAR answers without changing the report."""
        now = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(answers, ensure_ascii=False)
        with self.connect() as db:
            db.execute('INSERT INTO clear_review_drafts '
                       '(report_id, reviewer, report_version, answers, updated) VALUES (?,?,?,?,?) '
                       'ON CONFLICT(report_id, reviewer) DO UPDATE SET '
                       'report_version=excluded.report_version, answers=excluded.answers, updated=excluded.updated',
                       (report_id, reviewer, report_version, encoded, now))

    def load_clear_draft(self, report_id, reviewer, report_version):
        """Return only the draft for this reviewer and current report version."""
        with self.connect() as db:
            row = db.execute('SELECT answers FROM clear_review_drafts '
                             'WHERE report_id=? AND reviewer=? AND report_version=?',
                             (report_id, reviewer, report_version)).fetchone()
        if not row:
            return {}
        try:
            value = json.loads(row[0])
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def delete_clear_drafts(self, report_id):
        """Discard stale unfinished answers after a successful workflow transition."""
        with self.connect() as db:
            db.execute('DELETE FROM clear_review_drafts WHERE report_id=?', (report_id,))


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

    def events(self, actions=None):
        """Audit events in order, optionally only these actions (read-only; used by the oversight panel)."""
        self.database.initialise()
        with self.database.connect() as db:
            rows = db.execute('SELECT line FROM audit_log ORDER BY seq').fetchall()
        out = []
        for row in rows:
            try:
                event = json.loads(row[0])
            except ValueError:
                continue
            if actions is None or event.get('action') in actions:
                out.append(event)
        return out

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
NO_PASSWORD = '!'          # Google-only accounts: no password sign-in until one is set
USER_COLUMNS = 'username, password_hash, role, active, created, approved, email, display_name, google_sub'
EMAIL_PATTERN = r'[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,63}'


def normalize_email(email):
    import re
    email = (email or '').strip().lower()
    if email and not re.fullmatch(EMAIL_PATTERN, email):
        raise ValueError('Enter a valid email address.')
    return email


def clean_display_name(name):
    name = ' '.join((name or '').split())
    if len(name) > 80:
        raise ValueError('Use a name of up to 80 characters.')
    return name


class UserStore:
    """Accounts held in the server database. Passwords are stored only as PBKDF2 hashes.

    `approved` is 0 for self-registered accounts until an administrator approves them;
    `active` is 0 for accounts an administrator has disabled."""

    def __init__(self, database):
        self.database = database

    def _check_unique(self, db, username, email='', google_sub=''):
        if email and db.execute('SELECT 1 FROM users WHERE email=? AND username!=?', (email, username)).fetchone():
            raise ValueError('An account already uses that email address.')
        if google_sub and db.execute('SELECT 1 FROM users WHERE google_sub=? AND username!=?',
                                     (google_sub, username)).fetchone():
            raise ValueError('That Google account is already connected to another account.')

    def create(self, username, password, role='member', replace=False, *, email='', display_name='',
               approved=True, google_sub=''):
        from src.auth import normalize_username, validate_password
        username = normalize_username(username)
        if password is not None:
            validate_password(password)
        if role not in ROLES:
            raise ValueError(f'Role must be one of: {", ".join(ROLES)}.')
        email, display_name = normalize_email(email), clean_display_name(display_name)
        stored = password_hash(password) if password is not None else NO_PASSWORD
        self.database.initialise()
        now = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as db:
            with db:
                exists = db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
                if exists and not replace:
                    raise ValueError('That username is taken. Choose another one.' if not approved else
                                     'That account exists. Use --replace to change its password or role.')
                self._check_unique(db, username, email, google_sub)
                if exists:
                    db.execute('UPDATE users SET password_hash=?, role=?, active=1, approved=1 WHERE username=?',
                               (stored, role, username))
                    if email or display_name:
                        db.execute("UPDATE users SET email=CASE WHEN ?='' THEN email ELSE ? END, "
                                   "display_name=CASE WHEN ?='' THEN display_name ELSE ? END WHERE username=?",
                                   (email, email, display_name, display_name, username))
                else:
                    db.execute('INSERT INTO users (username, password_hash, role, active, created, approved, '
                               'email, display_name, google_sub) VALUES (?,?,?,?,?,?,?,?,?)',
                               (username, stored, role, 1, now, 1 if approved else 0, email, display_name, google_sub))
        return username

    def _update(self, username, sql, params):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                count = db.execute(f'UPDATE users SET {sql} WHERE username=?',
                                   (*params, username.strip().lower())).rowcount
        if not count:
            raise ValueError('No such account.')

    def set_active(self, username, active):
        self._update(username, 'active=?', (1 if active else 0,))

    def approve(self, username):
        self._update(username, 'approved=1, active=1', ())

    def set_role(self, username, role):
        if role not in ROLES:
            raise ValueError(f'Role must be one of: {", ".join(ROLES)}.')
        self._update(username, 'role=?', (role,))

    def set_password(self, username, password):
        from src.auth import validate_password
        validate_password(password)
        self._update(username, 'password_hash=?', (password_hash(password),))

    def update_profile(self, username, *, display_name=None, email=None):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                if email is not None:
                    email = normalize_email(email)
                    self._check_unique(db, username, email)
                    db.execute('UPDATE users SET email=? WHERE username=?', (email, username))
                if display_name is not None:
                    db.execute('UPDATE users SET display_name=? WHERE username=?',
                               (clean_display_name(display_name), username))

    def set_google(self, username, google_sub, email=''):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                self._check_unique(db, username, '', google_sub)
                db.execute("UPDATE users SET google_sub=?, email=CASE WHEN email='' THEN ? ELSE email END "
                           "WHERE username=?", (google_sub, email, username))

    def delete_pending(self, username):
        self.database.initialise()
        with self.database.connect() as db:
            with db:
                count = db.execute('DELETE FROM users WHERE username=? AND approved=0', (username,)).rowcount
        if not count:
            raise ValueError('Only an account that is still waiting for approval can be rejected.')

    def _one(self, column, value):
        self.database.initialise()
        with self.database.connect() as db:
            row = db.execute(f'SELECT {USER_COLUMNS} FROM users WHERE {column}=?', (value,)).fetchone()
        return dict(row) if row else None

    def get(self, username):
        return self._one('username', (username or '').strip().lower())

    def by_google(self, google_sub):
        return self._one('google_sub', google_sub) if google_sub else None

    def by_email(self, email):
        return self._one('email', email.strip().lower()) if email else None

    def free_username(self, email):
        """Suggest an unused username from an email address (heet.patel@gmail.com -> heet.patel)."""
        import re
        base = re.sub(r'[^a-z0-9_.-]', '', email.split('@')[0].lower()).strip('.-_')[:40] or 'user'
        name, number = base, 1
        while self.get(name) is not None:
            number += 1
            name = f'{base}{number}'
        return name

    def list(self):
        self.database.initialise()
        with self.database.connect() as db:
            rows = [dict(row) for row in db.execute(f'SELECT {USER_COLUMNS} FROM users ORDER BY approved, username')]
        for row in rows:
            row['has_password'] = row.pop('password_hash') != NO_PASSWORD
            row['google'] = bool(row.pop('google_sub'))
        return rows

    def authenticate(self, username, password):
        """Return the user for a correct password (approved or not), else None."""
        if not password or len(password) > 1024:
            return None
        user = self.get(username or '')
        # Hash even for unknown users so timing does not reveal which names exist.
        stored = user['password_hash'] if user else password_hash('x', salt='0' * 32)
        if password_matches(password, stored) and user and user['active']:
            return user
        return None
