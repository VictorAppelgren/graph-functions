# graph_utils/graph_stats.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Any, Optional, Dict, cast
from pydantic import BaseModel, Field
from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic import get_all_topics
import os
import json


class OrphansModel(BaseModel):
    topics: int = 0
    articles: int = 0


class SnapshotModel(BaseModel):
    topics: int = 0
    topics_with_full_analysis: int = 0
    topics_with_full_analysis_examples: List[str] = Field(default_factory=list)
    articles: int = 0
    connections: int = 0  # adjust type if you have richer connection objects
    about_links: int = 0
    inter_topic_links: int = 0
    unique_relationship_types: List[str] = Field(default_factory=list)
    orphans: OrphansModel = Field(default_factory=OrphansModel)
    last_updated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class ProblemsSectionModel(BaseModel):
    """Represents the 'problems' section of the stats dict."""

    zero_result_queries: int = 0
    topics_zero_results: List[str] = Field(default_factory=list)
    topic_rejections: int = 0
    no_replacement_candidates: int = 0
    no_replacement_events: List[Dict[str, Any]] = Field(default_factory=list)
    missing_analysis_fields: int = 0
    missing_analysis_events: List[Dict[str, Any]] = Field(default_factory=list)


class TodayStatsModel(BaseModel):
    queries: int = 0
    articles: int = 0
    articles_added: int = 0
    articles_removed: int = 0
    added_topic: int = 0
    removes_topic: int = 0
    about_links_added: int = 0
    about_links_removed: int = 0
    relationships_added: int = 0
    relationships_removed: int = 0
    rewrites_saved: int = 0
    rewrites_skipped_0_articles: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    qa_reports_generated: int = 0
    should_rewrite_true: int = 0
    should_rewrite_false: int = 0
    topic_replacements_decided: int = 0
    enrichment_attempts: int = 0
    enrichment_articles_added: int = 0
    llm_simple_calls: int = 0
    llm_medium_calls: int = 0
    llm_complex_calls: int = 0
    llm_simple_long_context_calls: int = 0
    topics_total_today: int = 0
    full_analysis_new_today: int = 0
    rewrite_skip_event: List[RewriteSkipModel] = []


