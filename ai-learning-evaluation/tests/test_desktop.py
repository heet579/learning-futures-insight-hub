"""Desktop workflow regressions; no external services or interactive dialogs."""
import json
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
def desktop(monkeypatch, tk_runtime, tmp_path):
    from src.ai.local_provider import LocalAnalysisProvider
    monkeypatch.setenv('AUDIT_LOG_PATH', str(tmp_path / 'audit.jsonl'))
    from src.ai.copilot import answer_question
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.executive_summary',
        lambda self, context, audience: LocalAnalysisProvider().executive_summary(context, audience))
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.recommendations',
        lambda self, context, audience: LocalAnalysisProvider().recommendations(context, audience))
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.recommendation_evidence',
        lambda self, context, audience: {})
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
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Alex Author')
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


def review_themes(app, reject=()):
    for i, theme in enumerate(app.theme_review.themes):
        app.theme_table.selection_set(str(i))
        app.inspect_theme()
        (app.reject_theme if theme.name in reject else app.confirm_theme)()
    assert app.theme_review.complete


def load_sample(app, count=500, review=True):
    app.load(build_synthetic_responses(count, 208), 'sample.csv')
    wait_for_load(app)
    assert app.context is not None
    if review:
        review_themes(app)


def draft(app):
    app.generate()
    wait_for_load(app)
    app.root.update()
    assert app.report is not None


def decide_all_claims(app):
    for claim in list(app.ledger.claims):
        app.claims_table.selection_set(claim.key)
        app.accept_claim()
    assert app.ledger.complete


def submit(app, author='Alex Author'):  # the name asked for at the first review decision
    app.author_entry.delete(0, 'end')
    app.author_entry.insert(0, author)
    assert app.submit_for_approval()


def test_startup_demo_and_navigation(desktop):
    assert desktop.progress.winfo_manager() == ''
    assert desktop.context is None
    assert getattr(desktop, 'startup_id', None) is None
    assert [widget.cget('text') for widget in desktop.metric_values] == ['PENDING'] * 4
    assert desktop.file_name.cget('text') == 'No file selected'
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


def test_report_preview_and_full_human_review_export(desktop, monkeypatch, tmp_path):
    from src.audit.logger import AuditTrail
    load_sample(desktop)
    draft(desktop)
    assert desktop.report_tabs.index('current') == 0
    assert str(desktop.editor.cget('state')) == 'normal'
    assert 'Executive Summary' in desktop.preview.get('1.0', 'end')
    assert '**' not in desktop.preview.get('1.0', 'end')
    assert 'Facilitator' in desktop.report_status.get()
    assert desktop.preview.tag_ranges('title')
    assert 'DRAFT' in desktop.preview.get('1.0', 'end')
    # Gate 2: every claim starts pending and blocks submission.
    assert desktop.ledger.claims and not desktop.ledger.complete
    assert desktop.author_entry.get() == 'Alex Author'  # asked for at the first theme decision
    assert desktop.submit_for_approval() is False
    assert desktop.workflow.status == 'DRAFT'
    assert desktop.export_button.instate(['disabled'])
    decide_all_claims(desktop)
    assert desktop.submit_for_approval()
    assert desktop.workflow.status == 'AWAITING HUMAN REVIEW'
    # Gate 4: the author cannot approve their own report.
    path = tmp_path / 'reviewed.docx'
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: str(path))
    desktop.approver_entry.insert(0, 'alex author')
    desktop.confirmed.set(True)
    assert desktop.export() is False
    assert not path.exists()
    desktop.approver_entry.delete(0, 'end')
    desktop.approver_entry.insert(0, 'Sam Approver')
    assert desktop.export()
    text = '\n'.join(p.text for p in Document(path).paragraphs)
    assert 'HUMAN REVIEWED' in text
    assert 'Review record' in text
    assert 'Approved by: Sam Approver, Learning Futures lead' in text
    assert 'Prepared and submitted by: Alex Author' in text
    assert desktop.workflow.status == 'HUMAN REVIEWED'
    assert not desktop.dirty
    # Gate 6: the audit chain is intact and holds no learner comments.
    chain = AuditTrail(tmp_path / 'audit.jsonl').verify()
    assert chain['ok'] and chain['entries'] > 5
    log = (tmp_path / 'audit.jsonl').read_text(encoding='utf-8')
    decisions = [json.loads(line) for line in log.splitlines() if '"Claim ' in line or '"Theme ' in line]
    assert decisions and all(d['actor'] == 'Alex Author' for d in decisions)
    assert 'Approved' in log and 'Exported' in log
    assert desktop.context.themes[0].evidence[0] not in log
    # Editing after approval sends the report back to draft.
    desktop.editor.insert('end', '\nA later edit.')
    desktop.root.update()
    assert desktop.workflow.status == 'DRAFT'


def test_draft_requires_theme_review_and_uses_only_confirmed_themes(desktop):
    load_sample(desktop, review=False)
    desktop.generate()
    assert desktop.report is None
    assert desktop.page_title.cget('text') == 'Themes & evidence'
    rejected = desktop.context.themes[0].name
    review_themes(desktop, reject={rejected})
    draft(desktop)
    themes_section = desktop.report.content.split('## Key Themes')[1].split('## ')[0]
    assert rejected not in themes_section
    assert 'Rejected' in desktop.theme_table.set('0', 'decision')


