from src.graph.neo4j_client import connect_graph_db
from utils import app_logging

logger = app_logging.get_logger(__name__)


def get_topic_id_by_name(name: str) -> str:
    """
    Resolve a Topic node's canonical id from its display name.

    Args:
        name (str): Topic.name (e.g., "EURUSD").

    Returns:
        str: Topic.id (e.g., "eurusd").

    Raises:
        RuntimeError: If no topic is found with the provided name.
    """
    if not name or not isinstance(name, str):
        raise ValueError("name is required and must be a non-empty string")

    logger.info(f"Resolving topic id by name: name='{name}'")
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = "MATCH (n:Topic {name: $name}) RETURN n.id AS id"
            logger.info(f"Running query: {query} | params={{'name': '{name}'}}")
            result = session.run(query, {"name": name})
            record = result.single()
            if not record or not record.get("id"):
                logger.error(f"No topic found with name '{name}'")
                raise RuntimeError(f"No topic found with name '{name}'")
            topic_id = record["id"]
            logger.info(f"Resolved topic name '{name}' -> id '{topic_id}'")
            return topic_id
    except Exception as e:
        logger.error(f"Failed to resolve topic id by name: {e}", exc_info=True)
        raise RuntimeError(f"Failed to resolve topic id by name: {e}")
