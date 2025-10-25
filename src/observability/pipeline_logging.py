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
import json
import fcntl
import time
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Any, List, Dict
from enum import Enum, unique

from src.graph.neo4j_client import run_cypher
from src.llm.config import ModelTier

LOG_DIR = "master_logs"
STATS_DIR = "master_stats"


# ============================================================================
# GRAPH METRICS - Pure graph queries (no state)
# ============================================================================

class OrphansModel(BaseModel):
    topics: int = 0
    articles: int = 0


class SnapshotModel(BaseModel):
    """Live snapshot of graph state."""
    topics: int = 0
    topics_with_full_analysis: int = 0
    topics_with_full_analysis_examples: List[str] = []
    articles: int = 0
    connections: int = 0
    about_links: int = 0
    inter_topic_links: int = 0
    mapped_to_links: int = 0
    unique_relationship_types: List[str] = []
    orphans: OrphansModel = OrphansModel()
    
    # Article-Topic Distribution
    articles_zero_topics: int = 0
    articles_one_topic: int = 0
    articles_multiple_topics: int = 0
    avg_topics_per_article: float = 0.0
    
    # Timeframe Distribution
    articles_by_timeframe: Dict[str, int] = {}
    
    # Perspective Scores
    avg_perspective_scores: Dict[str, float] = {}
    
    # Analysis Section Coverage
    analysis_section_coverage: Dict[str, int] = {}
    
    last_updated: str = ""


def _get_cnt(query: str, key: str = "cnt") -> int:
    """Run a count query and return an int (robust to empty/no rows)."""
    rows = run_cypher(query)
    if not rows:
        return 0
    val = rows[0].get(key, 0)
    try:
        return int(val)
    except Exception:
        return 0


def get_topic_count() -> int:
    """Count topics directly via Cypher."""
    return _get_cnt("MATCH (n:Topic) RETURN count(n) AS cnt")


def get_article_count() -> int:
    return _get_cnt("MATCH (n:Article) RETURN count(n) AS cnt")


def get_relationship_count() -> int:
    return _get_cnt("MATCH ()-[r]->() RETURN count(r) AS cnt")


def get_about_links_count() -> int:
    return _get_cnt("MATCH ()-[r:ABOUT]->() RETURN count(r) AS cnt")


def get_mapped_to_count() -> int:
    """Count MAPPED_TO relationships (article-to-topic links)."""
    return _get_cnt("MATCH ()-[r:MAPPED_TO]->() RETURN count(r) AS cnt")


def get_inter_topic_links_count() -> int:
    # All relationships except ABOUT and MAPPED_TO
    return _get_cnt(
        "MATCH ()-[r]->() WHERE type(r) <> 'ABOUT' AND type(r) <> 'MAPPED_TO' RETURN count(r) AS cnt"
    )


def get_unique_relationship_types() -> List[str]:
    rows = run_cypher("MATCH ()-[r]->() RETURN collect(DISTINCT type(r)) AS types") or []
    types = rows[0].get("types", []) if rows else []
    types = [str(t) for t in types]
    types.sort()
    return types


def get_orphan_topic_count() -> int:
    return _get_cnt("MATCH (n:Topic) WHERE NOT (n)--() RETURN count(n) AS cnt")


def get_orphan_article_count() -> int:
    return _get_cnt("MATCH (n:Article) WHERE NOT (n)--() RETURN count(n) AS cnt")


def get_topics_with_full_analysis_count() -> int:
    """Count topics that have all major analysis sections populated."""
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


def get_articles_by_topic_count() -> Dict[str, int]:
    """Get distribution of articles by number of topics."""
    query = """
    MATCH (a:Article)
    OPTIONAL MATCH (a)-[:MAPPED_TO]->(t:Topic)
    WITH a, count(t) AS topic_count
    RETURN 
        sum(CASE WHEN topic_count = 0 THEN 1 ELSE 0 END) AS zero_topics,
        sum(CASE WHEN topic_count = 1 THEN 1 ELSE 0 END) AS one_topic,
        sum(CASE WHEN topic_count >= 2 THEN 1 ELSE 0 END) AS multiple_topics,
        avg(toFloat(topic_count)) AS avg_topics_per_article
    """
    result = run_cypher(query)
    return result[0] if result else {}


