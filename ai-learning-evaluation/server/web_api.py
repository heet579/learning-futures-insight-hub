"""API for the browser app: create a report from uploaded files and work through every review step.

Each change loads the saved report, applies one workspace operation (src/workspace.py) and saves
it with an optimistic version check, so the browser and the desktop app share the same reports.
"""
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src import workspace
from src.storage.snapshot import pack, unpack

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SUFFIXES = {'.csv', '.xlsx', '.xls'}


def build_router(services, current_user):
    router = APIRouter(prefix='/api')

    def meta(row):
        return {key: row[key] for key in ('id', 'title', 'owner', 'status', 'version', 'reviewer', 'updated', 'course')}

    def permissions(row, state, user):
        status = state['workflow'].status
        can_edit = row['owner'] == user['username'] and status in workspace.EDITABLE
        assigned_to_me = row['reviewer'] == user['username'] or (not row['reviewer'] and user['role'] == 'admin')
        can_review = row['owner'] != user['username'] and status == 'AWAITING HUMAN REVIEW' and assigned_to_me
        return can_edit, can_review

    def open_report(report_id, user):
        row = services.reports.load(report_id, user['username'])
        if row['owner'] != user['username'] and user['role'] != 'admin' and row['reviewer'] != user['username']:
            raise ValueError('This report is unavailable for this account.')
        return row, unpack(row['snapshot'])

    def payload(row, state, user, **extra):
        can_edit, can_review = permissions(row, state, user)
        names = {u['username']: u['display_name'] or u['username'] for u in services.users.list()}
        report = meta(row)
        report.update(owner_name=names.get(row['owner'], row['owner']),
                      reviewer_name=names.get(row['reviewer'], row['reviewer']) if row['reviewer'] else '')
        return {'report': report, 'workspace': workspace.view(state, can_edit=can_edit, can_review=can_review), **extra}

    def change(report_id, user, operation, audit_action=None, **audit_details):
        """Load, check ownership, apply `operation(state)`, save; returns the new workspace view."""
        row, state = open_report(report_id, user)
        if row['owner'] != user['username']:
            raise HTTPException(403, 'Only the author can change this report.')
        result = operation(state)
        _, version = services.reports.save(actor=user['username'], title=row['title'], course=row['course'],
                                           status=state['workflow'].status, snapshot=pack(state),
                                           report_id=row['id'], version=row['version'])
        if audit_action:
            services.audit.append(audit_action, user['username'], report_id=row['id'], **audit_details)
        row = dict(row, version=version)
        return payload(row, state, user, result=result if isinstance(result, (str, dict, list, type(None))) else None)

    # ---- create ------------------------------------------------------------------------------
    @router.post('/reports')
    async def create_report(files: list[UploadFile] = File(...), title: str = Form(''), user=Depends(current_user)):
        if not files:
            raise ValueError('Choose at least one survey file.')
        with tempfile.TemporaryDirectory() as folder:
            paths, total = [], 0
            for upload in files:
                name = Path(upload.filename or 'survey.csv').name
                if Path(name).suffix.lower() not in SUFFIXES:
                    raise ValueError(f'{name}: choose CSV, XLSX or XLS survey files.')
                data = await upload.read()
                total += len(data)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError('Files are too large (25 MB maximum in total).')
                path = Path(folder) / name
                path.write_bytes(data)
                paths.append(path)
            raw = workspace.load_files(paths)
            state = workspace.new_state(raw, [p.name for p in paths])
        name = title.strip() or f"{state['context'].course_name if state['context'].course_name != workspace.ALL_COURSES else state['loaded_file_label']}"
        report_id, version = services.reports.save(actor=user['username'], title=name[:300], course=state['context'].course_name,
                                                   status='DRAFT', snapshot=pack(state))
        services.audit.append('Data imported', user['username'], report_id=report_id, source=state['source'],
                              responses=state['context'].metrics['response_count'], themes=len(state['context'].themes))
        row = services.reports.load(report_id, user['username'])
        return payload(row, state, user)

    # ---- read --------------------------------------------------------------------------------
    @router.get('/reports/{report_id}')
    def get_workspace(report_id: str, user=Depends(current_user)):
        row, state = open_report(report_id, user)
        return payload(row, state, user)

    @router.get('/reports/{report_id}/rows')
    def rows(report_id: str, search: str = '', offset: int = 0, user=Depends(current_user)):
        _, state = open_report(report_id, user)
        return workspace.survey_rows(state, search[:200], max(0, offset), 50)

    # ---- steps -------------------------------------------------------------------------------
    class ThemeDecision(BaseModel):
        name: str = Field(max_length=200)
        status: Literal['confirmed', 'rejected']
        category: str | None = None

    @router.post('/reports/{report_id}/themes')
    def theme(report_id: str, body: ThemeDecision, user=Depends(current_user)):
        return change(report_id, user, lambda s: workspace.decide_theme(s, body.name, body.status, body.category),
                      f'Theme {body.status}', theme=body.name, category=body.category or '')

    class Draft(BaseModel):
        audience: Literal['facilitator', 'client']

    @router.post('/reports/{report_id}/draft')
    def draft(report_id: str, body: Draft, user=Depends(current_user)):
        return change(report_id, user, lambda s: workspace.generate(s, body.audience), 'Draft generated',
                      audience=body.audience)

    class Content(BaseModel):
        content: str = Field(max_length=200_000)

    @router.put('/reports/{report_id}/content')
    def content(report_id: str, body: Content, user=Depends(current_user)):
        return change(report_id, user, lambda s: workspace.set_content(s, body.content), 'Draft edited')

    class ClaimDecision(BaseModel):
        decision: Literal['accept', 'reject']

    @router.post('/reports/{report_id}/claims/{key}')
    def claim(report_id: str, key: str, body: ClaimDecision, user=Depends(current_user)):
        def operation(state):
            item, decision = workspace.decide_claim(state, key, body.decision)
            return {'key': item.key, 'decision': decision}
        return change(report_id, user, operation, f'Claim {body.decision}ed', claim=key)

    class Revision(BaseModel):
        sections: list[str] = Field(max_length=6)
        instruction: str = Field(default='', max_length=4000)
        method: Literal['gemini', 'offline', 'manual'] = 'gemini'
        replacement: str = Field(default='', max_length=20000)

    @router.post('/reports/{report_id}/revisions')
    def revise(report_id: str, body: Revision, user=Depends(current_user)):
        return change(report_id, user, lambda s: workspace.propose(s, body.sections, body.instruction, body.method,
                                                                   body.replacement) and None)

    @router.post('/reports/{report_id}/revisions/{action}')
    def revision_action(report_id: str, action: Literal['apply', 'discard', 'undo'], user=Depends(current_user)):
        operation = {'apply': workspace.apply_revision, 'discard': workspace.discard_revision,
                     'undo': workspace.undo_revision}[action]
        return change(report_id, user, lambda s: operation(s) and None, f'Revision {action}')

    # ---- Gemini on the server ------------------------------------------------------------------
    def gemini():
        from src.ai.gemini_provider import GeminiAIProvider
        try:
            return GeminiAIProvider()
        except ValueError:
            raise ValueError('Gemini is not set up on the server yet (GEMINI_API_KEY).') from None

    @router.post('/reports/{report_id}/insights')
    def insights(report_id: str, user=Depends(current_user)):
        from src.ai.insights import render_insights
        _, state = open_report(report_id, user)
        provider = gemini()
        return {'markdown': render_insights(provider.insights(state['context']), state['context'], provider.model)}

    class Question(BaseModel):
        question: str = Field(min_length=1, max_length=2000)

    @router.post('/reports/{report_id}/ask')
    def ask(report_id: str, body: Question, user=Depends(current_user)):
        from src.ai.insights import insight_evidence
        _, state = open_report(report_id, user)
        result = gemini().answer_question(state['context'], body.question)
        facts = insight_evidence(state['context'])
        return {'answer': result['answer'], 'evidence': [facts[ref] for ref in result['evidence_ids'] if ref in facts]}

    # ---- export --------------------------------------------------------------------------------
    @router.get('/reports/{report_id}/export')
    def export(report_id: str, format: Literal['docx', 'md'] = 'docx', user=Depends(current_user)):
        import os
        from src.reporting.exporter import docx_bytes, markdown_bytes
        row, state = open_report(report_id, user)
        if state['workflow'].status == 'HUMAN REVIEWED' and state.get('approved_export'):
            text, suffix = state['approved_export'], 'reviewed'
        elif row['owner'] == user['username'] and state['content'].strip():
            text, suffix = '**DRAFT — REQUIRES HUMAN REVIEW**\n\n' + state['content'], 'draft'
        else:
            raise ValueError('There is nothing to export yet.')
        audience = state['report'].audience if state['report'] else 'report'
        name = f'learning_evaluation_{audience}_{suffix}.{format}'
        if format == 'docx':
            data, media = docx_bytes(text, os.getenv('UNIVERSITY_LOGO_PATH')), \
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            data, media = markdown_bytes(text), 'text/markdown; charset=utf-8'
        services.audit.append('Report exported', user['username'], report_id=row['id'], kind=suffix, format=format)
        return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{name}"'})

    @router.get('/config')
    def config():
        from src.workflow import APPROVER_ROLES, CLIENT_APPROVER_ROLE
        from server.app import google_config
        import os
        return {'google_web_client_id': os.getenv('GOOGLE_WEB_CLIENT_ID', '').strip(),
                'google_desktop': bool(google_config()[0]),
                'approver_roles': list(APPROVER_ROLES), 'client_approver_role': CLIENT_APPROVER_ROLE,
                'sections': list(__import__('src.reporting.revisions', fromlist=['SECTIONS']).SECTIONS)}

    return router

