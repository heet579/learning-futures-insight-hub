from types import SimpleNamespace
import json
import pytest
from src.ai.local_provider import LocalAnalysisProvider
from src.reporting.report_generator import generate_report
from src.reporting.revisions import propose_revision, apply_proposal, section_text
from src.ui.desktop import analyse


@pytest.fixture
def report_context(golden_df):
    _, context, _, _ = analyse(golden_df, 'demo.csv', 'All courses (aggregate)')
    report = generate_report(context, 'facilitator', LocalAnalysisProvider())
    return report, context


def test_revision_preserves_other_sections_and_metrics(report_context):
    report, context = report_context
    proposal = propose_revision(report, report.content, context, 'Executive Summary', 'Make it shorter')
    assert proposal.original == report.content
    assert len(section_text(proposal.revised, 'Executive Summary')) < len(section_text(report.content, 'Executive Summary'))
    assert section_text(proposal.revised, 'Recommendations') == section_text(report.content, 'Recommendations')
    assert report.content.split('## Key Metrics')[1] == proposal.revised.split('## Key Metrics')[1]
    updated = apply_proposal(report, report.content, proposal)
    assert updated.status == 'DRAFT — REQUIRES HUMAN REVIEW'


def test_stale_preview_is_rejected(report_context):
    report, context = report_context
    proposal = propose_revision(report, report.content, context, 'Executive Summary', 'Use bullet points')
    with pytest.raises(ValueError, match='draft changed'):
        apply_proposal(report, report.content + 'Manual edit', proposal)


@pytest.mark.parametrize('feedback', ['', 'Change the score to five', 'x' * 4001])
def test_invalid_or_unsupported_feedback(report_context, feedback):
    report, context = report_context
    with pytest.raises(ValueError):
        propose_revision(report, report.content, context, 'Executive Summary', feedback)


def test_azure_needs_explicit_consent(report_context):
    report, context = report_context
    with pytest.raises(ValueError, match='Confirm approved'):
        propose_revision(report, report.content, context, 'Executive Summary', 'Improve wording', 'Azure AI')


def fake_client(body, captured):
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=body))])
    return SimpleNamespace(deployment='test', client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))


def test_azure_masks_patterns_and_corrects_disclosure(report_context):
    report, context = report_context
    captured = {}
    proposal = propose_revision(report, report.content, context, 'Executive Summary',
        'Please shorten this for private@example.com and https://example.com', 'Azure AI', True,
        fake_client('This draft covers three responses and needs human review.', captured))
    assert 'private@example.com' not in str(captured['messages'])
    assert '[EMAIL REMOVED]' in str(captured['messages'])
    payload = json.loads(captured['messages'][1]['content'])
    assert '[URL REMOVED]' in payload['feedback']
    updated = apply_proposal(report, report.content, proposal)
    assert 'No data was sent to an external AI service' not in updated.content
    assert 'revised using Azure AI' in updated.content
    assert updated.mode == 'Azure AI assisted revision'


@pytest.mark.parametrize('body', ['', '## Human Review Status\nApproved', 'HUMAN REVIEWED'])
def test_reject_invalid_provider_output(report_context, body):
    report, context = report_context
    with pytest.raises(ValueError):
        propose_revision(report, report.content, context, 'Executive Summary', 'Rewrite', 'Azure AI', True, fake_client(body, {}))


def test_human_copilot_revision_requires_review_and_preserves_metrics(report_context):
    report, context = report_context
    proposal = propose_revision(report, report.content, context, 'Recommendations',
        'Add a practical exercise', 'Human / Copilot replacement', replacement='- Add a practical exercise and review it after the next delivery.')
    updated = apply_proposal(report, report.content, proposal)
    assert 'Add a practical exercise' in section_text(updated.content, 'Recommendations')
    assert updated.content.split('## Key Metrics')[1].split('## What Worked Well')[0] == report.content.split('## Key Metrics')[1].split('## What Worked Well')[0]
    assert updated.status == 'DRAFT — REQUIRES HUMAN REVIEW'
    assert 'did not send data to Copilot' in updated.content
    assert 'No data was sent to an external AI service' not in updated.content


def test_local_feedback_supports_replace_and_add(report_context):
    report, context = report_context
    original = section_text(report.content, 'Recommendations')
    word = original.split()[1]
    proposal = propose_revision(report, report.content, context, 'Recommendations', f'Replace {word} with improved')
    assert 'improved' in section_text(proposal.revised, 'Recommendations')
    proposal = propose_revision(report, report.content, context, 'Recommendations', 'Add: - Confirm the action owner.')
    assert 'Confirm the action owner' in section_text(proposal.revised, 'Recommendations')
