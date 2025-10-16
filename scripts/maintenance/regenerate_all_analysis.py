"""
Regenerate ALL analysis sections for ALL topics.

This script:
1. Fetches all topics from Neo4j
2. For each topic, regenerates ALL analysis sections using the new perspective-aware system
3. Tracks progress and errors
4. Provides detailed statistics

Use this after major changes to:
- Perspective classification system (importance_risk/opportunity/trend/catalyst)
- Analysis prompts (SECTION_FOCUS updates)
- Article classification (temporal_horizon changes)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.graph.neo4j_client import run_cypher
from src.analysis.orchestration.analysis_rewriter import analysis_rewriter, SECTIONS
from utils import app_logging

logger = app_logging.get_logger(__name__)


def fetch_all_topics():
    """Fetch all topics from Neo4j"""
    query = """
    MATCH (t:Topic)
    RETURN t.id as id, t.name as name
    ORDER BY t.name
    """
    result = run_cypher(query, {})
    return result if result else []


def count_articles_for_topic(topic_id: str) -> dict:
    """Count articles by temporal_horizon for a topic"""
    query = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id: $topic_id})
    WHERE coalesce(a.priority, '') <> 'hidden'
    WITH a.temporal_horizon as horizon, count(a) as count
    RETURN horizon, count
    """
    result = run_cypher(query, {"topic_id": topic_id})
    
    counts = {
        "fundamental": 0,
        "medium": 0,
        "current": 0,
        "invalid": 0,
        "total": 0
    }
    
    if result:
        for row in result:
            horizon = row.get("horizon", "invalid")
            count = row.get("count", 0)
            if horizon in counts:
                counts[horizon] = count
            counts["total"] += count
    
    return counts


def regenerate_all_analysis(test: bool = False, min_articles: int = 2):
    """
    Regenerate ALL analysis sections for ALL topics.
    
    Args:
        test: If True, don't save to database (dry run)
        min_articles: Minimum total articles required to attempt analysis
    """
    
    logger.info("Starting FULL analysis regeneration for all topics")
    
    # Fetch all topics
    topics = fetch_all_topics()
    total_topics = len(topics)
    
    logger.info(f"Found {total_topics} topics")
    
    if total_topics == 0:
        logger.info("✅ No topics found. Nothing to regenerate.")
        return
    
    print(f"\n{'='*80}")
    print(f"REGENERATING ANALYSIS FOR {total_topics} TOPICS")
    print(f"{'='*80}")
    print(f"Test mode: {test}")
    print(f"Minimum articles: {min_articles}")
    print(f"Sections to regenerate: {len(SECTIONS)}")
    print(f"  - {', '.join(SECTIONS)}")
    print(f"{'='*80}\n")
    
    # Track statistics
    successful_topics = 0
    skipped_insufficient = 0
    failed_topics = 0
    total_sections_generated = 0
    
    # Track failed topics for inspection
    failed_topic_list = []
    skipped_topic_list = []
    
    for i, topic in enumerate(topics, 1):
        topic_id = topic["id"]
        topic_name = topic.get("name", topic_id)
        
        # Count articles
        article_counts = count_articles_for_topic(topic_id)
        
        # Progress reporting every 5 topics
        if i % 5 == 0 or i == 1:
            print(f"Progress: {i}/{total_topics} ({i/total_topics*100:.1f}%) - "
                  f"Success: {successful_topics}, Skipped: {skipped_insufficient}, Failed: {failed_topics}")
        
        # Check if topic has enough articles
        if article_counts["total"] < min_articles:
            logger.info(
                f"⏭️  Skipping {topic_name} ({topic_id}): "
                f"Only {article_counts['total']} articles (need {min_articles})"
            )
            skipped_insufficient += 1
            skipped_topic_list.append((topic_id, topic_name, article_counts["total"]))
            continue
        
        logger.info(
            f"🔄 Regenerating analysis for {topic_name} ({topic_id}) | "
            f"Articles: F={article_counts['fundamental']}, M={article_counts['medium']}, "
            f"C={article_counts['current']}, Total={article_counts['total']}"
        )
        
        try:
            # Regenerate ALL sections for this topic
            analysis_rewriter(topic_id, test=test, analysis_type=None)
            
            successful_topics += 1
            total_sections_generated += len(SECTIONS)
            
            logger.info(f"✅ {topic_name} ({topic_id}): All sections regenerated")
            
        except Exception as e:
            logger.error(f"❌ Failed to regenerate analysis for {topic_name} ({topic_id}): {e}")
            failed_topics += 1
            failed_topic_list.append((topic_id, topic_name, str(e)[:100]))
    
    # Final report
    logger.info(
        f"✅ Regeneration complete: {successful_topics} successful, "
        f"{skipped_insufficient} skipped, {failed_topics} failed"
    )
    
    print(f"\n{'='*80}")
    print(f"✅ ANALYSIS REGENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total topics: {total_topics}")
    print(f"Successfully regenerated: {successful_topics}")
    print(f"Skipped (insufficient articles): {skipped_insufficient}")
    print(f"Failed (errors): {failed_topics}")
    print(f"Total sections generated: {total_sections_generated}")
    print(f"\nArticle distribution in skipped topics:")
    
    if skipped_topic_list:
        print(f"\nFIRST 10 SKIPPED TOPICS (insufficient articles):")
        for topic_id, topic_name, count in skipped_topic_list[:10]:
            print(f"  {topic_name} ({topic_id}): {count} articles")
    
    if failed_topic_list:
        print(f"\nFAILED TOPICS (for inspection):")
        for topic_id, topic_name, error in failed_topic_list:
            print(f"  {topic_name} ({topic_id}): {error}")
    
    print(f"{'='*80}\n")


