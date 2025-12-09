"""
Orchestrator for article capacity management.
Handles removal/downgrade of articles when capacity limits are reached.
"""

from src.articles.policies.article_capacity_manager import article_capacity_manager_llm
from src.graph.neo4j_client import run_cypher
from src.graph.ops.topic import get_topic_by_id
from src.graph.config import TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE
from src.observability.stats_client import track
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
    
    # Query existing articles in same timeframe + importance tier (exclude archived)
    query = """
    MATCH (t:Topic {id: $topic_id})<-[r:ABOUT]-(a:Article)
    WHERE r.timeframe = $timeframe
      AND (r.importance_risk >= $importance 
           OR r.importance_opportunity >= $importance
           OR r.importance_trend >= $importance
           OR r.importance_catalyst >= $importance)
      AND NOT (r.importance_risk = 0 
               AND r.importance_opportunity = 0 
               AND r.importance_trend = 0 
               AND r.importance_catalyst = 0)
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
    if decision.action == "downgrade":
        # Check if target tier has capacity before downgrading
        target_tier = decision.new_importance
        
        if not test:
            # Special case: tier 0 = archive (no capacity check needed)
            if target_tier == 0:
                archive_query = """
                MATCH (a:Article {id: $article_id})-[r:ABOUT]->(t:Topic {id: $topic_id})
                SET 
                    r.importance_risk = 0,
                    r.importance_opportunity = 0,
                    r.importance_trend = 0,
                    r.importance_catalyst = 0
                """
                run_cypher(archive_query, {
                    "article_id": decision.target_article_id,
                    "topic_id": topic_id
                })
                
                track("article_archived", 
                      f"Article {decision.target_article_id} archived (tier 0): {decision.motivation}")
                
                logger.info(
                    f"Archived article {decision.target_article_id} (downgraded to tier 0) "
                    f"to make room for {new_article_id}"
                )
            else:
                # Normal downgrade: check target tier capacity
                target_tier_query = """
                MATCH (t:Topic {id: $topic_id})<-[r:ABOUT]-(a:Article)
                WHERE r.timeframe = $timeframe
                  AND (r.importance_risk >= $importance 
                       OR r.importance_opportunity >= $importance
                       OR r.importance_trend >= $importance
                       OR r.importance_catalyst >= $importance)
                  AND NOT (r.importance_risk = 0 
                           AND r.importance_opportunity = 0 
                           AND r.importance_trend = 0 
                           AND r.importance_catalyst = 0)
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
                
                track("article_downgraded",
                      f"Article {decision.target_article_id} downgraded to {decision.new_importance}: {decision.motivation}")
                
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


# ============================================================================
# NEW: Two-Stage Capacity Management Functions
# ============================================================================

