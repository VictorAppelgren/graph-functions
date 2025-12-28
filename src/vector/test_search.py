"""Simple test for Qdrant search - no filters."""
from utils.env_loader import load_env
load_env()

from .embedder import embed
from .client import get_client, COLLECTION, count

def test_search_no_filters(query: str, limit: int = 5):
    """Search without any filters to debug."""
    print(f"\n=== Testing: '{query}' ===")

    # Check count
    total = count()
    print(f"Total vectors in DB: {total}")

    # Embed query
    print("Embedding query...")
    vector = embed(query)
    print(f"Vector dims: {len(vector)}")

    # Search without filters
    print("Searching (no filters)...")
    client = get_client()
    results = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=limit,
        with_payload=True,
        # No filter, no score_threshold
    )

    print(f"Found {len(results)} results:")
    for i, hit in enumerate(results, 1):
        print(f"\n  {i}. Score: {hit.score:.3f}")
        print(f"     Title: {hit.payload.get('title', 'N/A')[:60]}")
        print(f"     Topics: {hit.payload.get('topics', [])}")
        print(f"     Indexed: {hit.payload.get('indexed_at', 'N/A')}")


if __name__ == "__main__":
    test_search_no_filters("Federal Reserve interest rate policy")
    test_search_no_filters("inflation and consumer prices")
    test_search_no_filters("stock market rally")
