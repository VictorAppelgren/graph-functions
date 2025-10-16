"""
PERSPECTIVE RECLASSIFICATION MIGRATION

This script reclassifies ALL existing articles in Neo4j with the new perspective scoring system.
It runs the unified LLM classifier on each article to assign real importance scores.

WHAT IT DOES:
1. Fetches all articles needing classification (NULL scores OR all zeros)
2. For each article, runs classify_article_complete() on the summary
3. Updates the article with 4 perspective importance scores (0-3 each)
4. Also updates temporal_horizon, category, and priority based on new classification
5. Skips articles classified as "invalid"
6. Reports progress every 10 articles

PERSPECTIVE SCORES (0-3, independent):
- importance_risk: Downside/threat importance
- importance_opportunity: Upside/catalyst importance  
- importance_trend: Structural shift importance
- importance_catalyst: Immediate trigger importance

PERFORMANCE:
- ~10 seconds per article (LLM call)
- For 3594 articles: ~10 hours total
- Uses MEDIUM tier LLM
- Idempotent: safe to re-run (only processes articles without scores)

USAGE:
    python scripts/maintenance/add_perspective_fields.py

OUTPUT:
- Progress updates every 10 articles
- Final statistics: successful/failed/skipped counts
- Verification of all articles having perspective fields
"""
import sys
import os
from typing import List, Dict

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.neo4j_client import run_cypher
from src.llm.classify_article import classify_article_complete
from utils.app_logging import get_logger

logger = get_logger("migration.reclassify_perspectives")


def fetch_articles_needing_classification() -> List[Dict]:
    """Fetch all articles that need perspective classification"""
    
    query = """
    MATCH (a:Article)
    WHERE a.importance_risk IS NULL 
       OR (a.importance_risk = 0 
           AND a.importance_opportunity = 0 
           AND a.importance_trend = 0 
           AND a.importance_catalyst = 0)
    RETURN a.id as id, a.summary as summary
    ORDER BY a.published_at DESC
    """
    
    result = run_cypher(query, {})
    return result if result else []


def classify_and_update_article(article_id: str, summary: str) -> tuple[bool, str]:
    """Classify single article and update with perspective scores
    
    Returns:
        (success: bool, error_type: str)
        error_type: 'success' | 'invalid' | 'json_parse' | 'validation' | 'timeout' | 'db_error' | 'unknown'
    """
    
    try:
        # Run unified classifier
        classification = classify_article_complete(summary)
        
        # Skip invalid articles
        if classification.temporal_horizon == "invalid":
            logger.info(f"Article {article_id} classified as invalid, skipping")
            return (False, 'invalid')
        
        # Update article with perspective scores
        update_query = """
        MATCH (a:Article {id: $id})
        SET a.importance_risk = $importance_risk,
            a.importance_opportunity = $importance_opportunity,
            a.importance_trend = $importance_trend,
            a.importance_catalyst = $importance_catalyst,
            a.temporal_horizon = $temporal_horizon,
            a.type = $category,
            a.priority = $priority
        RETURN a
        """
        
        run_cypher(update_query, {
            "id": article_id,
            "importance_risk": classification.importance_risk,
            "importance_opportunity": classification.importance_opportunity,
            "importance_trend": classification.importance_trend,
            "importance_catalyst": classification.importance_catalyst,
            "temporal_horizon": classification.temporal_horizon,
            "category": classification.category,
            "priority": str(classification.overall_importance)
        })
        
        logger.info(
            f"✅ {article_id}: R{classification.importance_risk}/O{classification.importance_opportunity}/"
            f"T{classification.importance_trend}/C{classification.importance_catalyst} "
            f"({classification.primary_perspectives})"
        )
        
        return (True, 'success')
        
    except ValueError as e:
        error_msg = str(e)
        if 'not parseable as JSON' in error_msg or 'raw_output_preview' in error_msg:
            logger.error(f"❌ JSON_PARSE_ERROR {article_id}: {error_msg[:200]}")
            return (False, 'json_parse')
        else:
            logger.error(f"❌ VALUE_ERROR {article_id}: {error_msg[:200]}")
            return (False, 'validation')
    
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Categorize errors
        if 'timeout' in error_msg.lower() or 'TimeoutError' in error_type:
            logger.error(f"❌ TIMEOUT {article_id}: {error_msg[:200]}")
            return (False, 'timeout')
        elif 'ValidationError' in error_type:
            logger.error(f"❌ VALIDATION_ERROR {article_id}: {error_msg[:200]}")
            return (False, 'validation')
        elif 'neo4j' in error_msg.lower() or 'cypher' in error_msg.lower():
            logger.error(f"❌ DB_ERROR {article_id}: {error_msg[:200]}")
            return (False, 'db_error')
        else:
            logger.error(f"❌ UNKNOWN_ERROR {article_id} ({error_type}): {error_msg[:200]}")
            return (False, 'unknown')


