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



# --- Gate 6: tamper-evident review audit trail --------------------------------------
# Every review action is one JSON line holding the SHA-256 of the previous line. Changing
# or deleting an earlier line breaks the chain, which verify() reports. Lines hold names,
# decisions, counts and hashes only: never learner comments or report text.
import hashlib
import os

GENESIS = "0" * 64


def default_audit_path() -> Path:
    configured = os.getenv("AUDIT_LOG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".learning_futures_insight_hub" / "review_audit_log.jsonl"


def _digest(event: dict) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class AuditTrail:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_audit_path()

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = ""
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        return json.loads(last)["hash"] if last else GENESIS

    def append(self, action: str, actor: str = "", **details) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action,
                 "actor": actor, "details": details, "prev_hash": self._last_hash()}
        event["hash"] = _digest(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def verify(self) -> dict:
        """Recompute every hash. Returns ok, number of entries and where the chain breaks."""
        if not self.path.exists():
            return {"ok": True, "entries": 0, "head": GENESIS, "broken_at": None}
        previous, count = GENESIS, 0
        with self.path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    return {"ok": False, "entries": count, "head": previous, "broken_at": number}
                if event.get("prev_hash") != previous or event.get("hash") != _digest(event):
                    return {"ok": False, "entries": count, "head": previous, "broken_at": number}
                previous, count = event["hash"], count + 1
        return {"ok": True, "entries": count, "head": previous, "broken_at": None}
