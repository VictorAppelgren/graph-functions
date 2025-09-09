from src.graph.neo4j_client import connect_graph_db
from typing import Dict
from utils import app_logging

logger = app_logging.get_logger(__name__)

def get_node_by_id(node_id: str) -> Dict:
    """
    Fetch the full Topic node (all properties) from the Neo4j database by id.
    Returns:
        Dict: Node dict with all properties, or raises RuntimeError if not found.
    """
    logger.info(f" Called: Fetching full Topic node with id='{node_id}' from Neo4j...")
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            query = "MATCH (n:Topic {id: $id}) RETURN n"
            logger.info(f" Running query: {query} with id={node_id}")
            result = session.run(query, {"id": node_id})
            record = result.single()
            if not record:
                logger.warning(f" Node with id '{node_id}' not found.")
                raise RuntimeError(f"Node with id '{node_id}' not found.")
            node_props = dict(record["n"])
            preview = str(node_props)
            if len(preview) > 200:
                preview = preview[:200] + '...'
            logger.info(f" Fetched node: {preview}")
            return node_props
    except Exception as e:
        logger.error(f" Failed to fetch node from Neo4j: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch node from Neo4j: {e}")
