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
- Pipeline run completed: topics_processed=X, successful_topics=Y, day=YYYY-MM-DD, success=True/False
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

LOG_DIR = "master_logs"
STATS_DIR = "master_stats"


def _get_logfile() -> str:
    # Always ensure the directory exists before returning the logfile path
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f"master_{datetime.now().strftime('%Y-%m-%d')}.log")


import json
from pydantic import BaseModel
from typing import Any
from enum import Enum, unique
from src.graph.ops.graph_stats import get_graph_state_snapshot
from src.graph.ops.graph_stats import update_stats
from src.llm.config import ModelTier
from src.graph.ops.graph_stats import SnapshotModel


@unique
class Problem(Enum):
    REWRITE_SKIPPED_0_ARTICLES = "rewrites_skipped_0_articles"
    MISSING_REQ_FIELDS_FOR_ANALYSIS_MATERIAL = (
        "missing_required_fields_for_analysis_material"
    )
    REWRITE_SKIPPED_0_ARTICLES_SUMMARY_ONLY = "rewrites_skipped_0_articles_summary_only"
    MISSING_SUMMARY_FOR_REPLACEMENT_DECISION = (
        "missing_summary_for_replacement_decision"
    )
    NO_REPLACEMENT_CANDIDATES = "no_replacement_candidates"
    MISSING_SUMMARY_FOR_SHOULD_REWRITE = "missing_summary_for_should_rewrite"
    ZERO_RESULTS = "zero_results"
    CAPACITY_GUARD_REPLACE_DELETION_FAILED = "capacity_guard_replace_deletion_failed"
    CAPACITY_GUARD_REPLACE_MISSING_ID_TO_REMOVE = (
        "capacity_guard_replace_missing_id_to_remove"
    )
    CAPACITY_GUARD_REJECT = "capacity_guard_reject"
    TOPIC_REJECTED = "topic_rejected"


class StatsModel(BaseModel):
    # Phase 1: Data Ingestion
    queries: int = 0
    articles_processed: int = 0
    articles_added: int = 0
    articles_removed: int = 0
    articles_rejected_no_topics: int = 0
    articles_missing_from_storage: int = 0
    duplicates_skipped: int = 0
    
    # Phase 2: Topic & Relationship Discovery
    topics_created: int = 0
    topics_deleted: int = 0
    about_links_added: int = 0
    about_links_removed: int = 0
    relationships_added: int = 0
    relationships_removed: int = 0
    
    # Phase 3: Topic Enrichment
    enrichment_attempts: int = 0
    enrichment_articles_added: int = 0
    topics_enriched_successfully: int = 0
    
    # Phase 4: Analysis Generation
    analysis_sections_written: int = 0  # Combined: generated + rewritten
    analysis_sections_skipped_insufficient_articles: int = 0
    should_rewrite_true: int = 0
    should_rewrite_false: int = 0
    
    # Phase 4b: Should Rewrite Pipeline Tracking
    should_rewrite_attempted: int = 0
    should_rewrite_trigger_from_article_ingestion: int = 0
    should_rewrite_trigger_from_enrichment_completion: int = 0
    should_rewrite_stopped_insufficient_articles: int = 0
    should_rewrite_stopped_uneven_sections: int = 0
    should_rewrite_stopped_recent_analysis: int = 0
    should_rewrite_stopped_llm_failure: int = 0
    should_rewrite_llm_decided_false: int = 0
    should_rewrite_llm_decided_true: int = 0
    should_rewrite_completed_with_analysis: int = 0
    should_rewrite_stopped_analysis_failed: int = 0
    
    # Phase 4c: Analysis Generation Pipeline Tracking
    analysis_rewriter_attempted: int = 0
    analysis_rewriter_stopped_no_articles: int = 0
    analysis_llm_generation_proceeded: int = 0
    analysis_llm_generation_stopped_failure: int = 0
    analysis_save_proceeded: int = 0
    analysis_save_stopped_error: int = 0
    
    # Phase 5: Maintenance & Quality
    topic_replacements_decided: int = 0
    qa_reports_generated: int = 0
    all_topics_queried: bool = False
    
    # Phase 6: System Metrics
    errors: int = 0
    llm_calls_failed: int = 0
    llm_simple_calls: int = 0
    llm_medium_calls: int = 0
    llm_complex_calls: int = 0
    llm_simple_long_context_calls: int = 0


