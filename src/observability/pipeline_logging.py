"""
Saga Master Log Utility
----------------------------

Purpose:
--------
This module provides a simple, robust interface for writing high-level, human-readable daily master log entries for the Saga pipeline. The goal is to supplement detailed logs with a concise summary of completed actions and problems/errors, giving a clear overview of pipeline health and major events for each day.

Usage:
------
- One log file per day: logs/master/master_YYYY-MM-DD.log
- Use `master_log()` for completed actions (successes, removals, major changes).
- Use `master_log_error()` for problems/errors (failures, exceptions, skips due to error).
- Do NOT log 'started' or in-progress events; only completions and problems.

Events to Track:
----------------
- Scraped N articles for TOPIC
- Added article ARTICLE_ID to TOPIC
- Duplicate article ARTICLE_ID detected for TOPIC, skipping
- Article ARTICLE_ID removed from TOPIC (relevance test/removal)
- Section 'SECTION' rewritten for TOPIC
- Section 'SECTION' skipped for TOPIC (if due to error or empty, not just normal skip)
- Relationship 'TYPE' created: SRC -> TGT
- Relationship 'TYPE' removed: SRC -> TGT
- Pipeline run completed: nodes_processed=X, successful_nodes=Y, day=YYYY-MM-DD, success=True/False
- Any error/problem for the above events

Where to Add Master Log Events:
-------------------------------
| Event                                                | File                                      | Function(s)                       |
|------------------------------------------------------|-------------------------------------------|------------------------------------|
| Retrieved N articles for TOPIC                       | perigon/source_scraper.py                 | scrape_article_and_sources         |
| Added article ARTICLE_ID to TOPIC                    | graph_articles/add_article.py             | add_article                        |
| Duplicate article detected/skipped                   | graph_articles/add_article.py             | add_article                        |
| Article removed from TOPIC (relevance test/removal)  | analysis/does_article_replace_old.py      | does_article_replace_old           |
| Section 'SECTION' rewritten for TOPIC                | analysis/analysis_rewriter.py             | analysis_rewriter                  |
| Section 'SECTION' skipped for TOPIC                  | analysis/analysis_rewriter.py             | analysis_rewriter                  |
| Relationship created                                 | graph_articles/add_link.py                | add_link                           |
| Relationship removed                                 | graph_articles/add_link.py (or similar)   | remove_link (if exists)            |
| Pipeline run completed                               | main.py                                   | run_pipeline                       |

This ensures a comprehensive, actionable overview of all major pipeline events and issues for each day.

Where to Add Error Log Events:
------------------------------
| Error Context                                       | File                                      | Function(s)                       |
|-----------------------------------------------------|-------------------------------------------|------------------------------------|
| Scraping failed for TOPIC                           | perigon/source_scraper.py                 | scrape_article_and_sources         |
| Article ingestion failed for ARTICLE_ID             | graph_articles/add_article.py             | add_article                        |
| Duplicate detection failed                          | graph_articles/add_article.py             | add_article                        |
| Article removal/relevance test failed               | analysis/does_article_replace_old.py      | does_article_replace_old           |
| Section rewrite/save failed for TOPIC/SECTION       | analysis/analysis_rewriter.py             | analysis_rewriter                  |
| Relationship creation/removal failed                | graph_articles/add_link.py                | add_link, remove_link (if exists)  |
| Pipeline run failed                                | main.py                                   | run_pipeline                       |
| Any other exception                                | All above                                 | All above (exception handlers)      |

Add a call to master_log_error in each of these error/exception contexts for robust, actionable daily error reporting.


"""

import os
from datetime import datetime
import time

LOG_DIR = "master_logs"
STATS_DIR = "master_stats"

def _get_logfile() -> str:
    # Always ensure the directory exists before returning the logfile path
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f"master_{datetime.now().strftime('%Y-%m-%d')}.log")

import json
from typing import TypedDict
from src.graph.ops.graph_stats import get_graph_state_snapshot
from src.graph.ops.graph_stats import record_zero_result_problem
from src.graph.ops.graph_stats import record_topic_rejection
from src.graph.ops.graph_stats import record_rewrites_skipped_zero_articles
from src.graph.ops.graph_stats import record_no_replacement_candidates
from src.graph.ops.graph_stats import record_missing_analysis_fields
from src.llm.llm_router import ModelTier
from src.graph.ops.graph_stats import get_graph_state_snapshot

class Stats(TypedDict):
    topics_total_today: int
    all_topics_queried: bool
    full_analysis_new_today: int
    enrichment_attempts: int
    enrichment_articles_added: int
    queries: int
    articles: int
    articles_added: int
    articles_removed: int
    added_node: int
    removes_node: int
    about_links_added: int
    about_links_removed: int
    relationships_added: int
    relationships_removed: int
    rewrites_saved: int
    rewrites_skipped_0_articles: int
    duplicates_skipped: int
    errors: int
    qa_reports_generated: int
    should_rewrite_true: int
    should_rewrite_false: int
    topic_replacements_decided: int
    llm_simple_calls: int
    llm_medium_calls: int
    llm_complex_calls: int
    llm_simple_long_context_calls: int

