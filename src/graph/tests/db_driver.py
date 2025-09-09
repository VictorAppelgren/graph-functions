"""
Minimal test for Neo4j database connection.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from graph.neo4j_client import connect_graph_db
from utils import app_logging

def main():
    logger = app_logging.get_logger(__name__)
    logger.info("=== Starting Neo4j connection test ===")
    try:
        driver = connect_graph_db()
        logger.info("Successfully obtained Neo4j driver.")
        with driver.session() as session:
            logger.info("Running test query: MATCH (n) RETURN n LIMIT 3")
            result = session.run("MATCH (n) RETURN n LIMIT 3")
            nodes = list(result)
            logger.info(f"Found {len(nodes)} node(s) in the database (showing up to 3):")
            for idx, record in enumerate(nodes, 1):
                logger.info(f"Node {idx}: {record}")
        logger.info("Neo4j test completed successfully.")
    except Exception as e:
        logger.error(f"Neo4j test failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
