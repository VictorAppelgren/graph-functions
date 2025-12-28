"""Index Tier 2+ articles into Qdrant."""
import gc
from datetime import datetime
from .embedder import embed, embed_batch
from .client import upsert, count
from src.graph.neo4j_client import run_cypher
from utils.app_logging import get_logger

logger = get_logger(__name__)


def index_article(article_id: str) -> bool:
    """Index article if any importance score >= 2."""
    query = """
    MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic)
    WHERE r.importance_risk >= 2
       OR r.importance_opportunity >= 2
       OR r.importance_trend >= 2
       OR r.importance_catalyst >= 2
    RETURN a.id AS id, a.title AS title, a.summary AS summary,
           a.content AS content, a.url AS url, a.source AS source,
           a.published_date AS pub_date, collect(DISTINCT t.id) AS topics
    LIMIT 1
    """
    result = run_cypher(query, {"article_id": article_id})
    if not result:
        return False

    article = result[0]
    content = article.get("content") or article.get("summary") or ""
    if not content:
        return False

    embed_text = f"{article.get('title', '')}. {article.get('summary', '')}. {content[:1000]}"
    vector = embed(embed_text)

    payload = {
        "title": article.get("title"),
        "summary": article.get("summary"),
        "content": content[:2000],
        "url": article.get("url"),
        "source": article.get("source"),
        "pub_date": str(article.get("pub_date", "")),
        "topics": article.get("topics", []),
        "indexed_at": datetime.utcnow().isoformat()
    }

    upsert(article_id, vector, payload)
    logger.info(f"Indexed {article_id}")
    return True


def reindex_all(batch_size: int = 10) -> dict:
    """Reindex ALL articles with any importance >= 2. Run once after setup.

    Uses small batches and gc to stay within 2GB memory limit.
    """
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic)
    WHERE r.importance_risk >= 2
       OR r.importance_opportunity >= 2
       OR r.importance_trend >= 2
       OR r.importance_catalyst >= 2
    WITH a, collect(DISTINCT t.id) AS topics
    RETURN a.id AS id, a.title AS title, a.summary AS summary,
           a.content AS content, a.url AS url, a.source AS source,
           a.published_date AS pub_date, topics
    """
    articles = run_cypher(query, {})
    total = len(articles)
    stats = {"indexed": 0, "skipped": 0, "failed": 0}

    logger.info(f"Reindexing {total} articles in batches of {batch_size}")

    for i in range(0, total, batch_size):
        batch = articles[i:i+batch_size]
        texts, valid = [], []

        for article in batch:
            content = article.get("content") or article.get("summary") or ""
            if not content:
                stats["skipped"] += 1
                continue
            texts.append(f"{article.get('title', '')}. {article.get('summary', '')}. {content[:1000]}")
            valid.append(article)

        if not texts:
            continue

        try:
            vectors = embed_batch(texts)
            for article, vector in zip(valid, vectors):
                payload = {
                    "title": article.get("title"),
                    "summary": article.get("summary"),
                    "content": (article.get("content") or "")[:2000],
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "pub_date": str(article.get("pub_date", "")),
                    "topics": article.get("topics", []),
                    "indexed_at": datetime.utcnow().isoformat()
                }
                upsert(article["id"], vector, payload)
                stats["indexed"] += 1

            # Progress log every 100 articles
            if stats["indexed"] % 100 == 0:
                logger.info(f"Progress: {stats['indexed']}/{total} indexed")

            # Clear memory after each batch
            del vectors, texts, valid
            gc.collect()

        except Exception as e:
            logger.error(f"Batch failed: {e}")
            stats["failed"] += len(valid)

    logger.info(f"Reindex: {stats}")
    return stats


if __name__ == "__main__":
    from utils.env_loader import load_env
    load_env()

    print(f"Current: {count()}")
    print("Reindexing...")
    result = reindex_all()
    print(f"Done: {result}")
    print(f"Final: {count()}")
