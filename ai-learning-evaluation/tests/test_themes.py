from src.analytics.qualitative import collect_comments
from src.analytics.themes import extract_themes

def test_empty_comments_do_not_crash():
    assert extract_themes(["", "  "]) == []

def test_theme_extraction_with_sufficient_text():
    comments = ["More practical exercises would help"] * 4 + ["The facilitator explained clearly"] * 4
    themes = extract_themes(comments)
    names = {t.name for t in themes}
    assert "Practical activities" in names
    assert "Facilitator quality" in names

def test_collect_comments_ignores_empty(golden_df):
    assert "" not in collect_comments(golden_df)

