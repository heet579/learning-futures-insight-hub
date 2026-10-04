"""Gate 4 - separation of duties for report approval.

DRAFT -> (author submits) -> AWAITING HUMAN REVIEW -> (a different person approves) -> HUMAN REVIEWED
                                       |-> (approver returns with notes) -> CHANGES REQUESTED -> edits -> DRAFT
Any edit after submission or approval sends the report back to DRAFT.

Names are typed by the operator; this desktop prototype has no sign-in, so the record shows
who each person said they were, not an authenticated identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

APPROVER_ROLES = ("Learning Futures lead", "Program coordinator", "Facilitator")
CLIENT_APPROVER_ROLE = "Learning Futures lead"


@dataclass
class ReviewEvent:
    action: str
    actor: str
    notes: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReviewWorkflow:
    status: str = "DRAFT"
    reviewer: str = ""          # the author who prepared and submitted the report
    reviewer_role: str = ""
    approver: str = ""
    approver_role: str = ""
    events: list[ReviewEvent] = field(default_factory=list)

    @property
    def author(self) -> str:
        return self.reviewer

    def submit(self, reviewer: str, reviewer_role: str = "") -> None:
        if not reviewer.strip():
            raise ValueError("Enter the name of the person who prepared the report.")
        if self.status not in ("DRAFT", "CHANGES REQUESTED"):
            raise ValueError("Only a draft can be submitted.")
        self.reviewer = reviewer.strip()
        self.reviewer_role = reviewer_role.strip() or "Report author"
        self.approver = self.approver_role = ""
        self.status = "AWAITING HUMAN REVIEW"
        self.events.append(ReviewEvent("Submitted for review", self.reviewer, self.reviewer_role))

    def return_for_changes(self, actor: str, notes: str) -> None:
        if self.status != "AWAITING HUMAN REVIEW":
            raise ValueError("Only a submitted report can be returned.")
        if not notes.strip():
            raise ValueError("Change notes are required.")
        self.status = "CHANGES REQUESTED"
        self.events.append(ReviewEvent("Returned for changes", actor.strip(), notes.strip()))

    def approve(self, actor: str, notes: str = "", role: str = "", audience: str = "facilitator") -> None:
        if self.status != "AWAITING HUMAN REVIEW":
            raise ValueError("The report must be submitted for human review before approval.")
        actor = actor.strip()
        if not actor:
            raise ValueError("Enter the approver's name.")
        if actor.casefold() == self.reviewer.casefold():
            raise ValueError("The approver must be a different person from the author who submitted the report.")
        if audience == "client" and role != CLIENT_APPROVER_ROLE:
            raise ValueError(f"Client reports must be approved by a {CLIENT_APPROVER_ROLE}.")
        self.approver, self.approver_role = actor, role or "Approver"
        self.status = "HUMAN REVIEWED"
        self.events.append(ReviewEvent("Approved", actor, notes.strip() or "Required checks confirmed."))

    def reopen(self, reason: str = "Draft edited after submission.") -> bool:
        """Send a submitted or approved report back to DRAFT. Returns True if the status changed."""
        if self.status in ("AWAITING HUMAN REVIEW", "HUMAN REVIEWED"):
            self.status = "DRAFT"
            self.approver = self.approver_role = ""
            self.events.append(ReviewEvent("Reopened", "", reason))
            return True
        return False

    def times_returned(self) -> int:
        return sum(1 for e in self.events if e.action == "Returned for changes")
