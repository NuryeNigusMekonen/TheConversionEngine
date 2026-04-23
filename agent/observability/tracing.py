import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agent.config import settings


class TraceLogger:
    def __init__(self, trace_path: str | None = None) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = trace_path or str(settings.trace_path)

    def log(self, event_type: str, payload: dict) -> str:
        trace_id = f"tr_{uuid4().hex[:12]}"
        record = {
            "trace_id": trace_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        with open(self.trace_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return trace_id

    def count(self) -> int:
        path = Path(self.trace_path)
        if not path.exists():
            return 0
        with open(path, encoding="utf-8") as handle:
            return sum(1 for _ in handle)

    def recent(self, limit: int = 6) -> list[dict]:
        path = Path(self.trace_path)
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        recent_lines = list(reversed(lines[-limit:]))
        return [json.loads(line) for line in recent_lines]
