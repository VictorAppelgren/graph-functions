"""
Fix Bad Queries - Regenerate all naive fallback queries.

Run: python -m src.start_scripts.fix_bad_queries
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.app_logging import get_logger
from src.graph.ops.topic import get_all_topics
from src.graph.neo4j_client import run_cypher
from src.analysis.policies.query_generator import create_wide_query

logger = get_logger(__name__)


def is_valid_wide_query(query: str) -> bool:
    """
    Check if query is a proper boolean search query.
    
    Valid: (oil OR crude) AND (price OR inventory)
    Valid: ("Swedish Krona" OR SEK OR krona) AND (currency OR forex)
    Invalid: ("Topic Name")  ← Only one term, no synonyms/variants
    """
    if not query or len(query) < 20:
        return False
    
    # Count boolean operators
    and_count = query.upper().count(' AND ')
    or_count = query.upper().count(' OR ')
    not_count = query.upper().count(' NOT ')
    
    # Must have at least 1 operator (indicates multiple terms)
    total_operators = and_count + or_count + not_count
    if total_operators < 1:
        return False
    
    # Must have parentheses (indicates proper grouping)
    if '(' not in query or ')' not in query:
        return False
    
    # Check for naive fallback: ONLY a single quoted term with no other terms
    # Pattern: '("Single Term")' or '("Single Term")'  with nothing else
    stripped = query.strip()
    if stripped.startswith('("') and stripped.endswith('")'):
        # Check if there's ONLY one term (no OR/AND inside)
        inner = stripped[2:-2]  # Remove '("' and '")'
        if ' OR ' not in inner.upper() and ' AND ' not in inner.upper():
            return False
    
    return True


def find_bad_queries():
    """Find all topics with bad queries."""
    topics = get_all_topics(fields=["id", "name", "query"])
    
    bad_topics = []
    for topic in topics:
        query = topic.get("query", "")
        
        if not is_valid_wide_query(query):
            bad_topics.append(topic)
            logger.info(f"❌ Bad query: {topic['id']} → {query[:80]}")
    
    return bad_topics


def regenerate_query(topic_id: str, topic_name: str):
    """Regenerate query for a topic."""
    anchor_text = f"Name: {topic_name}"
    
    try:
        qres = create_wide_query(anchor_text)
        if isinstance(qres, dict) and qres.get("query"):
            new_query = qres["query"]
            
            if is_valid_wide_query(new_query):
                return new_query
            else:
                logger.error(f"❌ LLM generated invalid query for {topic_id}")
                return None
        else:
            logger.error(f"❌ LLM returned empty for {topic_id}")
            return None
    except Exception as e:
        logger.error(f"❌ Query generation failed for {topic_id}: {e}")
        return None


def update_topic_query(topic_id: str, new_query: str):
    """Update topic query in Neo4j."""
    query = """
    MATCH (t:Topic {id: $topic_id})
    SET t.query = $new_query
    RETURN t.id as id
    """
    result = run_cypher(query, {"topic_id": topic_id, "new_query": new_query})
    return result is not None


def main():
    """Fix all bad queries."""
    logger.info("="*80)
    logger.info("FIX BAD QUERIES - STARTED")
    logger.info("="*80)
    
    bad_topics = find_bad_queries()
    logger.info(f"\nFound {len(bad_topics)} topics with bad queries\n")
    
    fixed = 0
    failed = 0
    
    for topic in bad_topics:
        topic_id = topic["id"]
        topic_name = topic["name"]
        
        logger.info(f"Fixing: {topic_id} ({topic_name})")
        
        new_query = regenerate_query(topic_id, topic_name)
        
        if new_query:
            if update_topic_query(topic_id, new_query):
                logger.info(f"✅ Fixed: {topic_id}")
                logger.info(f"   New query: {new_query[:100]}...")
                fixed += 1
            else:
                logger.error(f"❌ Failed to update Neo4j for: {topic_id}")
                failed += 1
        else:
            logger.error(f"❌ Failed to generate query for: {topic_id}")
            failed += 1
    
    logger.info("\n" + "="*80)
    logger.info("FIX BAD QUERIES - COMPLETE")
    logger.info("="*80)
    logger.info(f"Results: {fixed} fixed, {failed} failed")
    logger.info("="*80)


if __name__ == "__main__":
    main()
