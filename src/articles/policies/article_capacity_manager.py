"""
LLM policy for article capacity management decisions.
Decides whether to downgrade an existing article or reject when adding new article at capacity.
"""

from typing import Any
from langchain_core.prompts import PromptTemplate

from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision, ArticleCapacityDecision
from src.llm.prompts.system_prompts import SYSTEM_MISSION
from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT
from src.articles.prompts.article_capacity_manager import ARTICLE_CAPACITY_MANAGER_PROMPT
from utils.app_logging import get_logger

logger = get_logger(__name__)


def article_capacity_manager_llm(
    topic_name: str,
    new_article_id: str,
    new_article_summary: str,
    new_article_source: str,
    new_article_published: str,
    new_article_classification: dict[str, Any],
    existing_articles: list[dict[str, Any]],
    capacity_status: dict[str, Any],
    test: bool = False
) -> ArticleCapacityDecision:
    """
    LLM decides whether to add new article and what to remove/downgrade.
    
    Args:
        topic_name: Name of the topic
        new_article_id: ID of new article
        new_article_summary: Summary text
        new_article_source: Source name
        new_article_published: Published date
        new_article_classification: {
            "timeframe": str,
            "overall_importance": int,
            "dominant_perspective": str,
            "importance_risk": int,
            "importance_opportunity": int,
            "importance_trend": int,
            "importance_catalyst": int
        }
        existing_articles: List of dicts with:
            - id: str
            - summary: str
            - source: str
            - published_at: str
            - risk: int
            - opp: int
            - trend: int
            - cat: int
            - timeframe: str
            - motivation: str
        capacity_status: {
            "timeframe": str,
            "importance_tier": int,
            "current_count": int,
            "max_allowed": int
        }
        test: If True, return mock decision
    
    Returns:
        ArticleCapacityDecision with action, target_article_id, new_importance
    """
    
    if test:
        return ArticleCapacityDecision(
            motivation="Test mode: no action",
            action="reject",
            target_article_id=None,
            new_importance=None
        )
    
    # Format existing articles for prompt (cap at 50 to keep prompt size safe)
    MAX_LLM_ARTICLES = 50
    prompt_articles = existing_articles[:MAX_LLM_ARTICLES]

    articles_formatted = []
    for i, article in enumerate(prompt_articles, 1):
        max_imp = max(article['risk'], article['opp'], article['trend'], article['cat'])
        
        # Determine dominant perspective
        scores = {
            'risk': article['risk'],
            'opportunity': article['opp'],
            'trend': article['trend'],
            'catalyst': article['cat']
        }
        dominant = max(scores, key=scores.get)
        
        articles_formatted.append(
            f"{i}. ID: {article['id']}\n"
            f"   Source: {article.get('source', 'unknown')}\n"
            f"   Published: {article.get('published_at', 'unknown')}\n"
            f"   Summary: {article['summary'][:200]}...\n"
            f"   Dominant Perspective: {dominant}\n"
            f"   Importance Scores: Risk={article['risk']}, Opportunity={article['opp']}, Trend={article['trend']}, Catalyst={article['cat']}\n"
            f"   Overall Importance: {max_imp}\n"
            f"   Classification Reason: {article.get('motivation', 'N/A')[:150]}"
        )
    
    allowed_ids_str = ", ".join([a["id"] for a in prompt_articles])
    
    # Build prompt
    prompt_text = ARTICLE_CAPACITY_MANAGER_PROMPT.format(
        system_mission=SYSTEM_MISSION,
        architecture_context=TOPIC_ARCHITECTURE_CONTEXT,
        topic_name=topic_name,
        timeframe=capacity_status["timeframe"],
        importance_tier=capacity_status["importance_tier"],
        current_count=capacity_status["current_count"],
        max_allowed=capacity_status["max_allowed"],
        new_article_id=new_article_id,
        new_article_source=new_article_source,
        new_article_published=new_article_published,
        new_article_summary=new_article_summary,
        dominant_perspective=new_article_classification["dominant_perspective"],
        risk=new_article_classification["importance_risk"],
        opp=new_article_classification["importance_opportunity"],
        trend=new_article_classification["importance_trend"],
        cat=new_article_classification["importance_catalyst"],
        existing_articles_formatted="\n\n".join(articles_formatted),
        allowed_ids_str=allowed_ids_str
    )
    
    # Get LLM
    llm = get_llm(ModelTier.SIMPLE)
    
    # Call LLM with sanitizer
    logger.info(
        f"Calling article capacity manager LLM | topic={topic_name} | "
        f"timeframe={capacity_status['timeframe']} | tier={capacity_status['importance_tier']}"
    )
    
    decision = run_llm_decision(
        chain=llm,
        prompt=prompt_text,
        model=ArticleCapacityDecision
    )
    
    # Validate target_article_id is in allowed list
    if decision.action == "downgrade":
        valid_ids = {a["id"] for a in prompt_articles}
        if decision.target_article_id not in valid_ids:
            logger.warning(
                f"LLM selected invalid article ID: {decision.target_article_id}. "
                f"Defaulting to reject."
            )
            decision.action = "reject"
            decision.target_article_id = None
            decision.new_importance = None
    
    logger.info(
        f"Article capacity decision | action={decision.action} | "
        f"target={decision.target_article_id} | motivation={decision.motivation[:100]}"
    )
    
    return decision