class StatsFileModel(BaseModel):
    today: StatsModel
    graph_state: SnapshotModel


class ProblemDetailsModel(BaseModel):
    section: str = ""
    article_id: str = ""
    missing: list[str] = []
    category: str | None = None
    failure_category: str = ""
    timeframe: str | None = None
    should_add_motivation: str | None = None
    should_add: bool = False
    rationale: str | None = None
    importance: int = 0
    guard_action: str | None = None
    guard_motivation: str | None = None
    error: str | None = None
    id_to_remove: str | None = None


class ProblemModel(BaseModel):
    topic_id: int
    problem: Problem
    details: ProblemDetailsModel


def _get_statsfile_path() -> str:
    os.makedirs(STATS_DIR, exist_ok=True)
    return os.path.join(
        STATS_DIR, f"statistics_{datetime.now().strftime('%Y_%m_%d')}.json"
    )


def load_stats_file() -> StatsFileModel:
    statsfile = _get_statsfile_path()
    if os.path.exists(statsfile):
        try:
            with open(statsfile, "r") as f:
                content = f.read()
                if not content.strip():
                    # Empty file -> recreate defaults
                    raise json.JSONDecodeError("empty", content, 0)
                data = json.loads(content)
                # Validate/construct a Pydantic model from the dict
                return StatsFileModel.model_validate(data)
        except json.JSONDecodeError:
            # Corrupt or empty -> recreate defaults
            graph_state: SnapshotModel = get_graph_state_snapshot()
            stats = StatsModel()
            stats_file = StatsFileModel(today=stats, graph_state=graph_state)
            save_stats_file(stats_file)
            return stats_file
    # File does not exist -> create and return defaults
    graph_state: SnapshotModel = get_graph_state_snapshot()
    stats = StatsModel()
    stats_file = StatsFileModel(today=stats, graph_state=graph_state)
    save_stats_file(stats_file)
    return stats_file


def increment_llm_usage(tier: ModelTier) -> None:
    """Increment the LLM usage counter for the given ModelTier."""
    stats = load_stats_file()
    today = stats.today
    key = f"llm_{tier.name.lower()}_calls"
    current = getattr(today, key, 0)
    updated_today = today.model_copy(update={key: current + 1})
    stats = stats.model_copy(update={"today": updated_today})
    save_stats_file(stats)


def save_stats_file(stats: StatsFileModel) -> None:
    statsfile = _get_statsfile_path()
    # Serialize Pydantic model to a plain dict before JSON dumping
    payload = stats.model_dump()
    with open(statsfile, "w") as f:
        json.dump(payload, f, indent=2)


