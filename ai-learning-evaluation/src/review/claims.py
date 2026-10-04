"""Gates 2, 3 and 5 - the claim ledger.

The draft is split into claims (one per bullet or sentence) and every learner quote is a
separate item. Each claim shows where it came from (calculated, AI-written or edited by a
person) and the evidence behind it. A person must accept or reject every claim and clear or
remove every quote before the report can be submitted. Decision timing is recorded so a
very fast run of approvals is flagged as a possible rubber stamp.
"""
from __future__ import annotations

import hashlib
import re
import statistics
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.models import AnalysisContext, ReportDraft
from src.reporting.grounding import QUOTE_RE, check_claims

# Sections whose unchanged wording is fixed template text. Their original lines are not
# listed for review, but anything a person adds or changes in them is.
TEMPLATE_SECTIONS = ("Course Information", "Learner Feedback Summary", "Human Review Status")
# Written by the application itself (method disclosure), never by the AI or the reviewer.
SYSTEM_SECTIONS = ("Analysis method", "AI / Automated Analysis Disclosure", "Review record")
AI_SECTIONS = ("Executive Summary", "Recommendations")
FAST_GAP_SECONDS = 3.0
FAST_MIN_DECISIONS = 5

# Capitalised words that are not personal names in this domain.
_NOT_NAMES = {
    "I", "The", "A", "An", "This", "That", "These", "Those", "It", "We", "Our", "My", "Your", "They", "He", "She",
    "Course", "Courses", "Facilitator", "Facilitators", "Presenter", "Presenters", "Learning", "Futures", "Overall",
    "Satisfaction", "Content", "Quality", "Relevance", "Effectiveness", "Recommendation", "Positive", "Improvement",
    "Review", "Emerging", "Pacing", "Engagement", "Practical", "Examples", "Case", "Technical", "Materials",
    "University", "Adelaide", "Australia", "South", "PACE", "Professional", "Continuing", "Education", "Q",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "Zoom", "Teams", "Microsoft", "Excel", "PowerPoint", "Word", "Gemini", "AI",
    "Representative", "Would", "Key", "Mean", "Strongly", "Somewhat", "Very", "Great", "Good", "More", "Less",
    "Thank", "Thanks", "Some", "All", "Many", "Most", "No", "Yes", "Not", "If", "When", "And", "But", "So",
}
_WORD = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"])")


@dataclass
class LedgerClaim:
    key: str
    section: str
    text: str
    kind: str                   # "statement" or "quote"
    origin: str                 # "Calculated", "AI-written" or "Human-edited"
    line: str                   # the full draft line the claim sits in
    problems: list[str] = field(default_factory=list)
    possible_names: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    checks: list = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.problems or self.possible_names)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


_COMMON_STARTS = {
    "How", "What", "Why", "Where", "Which", "Who", "Having", "Being", "Lots", "Plenty", "Everything", "Nothing",
    "Overall", "Really", "Definitely", "Maybe", "Perhaps", "Also", "Just", "Only", "Even", "Very", "Too",
    "Interaction", "Examples", "Example", "Content", "Course", "Learning", "Presenter", "Facilitator",
    "Great", "Good", "Excellent", "Amazing", "Fantastic", "Useful", "Helpful", "Clear", "Well", "Better",
    # Imperative verbs that open recommendations.
    "Pilot", "Add", "Run", "Consider", "Introduce", "Maintain", "Explore", "Provide", "Use", "Keep", "Offer",
    "Schedule", "Collect", "Gather", "Test", "Share", "Allow", "Build", "Create", "Develop", "Monitor", "Track",
    "Ensure", "Include", "Reduce", "Increase", "Extend", "Shorten", "Clarify", "Continue", "Embed", "Invite",
    "Ask", "Check", "Confirm", "Agree", "Trial", "Pair", "Plan", "Prepare", "Encourage", "Balance", "Allocate",
    "Adjust", "Revise", "Focus", "Highlight", "Celebrate", "Retain", "Follow", "Survey", "Compare", "Measure",
    "Learners", "Participants", "Respondents", "Feedback", "Several", "Fewer", "One", "Two", "Three", "Four",
    "Five", "Both", "Each", "Every", "Few", "Only", "Ratings", "Responses", "Comments", "Themes",
}
_SUFFIXES = ("ing", "tion", "sion", "ment", "ness", "ity", "ed", "ly", "ful", "ous", "ive", "able", "al", "s")


def _looks_like_first_word_name(word: str) -> bool:
    """A capitalised sentence-start word is only flagged if it does not look like ordinary English."""
    if word in _NOT_NAMES or word in _COMMON_STARTS or len(word) > 12:
        return False
    return not word.lower().endswith(_SUFFIXES)


