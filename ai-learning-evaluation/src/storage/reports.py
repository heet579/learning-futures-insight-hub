"""Local report repository. UI callers depend on these operations, not SQL."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ReportRepository:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('REPORT_LIBRARY_PATH') or
                         Path.home() / '.learning_futures_insight_hub' / 'reports.sqlite3')

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
            course TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL,
            version INTEGER NOT NULL, snapshot TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT '')''')
        if 'reviewer' not in {r['name'] for r in db.execute('PRAGMA table_info(reports)')}:
            db.execute("ALTER TABLE reports ADD COLUMN reviewer TEXT NOT NULL DEFAULT ''")
        try:
            with db:
                yield db
        finally:
            db.close()

    def list_owned(self, actor):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT id, owner, title, course, status, updated, version, reviewer FROM reports WHERE owner=? ORDER BY updated DESC', (actor,))]

    def load(self, report_id, actor):
        with self.connect() as db:
            row = db.execute('''SELECT * FROM reports WHERE id=? AND ? != '' AND
                (owner=? OR status='AWAITING HUMAN REVIEW' OR (status='HUMAN REVIEWED' AND reviewer=?))''',
                (report_id, actor, actor, actor)).fetchone()
        if row is None:
            raise ValueError('This report is unavailable for this account.')
        result = dict(row)
        result['snapshot'] = json.loads(result['snapshot'])
        return result

    def rename(self, *, actor, report_id, version, title):
        if not actor or not title.strip():
            raise ValueError('A signed-in account and report name are required.')
        with self.connect() as db:
            count = db.execute('''UPDATE reports SET title=?, updated=?, version=version+1
                WHERE id=? AND owner=? AND version=? AND status IN ('DRAFT', 'CHANGES REQUESTED')''',
                (title.strip(), datetime.now(timezone.utc).isoformat(),
                 report_id, actor, version)).rowcount
            if not count:
                raise ValueError('This draft changed or is unavailable. Refresh the library and reopen it before renaming.')
        return version + 1

    def delete(self, *, actor, report_id, version):
        with self.connect() as db:
            count = db.execute('''DELETE FROM reports WHERE id=? AND owner=? AND version=?
                AND status IN ('DRAFT', 'CHANGES REQUESTED')''',
                (report_id, actor, version)).rowcount
            if not count:
                raise ValueError('This draft changed or is unavailable. Refresh the library and reopen it before deleting.')

    def save(self, *, actor, title, course, status, snapshot, report_id=None, version=None):
        if not actor or not title.strip():
            raise ValueError('A signed-in account and report name are required.')
        if status not in ('DRAFT', 'CHANGES REQUESTED'):
            raise ValueError('Only editable drafts can be saved. Submitted and approved versions are locked.')
        payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        updated = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            if report_id:
                count = db.execute('''UPDATE reports SET title=?, course=?, status=?, updated=?,
                    version=version+1, snapshot=? WHERE id=? AND owner=? AND version=? AND status IN ('DRAFT', 'CHANGES REQUESTED')''',
                    (title.strip(), course, status, updated, payload, report_id, actor, version)).rowcount
                if not count:
                    raise ValueError('This draft changed or is unavailable. Reopen it from the library before saving.')
                return report_id, version + 1
            report_id = str(uuid4())
            db.execute('INSERT INTO reports (id,owner,title,course,status,updated,version,snapshot) VALUES (?,?,?,?,?,?,?,?)',
                       (report_id, actor, title.strip(), course, status, updated, 1, payload))
            return report_id, 1


    def list_pending(self, actor):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT id,owner,title,course,status,updated,version,reviewer
                FROM reports WHERE status='AWAITING HUMAN REVIEW' AND owner!=? AND ?!='' ORDER BY updated DESC""",
                (actor, actor))]

    def list_approved(self, actor):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT id,owner,title,course,status,updated,version,reviewer
                FROM reports WHERE status='HUMAN REVIEWED' AND (owner=? OR reviewer=?) AND ?!=''
                ORDER BY updated DESC""", (actor, actor, actor))]

    def transition(self, *, actor, report_id, version, action, notes='', role='', confirmed=False, audit=None):
        """Change the stored version atomically; never trust a reviewer's editable UI snapshot."""
        from src.storage.snapshot import unpack, pack
        from src.storage.review_state import checked_review
        from src.audit.logger import AuditTrail
        if not actor or action not in ('submit', 'return', 'approve'):
            raise ValueError('A signed-in account and valid review action are required.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reports WHERE id=? AND version=?', (report_id, version)).fetchone()
            if row is None:
                raise ValueError('This report changed. Reopen it from Library before continuing.')
            state = unpack(json.loads(row['snapshot']))
            workflow = state['workflow']
            if workflow.status != row['status']:
                raise ValueError('The saved review state does not match the report.')
            if action == 'submit':
                if actor != row['owner'] or row['status'] not in ('DRAFT', 'CHANGES REQUESTED'):
                    raise ValueError('Only the owner can submit an editable draft.')
                checked_review(state)
                workflow.submit(actor)
                reviewer = ''
            else:
                if actor.casefold() == row['owner'].casefold() or row['status'] != 'AWAITING HUMAN REVIEW':
                    raise ValueError('Only a different account can review a submitted report.')
                if workflow.reviewer != row['owner']:
                    raise ValueError('The submitted author does not match the report owner.')
                reviewer = actor
                if action == 'return':
                    workflow.return_for_changes(actor, notes)
                else:
                    if not confirmed:
                        raise ValueError('Confirm that you checked the evidence, privacy and final wording.')
                    themes, ledger = checked_review(state)
                    workflow.approve(actor, role=role, audience=state['report'].audience)
                    from src.reporting.report_generator import approve_report
                    from src.review.record import build_review_record, content_hash
                    from src.review.claims import ai_text_retained
                    trail = audit if audit is not None else AuditTrail()
                    if not trail.verify()['ok']:
                        raise ValueError('The audit log could not be verified. Approval is blocked.')
                    approved = approve_report(state['report'], state['content']).content
                    event = trail.append('Approved', actor, report_id=report_id, role=role,
                        author=row['owner'], report_sha256=content_hash(approved))
                    state['approved_export'] = approved + '\n\n' + build_review_record(
                        workflow=workflow, theme_counts=themes.counts(), claim_counts=ledger.counts(),
                        pace=ledger.pace(), ai_retained=ai_text_retained(state['report'], state['content']),
                        source_mode=state['report'].source_mode, report_hash=content_hash(approved),
                        approval_hash=event['hash'], audit_entries=trail.verify()['entries'], authenticated=True)
            payload = json.dumps(pack(state), ensure_ascii=False, allow_nan=False)
            db.execute("""UPDATE reports SET status=?, reviewer=?, updated=?, version=version+1,
                snapshot=? WHERE id=? AND version=?""", (workflow.status, reviewer,
                datetime.now(timezone.utc).isoformat(), payload, report_id, version))
        return version + 1, state