def master_statistics(
    # Phase 1: Data Ingestion
    queries: int = 0,
    articles_processed: int = 0,
    articles_added: int = 0,
    articles_removed: int = 0,
    articles_rejected_no_topics: int = 0,
    duplicates_skipped: int = 0,
    
    # Phase 2: Topic & Relationship Discovery
    topics_created: int = 0,
    topics_deleted: int = 0,
    about_links_added: int = 0,
    about_links_removed: int = 0,
    relationships_added: int = 0,
    relationships_removed: int = 0,
    
    # Phase 3: Topic Enrichment
    enrichment_attempts: int = 0,
    enrichment_articles_added: int = 0,
    topics_enriched_successfully: int = 0,
    
    # Phase 4: Analysis Generation
    analysis_sections_written: int = 0,  # Combined: generated + rewritten
    analysis_sections_skipped_insufficient_articles: int = 0,
    should_rewrite_true: int = 0,
    should_rewrite_false: int = 0,
    
    # Phase 4b: Should Rewrite Pipeline Tracking
    should_rewrite_attempted: int = 0,
    should_rewrite_trigger_from_article_ingestion: int = 0,
    should_rewrite_trigger_from_enrichment_completion: int = 0,
    should_rewrite_stopped_insufficient_articles: int = 0,
    should_rewrite_stopped_uneven_sections: int = 0,
    should_rewrite_stopped_recent_analysis: int = 0,
    should_rewrite_stopped_llm_failure: int = 0,
    should_rewrite_llm_decided_false: int = 0,
    should_rewrite_llm_decided_true: int = 0,
    should_rewrite_completed_with_analysis: int = 0,
    should_rewrite_stopped_analysis_failed: int = 0,
    
    # Phase 4c: Analysis Generation Pipeline Tracking
    analysis_rewriter_attempted: int = 0,
    analysis_rewriter_stopped_no_articles: int = 0,
    analysis_llm_generation_proceeded: int = 0,
    analysis_llm_generation_stopped_failure: int = 0,
    analysis_save_proceeded: int = 0,
    analysis_save_stopped_error: int = 0,
    
    # Phase 5: Maintenance & Quality
    topic_replacements_decided: int = 0,
    
    # Phase 6: System Metrics
    errors: int = 0,
    llm_calls_failed: int = 0,
    llm_simple_calls: int = 0,
    llm_medium_calls: int = 0,
    llm_complex_calls: int = 0,
    llm_simple_long_context_calls: int = 0,
) -> None:
    # Load existing stats and preserve any unknown counters in today's section (e.g., llm_*_calls)
    stats = load_stats_file()
    t = stats.today

    # Phase 1: Data Ingestion
    if queries:
        t.queries += queries
    if articles_processed:
        t.articles_processed += articles_processed
    if articles_added:
        t.articles_added += articles_added
    if articles_removed:
        t.articles_removed += articles_removed
    if articles_rejected_no_topics:
        t.articles_rejected_no_topics += articles_rejected_no_topics
    if duplicates_skipped:
        t.duplicates_skipped += duplicates_skipped
    
    # Phase 2: Topic & Relationship Discovery
    if topics_created:
        t.topics_created += topics_created
    if topics_deleted:
        t.topics_deleted += topics_deleted
    if about_links_added:
        t.about_links_added += about_links_added
    if about_links_removed:
        t.about_links_removed += about_links_removed
    if relationships_added:
        t.relationships_added += relationships_added
    if relationships_removed:
        t.relationships_removed += relationships_removed
    
    # Phase 3: Topic Enrichment
    if enrichment_attempts:
        t.enrichment_attempts += enrichment_attempts
    if enrichment_articles_added:
        t.enrichment_articles_added += enrichment_articles_added
    if topics_enriched_successfully:
        t.topics_enriched_successfully += topics_enriched_successfully
    
    # Phase 4: Analysis Generation
    if analysis_sections_written:
        t.analysis_sections_written += analysis_sections_written
    if analysis_sections_skipped_insufficient_articles:
        t.analysis_sections_skipped_insufficient_articles += analysis_sections_skipped_insufficient_articles
    if should_rewrite_true:
        t.should_rewrite_true += should_rewrite_true
    if should_rewrite_false:
        t.should_rewrite_false += should_rewrite_false
    
    # Phase 4b: Should Rewrite Pipeline Tracking
    if should_rewrite_attempted:
        t.should_rewrite_attempted += should_rewrite_attempted
    if should_rewrite_trigger_from_article_ingestion:
        t.should_rewrite_trigger_from_article_ingestion += should_rewrite_trigger_from_article_ingestion
    if should_rewrite_trigger_from_enrichment_completion:
        t.should_rewrite_trigger_from_enrichment_completion += should_rewrite_trigger_from_enrichment_completion
    if should_rewrite_stopped_insufficient_articles:
        t.should_rewrite_stopped_insufficient_articles += should_rewrite_stopped_insufficient_articles
    if should_rewrite_stopped_uneven_sections:
        t.should_rewrite_stopped_uneven_sections += should_rewrite_stopped_uneven_sections
    if should_rewrite_stopped_recent_analysis:
        t.should_rewrite_stopped_recent_analysis += should_rewrite_stopped_recent_analysis
    if should_rewrite_stopped_llm_failure:
        t.should_rewrite_stopped_llm_failure += should_rewrite_stopped_llm_failure
    if should_rewrite_llm_decided_false:
        t.should_rewrite_llm_decided_false += should_rewrite_llm_decided_false
    if should_rewrite_llm_decided_true:
        t.should_rewrite_llm_decided_true += should_rewrite_llm_decided_true
    if should_rewrite_completed_with_analysis:
        t.should_rewrite_completed_with_analysis += should_rewrite_completed_with_analysis
    if should_rewrite_stopped_analysis_failed:
        t.should_rewrite_stopped_analysis_failed += should_rewrite_stopped_analysis_failed
    
    # Phase 4c: Analysis Generation Pipeline Tracking
    if analysis_rewriter_attempted:
        t.analysis_rewriter_attempted += analysis_rewriter_attempted
    if analysis_rewriter_stopped_no_articles:
        t.analysis_rewriter_stopped_no_articles += analysis_rewriter_stopped_no_articles
    if analysis_llm_generation_proceeded:
        t.analysis_llm_generation_proceeded += analysis_llm_generation_proceeded
    if analysis_llm_generation_stopped_failure:
        t.analysis_llm_generation_stopped_failure += analysis_llm_generation_stopped_failure
    if analysis_save_proceeded:
        t.analysis_save_proceeded += analysis_save_proceeded
    if analysis_save_stopped_error:
        t.analysis_save_stopped_error += analysis_save_stopped_error
    
    # Phase 5: Maintenance & Quality
    if topic_replacements_decided:
        t.topic_replacements_decided += topic_replacements_decided
    
    # Phase 6: System Metrics
    if errors:
        t.errors += errors
    if llm_calls_failed:
        t.llm_calls_failed += llm_calls_failed
    if llm_simple_calls:
        t.llm_simple_calls += llm_simple_calls
    if llm_medium_calls:
        t.llm_medium_calls += llm_medium_calls
    if llm_complex_calls:
        t.llm_complex_calls += llm_complex_calls
    if llm_simple_long_context_calls:
        t.llm_simple_long_context_calls += llm_simple_long_context_calls

    stats.graph_state = get_graph_state_snapshot()

    save_stats_file(stats)


