from graph.neo4j_client import run_cypher

def get_article_temporal_horizon(article_id: str) -> str:
    """
    Fetch temporal_horizon from the Article node in Neo4j.
    Fail-fast if missing or not set.
    """
    q = """
    MATCH (a:Article {id:$id})
    RETURN a.temporal_horizon AS tf
    """
    rows = run_cypher(q, {"id": article_id}) or []
    if not rows or rows[0].get("tf") in (None, "", "null"):
        raise ValueError(f"Article {article_id} has no temporal_horizon in graph")
    return rows[0]["tf"]