from src.ai.local_provider import LocalAnalysisProvider
from src.analytics.qualitative import collect_comments
from src.analytics.quantitative import calculate_metrics
from src.analytics.themes import extract_themes
from src.models import AnalysisContext
from src.reporting.report_generator import REQUIRED_HEADINGS, approve_report, generate_report
from src.reporting.exporter import docx_bytes, markdown_bytes

def context(golden_df):
    return AnalysisContext(calculate_metrics(golden_df), extract_themes(collect_comments(golden_df)), "golden.csv", "Course")

def test_report_contains_required_sections_and_draft_status(golden_df):
    report = generate_report(context(golden_df), "facilitator", LocalAnalysisProvider())
    for heading in REQUIRED_HEADINGS:
        assert f"## {heading}" in report.content
    assert report.status == "DRAFT — REQUIRES HUMAN REVIEW"
    assert "No data was sent to an external AI service" in report.content

def test_audience_reports_differ(golden_df):
    ctx = context(golden_df)
    facilitator = generate_report(ctx, "facilitator", LocalAnalysisProvider()).content
    client = generate_report(ctx, "client", LocalAnalysisProvider()).content
    assert facilitator != client
    assert "internal coaching view" in facilitator
    assert "client-facing view" in client
    assert "Representative feedback" in facilitator
    assert "Representative feedback" not in client

def test_approval_changes_status(golden_df):
    draft = generate_report(context(golden_df), "client", LocalAnalysisProvider())
    approved = approve_report(draft)
    assert approved.status == "HUMAN REVIEWED"
    assert "DRAFT — REQUIRES HUMAN REVIEW" not in approved.content

def test_exports_are_nonempty_and_docx_is_valid_zip(golden_df):
    report = generate_report(context(golden_df), "client", LocalAnalysisProvider()).content
    assert markdown_bytes(report).startswith(b"# Course Evaluation")
    exported = docx_bytes(report)
    assert exported.startswith(b"PK")
    assert len(exported) > 1000

