from src.ai.copilot import answer_question
from src.analytics.qualitative import collect_comments
from src.analytics.quantitative import calculate_metrics
from src.analytics.themes import extract_themes
from src.models import AnalysisContext


def test_copilot_answers_are_grounded(golden_df):
    context = AnalysisContext(calculate_metrics(golden_df), extract_themes(collect_comments(golden_df)), "test.csv", "Test course")
    response = answer_question("What is the satisfaction performance?", context)
    assert "/5" in response
    assert "%" in response


def test_copilot_discloses_limits(golden_df):
    context = AnalysisContext(calculate_metrics(golden_df), [], "test.csv", "Test course")
    assert "human reviewer" in answer_question("Can I trust this?", context)
