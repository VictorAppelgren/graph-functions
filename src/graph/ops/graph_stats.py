# graph_utils/graph_stats.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, TypedDict, Any
from src.graph.neo4j_client import run_cypher
from src.graph.ops.get_all_nodes import get_all_nodes
import os
import json

class Orphans(TypedDict):
    topics: int
    articles: int

class Snapshot(TypedDict):
    topics: int
    topics_with_full_analysis: int
    topics_with_full_analysis_examples: list[Any | None]
    articles: int
    connections: int  # adjust type if you have richer connection objects
    about_links: int
    inter_topic_links: int
    unique_relationship_types: list[str]
    orphans: Orphans
    last_updated: str  # ISO-8601 formatted datetime string

class ProblemsSection(TypedDict):
    """Represents the 'problems' section of the stats dict."""
    zero_result_queries: int
    topics_zero_results: list[str]
    topic_rejections: int
    no_replacement_candidates: int
    no_replacement_events: list[str]
    missing_analysis_fields: int
    missing_analysis_events: list[str]

def _get_cnt(query: str, params: dict | None = None, key: str = "cnt") -> int:
    """Run a count query and return an int (robust to empty/no rows)."""
    rows = run_cypher(query, params or {}) or []
    if not rows:
        return 0
    val = rows[0].get(key, 0)
    try:
        return int(val)
    except Exception:
        return 0

def get_topic_count() -> int:
    # Unified counting: rely on get_all_nodes to fetch all Topic nodes and take len
    try:
        topics = get_all_nodes(fields=["id"])  # id-only for minimal payload
        return len(topics)
    except Exception:
        # Fallback to direct Cypher count if utility fetch fails
        return _get_cnt("MATCH (n:Topic) RETURN count(n) AS cnt")

def get_article_count() -> int:
    return _get_cnt("MATCH (n:Article) RETURN count(n) AS cnt")

def get_relationship_count() -> int:
    return _get_cnt("MATCH ()-[r]->() RETURN count(r) AS cnt")

def get_about_links_count() -> int:
    return _get_cnt("MATCH ()-[r:ABOUT]->() RETURN count(r) AS cnt")

def get_inter_topic_links_count() -> int:
    # All relationships except ABOUT
    return _get_cnt("MATCH ()-[r]->() WHERE type(r) <> 'ABOUT' RETURN count(r) AS cnt")

def get_unique_relationship_types() -> List[str]:
    # Fallback to collecting distinct types for maximum compatibility
    rows = run_cypher("MATCH ()-[r]->() RETURN collect(DISTINCT type(r)) AS types") or []
    types = rows[0].get("types", []) if rows else []
    # Ensure strings, sorted for stability
    types = [str(t) for t in types]
    types.sort()
    return types

def get_orphan_topic_count() -> int:
    # Nodes with no relationships
    return _get_cnt("MATCH (n:Topic) WHERE NOT (n)--() RETURN count(n) AS cnt")

def get_orphan_article_count() -> int:
    return _get_cnt("MATCH (n:Article) WHERE NOT (n)--() RETURN count(n) AS cnt")
    

def get_topics_with_full_analysis_count() -> int:
    """Count topics that have all major analysis sections populated with non-empty text."""
    return _get_cnt(
        """
        MATCH (t:Topic)
        WHERE coalesce(trim(t.fundamental_analysis), '') <> ''
          AND coalesce(trim(t.medium_analysis), '') <> ''
          AND coalesce(trim(t.current_analysis), '') <> ''
          AND coalesce(trim(t.drivers), '') <> ''
          AND coalesce(trim(t.executive_summary), '') <> ''
          AND coalesce(trim(t.movers_scenarios), '') <> ''
          AND coalesce(trim(t.swing_trade_or_outlook), '') <> ''
        RETURN count(t) AS cnt
        """
    )
    
