# Test for analysis pipeline only
import sys, os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from typing import cast
from src.graph.ops.get_all_nodes import get_all_nodes
from src.analysis.orchestration.analysis_rewriter import analysis_rewriter
from src.analysis.orchestration.should_rewrite import should_rewrite
from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)

def test_should_rewrite() -> bool:
    """Test the should_rewrite trigger function"""
    logger.info("=== TESTING ANALYSIS TRIGGER (should_rewrite) ===")
    
    # Get a topic with articles
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic)
    WHERE coalesce(a.priority, '') <> 'hidden'
    RETURN t.id as topic_id, t.name as topic_name, a.id as article_id
    LIMIT 1
    """
    
    results = run_cypher(query)
    if not results:
        logger.error("❌ No topics with articles found for testing")
        return False
    
    topic_id = results[0]["topic_id"]
    topic_name = results[0]["topic_name"]
    article_id = results[0]["article_id"]
    
    logger.info(f"Testing should_rewrite for topic='{topic_name}' ({topic_id}) with article={article_id}")
    
    try:
        should_rewrite(topic_id, article_id)
        logger.info(f"✅ should_rewrite completed for {topic_id}")
        return True
    except Exception as e:
        logger.error(f"❌ should_rewrite failed: {e}")
        return False

def test_analysis_direct() -> bool:
    """Test direct analysis generation"""
    logger.info("=== TESTING DIRECT ANALYSIS GENERATION ===")
    
    nodes = get_all_nodes()
    if not nodes:
        logger.error('❌ No nodes found in the graph!')
        return False

    # Filter for specific asset if set
    ASSET = "EURUSD"
    if ASSET:
        nodes = [node for node in nodes if node.get('name') == ASSET]
        if not nodes:
            logger.warning(f"Asset '{ASSET}' not found, using random node")
            nodes = get_all_nodes()
    
    node = random.choice(nodes)
    topic_id = cast(str, node.get('id'))
    topic_name = node.get('name', topic_id)
    
    logger.info(f'Testing direct analysis for: {topic_name} ({topic_id})')
    
    try:
        analysis_rewriter(topic_id, test=True)
        logger.info(f"✅ Direct analysis completed for {topic_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Direct analysis failed: {e}")
        return False

def test_analysis_with_sections() -> bool:
    """Test analysis generation for specific sections"""
    logger.info("=== TESTING ANALYSIS BY SECTION ===")
    
    nodes = get_all_nodes()
    if not nodes:
        logger.error('❌ No nodes found in the graph!')
        return False
    
    node = random.choice(nodes)
    topic_id = cast(str, node.get('id'))
    topic_name = node.get('name', topic_id)
    
    sections = ["fundamental", "medium", "current"]
    results = {}
    
    for section in sections:
        logger.info(f"Testing {section} analysis for: {topic_name} ({topic_id})")
        try:
            analysis_rewriter(topic_id, test=True, analysis_type=section)
            logger.info(f"✅ {section} analysis completed")
            results[section] = True
        except Exception as e:
            logger.error(f"❌ {section} analysis failed: {e}")
            results[section] = False
    
    passed = sum(results.values())
    total = len(results)
    logger.info(f"Section analysis results: {passed}/{total} passed")
    
    return passed > 0  # Success if at least one section worked

def run_analysis_tests() -> None:
    """Run all analysis-focused tests"""
    logger.info("🔬 STARTING ANALYSIS PIPELINE TESTS")
    
    results = {
        "should_rewrite": test_should_rewrite(),
        "direct_analysis": test_analysis_direct(),
        "section_analysis": test_analysis_with_sections()
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