def get_articles_by_timeframe() -> Dict[str, int]:
    """Get distribution of articles by temporal_horizon."""
    query = """
    MATCH (a:Article)
    WHERE a.temporal_horizon IS NOT NULL
    RETURN 
        a.temporal_horizon AS timeframe,
        count(a) AS count
    ORDER BY timeframe
    """
    result = run_cypher(query)
    return {r['timeframe']: r['count'] for r in result}


def get_perspective_score_stats() -> Dict[str, float]:
    """Get average perspective scores across all articles."""
    query = """
    MATCH (a:Article)
    RETURN 
        avg(toFloat(coalesce(a.importance_risk, 0))) AS avg_risk,
        avg(toFloat(coalesce(a.importance_opportunity, 0))) AS avg_opportunity,
        avg(toFloat(coalesce(a.importance_trend, 0))) AS avg_trend,
        avg(toFloat(coalesce(a.importance_catalyst, 0))) AS avg_catalyst
    """
    result = run_cypher(query)
    return result[0] if result else {}


def get_analysis_section_coverage() -> Dict[str, int]:
    """Count topics with each individual analysis section."""
    query = """
    MATCH (t:Topic)
    RETURN 
        sum(CASE WHEN coalesce(trim(t.fundamental_analysis), '') <> '' THEN 1 ELSE 0 END) AS fundamental,
        sum(CASE WHEN coalesce(trim(t.medium_analysis), '') <> '' THEN 1 ELSE 0 END) AS medium,
        sum(CASE WHEN coalesce(trim(t.current_analysis), '') <> '' THEN 1 ELSE 0 END) AS current,
        sum(CASE WHEN coalesce(trim(t.drivers), '') <> '' THEN 1 ELSE 0 END) AS drivers,
        sum(CASE WHEN coalesce(trim(t.executive_summary), '') <> '' THEN 1 ELSE 0 END) AS executive_summary,
        sum(CASE WHEN coalesce(trim(t.movers_scenarios), '') <> '' THEN 1 ELSE 0 END) AS movers_scenarios,
        sum(CASE WHEN coalesce(trim(t.swing_trade_or_outlook), '') <> '' THEN 1 ELSE 0 END) AS swing_trade
    """
    result = run_cypher(query)
    return result[0] if result else {}


def get_graph_state_snapshot() -> SnapshotModel:
    """
    Aggregate a live snapshot of core graph metrics.
    """
    from datetime import datetime, timezone
    
    # Basic counts
    topics = get_topic_count()
    articles = get_article_count()
    connections = get_relationship_count()
    about_links = get_about_links_count()
    mapped_to_links = get_mapped_to_count()
    inter_topic_links = get_inter_topic_links_count()
    unique_relationship_types = get_unique_relationship_types()
    orphans_topics = get_orphan_topic_count()
    orphans_articles = get_orphan_article_count()
    
    # Analysis coverage
    analysis_full = get_topics_with_full_analysis_count()
    
    # Get example topics with full analysis
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
    )
    analysis_examples = [r["name"] for r in rows if isinstance(r.get("name"), str)]
    
    # Article-topic distribution
    article_topic_dist = get_articles_by_topic_count()
    
    # Timeframe distribution
    articles_by_timeframe = get_articles_by_timeframe()
    
    # Perspective scores
    avg_perspective_scores = get_perspective_score_stats()
    
    # Analysis section coverage
    analysis_section_coverage = get_analysis_section_coverage()
    
    orphans = OrphansModel(topics=orphans_topics, articles=orphans_articles)
    
    return SnapshotModel(
        topics=topics,
        topics_with_full_analysis=analysis_full,
        topics_with_full_analysis_examples=analysis_examples,
        articles=articles,
        connections=connections,
        about_links=about_links,
        mapped_to_links=mapped_to_links,
        inter_topic_links=inter_topic_links,
        unique_relationship_types=unique_relationship_types,
        orphans=orphans,
        articles_zero_topics=article_topic_dist.get('zero_topics', 0),
        articles_one_topic=article_topic_dist.get('one_topic', 0),
        articles_multiple_topics=article_topic_dist.get('multiple_topics', 0),
        avg_topics_per_article=article_topic_dist.get('avg_topics_per_article', 0.0),
        articles_by_timeframe=articles_by_timeframe,
        avg_perspective_scores=avg_perspective_scores,
        analysis_section_coverage=analysis_section_coverage,
        last_updated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ============================================================================
# PROBLEMS TRACKING
# ============================================================================


def _get_logfile() -> str:
    # Always ensure the directory exists before returning the logfile path
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f"master_{datetime.now().strftime('%Y-%m-%d')}.log")


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


