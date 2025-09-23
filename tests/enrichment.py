# Test for enrichment pipeline only
import sys
import os

# Ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import random
from src.graph.ops.topic import get_all_topics
from src.analysis.policies.keyword_generator import generate_keywords
from worker.workflows.topic_enrichment import backfill_topic_from_storage
from worker.workflows.topic_enrichment import collect_candidates_by_keywords
from utils import app_logging
from typing import cast

logger = app_logging.get_logger(__name__)


def test_keywords() -> bool:
    """Test keyword generation for a sample topic"""
    logger.info("=== TESTING KEYWORD GENERATION ===")

    # Test with a known topic
    topic_name = "EUR/USD"
    section = "current"

    logger.info(
        f"Testing keyword generation for topic='{topic_name}' section='{section}'"
    )
    keywords_result = generate_keywords(topic_name, section)
    keywords = keywords_result.list

    if keywords:
        logger.info(f"✅ Generated {len(keywords)} keywords: {keywords[:5]}...")
        return True
    else:
        logger.error("❌ No keywords generated!")
        return False


def test_keyword_search() -> bool:
    """Test keyword-based article search"""
    logger.info("=== TESTING KEYWORD SEARCH ===")

    # Use some common financial keywords
    test_keywords = ["fed", "rate", "inflation", "dollar", "euro"]

    logger.info(f"Testing keyword search with: {test_keywords}")
    candidates = collect_candidates_by_keywords(
        keyword_list=test_keywords,
        max_articles=3,  # Small number for testing
        min_keyword_hits=2,  # Lower threshold for testing
    )

    if candidates:
        logger.info(f"✅ Found {len(candidates)} candidate articles")
        for i, (article_id, text) in enumerate(candidates[:2]):  # Show first 2
            logger.info(f"  Candidate {i+1}: {article_id} ({len(text)} chars)")
        return True
    else:
        logger.error("❌ No candidates found!")
        return False


def test_enrichment() -> bool:
    """Test enrichment for a sample topic"""
    logger.info("=== TESTING TOPIC ENRICHMENT ===")

    topics = get_all_topics()
    if not topics:
        logger.error("❌ No topics found in the graph!")
        return False

    # Pick a random topic
    topic = random.choice(topics)
    topic_id = cast(str, topic.get("id"))
    topic_name = topic.get("name", topic_id)

    logger.info(f"Testing enrichment for topic='{topic_name}' ({topic_id})")

    # Run enrichment with low threshold to see activity
    added = backfill_topic_from_storage(
        topic_id=topic_id,
        threshold=2,  # Low threshold to trigger enrichment
        max_articles_per_section=3,  # Small number for testing
        test=True,  # Test mode
        sections=["current"],  # Just test current section
    )

    logger.info(f"Enrichment test completed: {added} articles added")
    return added >= 0  # Success if no errors


def test_enrichment_full_pipeline() -> bool:
    """Test the full enrichment pipeline step by step"""
    logger.info("=== TESTING FULL ENRICHMENT PIPELINE ===")

    topics = get_all_topics()
    if not topics:
        logger.error("❌ No topics found!")
        return False

    topic = random.choice(topics)
    topic_id = cast(str, topic.get("id"))
    topic_name = topic.get("name", topic_id)

    logger.info(f"Full pipeline test for: {topic_name} ({topic_id})")

    # Step 1: Generate keywords
    logger.info("Step 1: Generating keywords...")
    keywords_result = generate_keywords(topic_name, "current")
    keywords = keywords_result.list
    if not keywords:
        logger.error("❌ Step 1 failed: No keywords generated")
        return False
    logger.info(f"✅ Step 1: Generated {len(keywords)} keywords")

    # Step 2: Search for candidates
    logger.info("Step 2: Searching for candidates...")
    candidates = collect_candidates_by_keywords(
        keyword_list=keywords, max_articles=5, min_keyword_hits=3
    )
    if not candidates:
        logger.warning("⚠️ Step 2: No candidates found (this might be normal)")
    else:
        logger.info(f"✅ Step 2: Found {len(candidates)} candidates")

    # Step 3: Run full enrichment
    logger.info("Step 3: Running full enrichment...")
    added = backfill_topic_from_storage(
        topic_id=topic_id,
        threshold=1,  # Very low threshold
        max_articles_per_section=2,
        test=True,
        sections=["current"],
    )

    logger.info(f"✅ Step 3: Full pipeline completed, {added} articles added")
    return True


def run_enrichment_tests() -> None:
    """Run all enrichment-focused tests"""
    logger.info("🌱 STARTING ENRICHMENT PIPELINE TESTS")

    results = {
        "keywords": test_keywords(),
        "keyword_search": test_keyword_search(),
        "enrichment": test_enrichment(),
        "full_pipeline": test_enrichment_full_pipeline(),
    }

    logger.info("=" * 60)
    logger.info("📊 ENRICHMENT TEST RESULTS:")
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {test_name.upper()}: {status}")

    all_passed = all(results.values())
    overall = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    logger.info(f"OVERALL: {overall}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_enrichment_tests()
