"""
Migration Script: Move Article Classification to Relationships

Migrates article-level classification to relationship-level:
1. For each Article-ABOUT-Topic relationship:
   - Copy temporal_horizon → r.timeframe
   - Copy importance_* → r.importance_*
   - Generate motivation & implications using LLM
2. Remove old properties from Article nodes

Run this ONCE after deploying the new system.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables (for Neo4j connection)
load_dotenv(project_root / ".env")

from src.graph.neo4j_client import run_cypher
from src.articles.load_article import load_article
from src.graph.ops.topic import get_topic_context
from src.llm.classify_article_for_topic import classify_article_for_topic
from utils.app_logging import get_logger

logger = get_logger(__name__)


def get_articles_needing_migration():
    """
    Find all Article-ABOUT-Topic relationships that need migration.
    
    Returns relationships where:
    - Article has old properties (temporal_horizon, importance_*)
    - Relationship doesn't have new properties (timeframe, motivation)
    """
    
    # First, check what we have in the database
    debug_query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic)
    RETURN 
        count(a) as total_relationships,
        count(CASE WHEN a.temporal_horizon IS NOT NULL THEN 1 END) as articles_with_old_props,
        count(CASE WHEN r.timeframe IS NOT NULL THEN 1 END) as relationships_with_new_props
    """
    debug_result = run_cypher(debug_query)
    if debug_result:
        logger.info(f"Database stats: {debug_result[0]}")
    
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic)
    WHERE a.temporal_horizon IS NOT NULL
      AND r.timeframe IS NULL
    RETURN a.id as article_id, 
           t.id as topic_id,
           a.temporal_horizon as old_timeframe,
           a.importance_risk as old_importance_risk,
           a.importance_opportunity as old_importance_opportunity,
           a.importance_trend as old_importance_trend,
           a.importance_catalyst as old_importance_catalyst
    """
    
    result = run_cypher(query)
    logger.info(f"Found {len(result) if result else 0} relationships needing migration")
    return result or []


def migrate_relationship(article_id: str, topic_id: str, old_data: dict):
    """
    Migrate one Article-ABOUT-Topic relationship.
    
    Steps:
    1. Get article summary and topic context
    2. Use LLM to generate motivation & implications
    3. Update relationship with all properties
    """
    
    logger.info(f"Migrating: {article_id} -> {topic_id}")
    
    try:
        # Load article for summary
        article = load_article(article_id)
        if not article or "argos_summary" not in article:
            logger.warning(f"Article {article_id} missing summary, using fallback")
            article_summary = "No summary available"
        else:
            article_summary = article["argos_summary"]
        
        # Get topic context
        topic_context = get_topic_context(topic_id)
        
        # Use LLM to generate motivation & implications
        logger.info(f"Generating motivation/implications for {article_id} -> {topic_id}")
        classification = classify_article_for_topic(
            article_summary=article_summary,
            topic_id=topic_id,
            topic_name=topic_context["name"],
            topic_analysis_snippet=topic_context["analysis_snippet"]
        )
        
        # Update relationship with all properties
        update_query = """
        MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
        SET r.timeframe = $timeframe,
            r.importance_risk = $importance_risk,
            r.importance_opportunity = $importance_opportunity,
            r.importance_trend = $importance_trend,
            r.importance_catalyst = $importance_catalyst,
            r.motivation = $motivation,
            r.implications = $implications,
            r.created_at = datetime()
        """
        
        run_cypher(update_query, {
            "article_id": article_id,
            "topic_id": topic_id,
            "timeframe": classification.timeframe,
            "importance_risk": classification.importance_risk,
            "importance_opportunity": classification.importance_opportunity,
            "importance_trend": classification.importance_trend,
            "importance_catalyst": classification.importance_catalyst,
            "motivation": classification.motivation,
            "implications": classification.implications
        })
        
        logger.info(
            f"✅ Migrated {article_id} -> {topic_id} | "
            f"timeframe={classification.timeframe} | "
            f"importance=(R:{classification.importance_risk} "
            f"O:{classification.importance_opportunity} "
            f"T:{classification.importance_trend} "
            f"C:{classification.importance_catalyst})"
        )
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate {article_id} -> {topic_id}: {e}")
        return False


def remove_old_article_properties():
    """
    Remove old classification properties from Article nodes.
    
    Only removes properties after relationships have been migrated.
    """
    
    # Check if any relationships still need migration
    check_query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic)
    WHERE a.temporal_horizon IS NOT NULL
      AND r.timeframe IS NULL
    RETURN count(r) as unmigrated_count
    """
    
    result = run_cypher(check_query)
    unmigrated_count = result[0]["unmigrated_count"] if result else 0
    
    if unmigrated_count > 0:
        logger.warning(
            f"⚠️ Cannot remove article properties yet - {unmigrated_count} relationships still need migration"
        )
        return False
    
    logger.info("All relationships migrated. Removing old article properties...")
    
    # Remove old properties from Article nodes
    cleanup_query = """
    MATCH (a:Article)
    WHERE a.temporal_horizon IS NOT NULL
    REMOVE a.temporal_horizon,
           a.type,
           a.priority,
           a.relevance_score,
           a.importance_risk,
           a.importance_opportunity,
           a.importance_trend,
           a.importance_catalyst,
           a.vector_id
    RETURN count(a) as cleaned_count
    """
    
    result = run_cypher(cleanup_query)
    cleaned_count = result[0]["cleaned_count"] if result else 0
    
    logger.info(f"✅ Cleaned {cleaned_count} article nodes")
    return True


