"""
Utility to create a Topic node in the graph DB with required properties. Returns the created node as a dict.
"""
from graph_db.db_driver import connect_graph_db
from utils import logging
from graph_utils.check_if_node_exists import check_if_node_exists

logger = logging.get_logger(__name__)

def create_topic_node(topic_dict: dict) -> dict:
    """
    Create a Topic node in the Neo4j graph with the provided properties.
    If a node with the same ID already exists, it will NOT be overwritten.
    
    Args:
        topic_dict: Dictionary containing all required node properties including 'id'
        
    Returns:
        dict: Created or existing node data
    """
    node_id = topic_dict.get('id')
    if not node_id:
        logger.error("Cannot create topic node: missing 'id' in topic_dict.")
        raise ValueError("Missing required 'id' field in topic_dict")
    
    # Check if node already exists
    if check_if_node_exists(node_id):
        logger.info(f"Node with ID '{node_id}' already exists, skipping creation.")
        
        # Fetch existing node and return it
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            cypher = "MATCH (n:Topic {id: $id}) RETURN n, elementId(n) AS eid"
            result = session.run(cypher, {"id": node_id})
            record = result.single()
            if record:
                node_dict = dict(record["n"])
                node_dict["element_id"] = record["eid"]
                return node_dict
            else:
                # This shouldn't happen if check_if_node_exists returned True
                logger.error(f"Node existence check inconsistency for ID '{node_id}'")
                raise RuntimeError(f"Node existence check inconsistency for ID '{node_id}'")
    
    # Create the node
    driver = connect_graph_db()
    with driver.session(database="argosgraph") as session:
        # Fail-fast: validate importance if present
        if "importance" in topic_dict:
            imp = topic_dict.get("importance")
            if isinstance(imp, str) and imp.isdigit():
                imp_val = int(imp)
                topic_dict["importance"] = imp_val
            else:
                imp_val = imp
            if not isinstance(imp_val, int) or imp_val not in {1, 2, 3, 4, 5}:
                raise ValueError(f"Invalid importance value: {imp} (must be integer 1..5)")

        # Convert all properties into a params dict for Cypher
        params = {"props": topic_dict}
        
        # Create node with all properties from topic_dict
        cypher = "CREATE (n:Topic $props) RETURN n, elementId(n) AS eid"
        result = session.run(cypher, params)
        record = result.single()
        
        if record:
            node_dict = dict(record["n"])
            node_dict["element_id"] = record["eid"]
            logger.info(f"Created new Topic node: {topic_dict.get('name')} (id={node_id}, element_id={node_dict['element_id']})")
            return node_dict
        else:
            logger.error(f"Failed to create Topic node with ID '{node_id}'")
            raise RuntimeError(f"Failed to create Topic node with ID '{node_id}'")
