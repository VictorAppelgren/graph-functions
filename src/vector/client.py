"""Qdrant client. Simple. Fail fast."""
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, Range
)
from utils.app_logging import get_logger

logger = get_logger(__name__)

COLLECTION = "saga_articles"
VECTOR_SIZE = 384  # BAAI/bge-small-en-v1.5 dimension

_client = None


def get_client() -> QdrantClient:
    """Get Qdrant client. Creates collection if needed."""
    global _client
    if _client is None:
        # Read env vars lazily (after load_env() is called)
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if qdrant_url:
            # Via NGINX proxy (local dev connecting to remote)
            # Explicit port required: 443 for HTTPS, 80 for HTTP
            # prefix without leading slash per qdrant-client docs
            is_https = qdrant_url.startswith("https://")
            port = 443 if is_https else 80

            _client = QdrantClient(
                url=qdrant_url,
                port=port,
                api_key=qdrant_api_key,
                prefix="qdrant"
            )
            logger.info(f"Qdrant: {'HTTPS' if is_https else 'HTTP'} proxy at {qdrant_url}:{port}/qdrant")
        else:
            # Direct connection (inside Docker or local Qdrant)
            # Use url= with http:// to avoid SSL issues with API key
            _client = QdrantClient(
                url=f"http://{qdrant_host}:{qdrant_port}",
                api_key=qdrant_api_key
            )
            logger.info(f"Qdrant: Direct at http://{qdrant_host}:{qdrant_port}")
        _ensure_collection()
    return _client


def _ensure_collection():
    """Create collection if not exists."""
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION not in collections:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )
        logger.info(f"Created collection: {COLLECTION}")


def upsert(article_id: str, vector: List[float], payload: Dict) -> bool:
    """Insert or update article."""
    client = get_client()
    point_id = abs(hash(article_id)) % (2**63)
    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=point_id, vector=vector, payload={**payload, "article_id": article_id})]
    )
    return True


def search(
    vector: List[float],
    limit: int = 10,
    min_score: float = 0.5
) -> List[Dict]:
    """Search similar articles. All indexed articles are Tier 2+ and recent."""
    client = get_client()

    results = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=limit,
        with_payload=True,
        score_threshold=min_score
    )

    return [{**hit.payload, "score": hit.score, "source_type": "local"} for hit in results]


def count() -> int:
    """Count vectors."""
    client = get_client()
    return client.get_collection(COLLECTION).points_count
