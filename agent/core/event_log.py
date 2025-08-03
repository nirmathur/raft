import json
import pathlib
from datetime import datetime, timezone

LOG_PATH = pathlib.Path("logs/event_log.jsonl")
LOG_PATH.parent.mkdir(exist_ok=True)


def record(event: str, payload: dict):
    # Ensure the file exists
    if not LOG_PATH.exists():
        LOG_PATH.touch()

    with LOG_PATH.open("a") as f:
        f.write(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                    "payload": payload,
                }
            )
            + "\n"
        )
