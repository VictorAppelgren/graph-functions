"""
Minimal QA runner: picks a random unprocessed tracker event, builds full context,
runs LLM critic, marks processed, logs, and writes a markdown report on fail.
Simplicity-first. No CLI. Single-run per invocation.
"""
import os
import sys
import json
import random
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Ensure project root (V1) is on sys.path so absolute imports work when running this script directly.
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_QUALITY_ASSURANCE_DIR = os.path.dirname(_FILE_DIR)  # This is the V1 project root
PROJECT_ROOT = _QUALITY_ASSURANCE_DIR
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.master_log import master_log, load_stats_file, save_stats_file
from graph_utils.get_node_by_id import get_node_by_id
from utils.load_article import load_article
from utils.article_text_formatter import extract_text_from_json_article
from utils.minimal_logging import get_logger

logger = get_logger(__name__)

from Quality_Assurance_Team.qa_prompts import (
    run_critic,
    PROJECT_SUMMARY,
    ACTION_TYPE_GUIDE,
)

# Versioning per user instruction: hardcoded here.
QA_VERSION = "v1"

# Allowed event types in v1
EVENT_TYPES = [
    "add_article",
    "add_node",
    "add_relationship",
    "remove_relationship",
]

TRACKER_DIR = os.path.join(PROJECT_ROOT, "tracker")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "Quality_Assurance_Team", "Quality_Reports")


