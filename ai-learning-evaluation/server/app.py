"""Insight Hub API: shared report library, review handoff, audit chain and accounts.

Run locally:   uvicorn server.app:app --reload        (from ai-learning-evaluation/)
On Render:     uvicorn server.app:app --host 0.0.0.0 --port $PORT
Configuration: DATABASE_URL (Neon pooled URL), optional DATABASE_URL_UNPOOLED, SECRET_KEY, optional ADMIN_USERNAME / ADMIN_PASSWORD.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.storage.database import Database, DatabaseAuditTrail, DatabaseReportRepository, UserStore
from server.security import issue_token, read_token

log = logging.getLogger('insight_hub.server')


class Services:
    def __init__(self, url, direct_url=None):
        self.database = Database(url, direct_url)
        self.reports = DatabaseReportRepository(self.database)
        # SQLite allows one writer per file, and an approval writes the audit chain while the
        # report row is locked, so a SQLite server keeps its audit chain in a second file.
        audit_database = self.database if self.database.is_postgres else Database(url + '.audit')
        self.audit = DatabaseAuditTrail(audit_database)
        self.users = UserStore(self.database)


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
        if user is None or not user['active']:
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
    class Login(BaseModel):
        username: str = Field(max_length=64)
        password: str = Field(max_length=1024)

    @app.post('/auth/login')
    def login(body: Login):
        user = services.users.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(401, 'Username or password is incorrect.')
        return {'token': issue_token(user['username'], user['role']),
                'username': user['username'], 'role': user['role']}

    @app.get('/auth/me')
    def me(user=Depends(current_user)):
        return {'username': user['username'], 'role': user['role']}

    class NewUser(BaseModel):
        username: str = Field(max_length=64)
        password: str = Field(max_length=1024)
        role: Literal['member', 'admin'] = 'member'
        replace: bool = False

    @app.get('/users')
    def list_users(admin=Depends(admin_user)):
        return services.users.list()

    @app.post('/users')
    def create_user(body: NewUser, admin=Depends(admin_user)):
        name = services.users.create(body.username, body.password, body.role, replace=body.replace)
        services.audit.append('Account saved', admin['username'], account=name, role=body.role)
        return {'username': name, 'role': body.role}

    @app.post('/users/{username}/active')
    def set_active(username: str, active: bool, admin=Depends(admin_user)):
        if username == admin['username'] and not active:
            raise ValueError('You cannot disable your own account.')
        services.users.set_active(username, active)
        services.audit.append('Account enabled' if active else 'Account disabled', admin['username'], account=username)
        return {'username': username, 'active': active}

    # ---- report library --------------------------------------------------------------------
    @app.get('/reports')
    def list_reports(view: Literal['mine', 'pending', 'approved'] = 'mine', user=Depends(current_user)):
        actor = user['username']
        if view == 'pending' and user['role'] != 'admin':
            return []   # only administrators receive review requests
        return {'mine': services.reports.list_owned, 'pending': services.reports.list_pending,
                'approved': services.reports.list_approved}[view](actor)

    @app.get('/reports/{report_id}')
    def load_report(report_id: str, user=Depends(current_user)):
        row = services.reports.load(report_id, user['username'])
        if row['owner'] != user['username'] and user['role'] != 'admin':
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

    @app.post('/reports/{report_id}/transition')
    def transition(report_id: str, body: Transition, user=Depends(current_user)):
        if body.action != 'submit' and user['role'] != 'admin':
            raise HTTPException(403, 'Only an administrator can return or approve a submitted report.')
        from src.storage.snapshot import pack
        version, state = services.reports.transition(actor=user['username'], report_id=report_id,
            version=body.version, action=body.action, notes=body.notes, role=body.role,
            confirmed=body.confirmed, audit=services.audit)
        return {'version': version, 'snapshot': pack(state)}

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

    return app


app = create_app()