def check_capacity(topic_id: str, timeframe: str, tier: int) -> dict:
    """
    Check capacity at this tier.
    
    AUTO-CLEANUP: If tier is over capacity, automatically downgrades
    weakest articles using LLM quality assessment until within limits.
    This ensures the system self-heals over time.
    
    Returns:
        {
            "has_room": bool,
            "count": int,
            "max": int,
            "articles": list[dict]
        }
    """
    max_allowed = TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE[tier]
    
    # Get articles at EXACTLY this tier (max perspective = tier, not higher)
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WHERE r.timeframe = $timeframe
      AND (r.importance_risk = $tier 
           OR r.importance_opportunity = $tier
           OR r.importance_trend = $tier
           OR r.importance_catalyst = $tier)
      AND NOT (r.importance_risk > $tier 
               OR r.importance_opportunity > $tier
               OR r.importance_trend > $tier
               OR r.importance_catalyst > $tier)
      AND NOT (r.importance_risk = 0 
               AND r.importance_opportunity = 0 
               AND r.importance_trend = 0 
               AND r.importance_catalyst = 0)
    RETURN 
        a.id as id,
        a.summary as summary,
        a.source as source,
        a.published_at as published_at
    ORDER BY a.published_at DESC
    """
    
    articles = run_cypher(query, {
        "topic_id": topic_id,
        "timeframe": timeframe,
        "tier": tier
    })
    
    count = len(articles) if articles else 0
    
    # ============================================================================
    # AUTO-CLEANUP: If over capacity, use LLM to downgrade weakest articles
    # ============================================================================
    if count > max_allowed:
        excess = count - max_allowed
        logger.warning(
            f"🔧 AUTO-CLEANUP: topic={topic_id} | timeframe={timeframe} | tier={tier} "
            f"over capacity ({count}/{max_allowed}). Using LLM to downgrade "
            f"{excess} weakest articles..."
        )
        
        # Import here to avoid circular dependency
        from src.graph.ops.link import set_about_link_tier

        # Downgrade excess articles one by one using LLM quality assessment
        for i in range(excess):
            # Re-query each time (list changes as we downgrade)
            current_articles = run_cypher(query, {
                "topic_id": topic_id,
                "timeframe": timeframe,
                "tier": tier
            })

            current_count = len(current_articles)
            if current_count <= max_allowed:
                logger.info(f"✅ Auto-cleanup complete after {i} downgrades")
                break  # Done!

            # Use LLM to pick weakest article
            weakest_result = pick_weakest_article(
                topic_id=topic_id,
                timeframe=timeframe,
                tier=tier,
                existing_articles=current_articles,
                test=False,  # Real LLM call for quality assessment
            )

            weakest_id = weakest_result["downgrade"]
            reasoning = weakest_result.get("reasoning", "No reason provided")

            logger.info(
                f"  [{i+1}/{excess}] Downgrading weakest: {weakest_id} "
                f"(Reason: {reasoning[:100]}...)"
            )

            # Move the weakest article down one tier IN PLACE (keep ABOUT link)
            new_tier = max(tier - 1, 0)
            set_about_link_tier(weakest_id, topic_id, timeframe, new_tier)
            track(
                "article_downgraded",
                f"Article {weakest_id} downgraded in-place from tier {tier} to tier {new_tier} in topic {topic_id}",
            )

            if new_tier == 0:
                logger.info(
                    f"    → Moved {weakest_id} to tier 0 (ABOUT retained; all importance_* = 0)"
                )
            else:
                logger.info(
                    f"    → Moved {weakest_id} from tier {tier} to tier {new_tier} (ABOUT retained)"
                )

        logger.info(
            f"✅ Auto-cleanup complete. Attempted to downgrade {excess} articles from tier {tier}."
        )
        
        # Re-query after cleanup
        articles = run_cypher(query, {
            "topic_id": topic_id,
            "timeframe": timeframe,
            "tier": tier
        })
        count = len(articles)
    
    return {
        "has_room": count < max_allowed,
        "count": count,
        "max": max_allowed,
        "articles": articles or []
    }


def check_capacity_per_perspective(
    topic_id: str,
    timeframe: str,
    perspective: str,
    tier: int,
) -> dict:
    """Check capacity for a single (timeframe, perspective, tier) bucket.

    AUTO-CLEANUP: If this perspective bucket is over capacity, automatically
    downgrades weakest articles using LLM quality assessment until within
    limits, downgrading tiers in-place via set_about_link_tier.

    Returns:
        {
            "has_room": bool,
            "count": int,
            "max": int,
            "articles": list[dict]
        }
    """
    max_allowed = TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE[tier]

    # Get articles where THIS perspective is exactly at this tier
    query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WITH a, r,
         CASE $perspective
             WHEN 'risk'        THEN coalesce(r.importance_risk, 0)
             WHEN 'opportunity' THEN coalesce(r.importance_opportunity, 0)
             WHEN 'trend'       THEN coalesce(r.importance_trend, 0)
             WHEN 'catalyst'    THEN coalesce(r.importance_catalyst, 0)
             ELSE 0
         END AS p_tier
    WHERE r.timeframe = $timeframe
      AND p_tier = $tier
      AND NOT (
          coalesce(r.importance_risk, 0) = 0 AND
          coalesce(r.importance_opportunity, 0) = 0 AND
          coalesce(r.importance_trend, 0) = 0 AND
          coalesce(r.importance_catalyst, 0) = 0
      )
    RETURN
        a.id as id,
        a.summary as summary,
        a.source as source,
        a.published_at as published_at
    ORDER BY a.published_at DESC
    """

    articles = run_cypher(
        query,
        {
            "topic_id": topic_id,
            "timeframe": timeframe,
            "perspective": perspective,
            "tier": tier,
        },
    )

    count = len(articles) if articles else 0

    if count > max_allowed:
        excess = count - max_allowed
        logger.warning(
            f"🔧 AUTO-CLEANUP (perspective): topic={topic_id} | timeframe={timeframe} | "
            f"perspective={perspective} | tier={tier} over capacity ({count}/{max_allowed}). "
            f"Using LLM to downgrade {excess} weakest articles..."
        )

        from src.graph.ops.link import set_about_link_tier

        for i in range(excess):
            current_articles = run_cypher(
                query,
                {
                    "topic_id": topic_id,
                    "timeframe": timeframe,
                    "perspective": perspective,
                    "tier": tier,
                },
            )

            current_count = len(current_articles)
            if current_count <= max_allowed:
                logger.info(
                    f"✅ Perspective auto-cleanup complete after {i} downgrades "
                    f"for perspective={perspective}"
                )
                break

            weakest_result = pick_weakest_article(
                topic_id=topic_id,
                timeframe=timeframe,
                tier=tier,
                existing_articles=current_articles,
                test=False,
            )

            weakest_id = weakest_result["downgrade"]
            reasoning = weakest_result.get("reasoning", "No reason provided")

            logger.info(
                f"  [{i+1}/{excess}] Downgrading weakest (perspective={perspective}): "
                f"{weakest_id} (Reason: {reasoning[:100]}...)"
            )

            new_tier = max(tier - 1, 0)
            set_about_link_tier(weakest_id, topic_id, timeframe, new_tier)
            track(
                "article_downgraded",
                f"Article {weakest_id} downgraded in-place from tier {tier} to {new_tier} "
                f"in topic {topic_id} (perspective={perspective})",
            )

            if new_tier == 0:
                logger.info(
                    f"    → Moved {weakest_id} to tier 0 (ABOUT retained; all importance_* = 0)"
                )
            else:
                logger.info(
                    f"    → Moved {weakest_id} from tier {tier} to tier {new_tier} (ABOUT retained)"
                )

        logger.info(
            f"✅ Perspective auto-cleanup complete. Attempted to downgrade {excess} "
            f"articles from tier {tier} for perspective={perspective}."
        )

        articles = run_cypher(
            query,
            {
                "topic_id": topic_id,
                "timeframe": timeframe,
                "perspective": perspective,
                "tier": tier,
            },
        )
        count = len(articles)

    return {
        "has_room": count < max_allowed,
        "count": count,
        "max": max_allowed,
        "articles": articles or [],
    }


