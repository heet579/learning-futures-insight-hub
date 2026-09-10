import pytest

from src.workflow import ReviewWorkflow


def test_human_review_workflow_requires_submission():
    workflow = ReviewWorkflow()
    with pytest.raises(ValueError):
        workflow.approve("Reviewer")
    workflow.submit("Alex", "Learning Futures lead")
    workflow.approve("Alex")
    assert workflow.status == "HUMAN REVIEWED"
    assert [event.action for event in workflow.events] == ["Submitted for review", "Approved"]


def test_return_for_changes_requires_notes():
    workflow = ReviewWorkflow()
    workflow.submit("Alex", "Reviewer")
    with pytest.raises(ValueError):
        workflow.return_for_changes("Alex", "")
    workflow.return_for_changes("Alex", "Clarify the recommendation evidence.")
    assert workflow.status == "CHANGES REQUESTED"
