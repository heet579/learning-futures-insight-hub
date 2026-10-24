"""Visible handoff outcomes must follow persisted state, including failed writes."""
from test_account_session import session
from test_handoff import ready_report, another_account


def assert_visible_inside(app, widget):
    # Native map events must run before querying visibility on Windows.
    app.root.update()
    assert widget.winfo_ismapped()
    assert widget.winfo_width() > 20
    assert widget.winfo_rootx() >= app.root.winfo_rootx()
    assert widget.winfo_rootx() + widget.winfo_width() <= app.root.winfo_rootx() + app.root.winfo_width()
    assert widget.winfo_rooty() + widget.winfo_height() <= app.root.winfo_rooty() + app.root.winfo_height()


def test_save_and_failed_submission_never_claim_handoff_complete(session, monkeypatch):
    ready_report(session)
    session.navigate(2)
    assert session.save_library_draft()
    assert 'Draft saved' in session.handoff_title.cget('text')
    assert 'not submitted' in session.handoff_message.cget('text')
    assert not session.repository.list_pending('sam')
    errors = []
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda *a, **kw: errors.append(a))
    def unavailable(**kwargs):
        raise OSError('Storage unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(session.repository, 'save', unavailable)
        assert not session.submit_persistent()
    assert session.workflow.status == 'DRAFT'
    with monkeypatch.context() as patch:
        patch.setattr(session.repository, 'transition', unavailable)
        assert not session.submit_persistent()
    assert len(errors) == 2
    assert 'Submitted and saved' not in session.handoff_title.cget('text')
    assert not session.repository.list_pending('sam')
    session.submit_button.invoke()
    assert session.workflow.status == 'AWAITING HUMAN REVIEW'
    assert 'Submitted and saved' in session.handoff_title.cget('text')
    assert 'Pending review' in session.handoff_notice_text.cget('text')
    assert session.repository.list_pending('sam')[0]['id'] == session.library_id
    assert not session.review_drawer_visible


def test_return_feedback_visible_after_restart_and_multiple_rounds(session, monkeypatch):
    ready_report(session)
    assert session.submit_persistent()
    rid = session.library_id
    notes = ['Please explain the recommendation.\n' + 'Include context and supporting evidence. ' * 12 + 'END OF FIRST NOTE',
             'Second round: clarify who will act on this recommendation.']
    for note in notes:
        with another_account(session, 'sam') as reviewer:
            reviewer.refresh_library()
            assert 'need your second review' in reviewer.library_attention.cget('text')
            assert reviewer.open_library_report(rid)
            monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **kw: note)
            assert reviewer.return_persistent()
        with another_account(session, 'alex') as owner:
            owner.refresh_library()
            card = owner.library_cards[rid]
            assert 'Returned by sam:' in card['feedback'].cget('text')
            assert card['resume'].cget('text') == 'Read feedback →'
            assert 'returned report' in owner.library_attention.cget('text')
            assert owner.open_library_report(rid)
            assert note in owner.handoff_notes.get('1.0', 'end-1c')
            assert owner.submit_button.cget('text') == 'Resubmit for review'
            assert not owner.review_drawer_visible
            assert owner.save_library_draft()
            assert owner.submit_persistent()
            assert note in owner.review_history_text()
    with another_account(session, 'sam') as reviewer:
        assert reviewer.open_library_report(rid)
        assert all(note in reviewer.review_history_text() for note in notes)
        assert reviewer.workflow.times_returned() == 2


def test_review_actions_and_feedback_fit_small_window(session, monkeypatch):
    ready_report(session)
    session.root.geometry('1080x740')
    session.navigate(2)
    assert_visible_inside(session, session.submit_button)
    assert session.submit_persistent()
    for widget in (session.handoff_library, session.handoff_switch):
        assert_visible_inside(session, widget)
    rid = session.library_id
    with another_account(session, 'sam') as reviewer:
        reviewer.root.geometry('1080x740')
        assert reviewer.open_library_report(rid)
        for widget in (reviewer.export_button, reviewer.return_button, reviewer.review_check):
            assert_visible_inside(reviewer, widget)
        assert reviewer.report_tabs.winfo_height() >= 140
        monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **kw: 'Please clarify. ' * 200)
        assert reviewer.return_persistent()
    assert session.open_library_report(rid)
    assert_visible_inside(session, session.handoff_feedback_toggle)
    assert not session.feedback_expanded
    session.handoff_feedback_toggle.invoke()
    for widget in (session.handoff_notes, session.handoff_edit, session.submit_button):
        assert_visible_inside(session, widget)
    assert session.report_tabs.winfo_height() >= 140
    assert session.submit_persistent()
    with another_account(session, 'sam') as reviewer:
        reviewer.root.geometry('1080x740')
        assert reviewer.open_library_report(rid)
        reviewer.confirmed.set(True)
        assert reviewer.approve_persistent()
        assert 'Approved and saved' in reviewer.handoff_title.cget('text')
        assert_visible_inside(reviewer, reviewer.export_button)
        assert not reviewer.handoff_options.winfo_manager()


