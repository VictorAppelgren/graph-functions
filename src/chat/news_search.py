"""
News Search for Chat

Searches local Qdrant first, Perigon fallback if needed.
Background thread adds Perigon articles to DB for pipeline processing.
"""

import threading
from typing import List, Dict, Any

from src.vector.search import search_articles
from src.api.backend_client import ingest_article
from utils.app_logging import get_logger

logger = get_logger(__name__)


def search_news(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search news for chat. Returns immediately, adds Perigon results to DB in background.

    Args:
        query: User's question or search query
        max_results: Number of results to return

    Returns:
        List of article dicts with title, summary, url, source, date, score
    """
    # Combined search: local Qdrant + Perigon fallback
    articles = search_articles(query, limit=max_results, include_perigon=True)

    logger.info(f"Chat search: '{query[:40]}...' -> {len(articles)} results")

    # Background add Perigon articles to DB (local already in DB)
    perigon_articles = [a for a in articles if a.get("source_type") == "perigon"]
    if perigon_articles:
        threading.Thread(
            target=_background_add_articles,
            args=(perigon_articles,),
            daemon=True
        ).start()

    return articles


def _background_add_articles(articles: List[Dict[str, Any]]) -> None:
    """Add articles to DB in background. Failures are logged but don't affect chat."""
    added = 0
    skipped = 0

    for article in articles:
        url = article.get("url")
        if not url:
            continue

        try:
            # Format for backend ingest
            article_data = {
                "url": url,
                "title": article.get("title", ""),
                "description": article.get("summary", ""),
                "pubDate": article.get("pubDate", ""),
                "source": {"domain": article.get("source", "")},
                "imageUrl": article.get("imageUrl", ""),
            }

            result = ingest_article(article_data)

            if result.get("status") == "created":
                added += 1
                logger.debug(f"Added article: {article.get('title', '')[:50]}")
            else:
                skipped += 1

        except Exception as e:
            logger.warning(f"Failed to add article {url[:50]}: {e}")
            continue

    logger.info(f"Background add complete: {added} new, {skipped} existing")


if __name__ == "__main__":
    # Test
    import sys
    import os
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    from utils.env_loader import load_env
    load_env()

    print("Testing chat news search...")
    results = search_news("What is happening with Federal Reserve interest rates?")

    print(f"\nFound {len(results)} articles:")
    for i, article in enumerate(results, 1):
        src = article.get('source_type', 'local')
        print(f"  {i}. [{src}] {article.get('title', 'N/A')[:60]}")

    # Wait a moment for background thread
    import time
    time.sleep(2)
    print("\nDone.")
