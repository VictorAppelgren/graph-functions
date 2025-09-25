"""LLM Router - Drop-in replacement with new smart routing

This module provides the same interface as the old llm_router but uses
the new smart routing system from config.py under the hood.

Maintains backward compatibility while adding:
- Smart local vs external routing based on token count
- Automatic busy status tracking
- Round-robin load balancing for external servers
"""

from src.llm.config import get_llm as _get_routed_llm, ModelTier
from langchain_core.runnables import Runnable
from langchain_core.messages import BaseMessage
from langchain_core.language_models import LanguageModelInput

from utils.app_logging import get_logger

logger = get_logger(__name__)


def get_llm(tier: ModelTier) -> Runnable[LanguageModelInput, BaseMessage]:
    """Get a LangChain-compatible LLM for the specified tier.
    
    Perfect drop-in replacement for the old get_llm function with smart routing:
    - Exact same API: get_llm(tier) -> llm.invoke(text)
    - Smart routing happens at invoke() time based on actual input size
    - Respects TOKEN_THRESHOLD for laptop-friendly routing
    - Round-robin load balancing across external servers
    
    Args:
        tier: The model tier to use (SIMPLE, MEDIUM, COMPLEX, SIMPLE_LONG_CONTEXT)
        
    Returns:
        A LangChain-compatible LLM instance (RoutedLLM that inherits from Runnable)
    """
    
    # Route SIMPLE_LONG_CONTEXT to SIMPLE (same as MEDIUM → SIMPLE)
    if tier == ModelTier.SIMPLE_LONG_CONTEXT:
        logger.debug("SIMPLE_LONG_CONTEXT tier → routing as SIMPLE")
        tier = ModelTier.SIMPLE
    
    # Get the smart routed LLM from the new config system
    routed_llm = _get_routed_llm(tier)
    
    # Return the RoutedLLM directly - it now properly inherits from Runnable
    # and routes intelligently at invoke() time for true drop-in compatibility
    return routed_llm


# Backward compatibility alias
get_llm_for_tier = get_llm
