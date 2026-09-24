"""Append-only JSON-lines event log per session, replayable (PLAN.md Phase 1).

Each line is one event dict, in the order handle_event received them. A
replay re-runs every event through a fresh engine and should land on the
exact same final state — the whole point being able to trust logs as a
faithful record, not just a debug trace.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

LOGS_ROOT = Path(__file__).resolve().parent.parent / "logs"


class EventLog:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event):
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def read_events(self):
        if not self.path.exists():
            return []
        events = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line)["event"])
        return events


def new_log(lesson_id, session_id=None):
    session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return EventLog(LOGS_ROOT / lesson_id / f"{session_id}.jsonl")


def replay(lesson, library, log_path):
    """Re-run every logged event through a fresh engine. Returns the final state."""
    from . import engine
    state = engine.initial_state()
    for event in EventLog(Path(log_path)).read_events():
        state, _ = engine.handle_event(lesson, library, state, event)
    return state