def test_progress_reopens_checks_and_links_to_work(session, monkeypatch):
    from test_desktop import decide_all_claims
    ready_report(session)
    assert [step[0] for step in session.review_progress_steps()] == ['done', 'done', 'done', 'active', 'pending']
    session.set_editor_text(session.editor.get('1.0', 'end-1c') + '\n\nWe recommend discussing delivery next term.')
    session.refresh_claims()
    assert session.review_progress_steps()[2][0] != 'done'
    assert session.submit_button.instate(['disabled'])
    session.open_progress_step(2)
    assert session.current_page == 2
    assert session.report_tabs.index(session.report_tabs.select()) == 3
    decide_all_claims(session)
    assert session.submit_persistent()
    assert [s[0] for s in session.review_progress_steps()] == ['done', 'done', 'done', 'done', 'active']
    with another_account(session, 'sam') as reviewer:
        assert reviewer.open_library_report(session.library_id)
        monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **kw: 'Explain the delivery recommendation.')
        assert reviewer.return_persistent()
    assert session.open_library_report(session.library_id)
    assert [s[0] for s in session.review_progress_steps()][3:] == ['attention', 'attention']
    session.open_progress_step(4)
    assert session.feedback_expanded
    assert 'Explain the delivery recommendation.' in session.handoff_notes.get('1.0', 'end-1c')
    session.themes_changed_since_draft = True
    session.update_review_panel()
    assert session.review_progress_steps()[2][0] == 'attention'
    assert session.submit_button.instate(['disabled'])


def test_approved_preview_matches_saved_export_and_compact_layout(session, monkeypatch):
    ready_report(session)
    session.navigate(2)
    session.root.geometry('1080x740')
    session.root.update_idletasks()
    assert not session.journey_bar.winfo_ismapped()
    assert session.report_tabs.winfo_height() / session.pages[2].winfo_height() >= .60
    assert session.submit_persistent()
    rid = session.library_id
    with another_account(session, 'sam') as reviewer:
        assert reviewer.open_library_report(rid)
        reviewer.confirmed.set(True)
        assert reviewer.approve_persistent()
        assert all(s[0] == 'done' for s in reviewer.review_progress_steps())
        assert reviewer.review_drawer_text.get() == 'Review progress · 5/5'
        rendered = []
        original_render = reviewer.render
        def capture_render(widget, content):
            rendered.append(content)
            original_render(widget, content)
        monkeypatch.setattr(reviewer, 'render', capture_render)
        reviewer.refresh_preview()
        assert rendered == [reviewer.approved_export]
        assert 'Status: HUMAN REVIEWED' in reviewer.preview.get('1.0', 'end-1c')
        assert 'DRAFT — REQUIRES HUMAN REVIEW' not in reviewer.preview.get('1.0', 'end-1c')
        assert reviewer.handoff_success
        reviewer.root.update_idletasks()
        height_with_notice = reviewer.report_tabs.winfo_height()
        reviewer.dismiss_handoff_success()
        reviewer.root.update_idletasks()
        assert not reviewer.handoff_notice.winfo_manager()
        assert reviewer.report_tabs.winfo_height() > height_with_notice
    assert session.open_library_report(rid)
    session.root.update_idletasks()
    assert not session.handoff_success
    assert not session.generate_button.winfo_ismapped()
    assert not session.studio_save_button.winfo_ismapped()
    assert not session.audience.winfo_ismapped()
    assert not session.report_tab_buttons[0][0].winfo_ismapped()
    assert not session.report_tab_buttons[2][0].winfo_ismapped()
    # Tk fonts and wrapping differ between macOS and Linux. Use the same
    # minimum reading-area share as drafts, plus a useful absolute height.
    # The relative check above verifies that collapsing the notice frees space.
    assert session.report_tabs.winfo_height() / session.pages[2].winfo_height() >= .60
    assert session.report_tabs.winfo_height() >= 300
    for widget in (session.export_button, session.review_drawer_button):
        assert_visible_inside(session, widget)
    session.select_report_tab(0)
    assert session.report_tabs.index(session.report_tabs.select()) == 1
    session.create_report()
    ready_report(session)
    session.navigate(2)
    session.root.update_idletasks()
    assert_visible_inside(session, session.report_tab_buttons[0][0])
    assert_visible_inside(session, session.report_tab_buttons[2][0])
