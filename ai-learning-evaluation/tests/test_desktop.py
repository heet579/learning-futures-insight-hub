"""Desktop workflow regressions; no external services or interactive dialogs."""
import time
import os
import sys
import tkinter as tk
from pathlib import Path
import pytest
from docx import Document
from src.ui.desktop import DesktopApp, analyse, _setup_environment
from src.synthetic import build_synthetic_responses
from test_qualtrics_real_export import _fake_export_csv


@pytest.fixture(scope='module')
def tk_runtime():
    # Keep one Tcl interpreter, with a fresh window per test. Repeated interpreter
    # creation intermittently fails loading Tcl library files on Windows.
    _setup_environment()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if sys.platform == 'win32' or os.getenv('REQUIRE_DESKTOP_TESTS') == '1':
            raise
        pytest.skip(f'Tk display unavailable: {exc}')
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def desktop(monkeypatch, tk_runtime):
    from src.ai.local_provider import LocalAnalysisProvider
    from src.ai.copilot import answer_question
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.executive_summary',
        lambda self, context, audience: LocalAnalysisProvider().executive_summary(context, audience))
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.recommendations',
        lambda self, context, audience: LocalAnalysisProvider().recommendations(context, audience))
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.answer_question',
        lambda self, context, question: {'answer': answer_question(question, context), 'evidence_ids': ['responses']})
    root = tk.Toplevel(tk_runtime)
    root.withdraw()
    app = DesktopApp(root)
    errors = []
    monkeypatch.setattr(tk_runtime, 'report_callback_exception', lambda *args: errors.append(args))
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)
    yield app
    app.dirty = False
    app.pool.shutdown(wait=True, cancel_futures=True)
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
    assert desktop.progress.winfo_manager() == ''
    assert desktop.context is None
    assert getattr(desktop, 'startup_id', None) is None
    assert [widget.cget('text') for widget in desktop.metric_values] == ['PENDING'] * 4
    assert desktop.file_name.cget('text') == 'NO FILE SELECTED'
    assert desktop.generate_button.instate(['disabled'])
    desktop.load_startup_data()
    wait_for_load(desktop)
    assert desktop.context.metrics['response_count'] > 0
    assert desktop.generate_button.instate(['!disabled'])
    assert desktop.progress.winfo_manager() == ''
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
    wait_for_load(desktop)
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
    wait_for_load(desktop)
    desktop.root.update()
    assert desktop.report_tabs.index('current') == 0
    assert str(desktop.editor.cget('state')) == 'normal'
    assert 'Executive Summary' in desktop.preview.get('1.0', 'end')
    assert '**' not in desktop.preview.get('1.0', 'end')
    assert 'Facilitator' in desktop.report_status.get()
    assert 'requires review' in desktop.report_status.get()
    assert desktop.preview.tag_ranges('title')
    assert desktop.preview.tag_ranges('heading')
    assert 'DRAFT' in desktop.preview.get('1.0', 'end')
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


def test_approval_refused_when_draft_has_fabricated_claim(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    desktop.root.update()
    desktop.editor.insert('end', '\n99.9% of learners said this was flawless.')
    desktop.root.update()
    assert 'unsupported' in desktop.evidence_status.get()
    desktop.reviewer.insert(0, 'Demo reviewer')
    desktop.confirmed.set(True)
    path = tmp_path / 'reviewed.docx'
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: str(path))
    assert desktop.export() is False
    assert not path.exists()


