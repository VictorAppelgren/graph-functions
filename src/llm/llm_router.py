"""LLM Router - Smart 4-tier routing system

4-Tier Architecture:
- SIMPLE: 20B model (local + :8686 + :8787) - Article ingestion, classification, relevance
- MEDIUM: 120B model (:3331) - Research writing, deeper analysis
- COMPLEX: DeepSeek v3.2 - Strategic reasoning, complex synthesis
- FAST: Anthropic Claude - User-facing chat, quick rewrites (expensive but fast)

Environment variables:
- DISABLE_LOCAL_LLM=true: Skip local server (for cloud deployment)
- LOCAL_LLM_ONLY=true: Only use local server (for offline/testing)
- DEEPSEEK_API_KEY: Required for COMPLEX tier
- ANTHROPIC_API_KEY: Required for FAST tier
"""

from src.llm.config import get_llm as _get_routed_llm, ModelTier
from langchain_core.runnables import Runnable
from langchain_core.messages import BaseMessage
from langchain_core.language_models import LanguageModelInput

from utils.app_logging import get_logger

logger = get_logger(__name__)


def get_llm(tier: ModelTier) -> Runnable[LanguageModelInput, BaseMessage]:
    """Get a LangChain-compatible LLM for the specified tier.

    Args:
        tier: The model tier to use:
            - SIMPLE: Article work (20B model, cheap)
            - MEDIUM: Research/writing (120B model)
            - COMPLEX: Strategic reasoning (DeepSeek v3.2)
            - FAST: User-facing (Anthropic Claude)
            - SIMPLE_LONG_CONTEXT: Deprecated, routes to SIMPLE

    Returns:
        A LangChain-compatible LLM instance (RoutedLLM)
    """
    # Route deprecated SIMPLE_LONG_CONTEXT to SIMPLE
    if tier == ModelTier.SIMPLE_LONG_CONTEXT:
        logger.debug("SIMPLE_LONG_CONTEXT tier -> routing as SIMPLE")
        tier = ModelTier.SIMPLE

    return _get_routed_llm(tier)


# Backward compatibility alias
get_llm_for_tier = get_llm