class IngestionStats(BaseModel):
    """Article ingestion workflow counters."""
    queries: int = 0
    articles_processed: int = 0
    articles_added: int = 0
    articles_rejected_no_topics: int = 0
    duplicates_skipped: int = 0


class GraphStats(BaseModel):
    """Graph building workflow counters."""
    topics_created: int = 0
    topics_deleted: int = 0
    about_links_added: int = 0
    about_links_removed: int = 0
    relationships_added: int = 0
    relationships_removed: int = 0


class EnrichmentStats(BaseModel):
    """Topic enrichment workflow counters."""
    enrichment_succeeded: int = 0


class AnalysisStats(BaseModel):
    """Analysis generation workflow counters."""
    sections_written: int = 0
    sections_skipped_insufficient_articles: int = 0
    rewrite_attempts: int = 0
    rewrite_succeeded: int = 0
    rewrite_declined: int = 0  # LLM decided article not important enough to rewrite
    rewrite_trigger_from_ingestion: int = 0
    rewrite_trigger_from_enrichment: int = 0


class MaintenanceStats(BaseModel):
    """Maintenance and quality workflow counters."""
    articles_removed: int = 0
    topic_replacements: int = 0


class CustomAnalysisStats(BaseModel):
    """Custom user strategy analysis counters."""
    custom_strategies_rewritten: int = 0
    daily_rewrite_completed: bool = False


class SystemStats(BaseModel):
    """System health and performance counters."""
    errors: int = 0
    llm_calls_failed: int = 0
    llm_simple_calls: int = 0
    llm_medium_calls: int = 0
    llm_complex_calls: int = 0
    llm_simple_long_context_calls: int = 0
    llm_hallucinated_topic_ids: int = 0


class StatsModel(BaseModel):
    """Daily statistics organized by workflow."""
    ingestion: IngestionStats = IngestionStats()
    graph: GraphStats = GraphStats()
    enrichment: EnrichmentStats = EnrichmentStats()
    analysis: AnalysisStats = AnalysisStats()
    maintenance: MaintenanceStats = MaintenanceStats()
    custom_analysis: CustomAnalysisStats = CustomAnalysisStats()
    system: SystemStats = SystemStats()


class RewriteSkipModel(BaseModel):
    """Details about a skipped rewrite event."""
    timestamp: str = ""
    topic_id: str = ""
    section: str = ""


class ProblemsSectionModel(BaseModel):
    """Tracks problems encountered during pipeline execution. Counts only - details in logs."""
    zero_result_queries: int = 0
    topics_zero_results: List[str] = []  # Keep this - useful to see which topics have issues
    topic_rejections: int = 0
    no_replacement_candidates: int = 0
    missing_analysis_fields: int = 0
    capacity_guard_rejects: int = 0
    other_problems: int = 0


