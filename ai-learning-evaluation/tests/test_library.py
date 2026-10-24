import copy
import json
import pytest
from src.storage.reports import ReportRepository
from src.storage.snapshot import unpack
from src.ai.local_provider import LocalAnalysisProvider
from src.reporting.report_generator import generate_report
from test_account_session import session
from test_desktop import load_sample, decide_all_claims


def test_repository_owner_and_conflict(tmp_path):
    repository = ReportRepository(tmp_path / 'reports.db')
    args = dict(actor='alex', title='Draft', course='Course', status='DRAFT', snapshot={'schema': 1})
    rid, version = repository.save(**args)
    assert repository.list_owned('sam') == []
    with pytest.raises(ValueError):
        repository.load(rid, 'sam')
    with pytest.raises(ValueError):
        repository.save(**{**args, 'actor':'sam'}, report_id=rid, version=version)
    assert repository.save(**args, report_id=rid, version=version)[1] == 2
    with pytest.raises(ValueError):
        repository.save(**args, report_id=rid, version=version)
    rid2, _ = repository.save(**args)
    assert rid2 != rid
    assert len(ReportRepository(repository.path).list_owned('alex')) == 2


def test_restore_complete_draft_after_fresh_workspace(session, monkeypatch, tmp_path):
    session.repository = ReportRepository(tmp_path / 'reports.db')
    load_sample(session, count=30)
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    decide_all_claims(session)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Saved course report')
    assert session.save_library_draft()
    rid = session.library_id
    snapshot = copy.deepcopy(session.workspace_snapshot())
    assert not session.library_unsaved()
    # Importing a fresh dataset releases the previous draft ID.
    session.load_startup_data = lambda: None
    result = (session.frame.copy(), session.context, 0, [])
    session.apply_analysis(result)
    assert session.library_id is None
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    assert session.open_library_report(rid)
    assert session.workspace_snapshot() == snapshot
    assert session.ledger.complete
    assert session.theme_review.complete
    session.root.update()
    assert not session.library_unsaved()
    session.theme_review.decisions.clear()
    assert session.library_unsaved()
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    assert session.open_library_report(rid)
    session.refresh_library()
    assert session.library_rows.winfo_children()
    assert not session.library_unsaved()


def test_save_failure_preserves_unsaved_work(session, monkeypatch, tmp_path):
    session.repository = ReportRepository(tmp_path / 'reports.db')
    load_sample(session, count=12)
    session._apply_generated_report(generate_report(session.review_context(), 'client', LocalAnalysisProvider()))
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Draft')
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: None)
    monkeypatch.setattr(session.repository, 'save', lambda **kw: (_ for _ in ()).throw(OSError('disk full')))
    assert not session.save_library_draft()
    assert session.library_id is None
    assert session.library_unsaved()


def test_unknown_snapshot_rejected():
    with pytest.raises(ValueError):
        unpack({'schema':99})


def test_restart_restores_section_decision_and_safe_toggle(session, monkeypatch, tmp_path):
    import tkinter as tk
    from src.ui.desktop import DesktopApp
    from test_desktop import wait_for_load
    session.repository = ReportRepository(tmp_path / 'reports.db')
    load_sample(session, count=30)
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    session.revision_provider.set('Edit from feedback')
    session.feedback.insert('1.0', 'Add: - Review delivery next term.')
    session.propose_feedback()
    wait_for_load(session)
    section = session.pending_revision.sections[0]
    session.show_revision_comparison(section)
    session.apply_current_revision_section()
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Revision draft')
    assert session.save_library_draft()
    rid, path = session.library_id, session.repository.path
    expected = copy.deepcopy(session.workspace_snapshot())
    session.dispose_workspace()
    fresh_root = tk.Toplevel(session.root.master)
    fresh = DesktopApp(fresh_root, username='alex', on_logout=lambda: None)
    fresh.repository = ReportRepository(path)
    try:
        assert fresh.open_library_report(rid)
        assert fresh.workspace_snapshot() == expected
        assert fresh.revision_section_decisions[section] == 'applied'
        fresh.show_revision_comparison(section)
        fresh.keep_current_revision_section()
        assert fresh.revision_section_decisions[section] == 'kept'
        assert fresh.library_unsaved()
        fresh.apply_current_revision_section()
        assert fresh.revision_section_decisions[section] == 'applied'
        assert fresh.save_library_draft()
        assert fresh.library_version == 2
    finally:
        fresh.dispose_workspace()
        fresh_root.destroy()


