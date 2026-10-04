"""Gate 1 - a person confirms, re-categorises or rejects every theme before drafting.

Themes come from keyword rules and statistics, so they can be wrong (a keyword such as
"time" is not always about pacing). Only confirmed themes reach the report.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace

from src.models import AnalysisContext, Theme

CATEGORIES = ("Positive", "Improvement", "Review")


@dataclass
class ThemeDecision:
    status: str          # "confirmed" or "rejected"
    category: str        # category the reviewer settled on
    decided_at: float


class ThemeReview:
    def __init__(self, themes: list[Theme]):
        self.themes = list(themes)
        self.decisions: dict[str, ThemeDecision] = {}

    def decide(self, name: str, status: str, category: str | None = None, now: float | None = None) -> ThemeDecision:
        theme = self._theme(name)
        if status not in ("confirmed", "rejected"):
            raise ValueError("A theme can only be confirmed or rejected.")
        category = category or theme.category
        if category not in CATEGORIES:
            raise ValueError("Choose Positive, Improvement or Review.")
        decision = ThemeDecision(status, category, time.time() if now is None else now)
        self.decisions[name] = decision
        return decision

    def status_of(self, name: str) -> str:
        decision = self.decisions.get(name)
        if not decision:
            return "Pending"
        if decision.status == "rejected":
            return "Rejected"
        original = self._theme(name).category
        return "Confirmed" if decision.category == original else f"Confirmed as {decision.category}"

    @property
    def reviewed(self) -> int:
        return sum(1 for t in self.themes if t.name in self.decisions)

    @property
    def total(self) -> int:
        return len(self.themes)

    @property
    def complete(self) -> bool:
        return self.reviewed == self.total

    def counts(self) -> dict[str, int]:
        statuses = [d.status for d in self.decisions.values()]
        changed = sum(1 for t in self.themes if t.name in self.decisions
                      and self.decisions[t.name].status == "confirmed"
                      and self.decisions[t.name].category != t.category)
        return {"confirmed": statuses.count("confirmed"), "rejected": statuses.count("rejected"),
                "recategorised": changed, "pending": self.total - self.reviewed}

    def approved_themes(self) -> list[Theme]:
        kept = []
        for theme in self.themes:
            decision = self.decisions.get(theme.name)
            if decision and decision.status == "confirmed":
                kept.append(replace(theme, category=decision.category))
        return kept

    def reviewed_context(self, context: AnalysisContext) -> AnalysisContext:
        return AnalysisContext(context.metrics, self.approved_themes(), context.source_name,
                               context.course_name, context.warnings)

    def _theme(self, name: str) -> Theme:
        for theme in self.themes:
            if theme.name == name:
                return theme
        raise ValueError(f"Unknown theme: {name}")


def matched_keywords(comment: str, theme: Theme) -> list[str]:
    """Which of the theme's keywords actually occur in this comment (shown to the reviewer)."""
    lowered = comment.lower()
    return [k for k in theme.keywords if re.search(rf"\b{re.escape(k.lower())}\b", lowered)]
