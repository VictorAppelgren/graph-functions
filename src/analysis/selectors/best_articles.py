"""
Selects the best articles for a node and time frame for analysis rewriting.
"""

from src.graph.neo4j_client import run_cypher

from utils import app_logging

logger = app_logging.get_logger(__name__)


def select_best_articles(topic_id: str, timeframe: str) -> list[dict[str, str]]:
    """
    For a given node and time frame, selects the top-N most important/relevant articles for inclusion in the analysis rewrite, using priority and relevance score.
    Reads top_n from the topic node in the graph, or uses a default if not present.
    Returns:
        list[dict]: List of article dicts.
    """
    if not topic_id or not timeframe:
        raise ValueError("node_id and timeframe are required")
    logger.info(
        f"Selecting best articles for topic_id={topic_id} timeframe={timeframe}"
    )

    topn_query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN coalesce(t.top_n, 5) AS top_n
    """
    top_n_result = run_cypher(topn_query, {"topic_id": topic_id})
    top_n = top_n_result[0]["top_n"] if top_n_result else 5
    logger.info(
        f"Selected top_n={top_n} articles for topic_id={topic_id} timeframe={timeframe}"
    )
    articles: list[dict[str, str]] = []
    for priority in ["3", "2", "1"]:
        if not top_n:
            break
        q = """
            MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
            WHERE r.timeframe = $timeframe
            WITH a, r,
                 CASE 
                   WHEN coalesce(r.importance_risk, 0) >= coalesce(r.importance_opportunity, 0) 
                        AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_trend, 0)
                        AND coalesce(r.importance_risk, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_risk, 0)
                   WHEN coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_trend, 0)
                        AND coalesce(r.importance_opportunity, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_opportunity, 0)
                   WHEN coalesce(r.importance_trend, 0) >= coalesce(r.importance_catalyst, 0)
                   THEN coalesce(r.importance_trend, 0)
                   ELSE coalesce(r.importance_catalyst, 0)
                 END as max_importance
            RETURN a.id AS id, a.title AS title, a.summary AS summary, a.published_at AS published_at,
                   r.importance_risk, r.importance_opportunity, r.importance_trend, r.importance_catalyst
            ORDER BY max_importance DESC, a.published_at DESC
            LIMIT $limit
        """
        limit = top_n - len(articles)
        results = run_cypher(
            q,
            {
                "topic_id": topic_id,
                "timeframe": timeframe,
                "priority": priority,
                "limit": limit,
            },
        )
        articles.extend(results)
    logger.info(
        f"Selected {len(articles)} articles for topic_id={topic_id} timeframe={timeframe}"
    )
    return articles[:top_n]