class StatsFileModel(BaseModel):
    today: StatsModel
    graph_state: SnapshotModel
    problems: ProblemsSectionModel = ProblemsSectionModel()


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
    """Load stats file with file locking to prevent race conditions."""
    statsfile = _get_statsfile_path()
    
    # Retry up to 5 times if file is locked
    max_retries = 5
    for attempt in range(max_retries):
        try:
            if os.path.exists(statsfile):
                with open(statsfile, "r") as f:
                    # Acquire shared lock (multiple readers allowed)
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        content = f.read()
                        if not content.strip():
                            # Empty file -> recreate defaults
                            raise json.JSONDecodeError("empty", content, 0)
                        data = json.loads(content)
                        # Validate/construct a Pydantic model from the dict
                        return StatsFileModel.model_validate(data)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:
                # File does not exist -> create and return defaults
                graph_state: SnapshotModel = get_graph_state_snapshot()
                stats = StatsModel()
                problems = ProblemsSectionModel()
                stats_file = StatsFileModel(today=stats, graph_state=graph_state, problems=problems)
                save_stats_file(stats_file)
                return stats_file
        except (json.JSONDecodeError, BlockingIOError) as e:
            if attempt < max_retries - 1:
                # Wait before retry (exponential backoff)
                time.sleep(0.1 * (2 ** attempt))
                continue
            else:
                # Last attempt failed -> recreate defaults
                graph_state: SnapshotModel = get_graph_state_snapshot()
                stats = StatsModel()
                problems = ProblemsSectionModel()
                stats_file = StatsFileModel(today=stats, graph_state=graph_state, problems=problems)
                save_stats_file(stats_file)
                return stats_file
    
    # Should never reach here, but return defaults as fallback
    graph_state: SnapshotModel = get_graph_state_snapshot()
    stats = StatsModel()
    problems = ProblemsSectionModel()
    return StatsFileModel(today=stats, graph_state=graph_state, problems=problems)


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
    """Save stats file with exclusive file locking to prevent race conditions."""
    statsfile = _get_statsfile_path()
    
    # Retry up to 5 times if file is locked
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Serialize Pydantic model to a plain dict before JSON dumping
            payload = stats.model_dump()
            
            # Open in r+ mode to allow locking before truncating
            mode = "r+" if os.path.exists(statsfile) else "w"
            with open(statsfile, mode) as f:
                # Acquire exclusive lock (no other readers or writers)
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    f.truncate()
                    json.dump(payload, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return  # Success!
        except BlockingIOError:
            if attempt < max_retries - 1:
                # Wait before retry (exponential backoff)
                time.sleep(0.1 * (2 ** attempt))
                continue
            else:
                # Last attempt failed -> log error but don't crash
                print(f"ERROR: Failed to save stats file after {max_retries} attempts")
                return


def master_statistics(
    # Ingestion workflow
    queries: int = 0,
    articles_processed: int = 0,
    articles_added: int = 0,
    articles_rejected_no_topics: int = 0,
    duplicates_skipped: int = 0,
    
    # Graph workflow
    topics_created: int = 0,
    topics_deleted: int = 0,
    about_links_added: int = 0,
    about_links_removed: int = 0,
    relationships_added: int = 0,
    relationships_removed: int = 0,
    
    # Enrichment workflow
    enrichment_succeeded: int = 0,
    
    # Analysis workflow
    analysis_sections_written: int = 0,
    analysis_sections_skipped_insufficient_articles: int = 0,
    should_rewrite_attempted: int = 0,
    should_rewrite_true: int = 0,
    should_rewrite_false: int = 0,
    should_rewrite_trigger_from_article_ingestion: int = 0,
    should_rewrite_trigger_from_enrichment_completion: int = 0,
    
    # Maintenance workflow
    articles_removed: int = 0,
    topic_replacements_decided: int = 0,
    
    # Custom analysis workflow
    custom_strategies_rewritten: int = 0,
    daily_rewrite_completed: bool = False,
    
    # System metrics
    errors: int = 0,
    llm_calls_failed: int = 0,
    llm_simple_calls: int = 0,
    llm_medium_calls: int = 0,
    llm_complex_calls: int = 0,
    llm_simple_long_context_calls: int = 0,
    llm_hallucinated_topic_ids: int = 0,
) -> None:
    # Load existing stats
    stats = load_stats_file()
    t = stats.today

    # Ingestion workflow
    if queries:
        t.ingestion.queries += queries
    if articles_processed:
        t.ingestion.articles_processed += articles_processed
    if articles_added:
        t.ingestion.articles_added += articles_added
    if articles_rejected_no_topics:
        t.ingestion.articles_rejected_no_topics += articles_rejected_no_topics
    if duplicates_skipped:
        t.ingestion.duplicates_skipped += duplicates_skipped
    
    # Graph workflow
    if topics_created:
        t.graph.topics_created += topics_created
    if topics_deleted:
        t.graph.topics_deleted += topics_deleted
    if about_links_added:
        t.graph.about_links_added += about_links_added
    if about_links_removed:
        t.graph.about_links_removed += about_links_removed
    if relationships_added:
        t.graph.relationships_added += relationships_added
    if relationships_removed:
        t.graph.relationships_removed += relationships_removed
    
    # Enrichment workflow
    if enrichment_succeeded:
        t.enrichment.enrichment_succeeded += enrichment_succeeded
    
    # Analysis workflow
    if analysis_sections_written:
        t.analysis.sections_written += analysis_sections_written
    if analysis_sections_skipped_insufficient_articles:
        t.analysis.sections_skipped_insufficient_articles += analysis_sections_skipped_insufficient_articles
    if should_rewrite_attempted:
        t.analysis.rewrite_attempts += should_rewrite_attempted
    if should_rewrite_true:
        t.analysis.rewrite_succeeded += should_rewrite_true
    if should_rewrite_false:
        t.analysis.rewrite_declined += should_rewrite_false
    if should_rewrite_trigger_from_article_ingestion:
        t.analysis.rewrite_trigger_from_ingestion += should_rewrite_trigger_from_article_ingestion
    if should_rewrite_trigger_from_enrichment_completion:
        t.analysis.rewrite_trigger_from_enrichment += should_rewrite_trigger_from_enrichment_completion
    
    # Maintenance workflow
    if articles_removed:
        t.maintenance.articles_removed += articles_removed
    if topic_replacements_decided:
        t.maintenance.topic_replacements += topic_replacements_decided
    
    # Custom analysis workflow
    if custom_strategies_rewritten:
        t.custom_analysis.custom_strategies_rewritten += custom_strategies_rewritten
    if daily_rewrite_completed:  # Only set to True when explicitly passed
        t.custom_analysis.daily_rewrite_completed = True
    
    # System metrics
    if errors:
        t.system.errors += errors
    if llm_calls_failed:
        t.system.llm_calls_failed += llm_calls_failed
    if llm_simple_calls:
        t.system.llm_simple_calls += llm_simple_calls
    if llm_medium_calls:
        t.system.llm_medium_calls += llm_medium_calls
    if llm_complex_calls:
        t.system.llm_complex_calls += llm_complex_calls
    if llm_simple_long_context_calls:
        t.system.llm_simple_long_context_calls += llm_simple_long_context_calls
    if llm_hallucinated_topic_ids:
        t.system.llm_hallucinated_topic_ids += llm_hallucinated_topic_ids

    stats.graph_state = get_graph_state_snapshot()

    save_stats_file(stats)


def master_log(
    message: str,
    # Ingestion workflow
    queries: int = 0,
    articles_processed: int = 0,
    articles_added: int = 0,
    articles_rejected_no_topics: int = 0,
    duplicates_skipped: int = 0,
    
    # Graph workflow
    topics_created: int = 0,
    topics_deleted: int = 0,
    about_links_added: int = 0,
    about_links_removed: int = 0,
    relationships_added: int = 0,
    relationships_removed: int = 0,
    
    # Enrichment workflow
    enrichment_succeeded: int = 0,
    
    # Analysis workflow
    analysis_sections_written: int = 0,
    analysis_sections_skipped_insufficient_articles: int = 0,
    should_rewrite_attempted: int = 0,
    should_rewrite_true: int = 0,
    should_rewrite_false: int = 0,
    should_rewrite_trigger_from_article_ingestion: int = 0,
    should_rewrite_trigger_from_enrichment_completion: int = 0,
    
    # Maintenance workflow
    articles_removed: int = 0,
    topic_replacements_decided: int = 0,
    
    # System metrics
    errors: int = 0,
    llm_calls_failed: int = 0,
    llm_simple_calls: int = 0,
    llm_medium_calls: int = 0,
    llm_complex_calls: int = 0,
    llm_simple_long_context_calls: int = 0,
    llm_hallucinated_topic_ids: int = 0,
) -> None:
    """Log a completed action (success, removal, etc) to the master daily log and increment stats."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(_get_logfile(), "a") as f:
        f.write(f"{timestamp} | {message}\n")
    master_statistics(
        queries=queries,
        articles_processed=articles_processed,
        articles_added=articles_added,
        articles_rejected_no_topics=articles_rejected_no_topics,
        duplicates_skipped=duplicates_skipped,
        topics_created=topics_created,
        topics_deleted=topics_deleted,
        about_links_added=about_links_added,
        about_links_removed=about_links_removed,
        relationships_added=relationships_added,
        relationships_removed=relationships_removed,
        enrichment_succeeded=enrichment_succeeded,
        analysis_sections_written=analysis_sections_written,
        analysis_sections_skipped_insufficient_articles=analysis_sections_skipped_insufficient_articles,
        should_rewrite_attempted=should_rewrite_attempted,
        should_rewrite_true=should_rewrite_true,
        should_rewrite_false=should_rewrite_false,
        should_rewrite_trigger_from_article_ingestion=should_rewrite_trigger_from_article_ingestion,
        should_rewrite_trigger_from_enrichment_completion=should_rewrite_trigger_from_enrichment_completion,
        articles_removed=articles_removed,
        topic_replacements_decided=topic_replacements_decided,
        errors=errors,
        llm_calls_failed=llm_calls_failed,
        llm_simple_calls=llm_simple_calls,
        llm_medium_calls=llm_medium_calls,
        llm_complex_calls=llm_complex_calls,
        llm_simple_long_context_calls=llm_simple_long_context_calls,
        llm_hallucinated_topic_ids=llm_hallucinated_topic_ids,
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
    problem: Problem, topic: str = "", details: ProblemDetailsModel | None = None
) -> None:
    """
    Record a minimal problem into the daily master stats JSON under the
    top-level "problems" section. Uses compact string summaries instead of full objects.
    
    Format: "topic_id | key_info | reason"
    Example: "eurusd | current | no replacement candidates"
    """

    # Ensures the stats file exists
    load_stats_file()
    
    # Load stats and update problems section
    stats = load_stats_file()
    
    if problem == Problem.ZERO_RESULTS:
        stats.problems.zero_result_queries += 1
        if topic and topic not in stats.problems.topics_zero_results:
            stats.problems.topics_zero_results.append(topic)
    
    elif problem == Problem.TOPIC_REJECTED:
        stats.problems.topic_rejections += 1
        # Details logged to master_logs, not stats
    
    elif problem == Problem.REWRITE_SKIPPED_0_ARTICLES:
        master_statistics(analysis_sections_skipped_insufficient_articles=1)
        if details:
            stats.today.rewrite_skip_event.append(
                RewriteSkipModel(
                    topic_id=details.topic_id if hasattr(details, 'topic_id') else topic,
                    section=details.section
                )
            )
    
    elif problem == Problem.NO_REPLACEMENT_CANDIDATES:
        stats.problems.no_replacement_candidates += 1
        # Details logged to master_logs, not stats
    
    elif problem == Problem.MISSING_REQ_FIELDS_FOR_ANALYSIS_MATERIAL:
        stats.problems.missing_analysis_fields += 1
        # Details logged to master_logs, not stats
    
    elif problem == Problem.CAPACITY_GUARD_REJECT:
        stats.problems.capacity_guard_rejects += 1
        # Details logged to master_logs, not stats
    
    else:
        # Catch-all for other problems
        stats.problems.other_problems += 1
        # Details logged to master_logs, not stats
    
    # Save updated stats
    save_stats_file(stats)
