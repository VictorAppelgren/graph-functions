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

# Config: Use URL for HTTPS proxy, or host:port for direct
QDRANT_URL = os.getenv("QDRANT_URL")  # e.g., "https://167.172.185.204/qdrant"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = "saga_articles"
VECTOR_SIZE = 1536

_client = None


def get_client() -> QdrantClient:
    """Get Qdrant client. Creates collection if needed."""
    global _client
    if _client is None:
        if QDRANT_URL:
            # HTTPS via NGINX proxy (local dev connecting to remote)
            _client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )
            logger.info(f"Qdrant: HTTPS proxy at {QDRANT_URL}")
        else:
            # Direct connection (inside Docker or local Qdrant)
            _client = QdrantClient(
                host=QDRANT_HOST,
                port=QDRANT_PORT,
                api_key=QDRANT_API_KEY
            )
            logger.info(f"Qdrant: Direct at {QDRANT_HOST}:{QDRANT_PORT}")
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
    days_back: int = 14,
    min_score: float = 0.5
) -> List[Dict]:
    """Search similar articles."""
    client = get_client()
    cutoff = datetime.utcnow() - timedelta(days=days_back)

    results = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        query_filter=Filter(must=[
            FieldCondition(key="indexed_at", range=Range(gte=cutoff.isoformat()))
        ]),
        limit=limit,
        with_payload=True,
        score_threshold=min_score
    )

    return [{**hit.payload, "score": hit.score, "source_type": "local"} for hit in results]


def count() -> int:
    """Count vectors."""
    client = get_client()
    return client.get_collection(COLLECTION).points_count
