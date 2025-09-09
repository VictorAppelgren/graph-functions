"""
Selects the best articles for a node and time frame for analysis rewriting.
"""
from typing import List, Dict

import sys, os
from typing import List, Dict
from graph.neo4j_client import run_cypher

from utils import app_logging
logger = app_logging.get_logger(__name__)

def select_best_articles(node_id: str, timeframe: str) -> List[Dict]:
    """
    For a given node and time frame, selects the top-N most important/relevant articles for inclusion in the analysis rewrite, using priority and relevance score.
    Reads top_n from the topic node in the graph, or uses a default if not present.
    Returns:
        list[dict]: List of article dicts.
    """
    if not node_id or not timeframe:
        raise ValueError("node_id and timeframe are required")
    logger.info(f"Selecting best articles for node_id={node_id} timeframe={timeframe}")
    # Get top_n from node
    topn_query = """
        MATCH (t:Topic {id: $node_id})
        RETURN coalesce(t.top_n, 5) AS top_n
    """
    top_n_result = run_cypher(topn_query, {"node_id": node_id})
    top_n = top_n_result[0]["top_n"] if top_n_result else 5
    logger.info(f"Selected top_n={top_n} articles for node_id={node_id} timeframe={timeframe}")
    articles = []
    for priority in ["3", "2", "1"]:
        if len(articles) >= top_n:
            break
        q = """
            MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $node_id})
            WHERE a.temporal_horizon = $timeframe
              AND coalesce(a.priority, '') <> 'hidden'
            RETURN a.id AS id, a.title AS title, a.summary AS summary, a.priority AS priority, a.relevance_score AS relevance_score, a.published_at AS published_at
            ORDER BY a.relevance_score DESC, a.published_at DESC
            LIMIT $limit
        """
        limit = top_n - len(articles)
        results = run_cypher(q, {"node_id": node_id, "timeframe": timeframe, "priority": priority, "limit": limit})
        articles.extend(results)
    logger.info(f"Selected {len(articles)} articles for node_id={node_id} timeframe={timeframe}")
    return articles[:top_n]
