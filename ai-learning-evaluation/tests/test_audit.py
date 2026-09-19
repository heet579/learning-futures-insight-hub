import json
from src.audit.logger import log_report_event

def test_audit_records_metadata_without_comments(tmp_path):
    path = tmp_path / "audit.jsonl"
    log_report_event(path, source_file="C:/private/demo.csv", response_count=3,
                     audience="client", mode="Local Analysis", status="DRAFT")
    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["source_file"] == "demo.csv"
    assert event["response_count"] == 3
    assert set(event) == {"timestamp", "source_file", "response_count", "report_audience", "generation_mode", "review_status"}

