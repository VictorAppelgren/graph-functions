"""
Minimal tracker for writing structured event JSONs.

Notes:
- Minimal by design: IDs only go in `inputs`; richer LLM outputs go in `details`.
- Outputs live under <project_root>/tracker/<event_type>/<primary_id>.json
- File name == graph ID to keep everything trivially discoverable.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Mapping
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from datetime import timezone

from paths import get_project_root

# -------- paths --------


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    # Local time is fine for human inspection; ISO seconds keep it compact
    return datetime.now().isoformat(timespec="seconds")


def get_tracker_dir() -> Path:
    return get_project_root() / "tracker"


def get_event_dir(event_type: EventType) -> Path:
    # replace with your real location policy
    root = Path("events")
    root.mkdir(parents=True, exist_ok=True)
    d = root / event_type.value
    d.mkdir(parents=True, exist_ok=True)
    return d


class EventType(str, Enum):
    ADD_ARTICLE = "add_article"
    REMOVE_ARTICLE = "remove_article"
    REWRITE_SKIPPED = "rewrite_skipped"
    REMOVE_TOPIC = "remove_topic"
    ANALYSIS_REWRITER_RUN = "analysis_rewriter_run"
    ANALYSIS_SECTION_REWRITE = "analysis_section_rewrite"
    ARTICLE_REPLACEMENT_DECISION = "article_replacement_decision"
    ADD_RELATIONSHIP = "add_relationship"
    ADD_TOPIC = "add_topic"
    REMOVE_RELATIONSHIP = "remove_relationship"


class EventModel(BaseModel):
    """Canonical event structure written to disk."""

    model_config = ConfigDict(extra="forbid")

    type: EventType
    timestamp: str = Field(default_factory=_now_iso)
    processed: bool = False
    id: Optional[str] = None

    # small scalar inputs (ids/flags); always strings on disk -> easy to grep/compare
    inputs: dict[str, str] = Field(default_factory=dict)

    # richer payloads (free-form, but still validated to be a mapping)
    details: dict[str, Any] = Field(default_factory=dict)


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

    def __init__(self, event_type: EventType):
        self.event = EventModel(type=event_type)
        self._out_dir = get_event_dir(event_type)

    def put(self, name: str, value: object) -> None:
        """
        - If value is a mapping -> stored under event.details[name] (verbatim)
        - Else -> stored under event.inputs[name] (stringified)
        """
        if not name:
            raise ValueError("name must be a non-empty string")

        if isinstance(value, Mapping):
            self.event.details[name] = dict(value)
        else:
            self.event.inputs[name] = str(value)

    def put_many(
        self, mapping: Mapping[str, object] | None = None, /, **kwargs: Any
    ) -> None:
        if mapping is None:
            mapping = kwargs
        elif kwargs:
            raise TypeError("Provide either a mapping OR kwargs, not both.")

        for k, v in mapping.items():
            self.put(k, v)

    def set_field(self, name: str, value: str | int | float | bool) -> None:
        self.put(name, value)

    def set_id(self, graph_id: Optional[str]) -> Path:
        """
        Set stable id (if provided), or write a fail_<ts>.json with id="none".
        Validates via Pydantic and writes pretty JSON.
        """
        gid = (graph_id or "").strip()
        if gid and gid.lower() != "none":
            self.event.id = gid
            fname = f"{gid}.json"
        else:
            self.event.id = "none"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            fname = f"fail_{stamp}.json"

        _ = self.event.model_dump()
        out_path = self._out_dir / fname
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(self.event.model_dump_json(), encoding="utf-8")
        tmp.replace(out_path)
        return out_path
