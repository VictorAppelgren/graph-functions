#!/usr/bin/env python3
"""
Diagnostic script to verify topic report sections are correctly stored and retrieved.
Run this on the server to confirm the API returns proper sections for collapsible UI.

Usage:
    python scripts/verify_topic_sections.py [topic_id]
    
If no topic_id provided, it will check all topics.
"""

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph.neo4j_client import run_cypher
from src.analysis.utils.report_aggregator import aggregate_reports
from src.analysis_agents.section_config import ALL_ANALYSIS_SECTIONS
from utils import app_logging

logger = app_logging.get_logger(__name__)


def get_all_topics():
    """Get all topic IDs from Neo4j"""
    query = "MATCH (t:Topic) RETURN t.id as id, t.name as name ORDER BY t.name"
    return run_cypher(query, {})


def verify_topic_sections(topic_id: str, topic_name: str = None) -> dict:
    """
    Verify sections for a single topic.
    Returns a report dict with section status.
    """
    result = {
        "topic_id": topic_id,
        "topic_name": topic_name or topic_id,
        "sections_found": [],
        "sections_missing": [],
        "sections_empty": [],
        "total_content_length": 0,
        "status": "unknown"
    }
    
    try:
        sections = aggregate_reports(topic_id)
        
        for section_key in ALL_ANALYSIS_SECTIONS:
            content = sections.get(section_key, "")
            if content and content.strip():
                result["sections_found"].append(section_key)
                result["total_content_length"] += len(content)
            elif section_key in sections:
                result["sections_empty"].append(section_key)
            else:
                result["sections_missing"].append(section_key)
        
        if len(result["sections_found"]) > 0:
            result["status"] = "ok"
        else:
            result["status"] = "no_content"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def print_report(result: dict):
    """Pretty print a verification result"""
    status_emoji = {
        "ok": "✅",
        "no_content": "⚠️",
        "error": "❌",
        "unknown": "❓"
    }
    
    emoji = status_emoji.get(result["status"], "❓")
    print(f"\n{emoji} {result['topic_name']} ({result['topic_id']})")
    print(f"   Status: {result['status']}")
    
    if result["sections_found"]:
        print(f"   ✓ Sections with content ({len(result['sections_found'])}):")
        for s in result["sections_found"]:
            print(f"      - {s}")
    
    if result["sections_empty"]:
        print(f"   ○ Empty sections ({len(result['sections_empty'])}):")
        for s in result["sections_empty"]:
            print(f"      - {s}")
    
    if result["sections_missing"]:
        print(f"   ✗ Missing sections ({len(result['sections_missing'])}):")
        for s in result["sections_missing"][:5]:  # Show first 5
            print(f"      - {s}")
        if len(result["sections_missing"]) > 5:
            print(f"      ... and {len(result['sections_missing']) - 5} more")
    
    print(f"   Total content: {result['total_content_length']:,} chars")
    
    if "error" in result:
        print(f"   Error: {result['error']}")


def main():
    print("=" * 60)
    print("TOPIC SECTIONS VERIFICATION")
    print("=" * 60)
    print(f"\nExpected sections: {len(ALL_ANALYSIS_SECTIONS)}")
    print(f"Section keys: {', '.join(ALL_ANALYSIS_SECTIONS[:5])}...")
    
    # Check if specific topic ID provided
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        print(f"\nVerifying single topic: {topic_id}")
        result = verify_topic_sections(topic_id)
        print_report(result)
    else:
        # Check all topics
        print("\nFetching all topics...")
        topics = get_all_topics()
        print(f"Found {len(topics)} topics\n")
        
        stats = {"ok": 0, "no_content": 0, "error": 0}
        
        for topic in topics:
            result = verify_topic_sections(topic["id"], topic["name"])
            print_report(result)
            stats[result["status"]] = stats.get(result["status"], 0) + 1
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✅ Topics with content: {stats.get('ok', 0)}")
        print(f"⚠️  Topics without content: {stats.get('no_content', 0)}")
        print(f"❌ Topics with errors: {stats.get('error', 0)}")
        print(f"Total topics checked: {len(topics)}")


if __name__ == "__main__":
    main()
