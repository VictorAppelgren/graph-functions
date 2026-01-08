"""
Topic Findings Storage - Risks and Opportunities

Stores findings as JSON strings on Topic node properties:
- t.risks = '[{"id": "R_ABC123XY", "headline": "...", "rationale": "...", ...}, ...]'
- t.opportunities = '[{"id": "O_ABC123XY", "headline": "...", "rationale": "...", ...}, ...]'

Max 3 findings per mode (risk/opportunity).

Finding IDs:
- Risk IDs start with "R_" (e.g., R_ABC123XY)
- Opportunity IDs start with "O_" (e.g., O_ABC123XY)
- 9 character suffix (uppercase + digits)
- Referenced in prompts like (R_ABC123XY) for clickable links
"""

import json
import random
import string
from typing import List, Dict, Optional, Set
from datetime import datetime

from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def generate_finding_id(mode: str, existing_ids: Set[str] = None) -> str:
    """
    Generate a unique finding ID.

    Format: {prefix}_{9 chars}
    - Risk: R_ABC123XYZ
    - Opportunity: O_ABC123XYZ

    Args:
        mode: "risk" or "opportunity"
        existing_ids: Set of existing IDs to avoid collisions

    Returns:
        Unique finding ID
    """
    prefix = "R" if mode == "risk" else "O"
    charset = string.ascii_uppercase + string.digits
    existing_ids = existing_ids or set()

    for _ in range(100):  # Max attempts
        suffix = ''.join(random.choices(charset, k=9))
        new_id = f"{prefix}_{suffix}"
        if new_id not in existing_ids:
            return new_id

    # Fallback with timestamp if somehow collision-prone
    import time
    return f"{prefix}_{int(time.time())}"


def get_all_finding_ids() -> Set[str]:
    """Get all existing finding IDs across all topics."""
    query = """
    MATCH (t:Topic)
    WHERE t.risks IS NOT NULL OR t.opportunities IS NOT NULL
    RETURN t.risks AS risks, t.opportunities AS opportunities
    """

    ids = set()
    try:
        result = run_cypher(query, {})
        for row in (result or []):
            for field in ["risks", "opportunities"]:
                findings_json = row.get(field)
                if findings_json:
                    try:
                        findings = json.loads(findings_json)
                        for f in findings:
                            if f.get("id"):
                                ids.add(f["id"])
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.warning(f"Failed to get all finding IDs: {e}")

    return ids


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
) -> Optional[str]:
    """
    Save a finding to topic. Max 3 per mode. Auto-generates finding ID.

    Args:
        topic_id: Topic ID
        mode: "risk" or "opportunity"
        finding: Dict with headline, rationale, flow_path, confidence, etc.
        replaces: If 1/2/3, replace that slot. If None, append (up to 3).

    Returns:
        Finding ID if saved, None if failed or at capacity
    """
    if mode not in ("risk", "opportunity"):
        logger.warning(f"Invalid mode '{mode}', must be 'risk' or 'opportunity'")
        return None

    field = "risks" if mode == "risk" else "opportunities"
    timestamp_field = f"{field}_updated_at"

    # Get existing findings
    existing = get_topic_findings(topic_id, mode)

    # Collect existing IDs to avoid collisions
    existing_ids = {f.get("id") for f in existing if f.get("id")}

    # Generate unique finding ID if not provided
    if not finding.get("id"):
        finding["id"] = generate_finding_id(mode, existing_ids)

    # Add metadata
    finding["saved_at"] = datetime.utcnow().isoformat()
    finding["topic_id"] = topic_id

    # Handle replace or append
    if replaces and 1 <= replaces <= 3:
        if len(existing) >= replaces:
            existing[replaces - 1] = finding
            logger.info(f"Replacing {mode} #{replaces} for topic {topic_id} → {finding['id']}")
        else:
            # Slot doesn't exist yet, just append
            existing.append(finding)
            logger.info(f"Appending {mode} (slot {replaces} didn't exist) for topic {topic_id} → {finding['id']}")
    elif len(existing) < 3:
        existing.append(finding)
        logger.info(f"Appending {mode} #{len(existing)} for topic {topic_id} → {finding['id']}")
    else:
        logger.warning(f"Cannot add {mode} to topic {topic_id}: already has 3, need replaces param")
        return None

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
        if result:
            return finding["id"]  # Return the finding ID on success
        return None
    except Exception as e:
        logger.error(f"Failed to save {mode} for topic {topic_id}: {e}")
        return None


def get_finding_by_id(finding_id: str) -> Optional[Dict]:
    """
    Get a finding by its unique ID (searches all topics).

    Args:
        finding_id: Finding ID (e.g., R_ABC123XY or O_XYZ789AB)

    Returns:
        Finding dict with topic_id included, or None if not found
    """
    if not finding_id:
        return None

    # Determine mode from prefix
    if finding_id.startswith("R_"):
        mode = "risk"
    elif finding_id.startswith("O_"):
        mode = "opportunity"
    else:
        logger.warning(f"Invalid finding ID format: {finding_id}")
        return None

    field = "risks" if mode == "risk" else "opportunities"

    query = f"""
    MATCH (t:Topic)
    WHERE t.{field} IS NOT NULL AND t.{field} CONTAINS $finding_id
    RETURN t.id AS topic_id, t.{field} AS findings
    LIMIT 1
    """

    try:
        result = run_cypher(query, {"finding_id": finding_id})
        if not result:
            return None

        topic_id = result[0].get("topic_id")
        findings_json = result[0].get("findings")

        if findings_json:
            findings = json.loads(findings_json)
            for f in findings:
                if f.get("id") == finding_id:
                    f["topic_id"] = topic_id  # Ensure topic_id is set
                    f["mode"] = mode
                    return f

    except Exception as e:
        logger.warning(f"Failed to get finding {finding_id}: {e}")

    return None


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
