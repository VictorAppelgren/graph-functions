# Minimal test for topic importance LLM helper
import sys, os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from graph_utils.get_all_nodes import get_all_nodes
from graph_nodes.topic_priority_classifier import classify_topic_importance
from utils import logging

logger = logging.get_logger(__name__)

def test_time_importance():
    nodes = get_all_nodes()
    if not nodes:
        logger.error('No nodes found in the graph!')
        return
    node = random.choice(nodes)
    name = node.get('name', '')
    ttype = node.get('type', '')
    context = node.get('fundamental_analysis', '') or node.get('medium_analysis', '') or ''
    logger.info(f'Picked node: {node.get("id")} | name: {name} | type: {ttype}')
    result = classify_topic_importance(topic_name=name, topic_type=ttype, context=context)
    logger.info(f'Picked node: {node.get("id")} | name: {name} | type: {ttype}')
    logger.info(f"Result for node {node.get('id')}: {result}")

if __name__ == "__main__":
    test_time_importance()