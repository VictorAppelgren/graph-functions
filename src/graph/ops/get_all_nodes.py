import sys, os
from typing import List, Dict

# Canonical import pattern to ensure absolute imports work when run as a script
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.neo4j_client import connect_graph_db
from utils import app_logging

logger = app_logging.get_logger(__name__)

def get_all_nodes(fields: list[str]) -> List[dict[str, str]]:
    """
    Fetch all current graph nodes from the Neo4j database.
    Args:
        fields (list): Optional list of property names to return for each node. Defaults to ['id', 'name', 'type'].
    Returns:
        List[Dict]: List of node dicts with requested fields.
    Raises:
        RuntimeError: If the database query fails.
    """
    try:
        driver = connect_graph_db()
        with driver.session(database="argosgraph") as session:
            return_clause = ', '.join([f"n.{f} AS {f}" for f in fields])
            query = f"MATCH (n:Topic) RETURN {return_clause}"
            logger.info(f" Running query: {query}")
            result = session.run(query)
            nodes = [dict(record) for record in result]
            logger.info(f" Fetched {len(nodes)} node(s) from Neo4j.")
            return nodes
    except Exception as e:
        logger.error(f" Failed to fetch nodes from Neo4j: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch nodes from Neo4j: {e}")

# a main that simply prints all nodes and logs with numbers all nodes
if __name__ == "__main__":
    nodes = get_all_nodes(['id', 'name', 'type'])
    for i, node in enumerate(nodes):
        logger.info(f" Node {i}: {node['name']} - {node['id']}")