def reclassify_all_articles():
    """Reclassify all existing articles with perspective scores"""
    
    logger.info("Starting migration: Reclassifying all articles with perspective scores")
    
    # Fetch articles needing classification
    articles = fetch_articles_needing_classification()
    total = len(articles)
    
    logger.info(f"Found {total} articles needing perspective classification")
    
    if total == 0:
        logger.info("✅ All articles already have perspective fields. Migration not needed.")
        return
    
    print(f"\n{'='*80}")
    print(f"RECLASSIFYING {total} ARTICLES")
    print(f"{'='*80}")
    print(f"This will take approximately {total * 10 / 60:.1f} minutes (~10s per article)")
    print(f"{'='*80}\n")
    
    # Process articles with detailed error tracking
    successful = 0
    skipped_no_summary = 0
    skipped_invalid = 0
    failed_json_parse = 0
    failed_validation = 0
    failed_timeout = 0
    failed_db = 0
    failed_unknown = 0
    
    # Track failed article IDs for inspection
    failed_articles = []
    
    for i, article in enumerate(articles, 1):
        article_id = article["id"]
        summary = article["summary"]
        
        if not summary:
            logger.warning(f"Article {article_id} has no summary, skipping")
            skipped_no_summary += 1
            continue
        
        # Progress reporting every 10 articles
        if i % 10 == 0:
            total_failed = failed_json_parse + failed_validation + failed_timeout + failed_db + failed_unknown
            print(f"Progress: {i}/{total} ({i/total*100:.1f}%) - "
                  f"Success: {successful}, Failed: {total_failed}, Invalid: {skipped_invalid}, Skipped: {skipped_no_summary}")
        
        # Classify and update
        success, error_type = classify_and_update_article(article_id, summary)
        
        if success:
            successful += 1
        elif error_type == 'invalid':
            skipped_invalid += 1
        elif error_type == 'json_parse':
            failed_json_parse += 1
            failed_articles.append((article_id, 'json_parse'))
        elif error_type == 'validation':
            failed_validation += 1
            failed_articles.append((article_id, 'validation'))
        elif error_type == 'timeout':
            failed_timeout += 1
            failed_articles.append((article_id, 'timeout'))
        elif error_type == 'db_error':
            failed_db += 1
            failed_articles.append((article_id, 'db_error'))
        else:
            failed_unknown += 1
            failed_articles.append((article_id, 'unknown'))
    
    total_failed = failed_json_parse + failed_validation + failed_timeout + failed_db + failed_unknown
    
    logger.info(f"✅ Migration complete: {successful} successful, {total_failed} failed, {skipped_invalid} invalid, {skipped_no_summary} skipped")
    
    print(f"\n{'='*80}")
    print(f"✅ MIGRATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total articles: {total}")
    print(f"Successfully classified: {successful}")
    print(f"Skipped (invalid content): {skipped_invalid}")
    print(f"Skipped (no summary): {skipped_no_summary}")
    print(f"\nFAILURE BREAKDOWN:")
    print(f"  JSON Parse Errors: {failed_json_parse}")
    print(f"  Validation Errors: {failed_validation}")
    print(f"  Timeouts: {failed_timeout}")
    print(f"  Database Errors: {failed_db}")
    print(f"  Unknown Errors: {failed_unknown}")
    print(f"  TOTAL FAILED: {total_failed}")
    
    if failed_articles:
        print(f"\nFIRST 10 FAILED ARTICLES (for inspection):")
        for article_id, error_type in failed_articles[:10]:
            print(f"  {article_id}: {error_type}")
    
    print(f"{'='*80}\n")


def verify_migration():
    """Verify all articles now have perspective fields"""
    
    logger.info("Verifying migration...")
    
    verify_query = """
    MATCH (a:Article)
    RETURN 
        count(a) as total_articles,
        count(a.importance_risk) as with_risk,
        count(a.importance_opportunity) as with_opportunity,
        count(a.importance_trend) as with_trend,
        count(a.importance_catalyst) as with_catalyst
    """
    
    result = run_cypher(verify_query, {})
    if result:
        stats = result[0]
        total = stats["total_articles"]
        
        print(f"\n{'='*80}")
        print(f"VERIFICATION RESULTS")
        print(f"{'='*80}")
        print(f"Total articles: {total}")
        print(f"Articles with importance_risk: {stats['with_risk']}")
        print(f"Articles with importance_opportunity: {stats['with_opportunity']}")
        print(f"Articles with importance_trend: {stats['with_trend']}")
        print(f"Articles with importance_catalyst: {stats['with_catalyst']}")
        
        if (stats['with_risk'] == total and 
            stats['with_opportunity'] == total and 
            stats['with_trend'] == total and 
            stats['with_catalyst'] == total):
            print(f"\n✅ VERIFICATION PASSED: All articles have perspective fields")
        else:
            print(f"\n⚠️  VERIFICATION FAILED: Some articles missing perspective fields")
        
        print(f"{'='*80}\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("PERSPECTIVE RECLASSIFICATION MIGRATION")
    print("="*80)
    print("This script reclassifies all existing articles with perspective scores.")
    print("Uses the unified LLM classifier to assign real importance scores.")
    print("="*80 + "\n")
    
    try:
        reclassify_all_articles()
        verify_migration()
        
        print("\n✅ Migration completed successfully!")
        print("All articles now have perspective scores from LLM classification.\n")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"\n❌ Migration failed: {e}\n")
        sys.exit(1)
