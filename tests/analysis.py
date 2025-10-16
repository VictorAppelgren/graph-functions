# Test for analysis pipeline only
import sys
import os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from typing import cast
from src.graph.ops.topic import get_all_topics
from src.analysis.orchestration.analysis_rewriter import analysis_rewriter
from src.analysis.orchestration.should_rewrite import should_rewrite
from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def test_should_rewrite() -> bool:
    """Test the should_rewrite trigger function"""
    logger.info("=== TESTING ANALYSIS TRIGGER (should_rewrite) ===")

    # Get EURUSD topic with recent articles that actually exist in file system
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {name: 'EURUSD'})
    WHERE coalesce(a.priority, '') <> 'hidden'
    AND a.published_at >= '2025-09-19'
    RETURN t.id as topic_id, t.name as topic_name, a.id as article_id
    ORDER BY a.published_at DESC
    LIMIT 5
    """

    results = run_cypher(query)
    if not results:
        logger.warning("❌ No recent EURUSD articles found, trying any recent topic with articles")
        # Fallback to any recent topic
        fallback_query = """
        MATCH (a:Article)-[:ABOUT]->(t:Topic)
        WHERE coalesce(a.priority, '') <> 'hidden'
        AND a.published_at >= '2025-09-19'
        RETURN t.id as topic_id, t.name as topic_name, a.id as article_id
        ORDER BY a.published_at DESC
        LIMIT 5
        """
        results = run_cypher(fallback_query)
        if not results:
            logger.error("❌ No recent articles found for testing")
            return False

    # Try each article until we find one that exists in the file system
    for result in results:
        topic_id = result["topic_id"]
        topic_name = result["topic_name"]
        article_id = result["article_id"]

        logger.info(
            f"Testing should_rewrite for topic='{topic_name}' ({topic_id}) with article={article_id}"
        )

        try:
            result = should_rewrite(topic_id, article_id, triggered_by="test")
            logger.info(f"✅ should_rewrite completed for {topic_id}: {result}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Article {article_id} failed: {e}")
            continue  # Try next article
    
    logger.error("❌ All articles failed - no working articles found")
    return False


def test_analysis_direct() -> bool:
    """Test direct analysis generation"""
    logger.info("=== TESTING DIRECT ANALYSIS GENERATION ===")

    topics = get_all_topics()
    if not topics:
        logger.error("❌ No topics found in the graph!")
        return False

    # Try to use EURUSD first, then fallback to any topic
    ASSET = "EURUSD"
    eurusd_topics = [topic for topic in topics if topic.get("name") == ASSET]
    
    if eurusd_topics:
        topic = eurusd_topics[0]
        topic_id = cast(str, topic.get("id"))
        topic_name = topic.get("name", topic_id)
    else:
        logger.warning(f"Asset '{ASSET}' not found, using random topic")
        topic = random.choice(topics)
        topic_id = cast(str, topic.get("id"))
        topic_name = topic.get("name", topic_id)

    logger.info(f"Testing direct analysis for: {topic_name} ({topic_id})")

    try:
        analysis_rewriter(topic_id, test=True)
        logger.info(f"✅ Direct analysis completed for {topic_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Direct analysis failed: {e}")
        return False


def test_analysis_with_sections() -> bool:
    """Test analysis generation for specific sections including new perspective sections"""
    logger.info("=== TESTING ANALYSIS BY SECTION ===")

    topics = get_all_topics()
    if not topics:
        logger.error("❌ No topics found in the graph!")
        return False

    topic = random.choice(topics)
    topic_id = cast(str, topic.get("id"))
    topic_name = topic.get("name", topic_id)

    # Test timeframe sections
    timeframe_sections = ["fundamental", "medium", "current"]
    # Test new perspective sections
    perspective_sections = ["risk_analysis", "opportunity_analysis", "trend_analysis", "catalyst_analysis"]
    
    all_sections = timeframe_sections + perspective_sections
    results = {}

    logger.info(f"Testing {len(all_sections)} sections for: {topic_name} ({topic_id})")
    
    for section in all_sections:
        logger.info(f"  Testing {section}...")
        try:
            analysis_rewriter(topic_id, test=True, analysis_type=section)
            logger.info(f"  ✅ {section} analysis completed")
            results[section] = True
        except Exception as e:
            logger.error(f"  ❌ {section} analysis failed: {e}")
            results[section] = False

    # Report results by category
    timeframe_passed = sum(results.get(s, False) for s in timeframe_sections)
    perspective_passed = sum(results.get(s, False) for s in perspective_sections)
    
    logger.info(f"Timeframe sections: {timeframe_passed}/{len(timeframe_sections)} passed")
    logger.info(f"Perspective sections: {perspective_passed}/{len(perspective_sections)} passed")
    logger.info(f"Total: {sum(results.values())}/{len(results)} passed")

    return sum(results.values()) > 0  # Success if at least one section worked


def run_analysis_tests() -> None:
    """Run all analysis-focused tests"""
    logger.info("🔬 STARTING ANALYSIS PIPELINE TESTS")

    results = {
        "should_rewrite": test_should_rewrite(),
        "direct_analysis": test_analysis_direct(),
        "section_analysis": test_analysis_with_sections(),
    }

    logger.info("=" * 60)
    logger.info("📊 ANALYSIS TEST RESULTS:")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {test_name.upper()}: {status}")

    all_passed = all(results.values())
    overall = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    logger.info(f"OVERALL: {overall}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_analysis_tests()
