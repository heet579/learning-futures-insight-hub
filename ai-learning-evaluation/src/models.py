from dataclasses import dataclass, field
from typing import Any

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    missing_columns: list[str] = field(default_factory=list)

@dataclass
class Theme:
    name: str
    keywords: list[str]
    frequency: int
    category: str
    evidence: list[str]

@dataclass
class AnalysisContext:
    metrics: dict[str, Any]
    themes: list[Theme]
    source_name: str
    course_name: str
    warnings: list[str] = field(default_factory=list)

@dataclass
class ReportDraft:
    audience: str
    content: str
    status: str = "DRAFT — REQUIRES HUMAN REVIEW"
    mode: str = "Local Analysis"
    # The text exactly as first generated; the claim ledger uses it to tell AI-written
    # sentences from later human edits and to measure how much AI wording survived.
    original: str = ""
    # Recommendation text -> calculated facts the AI cited for it.
    evidence: dict[str, list[str]] = field(default_factory=dict)
    # Who wrote the first draft ("Gemini" or "Local Analysis"); unlike `mode` it never changes.
    source_mode: str = ""

