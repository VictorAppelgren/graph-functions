"""Vector search. Local Qdrant + Perigon fallback."""
from typing import List, Dict, Optional
from .embedder import embed
from .client import search as qdrant_search
from src.clients.perigon.news_api_client import NewsApiClient
from src.llm.prompts.query_to_statement import convert_query_to_statement
from utils.app_logging import get_logger

logger = get_logger(__name__)

FALLBACK_THRESHOLD = 3


def search_articles(
    query: str,
    limit: int = 10,
    include_perigon: bool = True
) -> List[Dict]:
    """Search local first, Perigon fallback if < 3 results."""
    results = []
    statement = convert_query_to_statement(query)

    # Local Qdrant
    try:
        vector = embed(statement)
        local = qdrant_search(vector=vector, limit=limit)
        results.extend(local)
        logger.info(f"Local: {len(local)} results")
    except Exception as e:
        logger.error(f"Local search failed: {e}")

    # Perigon fallback
    if include_perigon and len(results) < FALLBACK_THRESHOLD:
        try:
            perigon = NewsApiClient()
            perigon_results = perigon.vector_search(statement, max_results=limit)
            for a in perigon_results.get("articles", []):
                a["source_type"] = "perigon"
            results.extend(perigon_results.get("articles", []))
            logger.info(f"Perigon: {len(perigon_results.get('articles', []))} results")
        except Exception as e:
            logger.error(f"Perigon failed: {e}")

    # Dedupe by URL
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)

    return unique[:limit]


if __name__ == "__main__":
    from utils.env_loader import load_env
    load_env()

    print("Testing search...")
    results = search_articles("Federal Reserve interest rate policy")
    print(f"\nFound {len(results)}:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.get('source_type')}] {r.get('title', '')[:50]}")
