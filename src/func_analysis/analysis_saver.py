"""
Saves updated analysis fields to the graph DB for a node.
"""
from typing import Dict

import sys, os
from graph_db.db_driver import run_cypher

from utils import logging
from utils.pipeline_logging import master_log
logger = logging.get_logger(__name__)

from datetime import datetime

def save_analysis(node_id: str, field: str, text: str):
    """
    Writes a single updated analysis field (from the LLM) to the node in the graph DB, updating the timestamp as needed.
    Args:
        node_id (str): The node ID.
        field (str): The analysis field name.
        text (str): The analysis text.
    """
    if not node_id or not field:
        raise ValueError("node_id and field are required")
    logger.info(f"Saving analysis for node_id={node_id} field={field}")
    # Fetch before
    fetch_query = """
        MATCH (t:Topic {id: $node_id})
        RETURN t { .* } AS topic
    """
    before = run_cypher(fetch_query, {"node_id": node_id})
    before_sample = str(before[0]["topic"])[:400] if before else ""
    # Update
    update_query = f"""
        MATCH (t:Topic {{id: $node_id}})
        SET t.{field} = $text, t.last_updated = datetime()
    """
    params = {"node_id": node_id, "text": text}
    run_cypher(update_query, params)
    # Fetch after
    after = run_cypher(fetch_query, {"node_id": node_id})
    after_sample = str(after[0]["topic"])[:400] if after else ""
    logger.info(f"Saved analysis for node_id={node_id} field={field} before_sample={before_sample} after_sample={after_sample}")
    
    master_log(f'Saved analysis | {node_id} | field "{field}" len={len(str(text))}', rewrites_saved=1)
