"""
Topic Mapper - Graph Strategy

MISSION: Get all available topics and their relationships from the graph.
"""

from typing import Dict, List
from src.graph.ops.topic import get_all_topics
from src.graph.neo4j_client import run_cypher


def explore_graph() -> Dict:
    """
    Get all available topics and their correlations.
    
    Returns:
        {
            "topics": List[{"id": str, "name": str}],
            "correlations": Dict[str, List[str]]  # topic_id -> [correlated_topic_ids]
        }
    """
    
    # Get all topics using helper function
    topics_result = get_all_topics(fields=["id", "name"])
    
    if not topics_result:
        return {
            "topics": [],
            "correlations": {}
        }
    
    topics = [
        {"id": row["id"], "name": row["name"]}
        for row in topics_result
    ]
    
    # Get correlations for all topics
    correlations_query = """
    MATCH (t1:Topic)-[:CORRELATES_WITH]-(t2:Topic)
    RETURN t1.id as topic_id, collect(DISTINCT t2.id) as correlated_ids
    """
    
    correlations_result = run_cypher(correlations_query, {})
    
    correlations = {}
    if correlations_result:
        for row in correlations_result:
            correlations[row["topic_id"]] = row["correlated_ids"]
    
    return {
        "topics": topics,
        "correlations": correlations
    }
