"""
Topic Findings Storage - Risks and Opportunities

Stores findings as JSON strings on Topic node properties:
- t.risks = '[{"headline": "...", "rationale": "...", ...}, ...]'
- t.opportunities = '[{"headline": "...", "rationale": "...", ...}, ...]'

Max 3 findings per mode (risk/opportunity).
"""

import json
from typing import List, Dict, Optional
from datetime import datetime

from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def get_topic_findings(topic_id: str, mode: str) -> List[Dict]:
    """
    Get risks or opportunities for a topic.

    Args:
        topic_id: Topic ID
        mode: "risk" or "opportunity"

    Returns:
        List of findings (max 3), empty list if none or error
    """
    if mode not in ("risk", "opportunity"):
        logger.warning(f"Invalid mode '{mode}', must be 'risk' or 'opportunity'")
        return []

    field = "risks" if mode == "risk" else "opportunities"

    query = f"""
    MATCH (t:Topic {{id: $topic_id}})
    RETURN t.{field} AS findings
    """

    try:
        result = run_cypher(query, {"topic_id": topic_id})

        if not result:
            return []

        findings_json = result[0].get("findings")
        if not findings_json:
            return []

        return json.loads(findings_json)

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {field} for topic {topic_id}: {e}")
        return []
    except Exception as e:
        logger.warning(f"Failed to get {field} for topic {topic_id}: {e}")
        return []


def save_topic_finding(
    topic_id: str,
    mode: str,
    finding: Dict,
    replaces: Optional[int] = None
) -> bool:
    """
    Save a finding to topic. Max 3 per mode.

    Args:
        topic_id: Topic ID
        mode: "risk" or "opportunity"
        finding: Dict with headline, rationale, flow_path, confidence, etc.
        replaces: If 1/2/3, replace that slot. If None, append (up to 3).

    Returns:
        True if saved, False if failed or at capacity
    """
    if mode not in ("risk", "opportunity"):
        logger.warning(f"Invalid mode '{mode}', must be 'risk' or 'opportunity'")
        return False

    field = "risks" if mode == "risk" else "opportunities"
    timestamp_field = f"{field}_updated_at"

    # Get existing findings
    existing = get_topic_findings(topic_id, mode)

    # Add timestamp
    finding["saved_at"] = datetime.utcnow().isoformat()

    # Handle replace or append
    if replaces and 1 <= replaces <= 3:
        if len(existing) >= replaces:
            existing[replaces - 1] = finding
            logger.info(f"Replacing {mode} #{replaces} for topic {topic_id}")
        else:
            # Slot doesn't exist yet, just append
            existing.append(finding)
            logger.info(f"Appending {mode} (slot {replaces} didn't exist) for topic {topic_id}")
    elif len(existing) < 3:
        existing.append(finding)
        logger.info(f"Appending {mode} #{len(existing)} for topic {topic_id}")
    else:
        logger.warning(f"Cannot add {mode} to topic {topic_id}: already has 3, need replaces param")
        return False

    # Save back to Neo4j
    query = f"""
    MATCH (t:Topic {{id: $topic_id}})
    SET t.{field} = $findings, t.{timestamp_field} = datetime()
    RETURN t.id AS id
    """

    try:
        result = run_cypher(query, {
            "topic_id": topic_id,
            "findings": json.dumps(existing)
        })
        return bool(result)
    except Exception as e:
        logger.error(f"Failed to save {mode} for topic {topic_id}: {e}")
        return False


def delete_topic_finding(topic_id: str, mode: str, index: int) -> bool:
    """
    Delete a finding by index (1-based).

    Args:
        topic_id: Topic ID
        mode: "risk" or "opportunity"
        index: 1, 2, or 3

    Returns:
        True if deleted, False if failed
    """
    if mode not in ("risk", "opportunity"):
        return False

    if not 1 <= index <= 3:
        return False

    field = "risks" if mode == "risk" else "opportunities"
    timestamp_field = f"{field}_updated_at"

    existing = get_topic_findings(topic_id, mode)

    if len(existing) < index:
        logger.warning(f"Cannot delete {mode} #{index} for topic {topic_id}: only {len(existing)} exist")
        return False

    # Remove at index (convert to 0-based)
    existing.pop(index - 1)
    logger.info(f"Deleted {mode} #{index} for topic {topic_id}")

    # Save back
    query = f"""
    MATCH (t:Topic {{id: $topic_id}})
    SET t.{field} = $findings, t.{timestamp_field} = datetime()
    RETURN t.id AS id
    """

    try:
        result = run_cypher(query, {
            "topic_id": topic_id,
            "findings": json.dumps(existing)
        })
        return bool(result)
    except Exception as e:
        logger.error(f"Failed to delete {mode} #{index} for topic {topic_id}: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    from utils.env_loader import load_env
    load_env()

    test_topic = "eurusd"

    # Test get (should return empty or existing)
    print(f"Current risks for {test_topic}:")
    risks = get_topic_findings(test_topic, "risk")
    print(f"  {risks}")

    print(f"\nCurrent opportunities for {test_topic}:")
    opps = get_topic_findings(test_topic, "opportunity")
    print(f"  {opps}")

    # Test save
    test_finding = {
        "headline": "Test Risk",
        "rationale": "This is a test rationale",
        "confidence": 0.8
    }

    print(f"\nSaving test finding...")
    # result = save_topic_finding(test_topic, "risk", test_finding)
    # print(f"  Saved: {result}")

    print("\nDone!")