def regenerate_specific_sections(sections: list[str], test: bool = False, min_articles: int = 2):
    """
    Regenerate SPECIFIC sections for ALL topics.
    
    Args:
        sections: List of section names to regenerate (e.g., ["risk_analysis", "opportunity_analysis"])
        test: If True, don't save to database (dry run)
        min_articles: Minimum total articles required to attempt analysis
    """
    
    logger.info(f"Starting regeneration of sections {sections} for all topics")
    
    # Validate sections
    from src.analysis.orchestration.analysis_rewriter import SECTIONS as ALL_SECTIONS
    invalid_sections = [s for s in sections if s not in ALL_SECTIONS]
    if invalid_sections:
        raise ValueError(f"Invalid sections: {invalid_sections}. Valid: {ALL_SECTIONS}")
    
    # Fetch all topics
    topics = fetch_all_topics()
    total_topics = len(topics)
    
    logger.info(f"Found {total_topics} topics")
    
    if total_topics == 0:
        logger.info("✅ No topics found. Nothing to regenerate.")
        return
    
    print(f"\n{'='*80}")
    print(f"REGENERATING SPECIFIC SECTIONS FOR {total_topics} TOPICS")
    print(f"{'='*80}")
    print(f"Sections: {', '.join(sections)}")
    print(f"Test mode: {test}")
    print(f"Minimum articles: {min_articles}")
    print(f"{'='*80}\n")
    
    # Track statistics
    successful_topics = 0
    skipped_insufficient = 0
    failed_topics = 0
    
    for i, topic in enumerate(topics, 1):
        topic_id = topic["id"]
        topic_name = topic.get("name", topic_id)
        
        # Count articles
        article_counts = count_articles_for_topic(topic_id)
        
        # Progress reporting every 5 topics
        if i % 5 == 0 or i == 1:
            print(f"Progress: {i}/{total_topics} ({i/total_topics*100:.1f}%) - "
                  f"Success: {successful_topics}, Skipped: {skipped_insufficient}, Failed: {failed_topics}")
        
        # Check if topic has enough articles
        if article_counts["total"] < min_articles:
            logger.info(
                f"⏭️  Skipping {topic_name} ({topic_id}): "
                f"Only {article_counts['total']} articles (need {min_articles})"
            )
            skipped_insufficient += 1
            continue
        
        logger.info(
            f"🔄 Regenerating {sections} for {topic_name} ({topic_id})"
        )
        
        try:
            # Regenerate each specified section
            for section in sections:
                analysis_rewriter(topic_id, test=test, analysis_type=section)
            
            successful_topics += 1
            logger.info(f"✅ {topic_name} ({topic_id}): Sections {sections} regenerated")
            
        except Exception as e:
            logger.error(f"❌ Failed to regenerate for {topic_name} ({topic_id}): {e}")
            failed_topics += 1
    
    # Final report
    print(f"\n{'='*80}")
    print(f"✅ SECTION REGENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total topics: {total_topics}")
    print(f"Successfully regenerated: {successful_topics}")
    print(f"Skipped (insufficient articles): {skipped_insufficient}")
    print(f"Failed (errors): {failed_topics}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate analysis for all topics")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode - don't save to database"
    )
    parser.add_argument(
        "--min-articles",
        type=int,
        default=2,
        help="Minimum total articles required to attempt analysis (default: 2)"
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        help="Specific sections to regenerate (e.g., risk_analysis opportunity_analysis). If not specified, regenerates ALL sections."
    )
    
    args = parser.parse_args()
    
    if args.sections:
        # Regenerate specific sections
        regenerate_specific_sections(
            sections=args.sections,
            test=args.test,
            min_articles=args.min_articles
        )
    else:
        # Regenerate all sections
        regenerate_all_analysis(
            test=args.test,
            min_articles=args.min_articles
        )
