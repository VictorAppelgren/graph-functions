import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import logging
from graph_utils.get_all_nodes import get_all_nodes
from graph_nodes.remove_node import remove_node
logger = logging.get_logger(__name__)

ASSET = "Taylor Swift: The Life of a Showgirl"

def test_remove_node():
    all_nodes = get_all_nodes()
    node_to_remove = None
    if ASSET:
        for node in all_nodes:
            if node.get('name') == ASSET:
                node_to_remove = node
                break
    if not node_to_remove:
        for node in all_nodes:
            imp = node.get('importance')
            try:
                imp_int = int(imp) if imp is not None else None
            except (ValueError, TypeError):
                imp_int = None
            if imp_int == 5:
                node_to_remove = node
                break
    if not node_to_remove:
        logger.warning("No removable node found (ASSET or importance==5)")
        return
    node_id = node_to_remove.get('id')
    logger.info(f"Removing node: {node_to_remove.get('name')} (id={node_id})")
    result = remove_node(node_id, reason="cleanup test path")
    print(f"[test_remove_node] Removed: {node_to_remove.get('name')} (id={node_id}) Result: {result}")

if __name__ == "__main__":
    test_remove_node()
