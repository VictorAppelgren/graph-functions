"""Inspect all Topic–Topic relationship types in Neo4j.

This is a READ-ONLY diagnostic script. It does NOT modify the graph.

WHAT IT DOES
- Connects to Neo4j via run_cypher
- Finds all relationships between Topic nodes
- Prints each distinct relationship type and how many relationships of that type exist

USAGE
    python scripts/maintenance/inspect_topic_relationship_types.py

This is intended as a first step before writing a one-off cleanup script
that normalizes legacy types (e.g. DRIVES/DRIVEN_BY/IMPACTS/RELATED_TO)
into the canonical set defined in src.graph.relationship_types.
"""

import os
import sys
from typing import List, Dict

# Add project root to path (same pattern as other maintenance scripts)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.env_loader import load_env
from utils.app_logging import get_logger
from src.graph.neo4j_client import run_cypher

# Load environment and logger
load_env()
logger = get_logger("maintenance.inspect_topic_relationship_types")


def fetch_topic_relationship_types() -> List[Dict]:
    """Return all distinct Topic–Topic relationship types with counts.

    Only looks at relationships where BOTH ends are Topic nodes.
    """
    query = """
    MATCH (a:Topic)-[r]->(b:Topic)
    RETURN type(r) as type, count(*) as count
    ORDER BY count DESC, type ASC
    """
    result = run_cypher(query, {})
    return result or []


def print_relationship_type_summary(rows: List[Dict]) -> None:
    if not rows:
        print("No Topic–Topic relationships found.")
        return

    total = sum(row["count"] for row in rows)
    print("\n" + "=" * 80)
    print("TOPIC–TOPIC RELATIONSHIP TYPES IN NEO4J")
    print("=" * 80)
    print(f"Total Topic–Topic relationships: {total}")
    print("")
    print(f"{'Type':<25} {'Count':>10}")
    print("-" * 40)
    for row in rows:
        rtype = row.get("type", "<unknown>")
        count = row.get("count", 0)
        print(f"{rtype:<25} {count:>10}")
    print("" + "=" * 80 + "\n")


def main() -> None:
    logger.info("Inspecting Topic–Topic relationship types in Neo4j...")
    rows = fetch_topic_relationship_types()
    print_relationship_type_summary(rows)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Inspection failed: {e}")
        print(f"\n❌ Inspection failed: {e}\n")
        sys.exit(1)
