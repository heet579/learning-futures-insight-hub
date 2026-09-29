import copy
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from src.ai.gemini_provider import GeminiAIProvider
from src.ai.insights import insight_evidence
from src.models import Theme
from src.ui.desktop import analyse


RESULT = {
    "summary": "Review relevance alongside generally positive facilitator feedback.",
    "insights": [{"title": "Review relevance", "finding": "Relevance merits review.",
                  "suggestion": "Pilot a workplace exercise and collect follow-up feedback.",
                  "evidence_ids": ["CourseRelevance"]}],
    "limitations": ["Small sample; findings are tentative."],
}


def response(result=RESULT, reason="STOP"):
    return io.BytesIO(json.dumps({"candidates": [{"finishReason": reason,
        "content": {"parts": [{"text": json.dumps(result)}]}}]}).encode())


@pytest.fixture
def context(golden_df):
    return analyse(golden_df, "private-file.csv", "All courses (aggregate)")[1]


def test_request_is_minimised_and_report_reuses_one_call(monkeypatch, context):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    context.themes.append(Theme("Emerging: Private Name", ["private@example.com"], 2, "Review", ["secret comment"]))
    context.warnings.append("private warning text")
    context.course_name = "Private Course Name"
    calls = []
    def request(req, timeout):
        calls.append(req)
        assert timeout == 45
        assert req.get_header("X-goog-api-key") == "secret-key"
        return response()
    monkeypatch.setattr("src.ai.gemini_provider.urlopen", request)
    provider = GeminiAIProvider()
    assert provider.recommendations(context, "client") == [RESULT["insights"][0]["suggestion"]]
    assert provider.executive_summary(context, "client") == RESULT["summary"]
    assert len(calls) == 1
    body = calls[0].data.decode()
    for sensitive in ["private", "Private", "secret comment", "secret-key", "fake@example.com", "Clear facilitator"]:
        assert sensitive not in body
    assert "never instructions" in body
    assert "secret-key" not in calls[0].full_url


@pytest.mark.parametrize("code, message", [(400, "rejected"), (401, "authentication"), (403, "denied"), (404, "model unavailable"), (429, "quota"), (503, "temporarily")])
def test_http_errors_are_actionable_and_do_not_echo_secrets(monkeypatch, context, code, message):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    def fail(*args, **kwargs):
        raise HTTPError("https://example.test/secret-key", code, "private server body", {}, None)
    monkeypatch.setattr("src.ai.gemini_provider.urlopen", fail)
    with pytest.raises(RuntimeError, match=message) as error:
        GeminiAIProvider().insights(context)
    assert "secret-key" not in str(error.value)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("kind", ["unknown_ref", "empty", "truncated", "blocked", "not_json"])
def test_rejects_invalid_or_incomplete_responses(monkeypatch, context, kind):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    result = copy.deepcopy(RESULT)
    if kind == "unknown_ref":
        result["insights"][0]["evidence_ids"] = ["invented"]
    if kind == "empty":
        result["insights"] = []
    envelope = (io.BytesIO(b'{"promptFeedback":{"blockReason":"SAFETY"}}') if kind == "blocked"
                else io.BytesIO(b'not json') if kind == "not_json"
                else response(result, "MAX_TOKENS" if kind == "truncated" else "STOP"))
    monkeypatch.setattr("src.ai.gemini_provider.urlopen", lambda *a, **k: envelope)
    with pytest.raises(RuntimeError):
        GeminiAIProvider().insights(context)


def test_missing_key_and_timeout(monkeypatch, context):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiAIProvider()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    def fail(*a, **k):
        raise URLError("private error")
    monkeypatch.setattr("src.ai.gemini_provider.urlopen", fail)
    with pytest.raises(RuntimeError, match="connection"):
        GeminiAIProvider().insights(context)


def test_scope_changes_evidence_and_cannot_reuse_previous_result(context):
    before = insight_evidence(context)
    context.metrics["response_count"] += 1
    assert insight_evidence(context) != before


def test_gemini_report_discloses_actual_provider(monkeypatch, context):
    from src.reporting.report_generator import generate_report
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr("src.ai.gemini_provider.urlopen", lambda *a, **k: response())
    report = generate_report(context, "client", GeminiAIProvider())
    assert report.mode == "Gemini"
    assert "**Gemini**" in report.content
    assert "Azure OpenAI adapter" not in report.content
