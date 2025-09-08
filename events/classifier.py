"""
Minimal tracker for writing structured event JSONs.

Notes:
- Minimal by design: IDs only go in `inputs`; richer LLM outputs go in `details`.
- Outputs live under <project_root>/tracker/<event_type>/<primary_id>.json
- File name == graph ID to keep everything trivially discoverable.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from paths import get_project_root

# -------- paths --------

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    # Local time is fine for human inspection; ISO seconds keep it compact
    return datetime.now().isoformat(timespec="seconds")


def get_tracker_dir() -> Path:
    return get_project_root() / "tracker"


def get_event_dir(event_type: str) -> Path:
    d = get_tracker_dir() / event_type
    _ensure_dir(d)
    return d


# -------- Generic Tracker --------

class EventClassifier:
    """
    Minimal generic tracker.
    - Initialize with event_type (e.g., "add_article").
    - Add values using put(name, value):
        - if value is a dict → stored under event["details"][name]
        - else → stored under event["inputs"][name] (IDs/small scalars)
    - Finalize with set_id(graph_id) which validates and writes JSON.
      If graph_id is None or "none", writes fail_<timestamp>.json and sets event["id"]="none".
    """

    def __init__(self, event_type: str):
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string")

        self.event_type = event_type
        self.event: Dict[str, Any] = {
            "type": event_type,
            "timestamp": _now_iso(),
            "processed": False,
        }
        self._out_dir = get_event_dir(event_type)
        
    def _validate_event(self) -> None:
        """Generic, minimal validation (no per-event schemas)."""
        ev = self.event
        if not isinstance(ev, dict):
            raise ValueError("event must be a dict")
        if not isinstance(ev.get("type"), str) or not ev["type"].strip():
            raise ValueError("event.type must be a non-empty string")
        if not isinstance(ev.get("timestamp"), str) or not ev["timestamp"]:
            raise ValueError("event.timestamp must be a non-empty string")
        if not isinstance(ev.get("processed"), bool):
            raise ValueError("event.processed must be a bool")
        if "id" in ev and (not isinstance(ev["id"], str) or not ev["id"].strip()):
            raise ValueError("event.id must be a non-empty string when present")
        inputs = ev.get("inputs")
        if inputs is not None and not isinstance(inputs, dict):
            raise ValueError("event.inputs must be a dict if present")
        details = ev.get("details")
        if details is not None and not isinstance(details, dict):
            raise ValueError("event.details must be a dict if present")

    def put(self, name: str, value: Any) -> None:
        """Unified setter.
        - If value is a dict → event['details'][name] = value
        - Else → event['inputs'][name] = str(value)
        """
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if isinstance(value, dict):
            details = self.event.setdefault("details", {})
            details[name] = value
        else:
            inputs = self.event.setdefault("inputs", {})
            inputs[name] = str(value)

    # Deprecated aliases for backward-compatibility
    def set_field(self, name: str, value: str) -> None:
        self.put(name, value)

    def set_id(self, graph_id: Optional[str]) -> Path:
        # Decide filename and id
        if isinstance(graph_id, str) and graph_id.strip() and graph_id.lower() != "none":
            self.event["id"] = graph_id
            filename = f"{graph_id}.json"
        else:
            self.event["id"] = "none"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"fail_{stamp}.json"

        # Final validation and write
        self._validate_event()
        out_path = self._out_dir / filename
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(self.event, f, ensure_ascii=False, indent=2, default=str)
        return out_path
