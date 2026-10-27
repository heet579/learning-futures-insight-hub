"""Claude as an alternative AI service: same prompts, schema and validation as Gemini."""
from types import SimpleNamespace

import pytest

from src.ai.claude_provider import ClaudeAIProvider, _json_schema
from src.ai.selection import ai_provider
from src.ai.insights import insight_evidence
from src.reporting.report_generator import generate_report
from src.ui.desktop import analyse


class FakeMessages:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason='tool_use',
                               content=[SimpleNamespace(type='tool_use', input=self.reply(kwargs))])


@pytest.fixture
def context(golden_df):
    return analyse(golden_df, 'test.csv', 'All courses (aggregate)')[1]


@pytest.fixture
def fake_claude(monkeypatch):
    import anthropic
    holder = {}

    def factory(**kwargs):
        holder['client'] = SimpleNamespace(messages=holder['messages'])
        return holder['client']
    monkeypatch.setattr(anthropic, 'Anthropic', factory)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    monkeypatch.delenv('ANTHROPIC_MODEL', raising=False)
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    return holder


def test_selection_prefers_claude_when_its_key_is_set(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setenv('GEMINI_API_KEY', 'g-key')
    assert ai_provider().name == 'Gemini'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-x')
    assert ai_provider().name == 'Claude'
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    assert ai_provider().name == 'Gemini'
    monkeypatch.delenv('GEMINI_API_KEY')
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    monkeypatch.delenv('AI_PROVIDER')
    with pytest.raises(ValueError):
        ai_provider()


def test_schema_is_converted_to_json_schema():
    converted = _json_schema({'type': 'OBJECT', 'properties': {'a': {'type': 'ARRAY', 'items': {'type': 'STRING', 'enum': ['x']}}}})
    assert converted == {'type': 'object', 'properties': {'a': {'type': 'array', 'items': {'type': 'string', 'enum': ['x']}}}}


def test_claude_writes_a_validated_draft(fake_claude, context):
    facts = list(insight_evidence(context))

    def reply(kwargs):
        assert kwargs['model'] == 'claude-haiku-5-5' and kwargs['tool_choice'] == {'type': 'tool', 'name': 'respond'}
        assert kwargs['tools'][0]['input_schema']['type'] == 'object'
        assert 'fake@example.com' not in kwargs['messages'][0]['content']      # no raw comments are sent
        return {'summary': 'Ratings are positive overall.', 'limitations': ['Small sample.'],
                'insights': [{'title': 'Pacing', 'finding': 'Some learners found the pace fast.',
                              'suggestion': 'Pilot a slower first session.', 'evidence_ids': [facts[0]]}]}
    fake_claude['messages'] = FakeMessages(reply)
    report = generate_report(context, 'facilitator', ClaudeAIProvider())
    assert report.source_mode == 'Claude' and 'Pilot a slower first session.' in report.content
    assert report.evidence['Pilot a slower first session.']


def test_claude_answers_must_cite_known_evidence(fake_claude, context):
    fake_claude['messages'] = FakeMessages(lambda kwargs: {'answer': 'Yes.', 'evidence_ids': ['made-up']})
    with pytest.raises(RuntimeError, match='Claude returned an invalid answer'):
        ClaudeAIProvider().answer_question(context, 'How many responses?')