def master_log(
    message: str,
    # Phase 1: Data Ingestion
    queries: int = 0,
    articles_processed: int = 0,
    articles_added: int = 0,
    articles_removed: int = 0,
    articles_rejected_no_topics: int = 0,
    duplicates_skipped: int = 0,
    
    # Phase 2: Topic & Relationship Discovery
    topics_created: int = 0,
    topics_deleted: int = 0,
    about_links_added: int = 0,
    about_links_removed: int = 0,
    relationships_added: int = 0,
    relationships_removed: int = 0,
    
    # Phase 3: Topic Enrichment
    enrichment_attempts: int = 0,
    enrichment_articles_added: int = 0,
    topics_enriched_successfully: int = 0,
    
    # Phase 4: Analysis Generation
    analysis_sections_written: int = 0,  # Combined: generated + rewritten
    analysis_sections_skipped_insufficient_articles: int = 0,
    should_rewrite_true: int = 0,
    should_rewrite_false: int = 0,
    
    # Phase 4b: Should Rewrite Pipeline Tracking
    should_rewrite_attempted: int = 0,
    should_rewrite_trigger_from_article_ingestion: int = 0,
    should_rewrite_trigger_from_enrichment_completion: int = 0,
    should_rewrite_stopped_insufficient_articles: int = 0,
    should_rewrite_stopped_uneven_sections: int = 0,
    should_rewrite_stopped_recent_analysis: int = 0,
    should_rewrite_stopped_llm_failure: int = 0,
    should_rewrite_llm_decided_false: int = 0,
    should_rewrite_llm_decided_true: int = 0,
    should_rewrite_completed_with_analysis: int = 0,
    should_rewrite_stopped_analysis_failed: int = 0,
    
    # Phase 4c: Analysis Generation Pipeline Tracking
    analysis_rewriter_attempted: int = 0,
    analysis_rewriter_stopped_no_articles: int = 0,
    analysis_llm_generation_proceeded: int = 0,
    analysis_llm_generation_stopped_failure: int = 0,
    analysis_save_proceeded: int = 0,
    analysis_save_stopped_error: int = 0,
    
    # Phase 5: Maintenance & Quality
    topic_replacements_decided: int = 0,
    
    # Phase 6: System Metrics
    llm_calls_failed: int = 0,
    llm_simple_calls: int = 0,
    llm_medium_calls: int = 0,
    llm_complex_calls: int = 0,
    llm_simple_long_context_calls: int = 0,
) -> None:
    """Log a completed action (success, removal, etc) to the master daily log and increment stats."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(_get_logfile(), "a") as f:
        f.write(f"{timestamp} | {message}\n")
    master_statistics(
        queries=queries,
        articles_processed=articles_processed,
        articles_added=articles_added,
        articles_removed=articles_removed,
        articles_rejected_no_topics=articles_rejected_no_topics,
        duplicates_skipped=duplicates_skipped,
        topics_created=topics_created,
        topics_deleted=topics_deleted,
        about_links_added=about_links_added,
        about_links_removed=about_links_removed,
        relationships_added=relationships_added,
        relationships_removed=relationships_removed,
        enrichment_attempts=enrichment_attempts,
        enrichment_articles_added=enrichment_articles_added,
        topics_enriched_successfully=topics_enriched_successfully,
        analysis_sections_written=analysis_sections_written,
        analysis_sections_skipped_insufficient_articles=analysis_sections_skipped_insufficient_articles,
        should_rewrite_true=should_rewrite_true,
        should_rewrite_false=should_rewrite_false,
        should_rewrite_attempted=should_rewrite_attempted,
        should_rewrite_trigger_from_article_ingestion=should_rewrite_trigger_from_article_ingestion,
        should_rewrite_trigger_from_enrichment_completion=should_rewrite_trigger_from_enrichment_completion,
        should_rewrite_stopped_insufficient_articles=should_rewrite_stopped_insufficient_articles,
        should_rewrite_stopped_uneven_sections=should_rewrite_stopped_uneven_sections,
        should_rewrite_stopped_recent_analysis=should_rewrite_stopped_recent_analysis,
        should_rewrite_stopped_llm_failure=should_rewrite_stopped_llm_failure,
        should_rewrite_llm_decided_false=should_rewrite_llm_decided_false,
        should_rewrite_llm_decided_true=should_rewrite_llm_decided_true,
        should_rewrite_completed_with_analysis=should_rewrite_completed_with_analysis,
        should_rewrite_stopped_analysis_failed=should_rewrite_stopped_analysis_failed,
        analysis_rewriter_attempted=analysis_rewriter_attempted,
        analysis_rewriter_stopped_no_articles=analysis_rewriter_stopped_no_articles,
        analysis_llm_generation_proceeded=analysis_llm_generation_proceeded,
        analysis_llm_generation_stopped_failure=analysis_llm_generation_stopped_failure,
        analysis_save_proceeded=analysis_save_proceeded,
        analysis_save_stopped_error=analysis_save_stopped_error,
        topic_replacements_decided=topic_replacements_decided,
        llm_calls_failed=llm_calls_failed,
        llm_simple_calls=llm_simple_calls,
        llm_medium_calls=llm_medium_calls,
        llm_complex_calls=llm_complex_calls,
        llm_simple_long_context_calls=llm_simple_long_context_calls,
    )


def master_log_error(message: str, error: Exception | None = None) -> None:
    """Log an error in a standardized 4-field line and increment error stats."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    details = f"{message}"
    if error:
        details += f" Error: {str(error)[:200]}"
    line = f"{timestamp} | Error | - | {details}"
    with open(_get_logfile(), "a") as f:
        f.write(line + "\n")
    master_statistics(errors=1)


