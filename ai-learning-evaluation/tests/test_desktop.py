"""Desktop workflow regressions; no external services or interactive dialogs."""
import time
import sys
import tkinter as tk
from pathlib import Path
import pytest
from docx import Document
from src.ui.desktop import DesktopApp, analyse, _setup_environment
from src.synthetic import build_synthetic_responses


@pytest.fixture
def desktop(monkeypatch):
    _setup_environment()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if sys.platform == 'win32':
            raise
        pytest.skip(f'Tk display unavailable: {exc}')
    root.withdraw()
    app = DesktopApp(root, auto_demo=False)
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)
    yield app
    app.dirty = False
    app.close()
    assert not errors, errors


def wait_for_load(app):
    deadline = time.monotonic() + 15
    while app.busy and time.monotonic() < deadline:
        app.root.update()
        time.sleep(.01)
    app.root.update()
    assert not app.busy, 'Background analysis timed out'


def load_sample(app, count=500):
    app.load(build_synthetic_responses(count, 208), 'sample.csv')
    wait_for_load(app)
    assert app.context is not None


def test_startup_demo_and_navigation(desktop):
    assert desktop.generate_button.instate(['disabled'])
    desktop.load_demo()
    wait_for_load(desktop)
    assert desktop.context.metrics['response_count'] > 0
    assert desktop.generate_button.instate(['!disabled'])
    for i, (title, _) in enumerate(desktop.TITLES):
        desktop.navigate(i)
        desktop.root.update()
        assert desktop.page_title.cget('text') == title


def test_search_full_dataset_and_inspect_row(desktop):
    load_sample(desktop, 1100)
    assert len(desktop.table.get_children()) == 1000
    response_id = str(desktop.frame.iloc[-1]['ResponseID'])
    desktop.search.set(response_id)
    desktop.filter_rows()
    assert len(desktop.table.get_children()) == 1
    desktop.table.selection_set(desktop.table.get_children()[0])
    desktop.inspect_row()
    assert response_id in desktop.row_detail.get('1.0', 'end')
    desktop.search.set('no_such_response_zzzz')
    desktop.filter_rows()
    assert not desktop.table.get_children()
    assert 'No matching' in desktop.row_detail.get('1.0', 'end')


def test_failed_load_preserves_current_workspace(desktop, tmp_path):
    load_sample(desktop)
    previous = desktop.context
    path = tmp_path / 'bad.csv'
    path.write_text('WrongColumn\nhello\n')
    desktop.load(path, path.name)
    wait_for_load(desktop)
    assert desktop.context is previous
    assert desktop.source == 'sample.csv'
    assert desktop.generate_button.instate(['!disabled'])


def test_scope_reset_and_discard_protection(desktop):
    load_sample(desktop)
    desktop.generate()
    draft = desktop.report
    course = str(desktop.raw['CourseName'].iloc[0])
    desktop.load(desktop.raw, desktop.source, course)
    assert desktop.report is draft  # Default response declines discarding unsaved work.
    desktop.dirty = False
    desktop.load(desktop.raw, desktop.source, course)
    wait_for_load(desktop)
    assert desktop.report is None
    assert desktop.context.course_name == course
    assert desktop.frame['CourseName'].eq(course).all()
    assert not desktop.confirmed.get()


def test_report_preview_edit_and_review_export(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    desktop.generate()
    desktop.root.update()
    assert 'Executive Summary' in desktop.preview.get('1.0', 'end')
    assert '**' not in desktop.preview.get('1.0', 'end')
    desktop.confirmed.set(True)
    desktop.editor.insert('end', '\nVerified edit for demonstration.')
    desktop.root.update()
    assert not desktop.confirmed.get()
    assert desktop.export() is False
    desktop.reviewer.insert(0, 'Demo reviewer')
    desktop.confirmed.set(True)
    path = tmp_path / 'reviewed.docx'
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: str(path))
    assert desktop.export()
    text = '\n'.join(p.text for p in Document(path).paragraphs)
    assert 'HUMAN REVIEWED' in text
    assert 'Reviewed by: Demo reviewer' in text
    assert 'Verified edit for demonstration.' in text
    assert not desktop.dirty


def test_draft_save_cancel_and_write_failure(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    desktop.generate()
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: '')
    assert desktop.export(False) is False
    assert desktop.dirty
    path = tmp_path / 'draft.md'
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: str(path))
    assert desktop.export(False)
    assert 'DRAFT — REQUIRES HUMAN REVIEW' in path.read_text(encoding='utf-8')
    desktop.dirty = True
    monkeypatch.setattr(Path, 'write_bytes', lambda *a: (_ for _ in ()).throw(PermissionError('File locked')))
    assert desktop.export(False) is False
    assert desktop.dirty


def test_theme_evidence_and_assistant(desktop):
    load_sample(desktop)
    desktop.theme_table.selection_set('0')
    desktop.inspect_theme()
    assert desktop.context.themes[0].name in desktop.theme_detail.get('1.0', 'end')
    desktop.ask('How many responses participated?')
    assert '500' in desktop.answer.get('1.0', 'end')
    assert desktop.context.course_name in desktop.answer.get('1.0', 'end')


def test_invalid_scope_is_rejected():
    with pytest.raises(ValueError, match='No responses'):
        analyse(build_synthetic_responses(500, 208), 'sample.csv', 'Missing course')
