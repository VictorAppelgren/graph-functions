"""
Backfill: Link orphan Article nodes to Topics by reusing the normal add_article() pipeline.

Minimal behavior:
- Find Article nodes with no relationships (orphans)
- For each, call add_article(article_id) to (re)discover topics and create ABOUT links
- Log progress; fail-fast on unexpected issues per module behavior

This script does not delete or mutate Topics; it only attempts to attach orphans
using existing ingestion logic.
"""

import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    

from utils.logging import get_logger
from graph_db.db_driver import run_cypher
from graph_articles.add_article import add_article
from utils.pipeline_logging import master_log, master_log_error

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
    return [r.get("id") for r in rows if r.get("id")]


def link_orphan_articles(limit: int = 1000) -> dict:
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
                # add_article already emits master_log events for links created
            else:
                failures += 1
                master_log_error(f"Backfill link_orphan_articles: add_article returned status={status} for {aid}")
        except Exception as e:
            failures += 1
            master_log_error(f"Backfill link_orphan_articles failed for {aid}", error=e)

    master_log(
        f"Backfill orphan links completed | processed={processed} | failures={failures}",
        queries=0,
        articles=0,
        about_links_added=0,  # individual edges are logged within add_article
    )
    return {"processed": processed, "failures": failures, "total": len(ids)}


if __name__ == "__main__":
    # Minimal runner: no CLI args, fixed default limit
    summary = link_orphan_articles(limit=1000)
    print(summary)
