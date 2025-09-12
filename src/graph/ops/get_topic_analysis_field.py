from typing import Any

from src.graph.neo4j_client import run_cypher
from src.graph.models import Neo4jRecord

def get_topic_analysis_field(topic_id: str, field: str) -> Any:
    """
    Fetch the value of the specified analysis field for a topic node.
    Logs clearly if missing, but does NOT raise or crash.
    Returns the string value or an empty string if not found.
    """
    q = f"""
    MATCH (n:AssetTopic {{id:$id}})
    RETURN n.{field} AS analysis
    """
    rows: list[Neo4jRecord] = run_cypher(q, {"id": topic_id}) or []
    return rows[0]["analysis"]