class StatsFile(TypedDict):
    today: Stats
    graph_state: dict[]

def _get_statsfile() -> str:
    os.makedirs(STATS_DIR, exist_ok=True)
    return os.path.join(STATS_DIR, f"statistics_{datetime.now().strftime('%Y_%m_%d')}.json")

_DEFAULT_STATS = {
    # Coverage (minimal, flat)
    "topics_total_today": 0,
    "all_topics_queried": False,

    # Progress (vs yesterday)
    "full_analysis_new_today": 0,

    # Enrichment (try/find new data)
    "enrichment_attempts": 0,
    "enrichment_articles_added": 0,

    "queries": 0,
    "articles": 0,
    "articles_added": 0,
    "articles_removed": 0,
    "added_node": 0,
    "removes_node": 0,
    "about_links_added": 0,
    "about_links_removed": 0,
    "relationships_added": 0,
    "relationships_removed": 0,
    "rewrites_saved": 0,
    "rewrites_skipped_0_articles": 0,
    "duplicates_skipped": 0,
    "errors": 0,
    "qa_reports_generated": 0,
    "should_rewrite_true": 0,
    "should_rewrite_false": 0,
    # Decisions / actions (non-problem) counters
    "topic_replacements_decided": 0,
    # Explicit LLM counters (preserve across writes)
    "llm_simple_calls": 0,
    "llm_medium_calls": 0,
    "llm_complex_calls": 0,
    "llm_simple_long_context_calls": 0
}

def load_stats_file() -> StatsFile:
    statsfile = _get_statsfile()
    if os.path.exists(statsfile):
        try:
            with open(statsfile, "r") as f:
                return json.load(f) or {}
        except json.JSONDecodeError:
            # Likely partial write; short sleep and retry once
            time.sleep(2)
            try:
                with open(statsfile, "r") as f:
                    return json.load(f) or {}
            except json.JSONDecodeError:
                # Fail-soft: return empty dict; callers add defaults
                return {}
    else:
        # Create a new stats file with today's defaults and graph_state
        try:
            graph_state = get_graph_state_snapshot()
        except Exception:
            graph_state = {}
        default_stats = {"today": _DEFAULT_STATS.copy(), "graph_state": graph_state}
        save_stats_file(default_stats)
        return default_stats

def _compute_full_analysis_new_today(current_graph_state: dict) -> int:
    """
    Compute delta vs yesterday for topics with full analysis.
    Returns max(today_full - yesterday_full, 0). Fail-soft: 0 on any I/O error.
    """
    try:
        from datetime import timedelta
        y = datetime.now() - timedelta(days=1)
        ypath = os.path.join(STATS_DIR, f"statistics_{y.strftime('%Y_%m_%d')}.json")
        if not os.path.exists(ypath):
            return 0
        with open(ypath, "r") as f:
            ystats = json.load(f) or {}
        y_graph = ystats.get("graph_state") or {}
        y_full = y_graph.get("topics_with_full_analysis")
        y_count = len(y_full) if isinstance(y_full, list) else int(y_full or 0)
    except Exception:
        return 0

    t_full = current_graph_state.get("topics_with_full_analysis")
    t_count = len(t_full) if isinstance(t_full, list) else int(t_full or 0)
    return max(t_count - y_count, 0)

def increment_llm_usage(tier: ModelTier) -> None:
    """Increment the LLM usage counter for the given ModelTier."""
    stats = load_stats_file() or {}
    today = stats.get("today") or {}
    key = f"llm_{tier.name.lower()}_calls"
    today[key] = int(today.get(key, 0)) + 1
    stats["today"] = today
    save_stats_file(stats)

def save_stats_file(stats: dict):
    statsfile = _get_statsfile()
    with open(statsfile, "w") as f:
        json.dump(stats, f, indent=2)

