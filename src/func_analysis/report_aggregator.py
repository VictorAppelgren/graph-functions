"""
Aggregates and merges analyses/reports from a node and its subnodes.
"""
from typing import Dict

from graph_db.db_driver import run_cypher
from utils import logging
from analysis.analysis_rewriter import SECTIONS

logger = logging.get_logger(__name__)

def aggregate_reports(node_id: str) -> dict:
    """
    Minimal aggregator: fetch the node and return its analysis fields under
    canonical keys. No recursion, no concatenation.
    Args:
        node_id (str): The node ID.
    Returns:
        dict: Report dict using canonical keys:
              fundamental_analysis, medium_analysis, current_analysis, drivers, executive_summary
    """
    logger.info(f"aggregate_reports | node_id={node_id}")

    if not node_id or not isinstance(node_id, str):
        raise ValueError("node_id must be a non-empty string")

    query = "MATCH (t:Topic {id: $id}) RETURN t"
    logger.info(f"report_aggregator | query={query} | params={{'id': '{node_id}'}}")
    rows = run_cypher(query, {"id": node_id})
    if not rows:
        raise RuntimeError(f"Topic not found: {node_id}")
    node = rows[0]["t"]

    property_map = {
        "fundamental": "fundamental_analysis",
        "medium": "medium_analysis",
        "current": "current_analysis",
        "drivers": "drivers",
        "executive_summary": "executive_summary",
    }

    report: Dict[str, str] = {}
    for section in SECTIONS:
        key = property_map.get(section, section)
        val = node.get(key)
        raw_len = len(val) if isinstance(val, str) else 0
        stripped = val.strip() if isinstance(val, str) else ""
        strip_len = len(stripped)
        sample = (stripped[:180] + ("..." if strip_len > 180 else "")) if strip_len > 0 else ""
        logger.info(
            f"report_aggregator | section={section} | key={key} | present={bool(val)} | raw_len={raw_len} | strip_len={strip_len} | sample={sample}"
        )
        if strip_len > 0:
            report[key] = stripped
    if not report:
        logger.warning(f"report_aggregator | empty_report | node_id={node_id}")
    return report