def get_graph_state_snapshot() -> Snapshot:
    """
    Aggregate a live snapshot of core graph metrics for the daily statistics JSON.
    """
    topics = get_topic_count()
    articles = get_article_count()
    connections = get_relationship_count()
    about_links = get_about_links_count()
    inter_topic_links = get_inter_topic_links_count()
    unique_relationship_types = get_unique_relationship_types()
    orphans_topics = get_orphan_topic_count()
    orphans_articles = get_orphan_article_count()

    analysis_full = get_topics_with_full_analysis_count()

    # Minimal examples list (names only), capped at 5, using the same predicate
    rows = run_cypher(
        """
        MATCH (t:Topic)
        WHERE coalesce(trim(t.fundamental_analysis), '') <> ''
          AND coalesce(trim(t.medium_analysis), '') <> ''
          AND coalesce(trim(t.current_analysis), '') <> ''
          AND coalesce(trim(t.drivers), '') <> ''
          AND coalesce(trim(t.executive_summary), '') <> ''
          AND coalesce(trim(t.movers_scenarios), '') <> ''
          AND coalesce(trim(t.swing_trade_or_outlook), '') <> ''
        RETURN t.name AS name
        LIMIT 5
        """
    ) or []
    analysis_examples = [r.get("name") for r in rows if r.get("name")]

    return {
        "topics": topics,
        "topics_with_full_analysis": analysis_full,
        "topics_with_full_analysis_examples": analysis_examples,
        "articles": articles,
        "connections": connections,
        "about_links": about_links,
        "inter_topic_links": inter_topic_links,
        "unique_relationship_types": unique_relationship_types,
        "orphans": {
            "topics": orphans_topics,
            "articles": orphans_articles,
        },
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

# ----------------------
# Problems section helpers
# ----------------------

def _today_stats_path() -> str:
    """Return the path to today's statistics JSON file."""
    return os.path.join("master_stats", f"statistics_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}.json")

def _load_daily_stats(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or {}
    if not isinstance(data, dict) or "today" not in data or "graph_state" not in data:
        raise ValueError("Daily stats malformed: missing 'today' or 'graph_state'")
    return data

def _save_daily_stats(path: str, data: dict[str, str]) -> None:
    if "today" not in data or "graph_state" not in data:
        raise ValueError("Refusing to save malformed stats: missing 'today' or 'graph_state'")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_problems_section(stats: dict[str, object]) -> ProblemsSection | dict[str, object]:
    if "problems" not in stats or not isinstance(stats["problems"], dict):
        stats["problems"] = ProblemsSection(
            zero_result_queries=0,
            topics_zero_results=[],
            topic_rejections=0,
            no_replacement_candidates=0,
            no_replacement_events=[],
            missing_analysis_fields=0,
            missing_analysis_events=[]
        )
    return stats

def record_zero_result_problem(topic_id: str) -> None:
    """Increment zero_result_queries and add topic_id to topics_zero_results (unique)."""
    if not topic_id:
        raise ValueError("topic_id is required")
    path = _today_stats_path()
    # Fail fast if the daily stats file does not exist; caller must ensure it is created via master_statistics
    if not os.path.exists(path):
        raise FileNotFoundError(f"Daily master stats file not found: {path}")

    stats = _load_daily_stats(path)
    ensure_problems_section(stats)
    stats["problems"]["zero_result_queries"] = int(stats["problems"].get("zero_result_queries", 0)) + 1
    lst = stats["problems"].get("topics_zero_results", [])
    if topic_id not in lst:
        lst.append(topic_id)
    stats["problems"]["topics_zero_results"] = lst
    _save_daily_stats(path, stats)

def record_no_replacement_candidates(topic_id: str, timeframe: str) -> None:
    """Record an event where no competing replacement candidates exist in the given timeframe.
    Increments a dedicated counter and appends an event item with topic and timeframe.
    Fail-fast if the daily stats file is missing.
    """
    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id is required")
    if not timeframe or not isinstance(timeframe, str):
        raise ValueError("timeframe is required")

    path = _today_stats_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Daily master stats file not found: {path}")

    stats = _load_daily_stats(path)
    ensure_problems_section(stats)
    probs = stats["problems"]

    # Increment counter (create if missing)
    probs["no_replacement_candidates"] = int(probs.get("no_replacement_candidates", 0)) + 1

    # Append event record (create list if missing)
    events = probs.get("no_replacement_events", [])
    events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic_id": topic_id,
        "timeframe": timeframe
    })
    probs["no_replacement_events"] = events

    _save_daily_stats(path, stats)

def record_topic_rejection(topic_name: str, category: str | None = None, failure_category: str | None = None) -> None:
    """Record a topic gating rejection into today's master stats problems section.
    Increments topic_rejections only. Fail-fast if the daily stats file is missing.
    """
    if not topic_name or not isinstance(topic_name, str):
        raise ValueError("topic_name is required")
    path = _today_stats_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Daily master stats file not found: {path}")

    stats = _load_daily_stats(path)
    ensure_problems_section(stats)
    probs = stats["problems"]
    probs["topic_rejections"] = int(probs.get("topic_rejections", 0)) + 1
    _save_daily_stats(path, stats)

def record_rewrites_skipped_zero_articles(topic_id: str, section: str) -> None:
    """Record a rewrite skip event (selected 0 articles) under today's problems.
    Increments a dedicated counter and appends an event item with topic and section.
    Fail-fast if the daily stats file is missing.
    """
    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id is required")
    if not section or not isinstance(section, str):
        raise ValueError("section is required")

    path = _today_stats_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Daily master stats file not found: {path}")

    stats = _load_daily_stats(path)
    ensure_problems_section(stats)
    probs = stats["problems"]

    # Increment counter
    probs["rewrites_skipped_0_articles"] = int(probs.get("rewrites_skipped_0_articles", 0)) + 1

    # Append event record
    events = probs.get("rewrite_skips", [])
    events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic_id": topic_id,
        "section": section
    })
    probs["rewrite_skips"] = events

    _save_daily_stats(path, stats)

def record_missing_analysis_fields(topic_id: str, section: str, article_id: str, missing_fields: list) -> None:
    """Record an event where required analysis fields are missing from article data.
    Increments a dedicated counter and appends an event item with details.
    Fail-fast if the daily stats file is missing.
    """
    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id is required")
    if not section or not isinstance(section, str):
        raise ValueError("section is required")
    if not article_id or not isinstance(article_id, str):
        raise ValueError("article_id is required")
    if not missing_fields or not isinstance(missing_fields, list):
        raise ValueError("missing_fields list is required")

    path = _today_stats_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Daily master stats file not found: {path}")

    stats = _load_daily_stats(path)
    ensure_problems_section(stats)
    probs = stats["problems"]

    # Increment counter
    probs["missing_analysis_fields"] = int(probs.get("missing_analysis_fields", 0)) + 1

    # Append event record
    events = probs.get("missing_analysis_events", [])
    events.append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic_id": topic_id,
        "section": section,
        "article_id": article_id,
        "missing_fields": missing_fields
    })
    probs["missing_analysis_events"] = events

    _save_daily_stats(path, stats)