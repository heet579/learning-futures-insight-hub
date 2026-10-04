"""Checks that numbers and quotes in a report draft are traceable to computed data.

Rounded figures are accepted when a real value rounds to them at the precision
written ("97%" for 97.4%), and "n/5" with a whole number is read as a scale point.

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


def _decimals(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def _matches(stated: str, values) -> bool:
    """A stated figure is supported when a real value rounds to it at the precision written.
    "97%", "97.4%" and "97.43%" all match 97.43; "98%" does not."""
    try:
        number = float(stated)
    except ValueError:
        return False
    places = _decimals(stated)
    return any(v is not None and round(float(v) + 1e-9, places) == round(number, places) for v in values)


def _allowed_percentages(context: AnalysisContext) -> list[float]:
    metrics = context.metrics
    values = [metrics.get("recommendation_percent"), metrics.get("response_completeness"),
              metrics.get("satisfaction_percent")]
    for rating in metrics["ratings"].values():
        n = rating.get("count") or 0
        distribution = rating.get("distribution") or {}
        if n:
            values += [count / n * 100 for count in distribution.values()]
            values.append((distribution.get("4", 0) + distribution.get("5", 0)) / n * 100)
    return [v for v in values if v is not None]


def _allowed_ratios(context: AnalysisContext) -> list[float]:
    return [v["mean"] for v in context.metrics["ratings"].values() if v["mean"] is not None]


def _allowed_counts(context: AnalysisContext) -> set[str]:
    metrics = context.metrics
    counts = {str(metrics["response_count"])}
    counts |= {str(t.frequency) for t in context.themes}
    for rating in metrics["ratings"].values():
        counts.add(str(rating["count"]))
        counts |= {str(c) for c in (rating.get("distribution") or {}).values()}
    for key in ("satisfaction_count", "recommendation_count", "recommendation_total"):
        if metrics.get(key) is not None:
            counts.add(str(metrics[key]))
    return counts


def _allowed_quotes(context: AnalysisContext) -> set[str]:
    return {e.strip() for theme in context.themes for e in theme.evidence}


def _ratio_supported(stated: str, means: list[float]) -> bool:
    # "5/5" or "4/5" names a point on the rating scale, not a calculated result.
    if "." not in stated and stated.isdigit() and 1 <= int(stated) <= 5:
        return True
    return _matches(stated, means)


def check_claims(content: str, context: AnalysisContext) -> list[Claim]:
    allowed_pct = _allowed_percentages(context)
    allowed_ratio = _allowed_ratios(context)
    allowed_counts = _allowed_counts(context)
    allowed_quotes = _allowed_quotes(context)
    claims: list[Claim] = []
    for m in PERCENT_RE.finditer(content):
        claims.append(Claim("percentage", m.group(0), _matches(m.group(1), allowed_pct)))
    for m in RATIO_RE.finditer(content):
        claims.append(Claim("rating", m.group(0), _ratio_supported(m.group(1), allowed_ratio)))
    for m in COUNT_RE.finditer(content):
        claims.append(Claim("count", m.group(0), m.group(1) in allowed_counts))
    for m in QUOTE_RE.finditer(content):
        text = m.group(1).strip()
        claims.append(Claim("quote", text, text in allowed_quotes))
    return claims


def unsupported_claims(content: str, context: AnalysisContext) -> list[Claim]:
    return [c for c in check_claims(content, context) if not c.supported]