def master_statistics(queries=0, articles=0, articles_added=0, articles_removed=0, added_node=0, removes_node=0, about_links_added=0, about_links_removed=0, relationships_added=0, relationships_removed=0, rewrites_saved=0, rewrites_skipped_0_articles=0, duplicates_skipped=0, errors=0, should_rewrite_true=0, should_rewrite_false=0, topic_replacements_decided=0, enrichment_attempts=0, enrichment_articles_added=0):
    # Load existing stats and preserve any unknown counters in today's section (e.g., llm_*_calls)
    stats = load_stats_file()
    existing_stats = stats if isinstance(stats, dict) else {}
    # Start from existing 'today' to keep dynamic keys
    today = dict(existing_stats.get("today") or {})
    # Ensure all default keys exist
    for k, default in _DEFAULT_STATS.items():
        today[k] = today.get(k, default)
    # Cleanup: drop deprecated keys
    if "topics_queried_today" in today:
        today.pop("topics_queried_today", None)
    # Increment only nonzero arguments
    for k, v in {
        "queries": queries,
        "articles": articles,
        "articles_added": articles_added,
        "articles_removed": articles_removed,
        "added_node": added_node,
        "removes_node": removes_node,
        "about_links_added": about_links_added,
        "about_links_removed": about_links_removed,
        "relationships_added": relationships_added,
        "relationships_removed": relationships_removed,
        "rewrites_saved": rewrites_saved,
        "rewrites_skipped_0_articles": rewrites_skipped_0_articles,
        "duplicates_skipped": duplicates_skipped,
        "errors": errors,
        "should_rewrite_true": should_rewrite_true,
        "should_rewrite_false": should_rewrite_false,
        "topic_replacements_decided": topic_replacements_decided,
        # New minimal coverage/enrichment counters
        "enrichment_attempts": enrichment_attempts,
        "enrichment_articles_added": enrichment_articles_added,
    }.items():
        if v:
            today[k] = today.get(k, 0) + v
    # Write back updates in-place and attach live graph snapshot
    existing_stats["today"] = today
    try:
        existing_stats["graph_state"] = get_graph_state_snapshot()
    except Exception as e:
        # Fail-soft but ensure the field exists for observability
        existing_stats["graph_state"] = {"error": str(e)[:200]}
    # Minimal coverage/progress logic (flat, auto-managed)
    g = existing_stats.get("graph_state") or {}
    if int(today.get("topics_total_today") or 0) == 0:
        today["topics_total_today"] = int(g.get("topics", 0) or 0)
    total = int(today.get("topics_total_today") or 0)
    # Compute daily delta for full analysis progress
    today["full_analysis_new_today"] = int(_compute_full_analysis_new_today(g))
    save_stats_file(existing_stats)

def master_log(message: str, queries=0, articles=0, articles_added=0, articles_removed=0, added_node=0, removes_node=0, about_links_added=0, about_links_removed=0, relationships_added=0, relationships_removed=0, rewrites_saved=0, rewrites_skipped_0_articles=0, duplicates_skipped=0, topic_replacements_decided=0):
    """Log a completed action (success, removal, etc) to the master daily log and increment stats."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(_get_logfile(), "a") as f:
        f.write(f"{timestamp} | {message}\n")
    master_statistics(
        queries=queries,
        articles=articles,
        articles_added=articles_added,
        articles_removed=articles_removed,
        added_node=added_node,
        removes_node=removes_node,
        about_links_added=about_links_added,
        about_links_removed=about_links_removed,
        relationships_added=relationships_added,
        relationships_removed=relationships_removed,
        rewrites_saved=rewrites_saved,
        rewrites_skipped_0_articles=rewrites_skipped_0_articles,
        duplicates_skipped=duplicates_skipped,
        topic_replacements_decided=topic_replacements_decided,
    )

def master_log_error(message: str, error: Exception = None):
    """Log an error in a standardized 4-field line and increment error stats."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    details = f"{message}"
    if error:
        details += f" Error: {str(error)[:200]}"
    line = f"{timestamp} | Error | - | {details}"
    with open(_get_logfile(), "a") as f:
        f.write(line + "\n")
    master_statistics(errors=1)

def problem_log(problem: str, topic: str, details=None):
    """
    Record a minimal problem into the daily master stats JSON under the
    top-level "problems" section. Currently supports only:
      - "Zero results": increments zero_result_queries and appends topic to topics_zero_results
    """

    # Ensures the stats file exists
    load_stats_file()

    if not problem or not topic:
        raise ValueError("problem and topic are required")
    if problem == "Zero results":
        # Update the problems section in the daily stats JSON (fail-fast)
        record_zero_result_problem(topic_id=topic)
    elif problem == "Topic rejected":
        category = None
        failure_category = None
        if isinstance(details, dict):
            category = details.get("category")
            failure_category = details.get("failure_category")
        record_topic_rejection(topic_name=topic, category=category, failure_category=failure_category)
    elif problem == "rewrites_skipped_0_articles":
        section = None
        if isinstance(details, dict) and "section" in details:
            section = details["section"]
        if not section:
            raise ValueError("details.section is required for rewrites_skipped_0_articles")
        record_rewrites_skipped_zero_articles(topic_id=topic, section=section)
    elif problem == "No replacement candidates":
        timeframe = None
        if isinstance(details, dict):
            timeframe = details.get("timeframe")
        if not timeframe:
            raise ValueError("details.timeframe is required for 'No replacement candidates'")
        record_no_replacement_candidates(topic_id=topic, timeframe=timeframe)
    elif problem == "missing_required_fields_for_analysis_material":
        section = None
        article_id = None
        missing = None
        if isinstance(details, dict):
            section = details.get("section")
            article_id = details.get("article_id")
            missing = details.get("missing")
        if not section:
            raise ValueError("details.section is required for 'missing_required_fields_for_analysis_material'")
        if not article_id:
            raise ValueError("details.article_id is required for 'missing_required_fields_for_analysis_material'")
        if not missing or not isinstance(missing, list):
            raise ValueError("details.missing list is required for 'missing_required_fields_for_analysis_material'")
        record_missing_analysis_fields(topic_id=topic, section=section, article_id=article_id, missing_fields=missing)
    else:
        # Keep the surface area minimal and explicit
        raise ValueError(f"Unsupported problem type: {problem}")


        