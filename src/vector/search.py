"""Vector search. Local Qdrant + Perigon in parallel."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from .embedder import embed
from .client import search as qdrant_search
from src.clients.perigon.news_api_client import NewsApiClient
from src.llm.prompts.query_to_statement import convert_query_to_statement
from utils.app_logging import get_logger

logger = get_logger(__name__)


def search_articles(
    query: str,
    limit: int = 10,
    include_perigon: bool = True
) -> List[Dict]:
    """Search Qdrant + Perigon in parallel, dedupe, return best results."""
    statement = convert_query_to_statement(query)
    vector = embed(statement)

    def search_local():
        try:
            results = qdrant_search(vector=vector, limit=limit)
            logger.info(f"Qdrant: {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

    def search_perigon():
        try:
            client = NewsApiClient()
            response = client.vector_search(statement, max_results=limit)
            articles = response.get("articles", [])
            for a in articles:
                a["source_type"] = "perigon"
            logger.info(f"Perigon: {len(articles)} results")
            return articles
        except Exception as e:
            logger.error(f"Perigon search failed: {e}")
            return []

    # Run searches in parallel
    results_by_source = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(search_local): "local"}
        if include_perigon:
            futures[executor.submit(search_perigon)] = "perigon"

        for future in as_completed(futures):
            source = futures[future]
            results_by_source[source] = future.result()

    # Combine: local first (preferred), then perigon
    local_results = results_by_source.get("local", [])
    perigon_results = results_by_source.get("perigon", [])
    combined = local_results + perigon_results

    # Dedupe by URL (or title if no URL), keeping first occurrence (local preferred)
    seen = set()
    unique = []
    for r in combined:
        # Use URL for dedup, fall back to title if no URL
        key = r.get("url") or r.get("title") or id(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Sort by score (highest first)
    unique.sort(key=lambda x: x.get("score", 0), reverse=True)

    return unique[:limit]


if __name__ == "__main__":
    from utils.env_loader import load_env
    load_env()

    print("Testing search...")
    results = search_articles("Federal Reserve interest rate policy")
    print(f"\nFound {len(results)}:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.get('source_type')}] {r.get('title', '')[:50]}")