def test_draft_save_cancel_and_write_failure(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
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
    wait_for_load(desktop)
    assert '500' in desktop.answer.get('1.0', 'end')
    assert desktop.context.course_name in desktop.answer.get('1.0', 'end')


def test_report_generation_needs_no_extra_approval(desktop, monkeypatch):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    assert desktop.report is not None
    assert not desktop.busy


def test_external_draft_provider_failure_is_reported(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    desktop.generate()
    wait_for_load(desktop)
    assert desktop.report is None
    assert not desktop.busy


def test_invalid_scope_is_rejected():
    with pytest.raises(ValueError, match='No responses'):
        analyse(build_synthetic_responses(500, 208), 'sample.csv', 'Missing course')

def test_only_selected_page_is_mapped(desktop):
    for index in range(len(desktop.pages)):
        desktop.navigate(index)
        desktop.root.update_idletasks()
        for i, page in enumerate(desktop.pages):
            assert page.winfo_manager() == ('grid' if i == index else '')
        assert desktop.nav_buttons[index].cget('style') == 'Selected.Nav.TButton'

def test_feedback_preview_apply_undo_and_reset(desktop, monkeypatch):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    desktop.root.update()
    original = desktop.editor.get('1.0', 'end-1c')
    desktop.feedback.insert('1.0', 'Make it shorter')
    desktop.root.update()
    desktop.confirmed.set(True)
    desktop.propose_feedback()
    wait_for_load(desktop)
    assert desktop.pending_revision is not None
    assert desktop.editor.get('1.0', 'end-1c') == original
    desktop.apply_feedback()
    assert desktop.editor.get('1.0', 'end-1c') != original
    assert not desktop.confirmed.get()
    assert len(desktop.revision_history) == 1
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    desktop.undo_revision()
    assert desktop.editor.get('1.0', 'end-1c') == original
    assert not desktop.revision_history
    desktop.dirty = False
    desktop.load_startup_data()
    wait_for_load(desktop)
    assert desktop.pending_revision is None
    assert not desktop.revision_history
    assert desktop.feedback.get('1.0', 'end-1c') == ''


def test_human_or_copilot_replacement_is_previewed_before_apply(desktop):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    original = desktop.editor.get('1.0', 'end-1c')
    desktop.revision_provider.set('Human / Copilot replacement')
    desktop.feedback.insert('1.0', 'Make the recommendation specific')
    desktop.replacement.insert('1.0', '- Run a practical exercise and review learner feedback after delivery.')
    desktop.propose_feedback()
    wait_for_load(desktop)
    assert desktop.editor.get('1.0', 'end-1c') == original
    assert 'Run a practical exercise' in desktop.revision_preview.get('1.0', 'end')
    desktop.apply_feedback()
    assert 'Run a practical exercise' in desktop.editor.get('1.0', 'end')
    assert desktop.report_tabs.index('current') == 0
    assert not desktop.confirmed.get()


def test_copilot_workflow_opens_browser_and_copies_masked_prompt(desktop, monkeypatch):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    desktop.feedback.insert('1.0', 'Make this clearer for person@example.com')
    opened = []
    monkeypatch.setattr('webbrowser.open', lambda url, new=0: opened.append(url) or True)
    desktop.open_copilot()
    prompt = desktop.root.clipboard_get()
    assert opened == ['https://copilot.microsoft.com/']
    assert '[EMAIL REMOVED]' in prompt
    assert 'person@example.com' not in prompt
    assert desktop.revision_provider.get() == 'Manual replacement'


def test_manual_edit_invalidates_feedback_preview(desktop):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    desktop.feedback.insert('1.0', 'Use bullet points')
    desktop.root.update()
    desktop.propose_feedback()
    wait_for_load(desktop)
    assert desktop.pending_revision
    desktop.editor.insert('end', '\nManual edit')
    desktop.root.update()
    assert desktop.pending_revision is None
    assert desktop.apply_button.instate(['disabled'])


def test_import_csv_auto_maps_a_raw_qualtrics_export(desktop, tmp_path):
    path = tmp_path / '8325+-+Fake+Course+-+August+2023_time.csv'
    path.write_text(_fake_export_csv(), encoding='utf-8')
    desktop.load(path, path.name)
    wait_for_load(desktop)
    assert desktop.context is not None
    assert len(desktop.frame) == 2
    assert 'Fake Course' in str(desktop.frame['CourseName'].iloc[0])


def test_configured_client_data_at_startup(desktop, monkeypatch, tmp_path):
    client_csv = tmp_path / 'client.csv'
    build_synthetic_responses(30, 208).to_csv(client_csv, index=False)
    monkeypatch.setenv('EVALUATION_DATA_PATH', str(client_csv))
    desktop.load_startup_data()
    wait_for_load(desktop)
    assert desktop.source == 'client.csv'
    assert len(desktop.frame) == 30


def test_insights_generate_directly_cache_and_reset_on_scope_change(desktop, monkeypatch):
    from test_gemini import RESULT
    load_sample(desktop, 30)
    assert 'Survey overview' in desktop.insights_text.get('1.0', 'end')
    calls = []
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.insights',
                        lambda *a, **k: calls.append(True) or RESULT)
    desktop.generate_insights()
    wait_for_load(desktop)
    assert len(calls) == 1
    assert 'Insights' in desktop.insights_text.get('1.0', 'end')
    desktop.generate_insights()
    assert len(calls) == 1
    course = sorted(desktop.raw['CourseName'].dropna().unique())[0]
    desktop.load(desktop.raw, desktop.source, course)
    wait_for_load(desktop)
    assert 'Survey overview' in desktop.insights_text.get('1.0', 'end')
    desktop.generate_insights()
    wait_for_load(desktop)
    assert len(calls) == 2


def test_failed_gemini_request_keeps_local_analysis(desktop, monkeypatch):
    load_sample(desktop, 30)
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    def fail(*a, **k):
        raise RuntimeError('quota reached')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.insights', fail)
    desktop.generate_insights()
    wait_for_load(desktop)
    assert 'Survey overview' in desktop.insights_text.get('1.0', 'end')
    assert desktop.insights_button.instate(['!disabled'])
    assert not desktop.insights_cache


def test_import_multiple_csv_and_excel_files(desktop, monkeypatch, tmp_path, golden_df):
    from test_excel_import import write_xlsx_fixture
    csv = tmp_path / 'survey.csv'
    xlsx = tmp_path / 'survey.xlsx'
    golden_df.to_csv(csv, index=False)
    write_xlsx_fixture(xlsx, golden_df)
    monkeypatch.setattr('tkinter.filedialog.askopenfilenames', lambda **kwargs: [str(csv), str(xlsx)])
    desktop.open_file()
    assert desktop.file_state.cget('text') == 'PROCESSING FILE'
    assert desktop.file_name.cget('text') == 'SURVEY.CSV (+1 MORE FILES)'
    wait_for_load(desktop)
    assert len(desktop.frame) == 6
    assert desktop.source == '2 survey files'
    assert desktop.file_state.cget('text') == 'LOADED FILE'
    assert desktop.metric_values[0].cget('text') == '6'


def test_failed_import_restores_loaded_file_badge(desktop, tmp_path):
    load_sample(desktop, 30)
    broken = tmp_path / 'broken.csv'
    broken.write_text('wrong,columns\n1,2\n', encoding='utf-8')
    desktop.load(broken, broken.name)
    assert desktop.file_name.cget('text') == 'BROKEN.CSV'
    wait_for_load(desktop)
    assert desktop.file_name.cget('text') == 'SAMPLE.CSV'
    assert desktop.file_state.cget('text') == 'LOADED FILE'
    assert desktop.metric_values[0].cget('text') == '30'


def test_gemini_report_provider_can_be_selected(desktop, monkeypatch):
    from test_gemini import response
    load_sample(desktop, 30)
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    monkeypatch.setattr('src.ai.gemini_provider.urlopen', lambda *a, **k: response())
    desktop.generate()
    wait_for_load(desktop)
    assert desktop.report.mode == 'Gemini'


def test_question_uses_gemini_caches_and_resets_on_scope_change(desktop, monkeypatch):
    load_sample(desktop, 30)
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    calls = []
    def answer(provider, context, question):
        calls.append((context.course_name, question))
        return {'answer': 'Review the supplied response count.', 'evidence_ids': ['responses']}
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.answer_question', answer)
    assert not hasattr(desktop, 'question_provider')
    desktop.ask('How many responses?')
    assert desktop.busy
    assert desktop.progress.winfo_manager() == 'pack'
    wait_for_load(desktop)
    assert desktop.progress.winfo_manager() == ''
    text = desktop.answer.get('1.0', 'end')
    assert 'Answer' in text and '30 survey responses' in text
    desktop.ask('How many responses?')
    assert len(calls) == 1
    desktop.load(desktop.raw, desktop.source, sorted(desktop.raw['CourseName'].dropna().unique())[0])
    wait_for_load(desktop)
    assert desktop.question.get() == ''
    assert 'Supporting calculated evidence' not in desktop.answer.get('1.0', 'end')
    desktop.ask('How many responses?')
    wait_for_load(desktop)
    assert len(calls) == 2


def test_question_failure_is_not_disguised_as_ai_answer(desktop, monkeypatch):
    load_sample(desktop, 30)
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    def fail(*args):
        raise RuntimeError('Quota reached')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.answer_question', fail)
    desktop.ask('What should we improve?')
    wait_for_load(desktop)
    assert 'Could not answer' in desktop.answer.get('1.0', 'end')
    assert desktop.progress.winfo_manager() == ''
    assert not desktop.question_cache
    assert desktop.question.instate(['!disabled'])


def test_question_requires_configuration_without_network_call(desktop, monkeypatch):
    load_sample(desktop, 30)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    desktop.ask('How many responses?')
    assert 'not configured' in desktop.answer.get('1.0', 'end')
    assert not desktop.busy