def gate_decision(
    topic_id: str,
    timeframe: str,
    tier: int,
    new_article_summary: str,
    new_article_source: str,
    new_article_published: str,
    existing_articles: list[dict],
    test: bool = False
) -> dict:
    """
    Stage 1: Gate decision with reject option.
    
    Returns:
        {
            "downgrade": str,  # "NEW" or existing ID
            "reject": bool,
            "reasoning": str
        }
    """
    if test:
        return {"downgrade": "NEW", "reject": False, "reasoning": "Test mode"}
    
    from src.llm.llm_router import get_llm
    from src.llm.config import ModelTier
    from src.llm.sanitizer import run_llm_decision, DowngradeDecision
    from src.articles.prompts.article_capacity_manager import ARTICLE_CAPACITY_MANAGER_PROMPT
    from src.llm.prompts.system_prompts import SYSTEM_MISSION
    from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT
    
    topic_info = get_topic_by_id(topic_id)
    
    # Format existing articles for prompt (cap at 50 to keep prompt size safe)
    MAX_LLM_ARTICLES = 50
    prompt_articles = existing_articles[:MAX_LLM_ARTICLES]

    articles_formatted = []
    for i, article in enumerate(prompt_articles, 1):
        articles_formatted.append(
            f"{i}. ID: {article['id']}\n"
            f"   Source: {article.get('source', 'unknown')}\n"
            f"   Published: {article.get('published_at', 'unknown')}\n"
            f"   Summary: {article['summary'][:200]}..."
        )
    
    allowed_ids = ", ".join([a["id"] for a in prompt_articles])
    
    prompt = ARTICLE_CAPACITY_MANAGER_PROMPT.format(
        system_mission=SYSTEM_MISSION,
        architecture_context=TOPIC_ARCHITECTURE_CONTEXT,
        topic_name=topic_info["name"],
        timeframe=timeframe,
        tier=tier,
        next_tier=tier - 1,
        count=len(existing_articles),
        max_allowed=TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE[tier],
        new_source=new_article_source,
        new_published=new_article_published,
        new_summary=new_article_summary,
        existing_articles="\n\n".join(articles_formatted),
        allowed_ids=allowed_ids
    )
    
    llm = get_llm(ModelTier.SIMPLE)
    decision = run_llm_decision(chain=llm, prompt=prompt, model=DowngradeDecision)
    
    # Validate downgrade ID (must be one of the prompt_articles IDs, not NEW)
    valid_ids = {a["id"] for a in prompt_articles}
    if decision.downgrade not in valid_ids and decision.downgrade != "NEW":
        logger.warning(f"LLM returned invalid ID: {decision.downgrade}, defaulting to NEW")
        decision.downgrade = "NEW"
    
    logger.info(
        f"Gate decision for tier {tier}: "
        f"downgrade={decision.downgrade}, reject={decision.reject} - {decision.reasoning}"
    )
    
    return {
        "downgrade": decision.downgrade,
        "reject": decision.reject,
        "reasoning": decision.reasoning
    }