def test_library_home_create_without_name_and_save_before_generation(session, monkeypatch):
    assert session.current_page == 3
    calls = []
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: calls.append(True) or 'Theme review')
    old_jobs = session.session_jobs.copy()
    assert session.create_report()
    assert session.current_page == 0
    assert calls == []
    assert not old_jobs.intersection(session.session_jobs)
    assert session.library_id is session.context is session.report is None
    load_sample(session, count=30, review=False)
    session.continue_report()
    assert session.current_page == 1
    assert session.next_button.instate(['disabled'])
    session.theme_table.selection_set('0')
    session.confirm_theme()
    session.audience.set('client')
    decisions = copy.deepcopy(session.theme_review.decisions)
    assert session.save_library_draft()
    rid = session.library_id
    assert calls == [True]
    assert session.save_library_draft()
    assert calls == [True]  # Existing drafts keep their name.
    assert session.create_report()
    assert session.context is None
    assert session.open_library_report(rid)
    assert session.report is None
    assert session.theme_review.decisions == decisions
    assert session.audience.get() == 'client'
    assert session.current_page == 1
    assert not session.library_unsaved()
    assert session.library_save_button.instate(['!disabled'])


def test_create_cancel_preserves_current_work_and_saved_copy(session, monkeypatch):
    load_sample(session, count=30, review=False)
    frame = session.frame
    assert not session.create_report()
    assert session.frame is frame
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: None)
    assert not session.save_library_draft()
    assert session.library_id is None
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'First')
    assert session.save_library_draft()
    rid = session.library_id
    assert session.create_report()
    load_sample(session, count=12, review=False)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Second')
    assert session.save_library_draft()
    assert session.library_id != rid
    assert len(session.repository.list_owned('alex')) == 2


def test_studio_guides_read_check_and_approval(session):
    from test_desktop import review_themes
    load_sample(session, count=30, review=False)
    session.navigate(1)
    assert session.next_button.instate(['disabled'])
    review_themes(session)
    session.continue_report()
    assert session.current_page == 2
    assert session.next_button.instate(['disabled'])
    assert session.generate_button.instate(['!disabled'])
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    assert session.report_tabs.index(session.report_tabs.select()) == 1
    session.continue_report()
    assert session.report_tabs.index(session.report_tabs.select()) == 3
    decide_all_claims(session)
    session.library_title = 'Visible handoff'
    session.continue_report()
    assert session.workflow.status == 'AWAITING HUMAN REVIEW'
    assert not session.review_drawer_visible
    assert 'Submitted and saved' in session.handoff_title.cget('text')


def test_schema_one_draft_still_opens(session, monkeypatch):
    from src.storage.snapshot import decode, pack
    load_sample(session, count=12)
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    state = decode(session.workspace_snapshot()['state'])
    state.pop('audience')
    old = pack(state)
    old['schema'] = 1
    rid, _ = session.repository.save(actor='alex', title='Older draft', course='Course', status='DRAFT', snapshot=old)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    assert session.open_library_report(rid)
    assert session.audience.get() == 'facilitator'
    assert not session.library_unsaved()


