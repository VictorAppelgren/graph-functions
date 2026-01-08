"""
Migration Script: Add IDs to Existing Findings

Scans all topics in Neo4j and adds R_XXXXXXXXX or O_XXXXXXXXX IDs
to any findings that don't have them.

Usage:
    cd graph-functions
    python scripts/migrate_finding_ids.py          # Dry run (show what would change)
    python scripts/migrate_finding_ids.py --fix    # Actually update the database
"""

import os
import sys
import json
import argparse

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.env_loader import load_env
load_env()

from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic_findings import generate_finding_id, get_all_finding_ids


def migrate_findings(dry_run: bool = True) -> dict:
    """
    Add IDs to all existing findings that don't have them.

    Args:
        dry_run: If True, only show what would change without updating

    Returns:
        Stats dict with counts
    """
    stats = {
        "topics_scanned": 0,
        "topics_with_findings": 0,
        "risks_updated": 0,
        "opportunities_updated": 0,
        "already_have_ids": 0,
        "errors": 0
    }

    # Get all existing IDs to avoid collisions
    existing_ids = get_all_finding_ids()
    print(f"Found {len(existing_ids)} existing finding IDs in database")

    # Get all topics with findings
    query = """
    MATCH (t:Topic)
    WHERE t.risks IS NOT NULL OR t.opportunities IS NOT NULL
    RETURN t.id AS topic_id, t.risks AS risks, t.opportunities AS opportunities
    """

    results = run_cypher(query, {})

    if not results:
        print("No topics with findings found")
        return stats

    print(f"Found {len(results)} topics with findings")

    for row in results:
        stats["topics_scanned"] += 1
        topic_id = row["topic_id"]
        risks_json = row.get("risks")
        opps_json = row.get("opportunities")

        risks_updated = False
        opps_updated = False

        # Process risks
        if risks_json:
            try:
                risks = json.loads(risks_json)
                for risk in risks:
                    if not risk.get("id"):
                        new_id = generate_finding_id("risk", existing_ids)
                        existing_ids.add(new_id)
                        risk["id"] = new_id
                        risk["topic_id"] = topic_id
                        stats["risks_updated"] += 1
                        risks_updated = True
                        print(f"  [RISK] {topic_id}: Added ID {new_id} to '{risk.get('headline', 'N/A')[:50]}'")
                    else:
                        stats["already_have_ids"] += 1

                if risks_updated and not dry_run:
                    update_query = """
                    MATCH (t:Topic {id: $topic_id})
                    SET t.risks = $risks
                    RETURN t.id
                    """
                    run_cypher(update_query, {"topic_id": topic_id, "risks": json.dumps(risks)})

            except json.JSONDecodeError as e:
                print(f"  [ERROR] {topic_id}: Invalid JSON in risks: {e}")
                stats["errors"] += 1

        # Process opportunities
        if opps_json:
            try:
                opps = json.loads(opps_json)
                for opp in opps:
                    if not opp.get("id"):
                        new_id = generate_finding_id("opportunity", existing_ids)
                        existing_ids.add(new_id)
                        opp["id"] = new_id
                        opp["topic_id"] = topic_id
                        stats["opportunities_updated"] += 1
                        opps_updated = True
                        print(f"  [OPP]  {topic_id}: Added ID {new_id} to '{opp.get('headline', 'N/A')[:50]}'")
                    else:
                        stats["already_have_ids"] += 1

                if opps_updated and not dry_run:
                    update_query = """
                    MATCH (t:Topic {id: $topic_id})
                    SET t.opportunities = $opps
                    RETURN t.id
                    """
                    run_cypher(update_query, {"topic_id": topic_id, "opps": json.dumps(opps)})

            except json.JSONDecodeError as e:
                print(f"  [ERROR] {topic_id}: Invalid JSON in opportunities: {e}")
                stats["errors"] += 1

        if risks_json or opps_json:
            stats["topics_with_findings"] += 1

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add IDs to existing findings")
    parser.add_argument("--fix", action="store_true", help="Actually update database (default is dry-run)")
    args = parser.parse_args()

    mode = "UPDATING DATABASE" if args.fix else "DRY RUN (use --fix to apply)"
    print(f"\n{'='*60}")
    print(f"Finding ID Migration - {mode}")
    print(f"{'='*60}\n")

    stats = migrate_findings(dry_run=not args.fix)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Topics scanned:        {stats['topics_scanned']}")
    print(f"  Topics with findings:  {stats['topics_with_findings']}")
    print(f"  Risks updated:         {stats['risks_updated']}")
    print(f"  Opportunities updated: {stats['opportunities_updated']}")
    print(f"  Already had IDs:       {stats['already_have_ids']}")
    print(f"  Errors:                {stats['errors']}")
    print(f"{'='*60}\n")

    if not args.fix and (stats['risks_updated'] > 0 or stats['opportunities_updated'] > 0):
        print("Run with --fix to apply these changes to the database")
