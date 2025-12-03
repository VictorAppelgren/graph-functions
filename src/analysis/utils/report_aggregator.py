"""
Aggregates and merges analyses/reports from a node and its subnodes.
"""

from src.graph.neo4j_client import run_cypher
from utils import app_logging
from src.analysis.orchestration.analysis_rewriter import SECTIONS
from src.analysis_agents.section_config import ALL_ANALYSIS_SECTIONS

logger = app_logging.get_logger(__name__)


def aggregate_reports(topic_id: str) -> dict[str, str]:
    """
    Minimal aggregator: fetch the topic and return its analysis fields under
    canonical keys. No recursion, no concatenation.
    Args:
        topic_id (str): The topic ID.
    Returns:
        dict: Report dict using canonical keys:
              fundamental_analysis, medium_analysis, current_analysis, drivers, executive_summary
    """
    logger.info(f"aggregate_reports | topic_id={topic_id}")

    if not topic_id or not isinstance(topic_id, str):
        raise ValueError("topic_id must be a non-empty string")

    query = "MATCH (t:Topic {id: $id}) RETURN t"
    logger.info(f"report_aggregator | query={query} | params={{'id': '{topic_id}'}}")
    rows = run_cypher(query, {"id": topic_id})
    if not rows:
        raise RuntimeError(f"Topic not found: {topic_id}")
    topic = rows[0]["t"]

    report: dict[str, str] = {}
    # Check both legacy SECTIONS and new ALL_ANALYSIS_SECTIONS (from section_config.py)
    all_sections_to_check = list(set(SECTIONS + ALL_ANALYSIS_SECTIONS))
    
    for section in all_sections_to_check:
        # Section name IS the Neo4j property name (no mapping needed!)
        val = topic.get(section)
        raw_len = len(val) if isinstance(val, str) else 0
        stripped = val.strip() if isinstance(val, str) else ""
        strip_len = len(stripped)
        sample = (
            (stripped[:180] + ("..." if strip_len > 180 else ""))
            if strip_len > 0
            else ""
        )
        logger.info(
            f"report_aggregator | section={section} | present={bool(val)} | raw_len={raw_len} | strip_len={strip_len} | sample={sample}"
        )
        if strip_len > 0:
            report[section] = stripped
    if not report:
        logger.warning(f"report_aggregator | empty_report | topic_id={topic_id}")
    return report