def test_regenerate_requires_confirmation_even_when_saved(session, monkeypatch):
    load_sample(session, count=12)
    session._apply_generated_report(generate_report(session.review_context(), 'facilitator', LocalAnalysisProvider()))
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Saved')
    assert session.save_library_draft()
    before = session.workspace_snapshot()
    session.generate()  # askyesno is False: keep this saved draft's current text.
    assert not session.busy
    assert session.workspace_snapshot() == before


def test_primary_navigation_fits_small_window(session):
    session.root.geometry('1080x740')
    for page in (0, 1, 2, 3):
        session.navigate(page)
        # Process native window mapping as well as idle layout on Windows.
        session.root.update()
        widgets = [session.account_button, session.nav_buttons[page]]
        widgets += ([session.create_report_button] if page == 3 else
                    [session.studio_save_button] if page == 2 else
                    [session.library_save_button, session.next_button, session.workspace_caption])
        for widget in widgets:
            assert widget.winfo_width() > 20
            assert widget.winfo_rootx() >= session.root.winfo_rootx()
            assert widget.winfo_rootx() + widget.winfo_width() <= session.root.winfo_rootx() + session.root.winfo_width()
    session.navigate(2)
    assert not session.report_tabbar.winfo_manager()
    load_sample(session, count=12)
    session._apply_generated_report(generate_report(session.review_context(), 'client', LocalAnalysisProvider()))
    session.navigate(2)
    session.root.update_idletasks()
    assert session.report_tabbar.winfo_manager() == 'pack'
    buttons = [pair[0] for pair in session.report_tab_buttons]
    assert buttons[1].winfo_rootx() < buttons[0].winfo_rootx()  # Reading preview leads.
    assert buttons[-1].winfo_rootx() + buttons[-1].winfo_width() <= session.root.winfo_rootx() + session.root.winfo_width()


def test_repository_rename_delete_owner_version_and_content(tmp_path):
    repository = ReportRepository(tmp_path / 'reports.db')
    snapshot = {'schema': 2, 'progress': ['reviewed']}
    rid, version = repository.save(actor='alex', title='Original', course='Course',
                                   status='DRAFT', snapshot=snapshot)
    for actor, expected_version in [('sam', version), ('alex', version + 1)]:
        with pytest.raises(ValueError):
            repository.rename(actor=actor, report_id=rid, version=expected_version, title='Changed')
        with pytest.raises(ValueError):
            repository.delete(actor=actor, report_id=rid, version=expected_version)
    with pytest.raises(ValueError):
        repository.rename(actor='alex', report_id=rid, version=version, title='  ')
    assert repository.load(rid, 'alex')['title'] == 'Original'
    new_version = repository.rename(actor='alex', report_id=rid, version=version, title='  Renamed  ')
    row = repository.load(rid, 'alex')
    assert row['title'] == 'Renamed'
    assert row['snapshot'] == snapshot
    assert row['version'] == new_version == version + 1
    with pytest.raises(ValueError):
        repository.delete(actor='alex', report_id=rid, version=version)
    repository.delete(actor='alex', report_id=rid, version=new_version)
    assert repository.list_owned('alex') == []
    with pytest.raises(ValueError):
        repository.load(rid, 'alex')


@pytest.mark.parametrize('status', ['AWAITING HUMAN REVIEW', 'HUMAN REVIEWED'])
def test_repository_management_rejects_noneditable_reports(tmp_path, status):
    repository = ReportRepository(tmp_path / 'reports.db')
    rid, version = repository.save(actor='alex', title='Draft', course='Course', status='DRAFT', snapshot={})
    with repository.connect() as db:
        db.execute('UPDATE reports SET status=? WHERE id=?', (status, rid))
    with pytest.raises(ValueError):
        repository.rename(actor='alex', report_id=rid, version=version, title='Renamed')
    with pytest.raises(ValueError):
        repository.delete(actor='alex', report_id=rid, version=version)
    assert repository.load(rid, 'alex')['title'] == 'Draft'


def saved_library_row(session, monkeypatch):
    load_sample(session, count=12, review=False)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Original')
    assert session.save_library_draft()
    return session.repository.list_owned('alex')[0]