def test_changing_a_theme_after_drafting_blocks_submission(desktop):
    load_sample(desktop)
    draft(desktop)
    decide_all_claims(desktop)
    desktop.theme_table.selection_set('0')
    desktop.reject_theme()
    assert desktop.themes_changed_since_draft
    assert desktop.submit_for_approval() is False


def test_rejecting_a_claim_removes_it_from_the_draft(desktop):
    load_sample(desktop)
    draft(desktop)
    claim = next(c for c in desktop.ledger.claims if c.section == 'Recommendations')
    desktop.claims_table.selection_set(claim.key)
    desktop.reject_claim()
    assert claim.text not in desktop.editor.get('1.0', 'end')
    assert desktop.ledger.counts()['rejected'] == 1


def test_fabricated_claim_cannot_be_accepted_or_submitted(desktop):
    load_sample(desktop)
    draft(desktop)
    desktop.editor.insert('end', '\n99.9% of learners said this was flawless.')
    desktop.root.update()
    assert 'not found' in desktop.evidence_status.get()
    decide_all_claims_safely = [c for c in desktop.ledger.claims]
    for claim in decide_all_claims_safely:
        desktop.claims_table.selection_set(claim.key)
        desktop.accept_claim()
    assert not desktop.ledger.complete  # the fabricated figure stays pending
    assert desktop.submit_for_approval() is False


def test_edit_after_submission_reopens_and_return_needs_notes(desktop, monkeypatch):
    load_sample(desktop)
    draft(desktop)
    decide_all_claims(desktop)
    submit(desktop)
    desktop.approver_entry.insert(0, 'Sam')
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Clarify the second recommendation.')
    assert desktop.return_for_changes()
    assert desktop.workflow.status == 'CHANGES REQUESTED'
    submit(desktop)
    desktop.editor.insert('end', '\nChanged after submission.')
    desktop.root.update()
    assert desktop.workflow.status == 'DRAFT'


def test_client_report_requires_learning_futures_lead(desktop, monkeypatch, tmp_path):
    load_sample(desktop)
    desktop.audience.set('client')
    draft(desktop)
    decide_all_claims(desktop)
    submit(desktop)
    desktop.approver_entry.insert(0, 'Sam')
    desktop.approver_role.set('Facilitator')
    desktop.confirmed.set(True)
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', lambda **kw: str(tmp_path / 'c.md'))
    assert desktop.export() is False
    desktop.approver_role.set('Learning Futures lead')
    assert desktop.export()


def test_fast_review_is_flagged(desktop):
    load_sample(desktop)
    draft(desktop)
    decide_all_claims(desktop)  # decided in well under a second each
    assert desktop.ledger.pace()['fast']
    assert 'Fast review' in desktop.pace_status.get()


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
    draft(desktop)
    assert not desktop.busy


def test_missing_gemini_key_falls_back_to_local_draft(desktop, monkeypatch):
    load_sample(desktop)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    draft(desktop)
    assert desktop.report.source_mode == 'Local Analysis'
    assert 'not set up' in desktop.status.get()
    assert all(c.origin != 'AI-written' for c in desktop.ledger.claims)


def test_gemini_failure_offers_local_draft(desktop, monkeypatch):
    load_sample(desktop)
    def fail(*a, **k):
        raise RuntimeError('Gemini quota reached.')
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.executive_summary', fail)
    desktop.generate()
    wait_for_load(desktop)
    assert desktop.report is None
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    desktop.generate()
    wait_for_load(desktop)
    assert desktop.report.source_mode == 'Local Analysis'


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
    desktop.revision_provider.set('Edit from feedback')
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


def test_gemini_revision_is_previewed_and_marked_ai_written(desktop, monkeypatch):
    load_sample(desktop)
    draft(desktop)
    calls = []
    def revise(self, context, section, current, instruction, audience):
        calls.append((section, instruction))
        return {'revised_section': 'A short summary of 500 responses for a busy manager.',
                'evidence': ['500 survey responses in the selected scope.'], 'note': ''}
    monkeypatch.setattr('src.ai.gemini_provider.GeminiAIProvider.revise_section', revise)
    assert desktop.revision_provider.get() == 'Ask Gemini'
    desktop.feedback.insert('1.0', 'write a short summary')
    desktop.root.update()
    desktop.propose_feedback()
    wait_for_load(desktop)
    assert calls == [('Executive Summary', 'write a short summary')]
    assert 'Evidence Gemini cited' in desktop.revision_preview.get('1.0', 'end')
    desktop.apply_feedback()
    desktop.refresh_claims()
    claim = next(c for c in desktop.ledger.claims if 'busy manager' in c.text)
    assert claim.origin == 'AI-written'
    assert claim.evidence == ['500 survey responses in the selected scope.']
    assert 'Gemini service' in desktop.editor.get('1.0', 'end')


def test_manual_edit_invalidates_feedback_preview(desktop):
    load_sample(desktop)
    desktop.generate()
    wait_for_load(desktop)
    desktop.revision_provider.set('Edit from feedback')
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
    file_label = desktop.file_name.cget('text')
    assert file_label.startswith('2 survey files loaded')
    assert 'survey' in file_label
    assert '+1 more' in file_label
    
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
    assert desktop.file_name.cget('text') == 'broken.csv'
    wait_for_load(desktop)
    assert desktop.file_name.cget('text').lower() == 'sample.csv'
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
