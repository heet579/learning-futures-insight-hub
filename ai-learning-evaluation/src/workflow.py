"""Human-in-the-loop workflow state for the prototype."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ReviewEvent:
    action: str
    actor: str
    notes: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReviewWorkflow:
    status: str = "DRAFT"
    reviewer: str = ""
    reviewer_role: str = ""
    events: list[ReviewEvent] = field(default_factory=list)

    def submit(self, reviewer: str, reviewer_role: str) -> None:
        if not reviewer.strip():
            raise ValueError("A reviewer is required.")
        self.reviewer = reviewer.strip()
        self.reviewer_role = reviewer_role.strip() or "Learning Futures reviewer"
        self.status = "AWAITING HUMAN REVIEW"
        self.events.append(ReviewEvent("Submitted for review", self.reviewer, self.reviewer_role))

    def return_for_changes(self, actor: str, notes: str) -> None:
        if not notes.strip():
            raise ValueError("Change notes are required.")
        self.status = "CHANGES REQUESTED"
        self.events.append(ReviewEvent("Returned for changes", actor.strip(), notes.strip()))

    def approve(self, actor: str, notes: str = "") -> None:
        if self.status != "AWAITING HUMAN REVIEW":
            raise ValueError("The report must be submitted for human review before approval.")
        self.status = "HUMAN REVIEWED"
        self.events.append(ReviewEvent("Approved", actor.strip(), notes.strip() or "Required checks confirmed."))