def test_rename_open_draft_preserves_unsaved_changes_and_next_save(session, monkeypatch):
    row = saved_library_row(session, monkeypatch)
    saved = copy.deepcopy(session.saved_snapshot)
    session.theme_table.selection_set('0')
    session.confirm_theme()
    edited = copy.deepcopy(session.workspace_snapshot())
    assert session.library_unsaved()
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: '  Renamed  ')
    assert session.rename_library_report(row)
    assert session.library_id == row['id']
    assert session.library_title == 'Renamed'
    assert session.workspace_snapshot() == edited
    assert session.saved_snapshot == saved
    assert session.repository.load(row['id'], 'alex')['snapshot'] == saved
    assert session.library_unsaved()
    assert session.save_library_draft()
    assert len(session.repository.list_owned('alex')) == 1
    stored = session.repository.load(row['id'], 'alex')
    assert stored['snapshot'] == edited
    assert stored['title'] == 'Renamed'
    assert stored['version'] == 3


@pytest.mark.parametrize('title', [None, '   '])
def test_rename_cancel_or_empty_keeps_draft(session, monkeypatch, title):
    row = saved_library_row(session, monkeypatch)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: title)
    assert not session.rename_library_report(row)
    assert session.library_title == 'Original'
    assert session.library_version == row['version']
    assert not session.library_unsaved()


def test_delete_cancel_then_confirm_clears_open_workspace(session, monkeypatch):
    row = saved_library_row(session, monkeypatch)
    session.theme_table.selection_set('0')
    session.confirm_theme()
    before = session.workspace_snapshot()
    assert not session.delete_library_report(row)
    assert session.workspace_snapshot() == before
    assert len(session.repository.list_owned('alex')) == 1
    prompts = []
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: prompts.append((a, k)) or True)
    assert session.delete_library_report(row)
    assert 'Original' in prompts[0][0][1]
    assert 'unsaved changes' in prompts[0][0][1]
    assert prompts[0][1]['default'] == 'no'
    assert session.current_page == 3
    assert session.library_id is session.context is session.report is session.raw is None
    assert session.username == 'alex'
    assert session.repository.list_owned('alex') == []
    assert not session.save_library_draft()  # Cannot accidentally re-save a deleted workspace.


def test_manage_other_draft_leaves_open_workspace_intact(session, monkeypatch):
    row = saved_library_row(session, monkeypatch)
    other_id, _ = session.repository.save(actor='alex', title='Other', course='Course',
        status='DRAFT', snapshot=session.workspace_snapshot())
    other = next(r for r in session.repository.list_owned('alex') if r['id'] == other_id)
    before = session.workspace_snapshot()
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Other renamed')
    assert session.rename_library_report(other)
    other = next(r for r in session.repository.list_owned('alex') if r['id'] == other_id)
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    assert session.delete_library_report(other)
    assert session.workspace_snapshot() == before
    assert session.library_id == row['id']
    assert session.library_title == 'Original'
    assert not session.library_unsaved()
    assert [r['id'] for r in session.repository.list_owned('alex')] == [row['id']]


@pytest.mark.parametrize('operation', ['rename', 'delete'])
def test_manage_stale_open_draft_keeps_current_edits(session, monkeypatch, operation):
    row = saved_library_row(session, monkeypatch)
    session.repository.rename(actor='alex', report_id=row['id'], version=row['version'], title='Another workspace')
    fresh_row = session.repository.list_owned('alex')[0]
    before = session.workspace_snapshot()
    errors = []
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **k: errors.append(a))
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Attempt')
    assert not getattr(session, f'{operation}_library_report')(fresh_row)
    assert errors
    assert session.workspace_snapshot() == before
    assert session.library_id == row['id']
    assert session.library_version == row['version']
    assert session.repository.load(row['id'], 'alex')['title'] == 'Another workspace'


