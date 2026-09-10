import json
from datetime import datetime, timezone
from pathlib import Path

def log_report_event(path: Path, *, source_file: str, response_count: int, audience: str, mode: str, status: str) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_file": Path(source_file).name,
        "response_count": response_count,
        "report_audience": audience,
        "generation_mode": mode,
        "review_status": status,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")