def _list_unprocessed_events() -> Optional[Tuple[str, str]]:
    """
    Return (event_type, absolute_path_to_event_json) for a random unprocessed event.
    If none found, return None.
    """
    candidates = []
    for et in EVENT_TYPES:
        et_dir = os.path.join(TRACKER_DIR, et)
        if not os.path.isdir(et_dir):
            continue
        for name in os.listdir(et_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(et_dir, name)
            try:
                with open(path, "r") as f:
                    obj = json.load(f)
                if not isinstance(obj, dict):
                    continue
                processed = bool(obj.get("processed", False))
                if not processed:
                    candidates.append((et, path))
            except Exception:
                # Skip malformed files to preserve simplicity/fail-fast
                continue
    if not candidates:
        return None
    return random.choice(candidates)


def _safe_json_dump(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        # Fallback to str if not JSON-serializable
        return str(obj)


def _build_context(event_type: str, event: Dict[str, Any]) -> Dict[str, str]:
    inputs = event.get("inputs", {}) if isinstance(event.get("inputs"), dict) else {}
    details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}

    article_text = ""
    start_node = ""
    end_node = ""
    extra_context = {}

    if event_type == "add_article":
        article_id = inputs.get("article_id") or inputs.get("id")
        if article_id:
            article = load_article(article_id)
            article_text = extract_text_from_json_article(article)
        topic_id = inputs.get("topic_id") or inputs.get("node_id")
        if topic_id:
            start_node = _safe_json_dump(get_node_by_id(topic_id))
        extra_context = {
            "classification": details.get("classification"),
            "relevance": details.get("relevance"),
            "dedup_decision": details.get("dedup_decision"),
        }
    elif event_type == "add_node":
        # Expect a node dict in details or at least its id
        node = details.get("node") or {}
        if not node and isinstance(inputs.get("node"), dict):
            node = inputs.get("node")
        start_node = _safe_json_dump(node)
        extra_context = {
            "macro_gate": details.get("macro_gate"),
            "category": details.get("category"),
            "motivations": details.get("motivations"),
        }
    elif event_type == "add_relationship":
        start_id = inputs.get("start_id") or inputs.get("source_id") or inputs.get("src_id")
        end_id = inputs.get("end_id") or inputs.get("target_id") or inputs.get("tgt_id")
        if start_id:
            start_node = _safe_json_dump(get_node_by_id(start_id))
        if end_id:
            end_node = _safe_json_dump(get_node_by_id(end_id))
        extra_context = {
            "candidate_ids": details.get("candidate_ids"),
            "candidate_motivation": details.get("candidate_motivation"),
            "selection_motivation": details.get("selection_motivation"),
            "existing_links_before": details.get("existing_links_before"),
            "existing_links_after": details.get("existing_links_after"),
            "dedup_decision": details.get("dedup_decision"),
        }
    elif event_type == "remove_relationship":
        start_id = inputs.get("start_id") or inputs.get("source_id") or inputs.get("src_id")
        end_id = inputs.get("end_id") or inputs.get("target_id") or inputs.get("tgt_id")
        if start_id:
            start_node = _safe_json_dump(get_node_by_id(start_id))
        if end_id:
            end_node = _safe_json_dump(get_node_by_id(end_id))
        extra_context = {
            "existing_links_before": details.get("existing_links_before"),
            "existing_links_after": details.get("existing_links_after"),
            "prioritized_link": details.get("prioritized_link"),
            "selection_motivation": details.get("selection_motivation"),
            "candidate_motivation": details.get("candidate_motivation"),
        }

    return {
        "event_inputs": _safe_json_dump(inputs),
        "event_details": _safe_json_dump(details),
        "article_text": article_text,
        "start_node": start_node,
        "end_node": end_node,
        "extra_context": _safe_json_dump(extra_context),
    }


def _write_report(event_type: str, motivation: str, recommendation: str, tracker_file: str) -> str:
    ts = datetime.now().strftime("%Y_%m_%d_%H_%M")
    base = f"{event_type}_{ts}.md"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, base)
    # Avoid collision
    if os.path.exists(out_path):
        i = 1
        while True:
            alt = os.path.join(REPORTS_DIR, f"{event_type}_{ts}_{i}.md")
            if not os.path.exists(alt):
                out_path = alt
                break
            i += 1
    lines = []
    lines.append(f"# QA Report {QA_VERSION} — {event_type} — {ts}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"Reviewed tracker: {os.path.relpath(tracker_file, PROJECT_ROOT)}")
    lines.append("")
    lines.append("## Judgment")
    lines.append("Status: fail")
    lines.append("")
    lines.append("### Motivation")
    lines.append(motivation or "(none)")
    lines.append("")
    lines.append("## Recommendation")
    lines.append(recommendation or "(none)")
    lines.append("")
    lines.append("## Metadata")
    lines.append(f"QA Version: {QA_VERSION}")
    lines.append(f"Timestamp: {ts}")
    lines.append(f"Tracker File: {os.path.relpath(tracker_file, PROJECT_ROOT)}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    return out_path


def _increment_daily_report_counter():
    stats = load_stats_file() or {}
    today = stats.get("today") or {}
    today["qa_reports_generated"] = int(today.get("qa_reports_generated", 0)) + 1
    stats["today"] = today
    save_stats_file(stats)


def _update_tracker_processed(tracker_file: str):
    with open(tracker_file, "r") as f:
        obj = json.load(f) or {}
    obj["processed"] = True
    with open(tracker_file, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main():
    picked = _list_unprocessed_events()
    if not picked:
        logger.info("No unprocessed tracker events found. QA run complete.")
        return
    event_type, tracker_file = picked
    logger.info(f"Selected event: {event_type} | Tracker file: {tracker_file}")
    with open(tracker_file, "r") as f:
        event = json.load(f)
    logger.info(f"Event type: {event_type}")
    logger.info(f"Tracker file: {tracker_file}")
    logger.info("Event top-level keys: %s", list(event.keys()))
    logger.info("Event['inputs']:")
    for line in json.dumps(event.get('inputs', {}), indent=2, ensure_ascii=False).splitlines():
        logger.info(line)
    logger.info("Event['details']:")
    for line in json.dumps(event.get('details', {}), indent=2, ensure_ascii=False).splitlines():
        logger.info(line)

    logger.info("Building full context for event...")
    ctx = _build_context(event_type, event)

    logger.info("Invoking LLM critic...")
    action_guide = ACTION_TYPE_GUIDE.get(event_type, "Use common sense and project summary.")
    result = run_critic(
        project_summary=PROJECT_SUMMARY,
        event_type=event_type,
        action_guide=action_guide,
        event_inputs=ctx["event_inputs"],
        event_details=ctx["event_details"],
        article_text=ctx["article_text"],
        start_node=ctx["start_node"],
        end_node=ctx["end_node"],
        extra_context=ctx["extra_context"],
    )
    logger.info(f"Critic result: status={result.get('status')} | motivation={result.get('motivation')} | recommendation={result.get('recommendation')}")

    status = str(result.get("status", "")).strip().lower()
    motivation = result.get("motivation") or ""
    recommendation = result.get("recommendation") or ""

    if status not in {"pass", "fail"}:
        status = "fail"
        if not motivation:
            motivation = "Critic returned invalid/missing status."
        if not recommendation:
            recommendation = "Fix the critic prompt or parser."

    logger.info("Marking tracker as processed.")
    _update_tracker_processed(tracker_file)

    rel_path = os.path.relpath(tracker_file, PROJECT_ROOT)
    master_log(f"QA {QA_VERSION} reviewed {event_type} ({rel_path}) — status={status}")

    if status == "fail":
        logger.info("Writing markdown QA report for failed event...")
        report_path = _write_report(event_type, motivation, recommendation, tracker_file)
        logger.info(f"Report written: {report_path}")
        logger.info("Incrementing daily QA report counter.")
        _increment_daily_report_counter()
        master_log(f"QA {QA_VERSION} report created for {event_type}: {os.path.relpath(report_path, PROJECT_ROOT)}")
    else:
        logger.info("Event passed QA. No report written.")


if __name__ == "__main__":
    main()