def run_migration(batch_size: int = 10, max_articles: int = None):
    """
    Run the complete migration process.
    
    Args:
        batch_size: Number of relationships to migrate before logging progress
        max_articles: Maximum number to migrate (for testing), None = all
    """
    
    logger.info("=" * 80)
    logger.info("🚀 STARTING ARTICLE CLASSIFICATION MIGRATION")
    logger.info("=" * 80)
    
    # Get all relationships needing migration
    relationships = get_articles_needing_migration()
    
    if not relationships:
        logger.info("✅ No relationships need migration!")
        return
    
    total = len(relationships)
    if max_articles:
        relationships = relationships[:max_articles]
        logger.info(f"Limiting to {max_articles} relationships for testing")
    
    logger.info(f"Migrating {len(relationships)} relationships...")
    
    # Migrate each relationship
    success_count = 0
    error_count = 0
    
    for i, rel in enumerate(relationships, 1):
        article_id = rel["article_id"]
        topic_id = rel["topic_id"]
        
        old_data = {
            "timeframe": rel.get("old_timeframe"),
            "importance_risk": rel.get("old_importance_risk", 0),
            "importance_opportunity": rel.get("old_importance_opportunity", 0),
            "importance_trend": rel.get("old_importance_trend", 0),
            "importance_catalyst": rel.get("old_importance_catalyst", 0)
        }
        
        success = migrate_relationship(article_id, topic_id, old_data)
        
        if success:
            success_count += 1
        else:
            error_count += 1
        
        # Log progress every batch_size relationships
        if i % batch_size == 0:
            logger.info(
                f"Progress: {i}/{len(relationships)} | "
                f"Success: {success_count} | Errors: {error_count}"
            )
    
    logger.info("=" * 80)
    logger.info(f"✅ MIGRATION COMPLETE")
    logger.info(f"Total: {len(relationships)} | Success: {success_count} | Errors: {error_count}")
    logger.info("=" * 80)
    
    # Remove old properties from articles
    if error_count == 0:
        logger.info("Cleaning up old article properties...")
        remove_old_article_properties()
    else:
        logger.warning(
            f"⚠️ Skipping cleanup - {error_count} errors occurred. "
            "Fix errors and re-run migration."
        )


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Test mode: migrate only 5 relationships
            logger.info("🧪 TEST MODE: Migrating 5 relationships only")
            run_migration(batch_size=1, max_articles=5)
        elif sys.argv[1] == "--dry-run":
            # Dry run: just show what would be migrated
            logger.info("🔍 DRY RUN: Showing relationships that need migration")
            relationships = get_articles_needing_migration()
            for rel in relationships[:10]:
                logger.info(
                    f"Would migrate: {rel['article_id']} -> {rel['topic_id']} | "
                    f"timeframe={rel.get('old_timeframe')}"
                )
            if len(relationships) > 10:
                logger.info(f"... and {len(relationships) - 10} more")
        else:
            logger.error(f"Unknown argument: {sys.argv[1]}")
            logger.info("Usage: python migrate_article_classification_to_relationships.py [--test|--dry-run]")
    else:
        # Full migration
        logger.info("🚀 FULL MIGRATION MODE")
        run_migration(batch_size=10)
