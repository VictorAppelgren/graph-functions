"""
Orchestrator for article capacity management.
Handles removal/downgrade of articles when capacity limits are reached.
"""

from src.articles.policies.article_capacity_manager import article_capacity_manager_llm
from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic import get_topic_by_id
from src.graph.config import TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE
from src.observability.pipeline_logging import master_log, master_statistics
from utils.app_logging import get_logger

logger = get_logger(__name__)


def make_room_for_article(
    topic_id: str,
    new_article_id: str,
    new_article_summary: str,
    new_article_source: str,
    new_article_published: str,
    new_article_classification: dict,
    test: bool = False
) -> dict:
    """
    Make room for a new article by removing or downgrading an existing one.
    
    Args:
        topic_id: Topic to add article to
        new_article_id: ID of new article
        new_article_summary: Summary text for LLM
        new_article_source: Source name
        new_article_published: Published date
        new_article_classification: {
            "timeframe": "fundamental" | "medium" | "current",
            "overall_importance": 1-3,
            "dominant_perspective": "risk" | "opportunity" | "trend" | "catalyst",
            "importance_risk": 0-3,
            "importance_opportunity": 0-3,
            "importance_trend": 0-3,
            "importance_catalyst": 0-3
        }
        test: If True, skip actual DB operations
    
    Returns:
        {
            "action": "remove" | "downgrade" | "reject",
            "target_article_id": str | None,
            "new_importance": int | None,
            "motivation": str
        }
    """
    
    timeframe = new_article_classification["timeframe"]
    importance = new_article_classification["overall_importance"]
    
    # Query existing articles in same timeframe + importance tier
    query = """
    MATCH (t:Topic {id: $topic_id})<-[r:ABOUT]-(a:Article)
    WHERE r.timeframe = $timeframe
      AND (r.importance_risk >= $importance 
           OR r.importance_opportunity >= $importance
           OR r.importance_trend >= $importance
           OR r.importance_catalyst >= $importance)
    RETURN 
        a.id as id,
        a.argos_summary as summary,
        a.source as source,
        a.published_at as published_at,
        r.importance_risk as risk,
        r.importance_opportunity as opp,
        r.importance_trend as trend,
        r.importance_catalyst as cat,
        r.timeframe as timeframe,
        r.motivation as motivation,
        r.created_at as created_at
    ORDER BY r.created_at DESC
    LIMIT 15
    """
    
    existing_articles = run_cypher(query, {
        "topic_id": topic_id,
        "timeframe": timeframe,
        "importance": importance
    })
    
    if not existing_articles:
        logger.info(f"No existing articles found for comparison. Accepting new article.")
        return {
            "action": "accept",
            "target_article_id": None,
            "new_importance": None,
            "motivation": "No existing articles to compare"
        }
    
    # Get topic context
    topic_info = get_topic_by_id(topic_id)
    
    # Call LLM to decide
    decision = article_capacity_manager_llm(
        topic_name=topic_info["name"],
        new_article_id=new_article_id,
        new_article_summary=new_article_summary,
        new_article_source=new_article_source,
        new_article_published=new_article_published,
        new_article_classification=new_article_classification,
        existing_articles=existing_articles,
        capacity_status={
            "timeframe": timeframe,
            "importance_tier": importance,
            "current_count": len(existing_articles),
            "max_allowed": TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE[importance]
        },
        test=test
    )
    
    # Execute decision
    if decision.action == "remove":
        if not test:
            # Remove the ABOUT relationship (not the article node)
            remove_query = """
            MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
            DELETE r
            """
            run_cypher(remove_query, {
                "article_id": decision.target_article_id,
                "topic_id": topic_id
            })
            
            master_log(
                f"Removed article link | {decision.target_article_id} | "
                f"from topic {topic_id} | reason: {decision.motivation}"
            )
            master_statistics(about_links_removed=1, articles_replaced_by_capacity=1)
        
        logger.info(
            f"Removed article {decision.target_article_id} from topic {topic_id} "
            f"to make room for {new_article_id}"
        )
        
    elif decision.action == "downgrade":
        # Check if target tier has capacity before downgrading
        target_tier = decision.new_importance
        
        if not test:
            # Check current count in target tier
            target_tier_query = """
            MATCH (t:Topic {id: $topic_id})<-[r:ABOUT]-(a:Article)
            WHERE r.timeframe = $timeframe
              AND (r.importance_risk >= $importance 
                   OR r.importance_opportunity >= $importance
                   OR r.importance_trend >= $importance
                   OR r.importance_catalyst >= $importance)
            RETURN count(a) as count
            """
            
            target_tier_result = run_cypher(target_tier_query, {
                "topic_id": topic_id,
                "timeframe": timeframe,
                "importance": target_tier
            })
            
            target_tier_count = target_tier_result[0]["count"] if target_tier_result else 0
            target_tier_max = TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE[target_tier]
            
            # If target tier is at capacity, we need to make room there first
            if target_tier_count >= target_tier_max:
                logger.warning(
                    f"Target tier {target_tier} is at capacity ({target_tier_count}/{target_tier_max}). "
                    f"Making room before downgrading article {decision.target_article_id}"
                )
                
                # Get the article we're about to downgrade to use as the "new" article for lower tier
                downgraded_article_query = """
                MATCH (a:Article {id: $article_id})
                RETURN a.argos_summary as summary, a.source as source, a.published_at as published_at
                """
                downgraded_article = run_cypher(downgraded_article_query, {"article_id": decision.target_article_id})
                
                if downgraded_article:
                    # Recursively make room in the target tier
                    # Note: We use the downgraded article's info as the "new" article
                    cascade_result = make_room_for_article(
                        topic_id=topic_id,
                        new_article_id=decision.target_article_id,
                        new_article_summary=downgraded_article[0].get("summary", ""),
                        new_article_source=downgraded_article[0].get("source", "unknown"),
                        new_article_published=downgraded_article[0].get("published_at", "unknown"),
                        new_article_classification={
                            "timeframe": timeframe,
                            "overall_importance": target_tier,
                            "dominant_perspective": new_article_classification["dominant_perspective"],
                            "importance_risk": target_tier,
                            "importance_opportunity": target_tier,
                            "importance_trend": target_tier,
                            "importance_catalyst": target_tier,
                        },
                        test=test
                    )
                    
                    if cascade_result["action"] == "reject":
                        # Can't make room in lower tier, so reject the downgrade
                        logger.warning(
                            f"Cannot downgrade article {decision.target_article_id} - "
                            f"target tier {target_tier} has no room"
                        )
                        return {
                            "action": "reject",
                            "target_article_id": None,
                            "new_importance": None,
                            "motivation": f"Cannot downgrade - tier {target_tier} at capacity"
                        }
            
            # Now perform the downgrade
            downgrade_query = """
            MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
            SET 
                r.importance_risk = CASE WHEN r.importance_risk > $new_importance THEN $new_importance ELSE r.importance_risk END,
                r.importance_opportunity = CASE WHEN r.importance_opportunity > $new_importance THEN $new_importance ELSE r.importance_opportunity END,
                r.importance_trend = CASE WHEN r.importance_trend > $new_importance THEN $new_importance ELSE r.importance_trend END,
                r.importance_catalyst = CASE WHEN r.importance_catalyst > $new_importance THEN $new_importance ELSE r.importance_catalyst END,
                r.downgraded_at = datetime(),
                r.downgrade_reason = $reason
            """
            run_cypher(downgrade_query, {
                "article_id": decision.target_article_id,
                "topic_id": topic_id,
                "new_importance": decision.new_importance,
                "reason": decision.motivation
            })
            
            master_log(
                f"Downgraded article | {decision.target_article_id} | "
                f"to importance {decision.new_importance} | reason: {decision.motivation}"
            )
            master_statistics(articles_downgraded=1)
        
        logger.info(
            f"Downgraded article {decision.target_article_id} to importance {decision.new_importance} "
            f"to make room for {new_article_id}"
        )
    
    # Return decision dict
    return {
        "action": decision.action,
        "target_article_id": decision.target_article_id,
        "new_importance": decision.new_importance,
        "motivation": decision.motivation
    }
