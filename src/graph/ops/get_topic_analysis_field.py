from src.graph.neo4j_client import run_cypher

def get_topic_analysis_field(topic_id: str, field: str) -> str:
    """
    Fetch the value of the specified analysis field for a topic node.
    Logs clearly if missing, but does NOT raise or crash.
    Returns the string value or an empty string if not found.
    """
    q = f"""
    MATCH (n:AssetTopic {{id:$id}})
    RETURN n.{field} AS analysis
    """
    rows = run_cypher(q, {"id": topic_id}) or []
    if not rows or not rows[0].get("analysis"):
        print(f"[get_topic_analysis_field] No value for field '{field}' on topic '{topic_id}'")
        return ""
    return rows[0]["analysis"]
