"""Insight Hub API: shared report library, review handoff, audit chain and accounts.

Run locally:   uvicorn server.app:app --reload        (from ai-learning-evaluation/)
On Render:     uvicorn server.app:app --host 0.0.0.0 --port $PORT
Configuration: DATABASE_URL (Neon pooled URL), optional DATABASE_URL_UNPOOLED, SECRET_KEY,
optional ADMIN_USERNAME / ADMIN_PASSWORD, optional GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
(a Google OAuth "Desktop app" client) to enable Sign in with Google.
"""
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.storage.database import (NO_PASSWORD, Database, DatabaseAuditTrail, DatabaseReportRepository,
                                  UserStore, password_matches)
from server.security import issue_token, read_token

log = logging.getLogger('insight_hub.server')
APP_FOLDER = Path(__file__).resolve().parents[1]
WEB_FOLDER = APP_FOLDER / 'web'

try:  # Local runs read ai-learning-evaluation/.env; on Render the dashboard variables are used.
    from dotenv import load_dotenv
    load_dotenv(APP_FOLDER / '.env', override=False)
except ImportError:
    pass


class Services:
    def __init__(self, url, direct_url=None):
        self.database = Database(url, direct_url)
        self.reports = DatabaseReportRepository(self.database)
        # SQLite allows one writer per file, and an approval writes the audit chain while the
        # report row is locked, so a SQLite server keeps its audit chain in a second file.
        audit_database = self.database if self.database.is_postgres else Database(url + '.audit')
        self.audit = DatabaseAuditTrail(audit_database)
        self.users = UserStore(self.database)
        self.verify_google = verify_google_token


def google_config():
    return os.getenv('GOOGLE_CLIENT_ID', '').strip(), os.getenv('GOOGLE_CLIENT_SECRET', '').strip()


def verify_google_token(token):
    """Check a Google ID token's signature, expiry, issuer and audience. Returns its claims."""
    audiences = [a for a in (google_config()[0], os.getenv('GOOGLE_WEB_CLIENT_ID', '').strip()) if a]
    if not audiences:
        raise ValueError('Google sign-in is not set up on this server.')
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    try:
        return id_token.verify_oauth2_token(token, google_requests.Request(), audiences)
    except ValueError:
        raise ValueError('Google sign-in could not be verified. Please try again.') from None


def default_database_url():
    url = os.getenv('DATABASE_URL', '').strip()
    if url:
        return url
    # Development fallback only: a SQLite file next to the project.
    return str(Path(__file__).resolve().parents[1] / 'reports' / 'server_dev.sqlite3')


def bootstrap_admin(users):
    """Render's free plan has no shell, so the first admin can come from environment variables."""
    name, password = os.getenv('ADMIN_USERNAME', '').strip(), os.getenv('ADMIN_PASSWORD', '')
    if name and password and users.get(name) is None:
        users.create(name, password, role='admin')
        log.warning('Created admin account %s from ADMIN_USERNAME.', name)


