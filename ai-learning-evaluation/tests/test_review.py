"""Human-in-the-loop review logic: themes, claim ledger, audit chain, review record."""
import json
from types import SimpleNamespace

import pytest

from src.ai.local_provider import LocalAnalysisProvider
from src.audit.logger import AuditTrail
from src.reporting.report_generator import generate_report
from src.reporting.revisions import propose_revision, apply_proposal, local_revision
from src.review.claims import ClaimLedger, extract_claims, remove_claim, possible_names, ai_text_retained
from src.review.themes import ThemeReview
from src.ui.desktop import analyse


@pytest.fixture
def ctx(golden_df):
    return analyse(golden_df, 'demo.csv', 'All courses (aggregate)')[1]


def test_rejected_and_recategorised_themes(ctx):
    review = ThemeReview(ctx.themes)
    first, *rest = ctx.themes
    review.decide(first.name, 'rejected')
    for theme in rest:
        review.decide(theme.name, 'confirmed', 'Review')
    assert review.complete
    kept = review.reviewed_context(ctx).themes
    assert first.name not in [t.name for t in kept]
    assert all(t.category == 'Review' for t in kept)
    assert ctx.themes[0].name == first.name  # the original analysis is untouched


def test_claims_have_origin_and_evidence(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    claims = extract_claims(report.content, report, ctx)
    sections = {c.section for c in claims}
    assert {'Executive Summary', 'Key Metrics', 'Recommendations'} <= sections
    assert 'Analysis method' not in sections
    assert all(c.origin == 'Calculated' for c in claims)  # local draft: no AI wording
    quotes = [c for c in claims if c.kind == 'quote']
    assert quotes and all(not c.problems for c in quotes)


def test_ai_sections_are_marked_and_human_edits_detected(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    report.source_mode = 'Gemini'
    edited = report.content.replace('## Recommendations\n\n', '## Recommendations\n\n- Added by Alex for Jordan Smith.\n')
    claims = {c.text: c for c in extract_claims(edited, report, ctx)}
    summary = next(c for c in claims.values() if c.section == 'Executive Summary')
    assert summary.origin == 'AI-written'
    added = claims['Added by Alex for Jordan Smith.']
    assert added.origin == 'Human-edited'
    assert 'Jordan' in added.possible_names and 'Smith' in added.possible_names


def test_unsupported_claim_cannot_be_accepted(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    content = report.content.replace('## Key Themes', '- 99.9% loved it.\n\n## Key Themes')
    ledger = ClaimLedger()
    ledger.sync(extract_claims(content, report, ctx))
    bad = next(c for c in ledger.claims if '99.9%' in c.text)
    with pytest.raises(ValueError, match='cannot be accepted'):
        ledger.accept(bad.key)
    ledger.reject(bad.key)
    assert '99.9%' not in remove_claim(content, bad)


def test_decisions_survive_unrelated_edits_but_not_changed_text(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    ledger = ClaimLedger()
    ledger.sync(extract_claims(report.content, report, ctx))
    for claim in ledger.claims:
        ledger.accept(claim.key, now=0)
    assert ledger.complete
    changed = report.content.replace('Overall satisfaction averaged', 'Overall satisfaction was')
    ledger.sync(extract_claims(changed, report, ctx))
    assert [c.section for c in ledger.pending] == ['Executive Summary']


def test_fast_review_flag():
    ledger = ClaimLedger()
    claims = [SimpleNamespace(key=str(i), section='S', kind='statement', origin='Calculated', problems=[]) for i in range(6)]
    ledger.claims = claims
    for i, claim in enumerate(claims):
        ledger._record(claim, 'accepted', now=100 + i * 0.5)
    assert ledger.pace()['fast']
    slow = ClaimLedger()
    slow.claims = claims
    for i, claim in enumerate(claims):
        slow._record(claim, 'accepted', now=100 + i * 20)
    assert not slow.pace()['fast']


def test_possible_names_ignores_sentence_starts_and_domain_words():
    assert possible_names('The facilitator from Adelaide University was great.') == []
    assert possible_names('Thanks to Priya for the examples.') == ['Priya']


def test_audit_chain_detects_tampering(tmp_path):
    trail = AuditTrail(tmp_path / 'log.jsonl')
    trail.append('Submitted for approval', 'Alex')
    trail.append('Approved', 'Sam', role='Learning Futures lead')
    assert trail.verify()['ok'] and trail.verify()['entries'] == 2
    lines = (tmp_path / 'log.jsonl').read_text(encoding='utf-8').splitlines()
    event = json.loads(lines[1])
    event['actor'] = 'Mallory'
    lines[1] = json.dumps(event)
    (tmp_path / 'log.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    result = trail.verify()
    assert not result['ok'] and result['broken_at'] == 2


def test_gemini_revision_uses_facts_and_is_disclosed(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    captured = {}

    def revise(context, section, current, instruction, audience):
        captured.update(section=section, current=current, instruction=instruction)
        return {'revised_section': 'Three responses were analysed; satisfaction averaged 4.00/5.',
                'evidence': ['3 survey responses in the selected scope.'], 'note': ''}

    client = SimpleNamespace(revise_section=revise)
    proposal = propose_revision(report, report.content, ctx, 'Executive Summary',
                                'write a summary for person@example.com', 'Gemini', client=client)
    assert captured['section'] == 'Executive Summary'
    assert proposal.evidence == ('3 survey responses in the selected scope.',)
    updated = apply_proposal(report, report.content, proposal)
    assert 'Gemini service' in updated.content
    assert updated.mode == 'Gemini assisted revision'
    assert updated.original == report.original


def test_gemini_unchanged_revision_explains_why(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    from src.reporting.revisions import section_text
    same = section_text(report.content, 'Executive Summary')
    client = SimpleNamespace(revise_section=lambda *a: {'revised_section': same, 'evidence': [],
                                                         'note': 'No trend data is available.'})
    with pytest.raises(ValueError, match='No trend data'):
        propose_revision(report, report.content, ctx, 'Executive Summary', 'show the trend', 'Gemini', client=client)


def test_offline_shortening_explains_single_sentence_limit():
    with pytest.raises(ValueError, match='Ask Gemini'):
        local_revision('Only one sentence here.', 'make it a short summary')
    assert local_revision('One. Two. Three. Four.', 'make it shorter') == 'One. Two.'


def test_ai_text_retained(ctx):
    report = generate_report(ctx, 'facilitator', LocalAnalysisProvider())
    assert ai_text_retained(report, report.content) is None  # local drafts have no AI wording
    report.source_mode = 'Gemini'
    assert ai_text_retained(report, report.content) == 100.0


