"""
Rewrite Policy - Determines when topic analysis should be rewritten.

Core Rules:
1. Only rewrite if there are NEW Tier 3 articles since last analysis
2. Never rewrite more than once per MIN_REWRITE_INTERVAL_HOURS
3. When rewriting, provide list of NEW article IDs to highlight

This prevents wasteful rewrites when no new information exists.
"""

from datetime import datetime
from typing import Tuple, List
from src.graph.neo4j_client import run_cypher
from src.observability.stats_client import track
from utils import app_logging

logger = app_logging.get_logger(__name__)

# Configuration - can be reduced later: 24h -> 12h -> 4h -> 1h
MIN_REWRITE_INTERVAL_HOURS = 24


def should_rewrite_topic(topic_id: str) -> Tuple[bool, str, List[str]]:
    """
    Determine if topic analysis should be rewritten.

    Logic:
    1. Get topic's last_analyzed timestamp from Neo4j
    2. Get NEW Tier 3 articles linked since last_analyzed
    3. If no new articles -> SKIP (no new information)
    4. If new articles exist BUT we rewrote < MIN_REWRITE_INTERVAL_HOURS ago -> SKIP (cooldown)
    5. If new articles exist AND cooldown passed -> REWRITE with highlighted article IDs

    Args:
        topic_id: The topic to check

    Returns:
        Tuple of:
        - should_rewrite: bool - True if we should run analysis
        - reason: str - Why we're rewriting or skipping (for logging/stats)
        - new_article_ids: List[str] - Article IDs that are NEW since last analysis
    """
    # Get topic's last_analyzed timestamp and new articles in one query
    # Note: ABOUT relationships use importance_* fields (1-3), not a single "tier" field
    # Tier 3 = any importance field equals 3
    query = """
    MATCH (t:Topic {id: $topic_id})
    OPTIONAL MATCH (t)<-[r:ABOUT]-(a:Article)
    WHERE (r.importance_risk = 3 OR r.importance_opportunity = 3
           OR r.importance_trend = 3 OR r.importance_catalyst = 3)
      AND (t.last_analyzed IS NULL OR r.created_at > t.last_analyzed)
    RETURN
        t.last_analyzed AS last_analyzed,
        collect(DISTINCT a.id) AS new_article_ids
    """
    result = run_cypher(query, {"topic_id": topic_id})

    if not result:
        logger.warning(f"Topic {topic_id} not found in graph")
        return False, "topic_not_found", []

    row = result[0]
    last_analyzed = row.get("last_analyzed")
    new_article_ids = [aid for aid in row.get("new_article_ids", []) if aid]  # Filter None values

    # RULE 1: No new articles -> SKIP
    if not new_article_ids:
        track("analysis.skipped.no_new_articles", f"{topic_id}")
        logger.info(f"SKIP {topic_id}: No new Tier 3 articles since last analysis")
        return False, "no_new_articles", []

    # RULE 2: Check cooldown (have we rewritten recently?)
    if last_analyzed:
        try:
            # Handle both string and datetime types from Neo4j
            if isinstance(last_analyzed, str):
                last_analyzed_dt = datetime.fromisoformat(last_analyzed.replace('Z', '+00:00'))
                last_analyzed_dt = last_analyzed_dt.replace(tzinfo=None)
            else:
                # Neo4j datetime object
                last_analyzed_dt = datetime(
                    last_analyzed.year, last_analyzed.month, last_analyzed.day,
                    last_analyzed.hour, last_analyzed.minute, last_analyzed.second
                )

            hours_since = (datetime.utcnow() - last_analyzed_dt).total_seconds() / 3600

            if hours_since < MIN_REWRITE_INTERVAL_HOURS:
                track("analysis.skipped.cooldown", f"{topic_id}: {len(new_article_ids)} new articles waiting")
                logger.info(
                    f"SKIP {topic_id}: Cooldown active "
                    f"({hours_since:.1f}h < {MIN_REWRITE_INTERVAL_HOURS}h) - "
                    f"{len(new_article_ids)} new articles waiting"
                )
                return False, "cooldown", new_article_ids
        except Exception as e:
            logger.warning(f"Could not parse last_analyzed for {topic_id}: {e}")
            # Continue to rewrite if we can't parse the timestamp

    # RULE 3: New articles exist AND cooldown passed -> REWRITE
    track("analysis.triggered.new_articles", f"{topic_id}: {len(new_article_ids)} new articles")
    logger.info(
        f"REWRITE {topic_id}: {len(new_article_ids)} new articles found, cooldown passed"
    )
    return True, "new_articles", new_article_ids


def get_articles_for_analysis(topic_id: str, new_article_ids: List[str]) -> dict:
    """
    Get all Tier 3 articles for topic, split into NEW vs EXISTING.

    This enables agents to focus on what's changed since last analysis.

    Args:
        topic_id: Topic ID
        new_article_ids: List of article IDs that are NEW since last analysis

    Returns:
        dict with:
        - new_articles: List of article dicts (these are NEW - agents focus here)
        - existing_articles: List of article dicts (already in previous analysis)
        - new_count: Number of new articles
        - total_count: Total articles
    """
    new_ids_set = set(new_article_ids)

    # Get all Tier 3 articles for this topic
    # Note: ABOUT relationships use importance_* fields (1-3), not a single "tier" field
    query = """
    MATCH (t:Topic {id: $topic_id})<-[r:ABOUT]-(a:Article)
    WHERE (r.importance_risk = 3 OR r.importance_opportunity = 3
           OR r.importance_trend = 3 OR r.importance_catalyst = 3)
    RETURN a.id AS id, a.title AS title, a.summary AS summary,
           a.url AS url, a.published_date AS published_date,
           r.created_at AS linked_at
    ORDER BY r.created_at DESC
    """
    articles = run_cypher(query, {"topic_id": topic_id})

    new_articles = []
    existing_articles = []

    for article in articles:
        if article["id"] in new_ids_set:
            new_articles.append(article)
        else:
            existing_articles.append(article)

    return {
        "new_articles": new_articles,
        "existing_articles": existing_articles,
        "new_count": len(new_articles),
        "total_count": len(articles),
    }
