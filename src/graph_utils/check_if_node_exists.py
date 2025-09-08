from graph_db.db_driver import connect_graph_db
from utils import logging

logger = logging.get_logger(__name__)

def check_if_node_exists(node_id: str) -> bool:
    """
    Check if a node with the given ID exists in the database.
    
    Args:
        node_id: String ID of the node to check
        
    Returns:
        bool: True if node exists, False otherwise
    """
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        cypher = "MATCH (n:Topic {id: $id}) RETURN n LIMIT 1"
        result = session.run(cypher, {"id": node_id})
        exists = result.single() is not None
        
        if exists:
            logger.debug(f"Node with ID '{node_id}' already exists in the database.")
        else:
            logger.debug(f"Node with ID '{node_id}' does not exist in the database.")
            
        return exists


def get_node_if_exists(node_id: str) -> dict:
    """
    Get a node with the given ID if it exists in the database.
    
    Args:
        node_id: String ID of the node to retrieve
        
    Returns:
        dict: Node data if found, None otherwise
    """
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        cypher = "MATCH (n:Topic {id: $id}) RETURN n LIMIT 1"
        result = session.run(cypher, {"id": node_id})
        record = result.single()
        
        if record:
            node = dict(record["n"])
            logger.debug(f"Retrieved node with ID '{node_id}'")
            return node
        else:
            logger.debug(f"Failed to retrieve node with ID '{node_id}': Not found")
            return None