def test_library_actions_busy_guard_and_small_window(session, monkeypatch):
    row = saved_library_row(session, monkeypatch)
    session.root.geometry('1080x740')
    session.navigate(3)
    session.root.update_idletasks()
    assert len(session.library_action_buttons) == 4
    item = session.library_cards[row['id']]
    assert not item['panel'].winfo_ismapped()
    for button in (item['resume'], item['trigger']):
        assert button.winfo_ismapped()
        assert button.winfo_rootx() + button.winfo_width() <= session.root.winfo_rootx() + session.root.winfo_width()
    session.busy = True
    session.sync_controls()
    assert all(button.instate(['disabled']) for button in session.library_action_buttons)
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: pytest.fail('Prompt while busy'))
    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: pytest.fail('Prompt while busy'))
    assert not session.rename_library_report(row)
    assert not session.delete_library_report(row)
    session.busy = False
    session.sync_controls()
    assert all(button.instate(['!disabled']) for button in session.library_action_buttons)


def test_library_more_menu_selection_dismissal_and_rename(session, monkeypatch):
    from types import SimpleNamespace
    first = saved_library_row(session, monkeypatch)
    second_id, _ = session.repository.save(actor='alex', title='Second report', course='Course',
        status='DRAFT', snapshot=session.workspace_snapshot())
    session.navigate(3)
    session.root.update_idletasks()
    first_card, second_card = session.library_cards[first['id']], session.library_cards[second_id]
    assert 'First reviewer: alex' in first_card['details'].cget('text')
    assert 'Last saved:' in first_card['details'].cget('text')
    assert not first_card['panel'].winfo_manager()
    first_card['trigger'].invoke()
    assert first_card['panel'].winfo_manager() == 'grid'
    second_card['trigger'].invoke()
    assert not first_card['panel'].winfo_manager()
    assert second_card['panel'].winfo_manager() == 'grid'
    session.dismiss_library_actions(SimpleNamespace(widget=second_card['rename']))
    assert session.library_open_actions is second_card
    session.dismiss_library_actions(SimpleNamespace(widget=session.page_title))
    assert session.library_open_actions is None
    assert not second_card['panel'].winfo_manager()
    first_card['trigger'].invoke()
    first_card['trigger'].invoke()
    assert session.library_open_actions is None
    first_card['trigger'].invoke()
    session.root.update()
    # Generated key events need keyboard focus, just as a real keypress does.
    first_card['rename'].focus_force()
    session.root.update()
    first_card['rename'].event_generate('<Escape>')
    session.root.update()
    assert session.library_open_actions is None
    first_card['trigger'].invoke()
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'Renamed from menu')
    first_card['rename'].invoke()
    assert session.repository.load(first['id'], 'alex')['title'] == 'Renamed from menu'
    assert session.library_open_actions is None
    session.library_cards[first['id']]['trigger'].invoke()
    session.navigate(0)
    assert session.library_open_actions is None


def test_library_expanded_card_fits_small_window_and_delete_cancel(session, monkeypatch):
    row = saved_library_row(session, monkeypatch)
    long_title = 'Long report title with several words ' * 5
    session.repository.rename(actor='alex', report_id=row['id'], version=row['version'], title=long_title)
    session.root.geometry('1080x740')
    session.navigate(3)
    item = session.library_cards[row['id']]
    item['trigger'].invoke()
    session.root.update_idletasks()
    for widget in (item['card'], item['resume'], item['trigger'], item['rename'], item['delete']):
        assert widget.winfo_ismapped()
        assert widget.winfo_rootx() >= session.root.winfo_rootx()
        assert widget.winfo_rootx() + widget.winfo_width() <= session.root.winfo_rootx() + session.root.winfo_width()
    item['delete'].invoke()  # Confirmation defaults to cancellation in this fixture.
    assert session.library_open_actions is None
    assert len(session.repository.list_owned('alex')) == 1
