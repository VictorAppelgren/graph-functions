"""
Backfill: Link orphan Article nodes to Topics by reusing the normal add_article() pipeline.

Minimal behavior:
- Find Article nodes with no relationships (orphans)
- For each, call add_article(article_id) to (re)discover topics and create ABOUT links
- Log progress; fail-fast on unexpected issues per module behavior

This script does not delete or mutate Topics; it only attempts to attach orphans
using existing ingestion logic.
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env file FIRST
from utils.env_loader import load_env
load_env()

from utils.app_logging import get_logger
from src.graph.neo4j_client import run_cypher
from src.articles.ingest_article import add_article

logger = get_logger(__name__)

ORPHAN_QUERY = """
MATCH (a:Article)
WHERE NOT (a)--()
RETURN a.id AS id
ORDER BY a.published_at DESC
LIMIT $limit
"""


def fetch_orphan_article_ids(limit: int = 1000) -> list[str]:
    rows = run_cypher(ORPHAN_QUERY, {"limit": limit}) or []

    ids: list[str] = []
    for r in rows:
        id_ = r.get("id")
        if id_:
            ids.append(id_)
    return ids


def link_orphan_articles(limit: int = 1000) -> dict[str, int]:
    ids = fetch_orphan_article_ids(limit=limit)
    logger.info(f"Found {len(ids)} orphan Article nodes to process (limit={limit})")
    processed = 0
    failures = 0

    for i, aid in enumerate(ids, start=1):
        try:
            logger.info(f"[{i}/{len(ids)}] Linking orphan article {aid}")
            res = add_article(aid, test=False)
            status = res.get("status")
            if status == "success":
                processed += 1
            else:
                failures += 1
                logger.error(f"Backfill link_orphan_articles: add_article returned status={status} for {aid}")
        except Exception as e:
            failures += 1
            logger.error(f"Backfill link_orphan_articles failed for {aid}: {e}")

    logger.info(
        f"Backfill orphan links completed | processed={processed} | failures={failures}"
    )
    return {"processed": processed, "failures": failures, "total": len(ids)}


if __name__ == "__main__":
    # Minimal runner: no CLI args, fixed default limit
    summary = link_orphan_articles(limit=1000)
    print(summary)
