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
            version INTEGER NOT NULL, snapshot TEXT NOT NULL)''')
        try:
            with db:
                yield db
        finally:
            db.close()

    def list_owned(self, actor):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT id, owner, title, course, status, updated, version FROM reports WHERE owner=? ORDER BY updated DESC', (actor,))]

    def load(self, report_id, actor):
        with self.connect() as db:
            row = db.execute('SELECT * FROM reports WHERE id=? AND owner=?', (report_id, actor)).fetchone()
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
            raise ValueError('Only editable drafts can be saved to the library in this release.')
        payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        updated = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            if report_id:
                count = db.execute('''UPDATE reports SET title=?, course=?, status=?, updated=?,
                    version=version+1, snapshot=? WHERE id=? AND owner=? AND version=?''',
                    (title.strip(), course, status, updated, payload, report_id, actor, version)).rowcount
                if not count:
                    raise ValueError('This draft changed or is unavailable. Reopen it from the library before saving.')
                return report_id, version + 1
            report_id = str(uuid4())
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?,?,?)',
                       (report_id, actor, title.strip(), course, status, updated, 1, payload))
            return report_id, 1
