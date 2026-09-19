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