def pick_weakest_article(
    topic_id: str,
    timeframe: str,
    tier: int,
    existing_articles: list[dict],
    test: bool = False
) -> dict:
    """
    Stage 2: Pick weakest article (no reject option).
    
    Returns:
        {
            "downgrade": str,  # Existing article ID
            "reasoning": str
        }
    """
    if test:
        return {
            "downgrade": existing_articles[0]["id"],
            "reasoning": "Test mode - picked first article"
        }
    
    from src.llm.llm_router import get_llm
    from src.llm.config import ModelTier
    from src.llm.sanitizer import run_llm_decision, DowngradeDecision
    from src.articles.prompts.article_capacity_pick_weakest import ARTICLE_CAPACITY_PICK_WEAKEST_PROMPT
    from src.llm.prompts.system_prompts import SYSTEM_MISSION
    from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT
    
    topic_info = get_topic_by_id(topic_id)
    
    # Format existing articles for prompt (cap at 50 to keep prompt size safe)
    MAX_LLM_ARTICLES = 50
    prompt_articles = existing_articles[:MAX_LLM_ARTICLES]

    articles_formatted = []
    for i, article in enumerate(prompt_articles, 1):
        articles_formatted.append(
            f"{i}. ID: {article['id']}\n"
            f"   Source: {article.get('source', 'unknown')}\n"
            f"   Published: {article.get('published_at', 'unknown')}\n"
            f"   Summary: {article['summary'][:200]}..."
        )
    
    allowed_ids = ", ".join([a["id"] for a in prompt_articles])
    
    prompt = ARTICLE_CAPACITY_PICK_WEAKEST_PROMPT.format(
        system_mission=SYSTEM_MISSION,
        architecture_context=TOPIC_ARCHITECTURE_CONTEXT,
        topic_name=topic_info["name"],
        timeframe=timeframe,
        tier=tier,
        next_tier=tier - 1,
        existing_articles="\n\n".join(articles_formatted),
        allowed_ids=allowed_ids
    )
    
    llm = get_llm(ModelTier.SIMPLE)
    decision = run_llm_decision(chain=llm, prompt=prompt, model=DowngradeDecision)
    
    # Validate downgrade ID (must be one of the prompt_articles IDs, not NEW)
    valid_ids = {a["id"] for a in prompt_articles}
    if decision.downgrade not in valid_ids:
        logger.warning(f"LLM returned invalid ID: {decision.downgrade}, picking first article")
        decision.downgrade = prompt_articles[0]["id"]
    
    logger.info(f"Picked weakest article: {decision.downgrade} - {decision.reasoning}")
    
    return {
        "downgrade": decision.downgrade,
        "reasoning": decision.reasoning
    }
