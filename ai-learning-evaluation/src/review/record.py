"""The Review record page appended to every approved export (Gate 6)."""
from __future__ import annotations

import hashlib
from datetime import datetime


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _local(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def build_review_record(*, workflow, theme_counts: dict, claim_counts: dict, pace: dict,
                        ai_retained: float | None, source_mode: str, report_hash: str,
                        approval_hash: str, audit_entries: int) -> str:
    submitted = next((e for e in reversed(workflow.events) if e.action == "Submitted for review"), None)
    approved = next((e for e in reversed(workflow.events) if e.action == "Approved"), None)
    lines = [
        "## Review record",
        "",
        f"- Prepared and submitted by: {workflow.reviewer}" + (f" ({_local(submitted.timestamp)})" if submitted else ""),
        f"- Approved by: {workflow.approver}, {workflow.approver_role}" + (f" ({_local(approved.timestamp)})" if approved else ""),
        f"- First draft written by: {source_mode or 'Unknown'}",
        f"- Themes: {theme_counts.get('confirmed', 0)} confirmed, {theme_counts.get('rejected', 0)} rejected, "
        f"{theme_counts.get('recategorised', 0)} re-categorised by the reviewer",
        f"- Claims: {claim_counts.get('accepted', 0)} accepted, {claim_counts.get('rejected', 0)} rejected; "
        f"quotes: {claim_counts.get('cleared', 0)} cleared for privacy, {claim_counts.get('removed', 0)} removed",
        f"- Claims written or changed by a person: {claim_counts.get('human_edited', 0)}",
    ]
    if ai_retained is not None:
        lines.append(f"- AI wording kept unchanged in the summary and recommendations: {ai_retained:.0f} percent")
    lines.append(f"- Times returned for changes: {workflow.times_returned()}")
    if pace.get("fast"):
        lines.append(f"- Review pace warning: {pace['message']}")
    else:
        lines.append(f"- Review pace: {pace.get('decisions', 0)} decisions over {pace.get('seconds', 0):.0f} seconds")
    lines += [
        f"- Report text SHA-256: {report_hash}",
        f"- Approval audit entry: {approval_hash} ({audit_entries} entries in a verified hash chain)",
        "",
        "Names are entered by the operator and are not authenticated identities.",
    ]
    return "\n".join(lines)