class RewriteSkipModel(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    topic_id: str = ""
    section: str = ""


class TodayStatsFileModel(BaseModel):
    today: TodayStatsModel = Field(default_factory=TodayStatsModel)
    graph_state: SnapshotModel = Field(default_factory=SnapshotModel)
    problems: ProblemsSectionModel = Field(default_factory=ProblemsSectionModel)


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
    # Unified counting: rely on get_all_topics to fetch all Topic topics and take len
    try:
        topics = get_all_topics(fields=["id"])  # id-only for minimal payload
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
    rows = (
        run_cypher("MATCH ()-[r]->() RETURN collect(DISTINCT type(r)) AS types") or []
    )
    types = rows[0].get("types", []) if rows else []
    # Ensure strings, sorted for stability
    types = [str(t) for t in types]
    types.sort()
    return types


def get_orphan_topic_count() -> int:
    # topics with no relationships
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


def get_graph_state_snapshot() -> SnapshotModel:
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
    )

    analysis_examples: list[str] = [
        r["name"] for r in rows if isinstance(r.get("name"), str)
    ]

    orphans = OrphansModel(topics=orphans_topics, articles=orphans_articles)

    return SnapshotModel(
        topics=topics,
        topics_with_full_analysis=analysis_full,
        topics_with_full_analysis_examples=analysis_examples,
        articles=articles,
        connections=connections,
        about_links=about_links,
        inter_topic_links=inter_topic_links,
        unique_relationship_types=unique_relationship_types,
        orphans=orphans,
        last_updated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _load_daily_stats() -> TodayStatsFileModel:

    path = os.path.join(
        "master_stats",
        f"statistics_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}.json",
    )

    with open(path, "r", encoding="utf-8") as f:
        return cast(TodayStatsFileModel, json.load(f))


def _save_daily_stats(data: TodayStatsFileModel) -> None:

    path = os.path.join(
        "master_stats",
        f"statistics_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}.json",
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_stats(
    *,
    # increments (pass only what you need; zeros ignored)
    queries: int = 0,
    articles: int = 0,
    articles_added: int = 0,
    articles_removed: int = 0,
    added_topic: int = 0,
    removes_topic: int = 0,
    about_links_added: int = 0,
    about_links_removed: int = 0,
    relationships_added: int = 0,
    relationships_removed: int = 0,
    rewrites_saved: int = 0,
    rewrites_skipped_0_articles: int = 0,
    duplicates_skipped: int = 0,
    errors: int = 0,
    qa_reports_generated: int = 0,
    should_rewrite_true: int = 0,
    should_rewrite_false: int = 0,
    topic_replacements_decided: int = 0,
    enrichment_attempts: int = 0,
    enrichment_articles_added: int = 0,
    no_replacement_candidates: int = 0,
    # llm usage (choose one or none per call)
    llm_simple_calls: int = 0,
    llm_medium_calls: int = 0,
    llm_complex_calls: int = 0,
    llm_simple_long_context_calls: int = 0,
    # optional problems events to append
    zero_result_topic_ids: List[str] = [],
    topic_rejections: int = 0,
    no_replacement_event: Optional[Dict[str, Any]] = None,
    missing_analysis_event: Optional[Dict[str, Any]] = None,
    rewrite_skip_event: Optional[Dict[str, Any]] = None,
    # controls
    refresh_snapshot: bool = True,
) -> None:
    """
    Load the current daily stats, apply increments and optional problem events,
    recompute derived fields, optionally refresh the snapshot, and save atomically.
    """
    stats = _load_daily_stats()
    t = stats.today

    # ---- increments (attribute-style, ignore zeros) ----
    if queries:
        t.queries += queries
    if articles:
        t.articles += articles
    if articles_added:
        t.articles_added += articles_added
    if articles_removed:
        t.articles_removed += articles_removed
    if added_topic:
        t.added_topic += added_topic
    if removes_topic:
        t.removes_topic += removes_topic
    if about_links_added:
        t.about_links_added += about_links_added
    if about_links_removed:
        t.about_links_removed += about_links_removed
    if relationships_added:
        t.relationships_added += relationships_added
    if relationships_removed:
        t.relationships_removed += relationships_removed
    if rewrites_saved:
        t.rewrites_saved += rewrites_saved
    if rewrites_skipped_0_articles:
        t.rewrites_skipped_0_articles += rewrites_skipped_0_articles
    if duplicates_skipped:
        t.duplicates_skipped += duplicates_skipped
    if errors:
        t.errors += errors
    if qa_reports_generated:
        t.qa_reports_generated += qa_reports_generated
    if should_rewrite_true:
        t.should_rewrite_true += should_rewrite_true
    if should_rewrite_false:
        t.should_rewrite_false += should_rewrite_false
    if topic_replacements_decided:
        t.topic_replacements_decided += topic_replacements_decided
    if enrichment_attempts:
        t.enrichment_attempts += enrichment_attempts
    if enrichment_articles_added:
        t.enrichment_articles_added += enrichment_articles_added
    if llm_simple_calls:
        t.llm_simple_calls += llm_simple_calls
    if llm_medium_calls:
        t.llm_medium_calls += llm_medium_calls
    if llm_complex_calls:
        t.llm_complex_calls += llm_complex_calls
    if llm_simple_long_context_calls:
        t.llm_simple_long_context_calls += llm_simple_long_context_calls

    # ---- problems section (optional) ----
    if zero_result_topic_ids:
        stats.problems.zero_result_queries += len(zero_result_topic_ids)
        for tid in zero_result_topic_ids:
            if tid not in stats.problems.topics_zero_results:
                stats.problems.topics_zero_results.append(tid)
    if topic_rejections:
        stats.problems.topic_rejections += topic_rejections
    if no_replacement_event:
        stats.problems.no_replacement_candidates += 1
        stats.problems.no_replacement_events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **no_replacement_event,
            }
        )
    if missing_analysis_event:
        stats.problems.missing_analysis_fields += 1
        stats.problems.missing_analysis_events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **missing_analysis_event,
            }
        )
    if rewrite_skip_event:
        stats.today.rewrite_skip_event.append(
            RewriteSkipModel(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **rewrite_skip_event,
            )
        )

    # ---- snapshot refresh + derived fields ----
    if refresh_snapshot:
        try:
            stats.graph_state = get_graph_state_snapshot()
        except Exception as e:
            # keep previous snapshot but stamp an error marker
            stats.graph_state.last_updated = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )

            stats.problems.missing_analysis_events.append(
                {"snapshot_error": str(e)[:200]}
            )

    _save_daily_stats(stats)
