"""Model Configuration for Argos Research Platform

Minimal, single-responsibility LLM configuration with per-request timeouts
and Runnable-level retries via `.with_retry()`.

PLANNED EVOLUTION - Multi-Backend LLM Router:
Current: Simple tier-based model selection with hardcoded endpoints
Target: SQLite-based router with multi-backend support:
- Backend types: openai_api (SDK), vllm_http (custom servers), ollama_local
- Pools: short/long based on token estimates, with automatic backend selection
- Features: Automatic failover, load balancing, passive health monitoring
- Policy: Prefer idle backends, fallback to working ones, fail_count cooldowns
- Routing: Token gate (4k threshold) → pool selection → backend acquisition
- Adapters: Type-specific call handlers (HTTP, SDK, local) with unified interface
- Logging: Acquire/release events with timing, tokens, success/failure tracking
- Schema: backends table with type, endpoint, model_name, max_context, status, inflight
"""

import os
from src.llm.config import ModelTier, DEFAULT_CONFIG
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable
from langchain_core.messages import BaseMessage
from langchain_core.language_models import LanguageModelInput

# Set up API keys from environment variables if available
# Otherwise, these will need to be set by the user

# API keys (if needed) should be provided via environment variables externally.

from utils.app_logging import get_logger

logger = get_logger(__name__)

# My OpenAI API key
os.environ.setdefault(
    "OPENAI_API_KEY",
    "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",
)  # User will need to set this

# --- LLM call policy (per-request) ---
_LLM_CALL_TIMEOUT_S = 300.0  # 5 minutes per request
_LLM_RETRY_ATTEMPTS = 3  # total attempts via with_retry()


def _build_llm(
    provider: str, model: str, temperature: float, base_url: str | None
) -> Runnable[LanguageModelInput, BaseMessage]:
    """Construct a LangChain LLM client for the given provider (no network call)."""
    if provider == "ollama":
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_ctx=49152,
            timeout=int(_LLM_CALL_TIMEOUT_S),
            request_timeout=_LLM_CALL_TIMEOUT_S,
        ).with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)

    elif provider == "openai":
        kwargs = dict(
            model=model,
            temperature=temperature,
            timeout=_LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )

        if base_url:
            kwargs["base_url"] = base_url

        return ChatOpenAI(
            **kwargs
        ).with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)

    elif provider == "anthropic":
        return ChatAnthropic(
            model_name=model,
            temperature=temperature,
            timeout=_LLM_CALL_TIMEOUT_S,
            max_retries=0,
            stop=None,
        ).with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_llm(tier: ModelTier) -> Runnable[LanguageModelInput, BaseMessage]:

    """Get a LangChain-compatible LLM for the specified tier.
    
    This function returns a properly configured LangChain LLM instance
    based on the provider specified in the configuration for the given tier.
    
    Args:
        tier: The model tier to use (SIMPLE, MEDIUM, or COMPLEX)
        
    Returns:
        A LangChain-compatible LLM instance
    """
    config = DEFAULT_CONFIG[tier]
    provider = config["provider"]
    model = config["model"]
    temperature = config.get("temperature", 0.2)
    base_url = config.get("base_url")

    # --- LOG WHERE THE REQUEST IS GOING ---
    if provider == "ollama":
        logger.debug(
            f"[LLM REQUEST] Using Ollama (local) | Model: {model} | Base URL: {ollama_url}"
        )
    elif provider == "openai":
        logger.debug(f"[LLM REQUEST] Using OpenAI | Model: {model}")
    elif provider == "anthropic":
        logger.debug(f"[LLM REQUEST] Using Anthropic | Model: {model}")
    else:
        logger.debug(f"[LLM REQUEST] Using provider: {provider} | Model: {model}")
    # --- END LOG ---

    try:
        # Build the client and cache it; per-call timeouts and retries are handled by the client
        llm = _build_llm(provider, model, temperature, base_url)
        logger.debug(f"✅ Initialized {provider} LLM for tier: {tier.name}")
        return llm

    except ImportError as e:
        logger.error(f"❌ Failed to import {provider} client: {e}")
        logger.error(
            f"Make sure you have installed the required package for {provider}"
        )
        raise
    except Exception as e:
        logger.error(f"❌ Failed to initialize {provider} LLM: {e}")
        raise
