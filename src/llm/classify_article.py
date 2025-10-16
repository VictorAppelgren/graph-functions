"""
Unified article classifier - replaces find_time_frame, find_category, find_impact
Single LLM call returns complete classification with 4 perspective scores
"""
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.prompts.classify_article_complete import CLASSIFY_ARTICLE_COMPLETE_PROMPT
from src.llm.sanitizer import run_llm_decision
from src.llm.models import ArticleClassification
from utils.app_logging import get_logger

logger = get_logger("llm.classify_article")

CATEGORIES = [
    "macro_event",
    "policy",
    "market_data",
    "corporate",
    "geopolitical",
    "economic_data",
    "central_bank",
    "other"
]


def classify_article_complete(article_text: str) -> ArticleClassification:
    """
    Complete article classification in single LLM call.
    
    Returns all fields:
    - temporal_horizon: fundamental/medium/current/invalid
    - category: article type
    - importance_risk: 0-3
    - importance_opportunity: 0-3
    - importance_trend: 0-3
    - importance_catalyst: 0-3
    
    Note: Scores are INDEPENDENT - article can score 3 on all 4 perspectives!
    """
    logger.info("Calling unified classifier")
    
    llm = get_llm(ModelTier.MEDIUM)
    
    prompt = CLASSIFY_ARTICLE_COMPLETE_PROMPT.format(
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT,
        article_text=article_text[:5000],  # Limit to 5k chars
        categories=", ".join(CATEGORIES)
    )
    
    result = run_llm_decision(
        chain=llm,
        prompt=prompt,
        model=ArticleClassification
    )
    
    logger.info(
        f"Classification: horizon={result.temporal_horizon}, "
        f"category={result.category}, "
        f"perspectives={result.primary_perspectives}, "
        f"scores=R{result.importance_risk}/O{result.importance_opportunity}/"
        f"T{result.importance_trend}/C{result.importance_catalyst}, "
        f"overall={result.overall_importance}"
    )
    
    return result
