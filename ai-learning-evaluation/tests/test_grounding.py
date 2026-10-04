from src.models import AnalysisContext, Theme
from src.reporting.grounding import unsupported_claims


def _context():
    metrics = {
        "response_count": 10,
        "response_completeness": 80.0,
        "ratings": {"OverallSatisfaction": {"label": "Overall satisfaction", "mean": 4.25, "median": 4.0, "count": 10, "distribution": {}}},
        "satisfaction_percent": 90.0,
        "recommendation_percent": 75.0,
        "strongest_area": "OverallSatisfaction",
        "lowest_area": "OverallSatisfaction",
    }
    themes = [Theme("Facilitator quality", ["facilitator"], 5, "Positive", ["Great facilitator throughout"])]
    return AnalysisContext(metrics, themes, "source", "Course", [])


def test_real_numbers_and_quotes_are_supported():
    content = 'Would recommend: 75.0%. Overall satisfaction: 4.25/5. 5 matching comment(s). Representative feedback: "Great facilitator throughout"'
    assert unsupported_claims(content, _context()) == []


def test_fabricated_number_and_quote_are_flagged():
    content = 'Would recommend: 99.9%. Representative feedback: "This never happened in the data"'
    bad = unsupported_claims(content, _context())
    assert {c.kind for c in bad} == {"percentage", "quote"}


def test_fabricated_comment_count_is_flagged():
    content = "42 matching comment(s) support this theme."
    bad = unsupported_claims(content, _context())
    assert any(c.kind == "count" for c in bad)


def test_rounded_figures_and_scale_points_are_accepted():
    content = "About 75% would recommend; satisfaction averaged 4.3/5 and many answers were 5/5."
    assert unsupported_claims(content, _context()) == []


def test_rounding_to_a_different_value_is_still_flagged():
    bad = unsupported_claims("Satisfaction averaged 4.4/5 and 76% would recommend.", _context())
    assert {c.text for c in bad} == {"4.4/5", "76%"}
