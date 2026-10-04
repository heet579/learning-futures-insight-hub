import pytest

from src.workflow import ReviewWorkflow


def test_human_review_workflow_requires_submission():
    workflow = ReviewWorkflow()
    with pytest.raises(ValueError):
        workflow.approve("Reviewer")
    workflow.submit("Alex", "Learning Futures lead")
    workflow.approve("Sam")
    assert workflow.status == "HUMAN REVIEWED"
    assert [event.action for event in workflow.events] == ["Submitted for review", "Approved"]


def test_author_cannot_approve_own_report():
    workflow = ReviewWorkflow()
    workflow.submit("Alex")
    with pytest.raises(ValueError, match="different person"):
        workflow.approve(" alex ")
    assert workflow.status == "AWAITING HUMAN REVIEW"


def test_client_report_needs_learning_futures_lead():
    workflow = ReviewWorkflow()
    workflow.submit("Alex")
    with pytest.raises(ValueError, match="Learning Futures lead"):
        workflow.approve("Sam", role="Facilitator", audience="client")
    workflow.approve("Sam", role="Learning Futures lead", audience="client")
    assert workflow.approver_role == "Learning Futures lead"


def test_return_for_changes_requires_notes():
    workflow = ReviewWorkflow()
    workflow.submit("Alex", "Reviewer")
    with pytest.raises(ValueError):
        workflow.return_for_changes("Sam", "")
    workflow.return_for_changes("Sam", "Clarify the recommendation evidence.")
    assert workflow.status == "CHANGES REQUESTED"
    workflow.submit("Alex")
    assert workflow.times_returned() == 1


def test_edit_after_submission_reopens_draft():
    workflow = ReviewWorkflow()
    workflow.submit("Alex")
    assert workflow.reopen()
    assert workflow.status == "DRAFT"
    assert not workflow.reopen()
