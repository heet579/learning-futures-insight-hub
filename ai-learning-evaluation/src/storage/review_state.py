"""Reconstruct and validate the saved first-reviewer decisions before handoff."""
from src.review.themes import ThemeReview
from src.review.claims import ClaimLedger, extract_claims
from src.reporting.grounding import unsupported_claims


def checked_review(state):
    report = state['report']
    if report is None or not state['content'].strip():
        raise ValueError('Generate a report before submitting it.')
    themes = ThemeReview(state['context'].themes)
    themes.decisions = state['theme_decisions']
    if not themes.complete or state['themes_changed_since_draft']:
        raise ValueError('Complete theme review and regenerate the report after changing themes.')
    context = themes.reviewed_context(state['context'])
    ledger = ClaimLedger()
    ledger.decisions, ledger.history = state['claim_decisions'].copy(), state['claim_history'][:]
    ledger.sync(extract_claims(state['content'], report, context))
    if not ledger.complete or any(ledger.status_of(c.key) != ledger.ACCEPT[c.kind] for c in ledger.claims):
        raise ValueError('Check every claim and clear every quote before submitting.')
    if unsupported_claims(state['content'], context):
        raise ValueError('Fix unsupported numbers and quotes before submitting.')
    return themes, ledger