def possible_names(text: str) -> list[str]:
    """Heuristic flags for the reviewer, not a decision: capitalised words that are not known
    domain words. Words after the first are flagged unless known; a sentence's first word is
    flagged only when it does not look like an ordinary English word (e.g. "Alina made...")."""
    found = []
    for sentence in _SENTENCE.split(text):
        for match in _WORD.finditer(sentence):
            word = match.group(0)
            first = not sentence[:match.start()].strip(" “\"'(-:")
            if word in _NOT_NAMES or word.split("-")[0] in _NOT_NAMES:
                continue
            if first and not _looks_like_first_word_name(word):
                continue
            if word not in found:
                found.append(word)
    return found


_HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def section_spans(content: str) -> list[tuple[str, int, int]]:
    """(heading, body start, body end) for every '## ' section, including ones a person added."""
    heads = list(_HEADING.finditer(content))
    return [(h.group(1).strip(), h.end(), heads[i + 1].start() if i + 1 < len(heads) else len(content))
            for i, h in enumerate(heads)]


def _section_body(content: str, section: str) -> str:
    for name, start, end in section_spans(content):
        if name == section:
            return content[start:end]
    return ""


def extract_claims(content: str, report: ReportDraft | None, context: AnalysisContext) -> list[LedgerClaim]:
    claims: list[LedgerClaim] = []
    seen: dict[str, int] = {}
    original = report.original if report else ""
    ai_mode = bool(report) and report.source_mode not in ("", "Local Analysis")
    allowed_quotes = {_norm(e) for theme in context.themes for e in theme.evidence}
    for section, start, end in section_spans(content):
        if section in SYSTEM_SECTIONS:
            continue
        body = content[start:end]
        original_body = _norm(_section_body(original, section)) if original else ""
        for line in body.splitlines():
            if not line.strip():
                continue
            stripped = line.strip()
            if section in TEMPLATE_SECTIONS and original_body and _norm(stripped) in original_body:
                continue  # unchanged fixed wording
            quotes = list(QUOTE_RE.finditer(stripped))
            if stripped.startswith("- Representative feedback:") or (stripped.startswith("-") and quotes and line.startswith(" ")):
                for q in quotes:
                    claims.append(_make(section, q.group(1), "quote", line, original_body, ai_mode, report, context,
                                        allowed_quotes, seen))
                continue
            if stripped.startswith("- "):
                parts = [stripped[2:]]
            else:
                parts = [p for p in _SENTENCE.split(stripped) if p.strip()]
            for part in parts:
                claims.append(_make(section, part, "statement", line, original_body, ai_mode, report, context,
                                    allowed_quotes, seen))
    return claims


def _make(section, text, kind, line, original_body, ai_mode, report, context, allowed_quotes, seen) -> LedgerClaim:
    clean = _norm(text)
    base = hashlib.sha1(f"{section}|{kind}|{clean}".encode("utf-8")).hexdigest()[:10]
    seen[base] = seen.get(base, 0) + 1
    key = base if seen[base] == 1 else f"{base}-{seen[base]}"
    if original_body and clean in original_body:
        origin = "AI-written" if ai_mode and section in AI_SECTIONS else "Calculated"
    elif report and any(clean in _norm(k) for k in report.evidence):
        origin = "AI-written"   # produced by an "Ask Gemini" revision the reviewer applied
    else:
        origin = "Human-edited"
    claim = LedgerClaim(key, section, clean, kind, origin, line)
    if kind == "quote":
        if clean not in allowed_quotes:
            claim.problems.append("Quote does not match any analysed comment.")
        claim.possible_names = possible_names(clean)
    else:
        claim.checks = check_claims(clean, context)
        for check in claim.checks:
            if not check.supported:
                claim.problems.append(f"Unsupported {check.kind}: {check.text}")
        claim.possible_names = possible_names(clean) if origin != "Calculated" else []
    if report:
        for key_text, facts in report.evidence.items():
            if clean and (clean in _norm(key_text) or _norm(key_text) in clean):
                claim.evidence.extend(f for f in facts if f not in claim.evidence)
    if origin == "AI-written" and not claim.evidence and not claim.checks:
        claim.problems.append("AI wording with no cited evidence - check it against the metrics before accepting.")
    return claim


@dataclass
class DecisionEvent:
    key: str
    section: str
    kind: str
    origin: str
    decision: str     # accepted, rejected, cleared, removed
    at: float


