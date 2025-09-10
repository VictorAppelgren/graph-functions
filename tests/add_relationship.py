# Minimal test for add_relationship
import sys, os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from src.graph.ops.get_all_nodes import get_all_nodes
from src.graph.ops.find_link import find_influences_and_correlates
from utils import app_logging

logger = app_logging.get_logger(__name__)

def test_relationship_finder():
    nodes = get_all_nodes()
    if not nodes:
        logger.error('No nodes found in the graph!')
        return
    node = random.choice(nodes)
    node_id = node.get('id')
    logger.info(f'Picked node: {node_id}')
    result = find_influences_and_correlates(node_id, test=False)
    logger.info(f"[test_relationship_finder] Results for node {node_id}: {result}")

if __name__ == "__main__":
    test_relationship_finder()
