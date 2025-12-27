"""
Test Perigon Vector Search

Tests the semantic/vector search capability of Perigon API.
Uses the query-to-statement converter for optimal search results.

Run with:
    cd graph-functions
    python -m src.clients.perigon.test_vector_search
"""

import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.env_loader import load_env
load_env()

from src.clients.perigon.news_api_client import NewsApiClient
from src.llm.prompts.query_to_statement import convert_query_to_statement


def test_vector_search():
    """Test Perigon vector search with query conversion."""
    print("=" * 70)
    print("PERIGON VECTOR SEARCH TEST (14-day window)")
    print("=" * 70)

    client = NewsApiClient()

    # Test queries - mix of questions and statements
    test_queries = [
        "What are the implications of Federal Reserve interest rate decisions?",
        "How is artificial intelligence disrupting traditional finance?",
        "risks of persistent inflation in developed economies",
        "EURUSD currency movements and forex analysis",
    ]

    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {query}")

        # Convert to statement for better search
        statement = convert_query_to_statement(query)
        if statement != query:
            print(f"SEARCH: {statement}")

        print("-" * 70)

        try:
            result = client.vector_search(statement, max_results=5)
            articles = result.get("articles", [])

            print(f"Found: {len(articles)} articles (past 14 days)\n")

            for i, article in enumerate(articles, 1):
                score = article.get("score", 0)
                title = (article.get("title") or "N/A")[:65]
                source = article.get("source", "")
                date = (article.get("pubDate") or "")[:10]

                print(f"  {i}. [{score:.2f}] {title}")
                print(f"     {source} | {date}")

        except Exception as e:
            print(f"ERROR: {e}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_vector_search()