def problem_log(
    problem: Problem, topic: str, details: ProblemDetailsModel | None = None
) -> None:
    """
    Record a minimal problem into the daily master stats JSON under the
    top-level "problems" section. Currently supports only:
      - "Zero results": increments zero_result_queries and appends topic to topics_zero_results
    """

    # Ensures the stats file exists
    load_stats_file()

    if not problem or not topic:
        raise ValueError("problem and topic are required")
    if problem == Problem.ZERO_RESULTS:
        update_stats(zero_result_topic_ids=[topic])
    elif problem == Problem.TOPIC_REJECTED:
        update_stats(topic_rejections=1)
    elif problem == Problem.REWRITE_SKIPPED_0_ARTICLES:
        update_stats(
            analysis_sections_skipped_insufficient_articles=1,
            rewrite_skip_event=details.model_dump() if details else None,
        )
    elif problem == Problem.NO_REPLACEMENT_CANDIDATES:
        update_stats(
            no_replacement_candidates=1,
            no_replacement_event=details.model_dump() if details else None,
        )
    elif problem == Problem.MISSING_REQ_FIELDS_FOR_ANALYSIS_MATERIAL:
        if details:
            update_stats(
                missing_analysis_event={
                    "topic_id": topic,
                    "section": details.section,
                    "article_id": details.article_id,
                    "missing_fields": details.missing,
                }
            )
    else:
        return
