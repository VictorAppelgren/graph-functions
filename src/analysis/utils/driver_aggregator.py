from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def aggregate_driver_analyses(topic_id: str) -> list[dict[str, str]]:
    """
    Fetch analyses from all INFLUENCES, CORRELATES_WITH, and PEERS topic nodes.
    Returns a list of dicts: {name, relation, executive_summary}
    """
    if not topic_id:
        raise ValueError("topic_id is required")
    logger.info(f"Aggregating driver analyses for topic_id={topic_id}")
    drivers = []
    # INFLUENCES
    influences_query = """
        MATCH (d:Topic)-[r:INFLUENCES]->(t:Topic {id: $topic_id})
        RETURN d.id AS id, d.name AS name, d.executive_summary AS executive_summary
    """
    influences = run_cypher(influences_query, {"topic_id": topic_id})
    for d in influences:
        drivers.append(
            {
                "name": d["name"],
                "relation": "influences",
                "executive_summary": d.get("executive_summary", ""),
            }
        )
    # CORRELATES_WITH
    correlates_query = """
        MATCH (d:Topic)-[r:CORRELATES_WITH]-(t:Topic {id: $topic_id})
        RETURN d.id AS id, d.name AS name, d.executive_summary AS executive_summary
    """
    correlates = run_cypher(correlates_query, {"topic_id": topic_id})
    for d in correlates:
        drivers.append(
            {
                "name": d["name"],
                "relation": "correlates_with",
                "executive_summary": d.get("executive_summary", ""),
            }
        )
    # PEERS
    peers_query = """
        MATCH (d:Topic)-[r:PEERS]-(t:Topic {id: $topic_id})
        RETURN d.id AS id, d.name AS name, d.executive_summary AS executive_summary
    """
    peers = run_cypher(peers_query, {"topic_id": topic_id})
    for d in peers:
        drivers.append(
            {
                "name": d["name"],
                "relation": "peer",
                "executive_summary": d.get("executive_summary", ""),
            }
        )
    logger.info(f"Aggregated {len(drivers)} drivers for topic_id={topic_id}")
    return drivers
