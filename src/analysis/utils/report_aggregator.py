"""
Aggregates and merges analyses/reports from a node and its subnodes.
"""

from src.graph.neo4j_client import run_cypher
from utils import app_logging
from src.analysis.orchestration.analysis_rewriter import SECTIONS

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

    # Map SECTIONS to Neo4j property names (all 11 canonical sections)
    property_map = {
        "fundamental": "fundamental_analysis",
        "medium": "medium_analysis",
        "current": "current_analysis",
        "drivers": "drivers",
        "movers_scenarios": "movers_scenarios",
        "swing_trade_or_outlook": "swing_trade_or_outlook",
        "executive_summary": "executive_summary",
        "risk_analysis": "risk_analysis",
        "opportunity_analysis": "opportunity_analysis",
        "trend_analysis": "trend_analysis",
        "catalyst_analysis": "catalyst_analysis",
    }

    report: dict[str, str] = {}
    for section in SECTIONS:
        key = property_map.get(section, section)
        val = topic.get(key)
        raw_len = len(val) if isinstance(val, str) else 0
        stripped = val.strip() if isinstance(val, str) else ""
        strip_len = len(stripped)
        sample = (
            (stripped[:180] + ("..." if strip_len > 180 else ""))
            if strip_len > 0
            else ""
        )
        logger.info(
            f"report_aggregator | section={section} | key={key} | present={bool(val)} | raw_len={raw_len} | strip_len={strip_len} | sample={sample}"
        )
        if strip_len > 0:
            report[key] = stripped
    if not report:
        logger.warning(f"report_aggregator | empty_report | topic_id={topic_id}")
    return report
