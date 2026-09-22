"""Checks that numbers and quotes in a report draft are traceable to computed data.

Deliberately narrow: it verifies the specific claim shapes the report template
actually produces (percentages, rating means, response/comment counts, and
quoted feedback), not every number in the text. A reviewer still has to read
the draft; this only catches numbers and quotes that don't match anything real.
"""
import re
from dataclasses import dataclass
from src.models import AnalysisContext

PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
RATIO_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*5\b")
COUNT_RE = re.compile(r"\b(\d+)\s*(?:matching comment|related comment|response|comment)")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")


@dataclass
class Claim:
    kind: str
    text: str
    supported: bool


def _allowed_percentages(context: AnalysisContext) -> set[str]:
    metrics = context.metrics
    values = {
        metrics.get("recommendation_percent"),
        metrics.get("response_completeness"),
        metrics.get("satisfaction_percent"),
    }
    return {f"{v:.1f}" for v in values if v is not None}


def _allowed_ratios(context: AnalysisContext) -> set[str]:
    return {f"{v['mean']:.2f}" for v in context.metrics["ratings"].values() if v["mean"] is not None}


def _allowed_counts(context: AnalysisContext) -> set[str]:
    counts = {str(context.metrics["response_count"])}
    counts |= {str(t.frequency) for t in context.themes}
    counts |= {str(v["count"]) for v in context.metrics["ratings"].values()}
    return counts


def _allowed_quotes(context: AnalysisContext) -> set[str]:
    return {e.strip() for theme in context.themes for e in theme.evidence}


def check_claims(content: str, context: AnalysisContext) -> list[Claim]:
    allowed_pct = _allowed_percentages(context)
    allowed_ratio = _allowed_ratios(context)
    allowed_counts = _allowed_counts(context)
    allowed_quotes = _allowed_quotes(context)
    claims: list[Claim] = []
    for m in PERCENT_RE.finditer(content):
        claims.append(Claim("percentage", m.group(0), m.group(1) in allowed_pct))
    for m in RATIO_RE.finditer(content):
        claims.append(Claim("rating", m.group(0), m.group(1) in allowed_ratio))
    for m in COUNT_RE.finditer(content):
        claims.append(Claim("count", m.group(0), m.group(1) in allowed_counts))
    for m in QUOTE_RE.finditer(content):
        text = m.group(1).strip()
        claims.append(Claim("quote", text, text in allowed_quotes))
    return claims


def unsupported_claims(content: str, context: AnalysisContext) -> list[Claim]:
    return [c for c in check_claims(content, context) if not c.supported]
