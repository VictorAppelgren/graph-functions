"""
Super Simple Analysis Rewriter - Loops all topics and rewrites with god-tier prompts
"""

import os
import sys
import random

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.app_logging import get_logger
from src.graph.ops.topic import get_all_topics, get_topic_analysis_field
from src.analysis.orchestration.analysis_rewriter import analysis_rewriter, SECTIONS
from src.graph.neo4j_client import run_cypher

logger = get_logger(__name__)

def count_articles_for_topic_section(topic_id: str, section: str) -> int:
    """Count articles for a topic in a specific timeframe section"""
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE a.temporal_horizon = $section AND coalesce(a.priority, '') <> 'hidden'
    RETURN count(a) AS count
    """
    result = run_cypher(query, {"topic_id": topic_id, "section": section})
    return int(result[0]["count"]) if result else 0

def get_topic_analysis_info(topic_id: str) -> dict:
    """Get analysis section status for a topic"""
    info = {}
    
    # Check which sections exist (just existence, not article counts)
    for section in SECTIONS:
        try:
            section_key = f"{section}_analysis" if section in ["fundamental", "medium", "current"] else section
            content = get_topic_analysis_field(topic_id, section_key)
            info[f"{section}_exists"] = bool(content and str(content).strip())
        except Exception:
            info[f"{section}_exists"] = False
    
    return info

if __name__ == "__main__":
    logger.info("🏆 Starting god-tier analysis rewrite")
    
    topics = get_all_topics()
    random.shuffle(topics)  # Random order
    logger.info(f"Found {len(topics)} topics (randomized)")
    
    for i, topic in enumerate(topics, 1):
        topic_id = topic["id"]
        topic_name = topic.get("name", topic_id)
        
        # Clear separation like main.py
        logger.info("=" * 80)
        logger.info(f"[{i}/{len(topics)}] PROCESSING: {topic_name} ({topic_id})")
        logger.info("=" * 80)
        
        # Get analysis info before rewriting
        info = get_topic_analysis_info(topic_id)
        if info:
            logger.info(f"EXISTING ANALYSIS SECTIONS:")
            for section in SECTIONS:
                exists = "✅" if info.get(f"{section}_exists", False) else "❌"
                logger.info(f"  {section}: {exists}")
        
        try:
            analysis_rewriter(topic_id=topic_id)
            logger.info(f"✅ COMPLETED: {topic_name}")
        except Exception as e:
            logger.error(f"❌ FAILED {topic_name}: {e}")
        
        logger.info("=" * 80)
    
    logger.info("🏆 ALL TOPICS COMPLETE!")
