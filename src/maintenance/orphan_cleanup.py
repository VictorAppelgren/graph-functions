"""
Orphan Article Cleanup

Daily job to clean up orphan articles (articles with no topic connections).

Logic:
1. Find ALL orphan articles older than 7 days
2. Re-run topic matching ONE more time (maybe topic universe expanded)
3. If match found -> article is linked (success!)
4. If still no match -> DELETE the article node (not contributing to the graph)

This keeps the Neo4j graph lean and removes noise.

Usage:
    from src.maintenance.orphan_cleanup import run_orphan_cleanup
    stats = run_orphan_cleanup()  # Runs until all orphans processed
"""

from datetime import datetime, timedelta
from src.graph.neo4j_client import run_cypher
from src.articles.ingest_article import add_article
from src.observability.stats_client import track
from utils.app_logging import get_logger

logger = get_logger(__name__)

# Only process orphans older than this (give fresh articles time to be matched)
ORPHAN_AGE_DAYS = 7


def get_orphan_articles() -> list[dict]:
    """
    Get ALL orphan articles older than ORPHAN_AGE_DAYS.
    Returns list of {id, title, created_at} dicts.
    """
    cutoff = datetime.utcnow() - timedelta(days=ORPHAN_AGE_DAYS)

    query = """
    MATCH (a:Article)
    WHERE NOT (a)--()
      AND a.created_at < $cutoff
    RETURN a.id AS id, a.title AS title, a.created_at AS created_at
    ORDER BY a.created_at ASC
    """

    result = run_cypher(query, {"cutoff": cutoff.isoformat()})
    return result or []


def delete_article(article_id: str) -> bool:
    """Delete an article node from Neo4j."""
    query = """
    MATCH (a:Article {id: $article_id})
    DETACH DELETE a
    RETURN count(a) as deleted
    """
    result = run_cypher(query, {"article_id": article_id})
    return result and result[0].get("deleted", 0) > 0


def run_orphan_cleanup() -> dict:
    """
    Clean up ALL orphan articles.

    For each orphan:
    1. Try to re-match to topics via add_article()
    2. If still no match -> delete the article

    Returns stats dict with matched/deleted/failed counts.
    """
    orphans = get_orphan_articles()
    total = len(orphans)

    if total == 0:
        logger.info("No orphan articles to clean up")
        return {"matched": 0, "deleted": 0, "failed": 0, "total": 0}

    logger.info(f"Starting orphan cleanup: {total} orphans older than {ORPHAN_AGE_DAYS} days")
    track("orphan_cleanup_started", f"total={total}")

    stats = {"matched": 0, "deleted": 0, "failed": 0, "total": total}

    for i, orphan in enumerate(orphans, start=1):
        article_id = orphan.get("id")
        if not article_id:
            continue

        try:
            logger.info(f"[{i}/{total}] Processing orphan: {article_id}")

            # Try to re-match via normal ingestion
            result = add_article(article_id, test=False)
            status = result.get("status")

            if status == "success":
                # Article found a topic match!
                stats["matched"] += 1
                track("orphan_matched", article_id)
                logger.info(f"  -> Matched to topic(s)")
            else:
                # Still no match -> delete
                if delete_article(article_id):
                    stats["deleted"] += 1
                    track("orphan_deleted", article_id)
                    logger.info(f"  -> Deleted (no match found)")
                else:
                    stats["failed"] += 1
                    logger.warning(f"  -> Failed to delete")

        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  -> Error processing {article_id}: {e}")

    logger.info(
        f"Orphan cleanup complete: "
        f"matched={stats['matched']}, deleted={stats['deleted']}, "
        f"failed={stats['failed']}, total={stats['total']}"
    )
    track("orphan_cleanup_completed", f"matched={stats['matched']},deleted={stats['deleted']}")

    return stats


if __name__ == "__main__":
    # Allow running directly for testing
    import sys
    import os

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
        PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    from utils.env_loader import load_env
    load_env()

    stats = run_orphan_cleanup()
    print(stats)
