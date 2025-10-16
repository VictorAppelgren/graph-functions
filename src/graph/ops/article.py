from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def get_article_temporal_horizon(article_id: str) -> str:
    """
    Fetch temporal_horizon from the Article in Neo4j.
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


def set_article_hidden(article_id: str) -> None:
    """
    Sets the status of an Article to 'hidden' in the graph DB.
    """
    if not article_id:
        raise ValueError("article_id is required")
    cypher = """
    MATCH (a:Article {id: $article_id})
    SET a.status = 'hidden'
    """
    run_cypher(cypher, {"article_id": article_id})
    logger.info(f"Set article {article_id} to hidden.")


def remove_article_from_graph(article_id: str) -> None:
    """
    Removes an Article and all its relationships from the graph DB.
    """
    if not article_id:
        raise ValueError("article_id is required")
    cypher = """
    MATCH (a:Article {id: $article_id}) DETACH DELETE a
    """
    run_cypher(cypher, {"article_id": article_id})
    logger.info(f"Removed article {article_id} from graph.")


def update_article_priority(article_id: str) -> None:
    """
    Updates the priority of an Article in the graph DB.
    """
    # Fetch current priority
    cypher_get = """
    MATCH (a:Article {id: $article_id}) RETURN a.priority AS priority
    """
    result = run_cypher(cypher_get, {"article_id": article_id})
    if not result or "priority" not in result[0]:
        logger.error(f"Article {article_id} not found or missing priority.")
        return
    current = str(result[0]["priority"])
    next_priority = {"3": "2", "2": "1", "1": "hidden", "hidden": "hidden"}.get(
        current, "hidden"
    )
    cypher_set = """
    MATCH (a:Article {id: $article_id}) SET a.priority = $priority
    """
    run_cypher(cypher_set, {"article_id": article_id, "priority": next_priority})
    logger.info(
        f"Lowered article {article_id} priority from {current} to {next_priority}."
    )