def create_app(database_url=None):
    services = Services(database_url or default_database_url(),
                        None if database_url else os.getenv('DATABASE_URL_UNPOOLED', '').strip() or None)

    @asynccontextmanager
    async def lifespan(app):
        services.database.initialise()
        bootstrap_admin(services.users)
        if not os.getenv('SECRET_KEY'):
            log.warning('SECRET_KEY is not set: sign-ins will expire whenever the server restarts.')
        yield

    app = FastAPI(title='Learning Futures Insight Hub API', version='1.0', lifespan=lifespan)
    app.state.services = services

    @app.exception_handler(ValueError)
    def value_error(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={'detail': str(exc)})

    def current_user(authorization: str = Header(default='')):
        claims = read_token(authorization.removeprefix('Bearer ').strip())
        if claims is None:
            raise HTTPException(401, 'Your session has expired. Sign out and sign in again.')
        user = services.users.get(claims['u'])
        if user is None or not user['active'] or not user['approved']:
            raise HTTPException(401, 'This account is disabled. Contact your administrator.')
        return user

    def admin_user(user=Depends(current_user)):
        if user['role'] != 'admin':
            raise HTTPException(403, 'Only an administrator can manage accounts.')
        return user

    # ---- service ---------------------------------------------------------------------------
    @app.get('/health')
    def health():
        services.database.initialise()
        return {'ok': True, 'database': 'postgres' if services.database.is_postgres else 'sqlite'}

    # ---- accounts --------------------------------------------------------------------------
    PENDING = 'Your account is waiting for administrator approval. You can sign in once it is approved.'

    def session(user):
        if not user['approved']:
            raise HTTPException(403, PENDING)
        return {'token': issue_token(user['username'], user['role']), 'username': user['username'],
                'role': user['role'], 'display_name': user['display_name']}

    def profile(user):
        return {'username': user['username'], 'role': user['role'], 'display_name': user['display_name'],
                'email': user['email'], 'google': bool(user['google_sub']),
                'has_password': user['password_hash'] != NO_PASSWORD}

    class Login(BaseModel):
        username: str = Field(max_length=64)
        password: str = Field(max_length=1024)

    @app.post('/auth/login')
    def login(body: Login):
        user = services.users.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(401, 'Username or password is incorrect.')
        return session(user)

    class Register(BaseModel):
        username: str = Field(max_length=64)
        password: str = Field(max_length=1024)
        email: str = Field(max_length=254)
        display_name: str = Field(default='', max_length=80)

    @app.post('/auth/register')
    def register(body: Register):
        if not body.email.strip():
            raise ValueError('Enter your email address.')
        name = services.users.create(body.username, body.password, 'member', email=body.email,
                                     display_name=body.display_name, approved=False)
        services.audit.append('Account requested', name, account=name, method='password')
        return {'username': name, 'pending': True, 'detail': PENDING}

    @app.get('/auth/google/config')
    def google_client():
        # A Desktop-app OAuth client's secret is not confidential (Google documents this);
        # serving it lets every PC use Google sign-in with only SERVER_URL configured.
        client_id, client_secret = google_config()
        return {'enabled': bool(client_id), 'client_id': client_id, 'client_secret': client_secret}

    class GoogleToken(BaseModel):
        id_token: str = Field(max_length=8192)

    def google_identity(token):
        claims = services.verify_google(token)
        if not claims.get('email_verified'):
            raise ValueError('Use a Google account with a verified email address.')
        return claims['sub'], claims['email'].lower(), claims.get('name', '')

    @app.post('/auth/google')
    def google_login(body: GoogleToken):
        sub, email, name = google_identity(body.id_token)
        user = services.users.by_google(sub)
        if user is None:
            user = services.users.by_email(email)
            if user is not None:      # Google proved this address: connect it to the account.
                services.users.set_google(user['username'], sub, email)
                services.audit.append('Google connected', user['username'], account=user['username'])
            else:
                username = services.users.create(services.users.free_username(email), None, 'member',
                    email=email, display_name=name, approved=False, google_sub=sub)
                services.audit.append('Account requested', username, account=username, method='google')
                return JSONResponse(status_code=202, content={'username': username, 'pending': True,
                                                              'detail': PENDING})
        if not user['active']:
            raise HTTPException(401, 'This account is disabled. Contact your administrator.')
        return session(user)

    @app.get('/auth/me')
    def me(user=Depends(current_user)):
        return profile(user)

    class ProfileChange(BaseModel):
        display_name: str | None = Field(default=None, max_length=80)
        email: str | None = Field(default=None, max_length=254)
        current_password: str = Field(default='', max_length=1024)

    @app.patch('/auth/me')
    def update_me(body: ProfileChange, user=Depends(current_user)):
        if body.email is not None and body.email.strip().lower() != user['email']:
            # Changing the contact address needs the password (when the account has one).
            if user['password_hash'] != NO_PASSWORD and not password_matches(body.current_password, user['password_hash']):
                raise ValueError('Enter your current password to change your email address.')
        services.users.update_profile(user['username'], display_name=body.display_name, email=body.email)
        services.audit.append('Profile updated', user['username'], account=user['username'])
        return profile(services.users.get(user['username']))

    class PasswordChange(BaseModel):
        current_password: str = Field(default='', max_length=1024)
        new_password: str = Field(max_length=1024)

    @app.post('/auth/password')
    def change_password(body: PasswordChange, user=Depends(current_user)):
        if user['password_hash'] != NO_PASSWORD and not password_matches(body.current_password, user['password_hash']):
            raise ValueError('Your current password is incorrect.')
        services.users.set_password(user['username'], body.new_password)
        services.audit.append('Password changed', user['username'], account=user['username'])
        return {'ok': True}

    @app.post('/auth/google/link')
    def link_google(body: GoogleToken, user=Depends(current_user)):
        sub, email, _ = google_identity(body.id_token)
        services.users.set_google(user['username'], sub, email)
        services.audit.append('Google connected', user['username'], account=user['username'])
        return profile(services.users.get(user['username']))

    @app.delete('/auth/google/link')
    def unlink_google(user=Depends(current_user)):
        if user['password_hash'] == NO_PASSWORD:
            raise ValueError('Set a password first, otherwise you could not sign in without Google.')
        services.users.set_google(user['username'], '')
        services.audit.append('Google disconnected', user['username'], account=user['username'])
        return profile(services.users.get(user['username']))

    # ---- administration ------------------------------------------------------------------
    class NewUser(BaseModel):
        username: str = Field(max_length=64)
        password: str = Field(max_length=1024)
        role: Literal['member', 'admin'] = 'member'
        replace: bool = False
        email: str = Field(default='', max_length=254)
        display_name: str = Field(default='', max_length=80)

    @app.get('/users')
    def list_users(admin=Depends(admin_user)):
        return services.users.list()

    @app.post('/users')
    def create_user(body: NewUser, admin=Depends(admin_user)):
        name = services.users.create(body.username, body.password, body.role, replace=body.replace,
                                     email=body.email, display_name=body.display_name)
        services.audit.append('Account saved', admin['username'], account=name, role=body.role)
        return {'username': name, 'role': body.role}

    def not_self(admin, username, what):
        if username.strip().lower() == admin['username']:
            raise ValueError(f'You cannot {what} your own account.')

    @app.post('/users/{username}/approve')
    def approve_user(username: str, admin=Depends(admin_user)):
        services.users.approve(username)
        services.audit.append('Account approved', admin['username'], account=username)
        return {'username': username, 'approved': True}

    @app.post('/users/{username}/reject')
    def reject_user(username: str, admin=Depends(admin_user)):
        services.users.delete_pending(username)
        services.audit.append('Account request rejected', admin['username'], account=username)
        return {'username': username, 'rejected': True}

    @app.post('/users/{username}/active')
    def set_active(username: str, active: bool, admin=Depends(admin_user)):
        if not active:
            not_self(admin, username, 'disable')
        services.users.set_active(username, active)
        services.audit.append('Account enabled' if active else 'Account disabled', admin['username'], account=username)
        return {'username': username, 'active': active}

    class RoleChange(BaseModel):
        role: Literal['member', 'admin']

    @app.post('/users/{username}/role')
    def set_role(username: str, body: RoleChange, admin=Depends(admin_user)):
        if body.role != 'admin':
            not_self(admin, username, 'remove administrator rights from')
        services.users.set_role(username, body.role)
        services.audit.append('Role changed', admin['username'], account=username, role=body.role)
        return {'username': username, 'role': body.role}

    class PasswordReset(BaseModel):
        new_password: str = Field(max_length=1024)

    @app.post('/users/{username}/password')
    def reset_password(username: str, body: PasswordReset, admin=Depends(admin_user)):
        services.users.set_password(username, body.new_password)
        services.audit.append('Password reset', admin['username'], account=username)
        return {'username': username}

    # ---- report library --------------------------------------------------------------------
    def reviewers(author):
        """Who an author may send a report to: never themselves. Members send to administrators;
        an administrator's own report can go to another administrator or to a team member."""
        people = [u for u in services.users.list()
                  if u['approved'] and u['active'] and u['username'] != author['username']
                  and (u['role'] == 'admin' or author['role'] == 'admin')]
        people.sort(key=lambda u: (u['role'] != 'admin', (u['display_name'] or u['username']).lower()))
        return [{'username': u['username'], 'display_name': u['display_name'] or u['username'], 'role': u['role']}
                for u in people]

    def may_review(user, row):
        """The person a report was sent to, or any administrator when it was sent to no one in particular."""
        return row['reviewer'] == user['username'] or (not row['reviewer'] and user['role'] == 'admin')

    def with_names(rows):
        names = {u['username']: u['display_name'] or u['username'] for u in services.users.list()}
        for row in rows:
            row['owner_name'] = names.get(row['owner'], row['owner'])
            row['reviewer_name'] = names.get(row['reviewer'], row['reviewer']) if row.get('reviewer') else ''
        return rows

    @app.get('/reports')
    def list_reports(view: Literal['mine', 'pending', 'approved'] = 'mine', user=Depends(current_user)):
        actor = user['username']
        if view == 'pending':
            return with_names([r for r in services.reports.list_pending(actor) if may_review(user, r)])
        return with_names({'mine': services.reports.list_owned,
                           'approved': services.reports.list_approved}[view](actor))

    @app.get('/api/reviewers')
    def list_reviewers(user=Depends(current_user)):
        return reviewers(user)

    @app.get('/reports/{report_id}')
    def load_report(report_id: str, user=Depends(current_user)):
        row = services.reports.load(report_id, user['username'])
        if row['owner'] != user['username'] and user['role'] != 'admin' and row['reviewer'] != user['username']:
            raise ValueError('This report is unavailable for this account.')
        return row

    class Save(BaseModel):
        title: str = Field(max_length=300)
        course: str = Field(max_length=300)
        status: str
        snapshot: dict
        report_id: str | None = None
        version: int | None = None

    @app.post('/reports')
    def save_report(body: Save, user=Depends(current_user)):
        from src.storage.snapshot import unpack
        # Reject malformed snapshots and status mismatches before anything is stored.
        try:
            state = unpack(body.snapshot)
        except Exception:
            raise ValueError('The saved workspace could not be read. Reopen the report and try again.') from None
        if state['workflow'].status != body.status:
            raise ValueError('The saved review state does not match the report status.')
        report_id, version = services.reports.save(actor=user['username'], title=body.title, course=body.course,
            status=body.status, snapshot=body.snapshot, report_id=body.report_id, version=body.version)
        return {'id': report_id, 'version': version}

    class Rename(BaseModel):
        version: int
        title: str = Field(max_length=300)

    @app.post('/reports/{report_id}/rename')
    def rename_report(report_id: str, body: Rename, user=Depends(current_user)):
        return {'version': services.reports.rename(actor=user['username'], report_id=report_id,
                                                   version=body.version, title=body.title)}

    @app.delete('/reports/{report_id}')
    def delete_report(report_id: str, version: int, user=Depends(current_user)):
        services.reports.delete(actor=user['username'], report_id=report_id, version=version)
        return {'deleted': report_id}

    class Transition(BaseModel):
        version: int
        action: Literal['submit', 'return', 'approve']
        notes: str = Field(default='', max_length=5000)
        role: str = Field(default='', max_length=200)
        confirmed: bool = False
        reviewer: str = Field(default='', max_length=64)   # submit: who should review it
        clear: dict | None = None                           # approve: the reviewer's CLEAR answers

    def review_started(report_id, reviewer):
        """When this reviewer first opened the report since it was last sent for review."""
        started = None
        for event in services.audit.events({'Review requested', 'Submitted for review', 'Review opened'}):
            if event.get('details', {}).get('report_id') != report_id:
                continue
            if event['action'] != 'Review opened':
                started = None          # a new submission restarts the clock
            elif event.get('actor') == reviewer and started is None:
                started = datetime.fromisoformat(event['timestamp'])
        return started

    @app.post('/reports/{report_id}/transition')
    def transition(report_id: str, body: Transition, user=Depends(current_user)):
        assigned = ''
        if body.action == 'submit':
            choices = {r['username']: r for r in reviewers(user)}
            assigned = body.reviewer.strip().lower()
            if assigned and assigned not in choices:
                raise ValueError('Choose someone other than yourself to review this report'
                                 + ('.' if user['role'] == 'admin' else ': members send reports to an administrator.'))
            if not assigned and user['role'] != 'admin' and len(choices) == 1:
                assigned = next(iter(choices))       # the only possible reviewer
            if not assigned and user['role'] == 'admin':
                raise ValueError('Choose who should review your report.')
        else:
            row = services.reports.load(report_id, user['username'])
            if row['status'] == 'AWAITING HUMAN REVIEW' and not may_review(user, row):
                raise HTTPException(403, f"This report was sent to {row['reviewer']} for review." if row['reviewer']
                                    else 'Only an administrator can return or approve this report.')
        from src.storage.snapshot import pack
        clear = dict(body.clear) if body.clear is not None else None
        if clear is not None and body.action == 'approve':
            started = review_started(report_id, user['username'])
            if started is not None:   # measured by the server, not the browser
                clear['seconds'] = (datetime.now(timezone.utc) - started).total_seconds()
        version, state = services.reports.transition(actor=user['username'], report_id=report_id,
            version=body.version, action=body.action, notes=body.notes, role=body.role,
            confirmed=body.confirmed, audit=services.audit, clear=clear)
        if assigned:
            services.reports.assign_reviewer(report_id, version, assigned)
        if body.action == 'submit':
            services.audit.append('Review requested', user['username'], report_id=report_id, reviewer=assigned)
        return {'version': version, 'snapshot': pack(state), 'reviewer': assigned}

    # ---- audit chain -----------------------------------------------------------------------
    class AuditEvent(BaseModel):
        action: str = Field(max_length=200)
        actor: str = Field(default='', max_length=200)
        details: dict = Field(default_factory=dict)

    @app.post('/audit')
    def append_audit(body: AuditEvent, user=Depends(current_user)):
        details = {k: v for k, v in body.details.items() if k not in ('action', 'actor')}
        details['account'] = user['username']   # the signed-in account, not a typed name
        return services.audit.append(body.action, body.actor or user['username'], **details)

    @app.get('/audit/verify')
    def verify_audit(user=Depends(current_user)):
        return services.audit.verify()

    from server.web_api import build_router
    app.include_router(build_router(services, current_user))

    if WEB_FOLDER.is_dir():
        # The browser app. Registered last so every API route above takes precedence.
        from fastapi.staticfiles import StaticFiles
        app.mount('/', StaticFiles(directory=WEB_FOLDER, html=True), name='web')

    return app


app = create_app()