class ClaimLedger:
    ACCEPT = {"statement": "accepted", "quote": "cleared"}
    REJECT = {"statement": "rejected", "quote": "removed"}

    def __init__(self):
        self.claims: list[LedgerClaim] = []
        self.decisions: dict[str, str] = {}
        self.history: list[DecisionEvent] = []

    def sync(self, claims: list[LedgerClaim]) -> None:
        """Re-read the draft. Decisions survive for unchanged claims; edited text is a new, pending claim."""
        self.claims = claims
        live = {c.key for c in claims}
        self.decisions = {k: v for k, v in self.decisions.items() if k in live}

    def reset(self) -> None:
        self.claims, self.decisions, self.history = [], {}, []

    def get(self, key: str) -> LedgerClaim:
        for claim in self.claims:
            if claim.key == key:
                return claim
        raise ValueError("That claim is no longer in the draft.")

    def accept(self, key: str, now: float | None = None) -> str:
        claim = self.get(key)
        hard = [p for p in claim.problems if p.startswith(("Unsupported", "Quote does not match"))]
        if hard:
            raise ValueError("This claim cannot be accepted until it is fixed: " + "; ".join(hard)
                             + ". Edit the draft or reject the claim.")
        return self._record(claim, self.ACCEPT[claim.kind], now)

    def reject(self, key: str, now: float | None = None) -> str:
        claim = self.get(key)
        return self._record(claim, self.REJECT[claim.kind], now)

    def _record(self, claim: LedgerClaim, decision: str, now: float | None) -> str:
        self.decisions[claim.key] = decision
        self.history.append(DecisionEvent(claim.key, claim.section, claim.kind, claim.origin, decision,
                                          time.time() if now is None else now))
        return decision

    def status_of(self, key: str) -> str:
        return self.decisions.get(key, "pending")

    @property
    def pending(self) -> list[LedgerClaim]:
        return [c for c in self.claims if c.key not in self.decisions]

    @property
    def complete(self) -> bool:
        return bool(self.claims) and not self.pending

    def counts(self) -> dict[str, int]:
        final = {}
        for event in self.history:
            final[event.key] = event.decision  # last decision per claim wins
        values = list(final.values())
        return {
            "total": len(self.claims), "decided": len(self.claims) - len(self.pending),
            "accepted": values.count("accepted"), "rejected": values.count("rejected"),
            "cleared": values.count("cleared"), "removed": values.count("removed"),
            "human_edited": sum(1 for c in self.claims if c.origin == "Human-edited"),
            "ai_written": sum(1 for c in self.claims if c.origin == "AI-written"),
            "attention": sum(1 for c in self.claims if c.needs_attention),
        }

    def pace(self) -> dict:
        times = sorted(e.at for e in self.history)
        gaps = [b - a for a, b in zip(times, times[1:])]
        median_gap = statistics.median(gaps) if gaps else None
        fast = len(times) >= FAST_MIN_DECISIONS and median_gap is not None and median_gap < FAST_GAP_SECONDS
        total = (times[-1] - times[0]) if len(times) > 1 else 0.0
        message = ""
        if fast:
            message = (f"Fast review: {len(times)} decisions in {total:.0f} s "
                       f"(median {median_gap:.1f} s each). Re-check the evidence before submitting.")
        return {"decisions": len(times), "seconds": round(total, 1),
                "median_gap": None if median_gap is None else round(median_gap, 1),
                "fast": fast, "message": message}


def remove_claim(content: str, claim: LedgerClaim) -> str:
    """Remove a rejected claim (or removed quote) from the draft text."""
    spans = {name: (start, end) for name, start, end in section_spans(content)}
    if claim.section not in spans:
        raise ValueError("That claim is no longer in the draft. Refresh the claim list.")
    start, end = spans[claim.section]
    body = content[start:end]
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if line != claim.line:
            continue
        stripped = line.strip()
        if claim.kind == "quote" or stripped.startswith("- "):
            lines.pop(i)
        else:
            parts = [p for p in _SENTENCE.split(stripped) if _norm(p) != claim.text]
            if parts:
                lines[i] = " ".join(parts)
            else:
                lines.pop(i)
        new_body = "\n".join(lines)
        if not new_body.strip():
            new_body = "\n\n- Removed by the reviewer.\n\n"
        return content[:start] + new_body + content[end:]
    raise ValueError("That claim is no longer in the draft. Refresh the claim list.")


def ai_text_retained(report: ReportDraft | None, content: str) -> float | None:
    """How much of the AI-written wording survived review (100 = unchanged)."""
    if not report or not report.original or report.source_mode in ("", "Local Analysis"):
        return None
    ratios = []
    for section in AI_SECTIONS:
        before = _norm(_section_body(report.original, section))
        after = _norm(_section_body(content, section))
        if before:
            ratios.append(SequenceMatcher(None, before, after).ratio())
    return round(sum(ratios) / len(ratios) * 100, 1) if ratios else None
