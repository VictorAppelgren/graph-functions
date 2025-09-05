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
from enum import Enum
from typing import Dict, Any

# Set up API keys from environment variables if available
# Otherwise, these will need to be set by the user

# API keys (if needed) should be provided via environment variables externally.

from utils.minimal_logging import get_logger
logger = get_logger(__name__)

# --- OLLAMA SINGLE URL (manual toggle by commenting) ---
ollama_url = "http://gate04.cfa.handels.gu.se:11434"
#ollama_url = "http://gate04.cfa.handels.gu.se:8787"

#vllm_url = "http://gate04.cfa.handels.gu.se:8787/v1"
vllm_url = "http://gate04.cfa.handels.gu.se:8686/v1"

class ModelTier(Enum):
    """Enumeration of model tiers based on task complexity."""
    SIMPLE = 1   # Simple tasks like classification, tagging
    MEDIUM = 2   # Medium tasks like summarization, relevance assessment
    COMPLEX = 3  # Complex tasks like research generation, counterfactual reasoning
    SIMPLE_LONG_CONTEXT = 4  # Simple tasks with long context window (e.g. GPT-5 Nano)

# My OpenAI API key
os.environ.setdefault('OPENAI_API_KEY', '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')  # User will need to set this

# Default configuration for each model tier
# These can be overridden via environment variables
DEFAULT_CONFIG = {
    #ModelTier.SIMPLE: {
    #    "provider": "ollama",
    #    "model": "gpt-oss",
    #    "temperature": 0.1,
    #    "api_base": "http://localhost:11434",
    #},
    ModelTier.SIMPLE: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.1,
        "base_url": "http://gate04.cfa.handels.gu.se:8686/v1"
    },
    ModelTier.MEDIUM: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
    ModelTier.COMPLEX: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
    #ModelTier.COMPLEX: {
    #    "provider": "openai",
    #    "model": "gpt-5-nano",
        #"temperature": 0,
    #},
    #ModelTier.COMPLEX: {
    #    "provider": "anthropic",
    #    "model": "claude-3-5-sonnet-20240620",
    #    "temperature": 0.3,
    #}
    #ModelTier.SIMPLE_LONG_CONTEXT: {
    #    "provider": "openai",
    #    "model": "gpt-5-nano",
    #    #"temperature": 0,
    #    # Add any other relevant config here
    #},
    ModelTier.SIMPLE_LONG_CONTEXT: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
}

# Environment variable prefixes for each tier
ENV_PREFIXES = {
    ModelTier.SIMPLE: "ARGOS_SIMPLE_",
    ModelTier.MEDIUM: "ARGOS_MEDIUM_",
    ModelTier.COMPLEX: "ARGOS_COMPLEX_",
    ModelTier.SIMPLE_LONG_CONTEXT: "ARGOS_SIMPLE_LONG_CONTEXT_"
}

# Cache for initialized clients
_client_cache = {}

# --- LLM call policy (per-request) ---
_LLM_CALL_TIMEOUT_S = 900.0  # 10 minutes per request
_LLM_RETRY_ATTEMPTS = 3      # total attempts via with_retry()

def _build_llm(provider: str, model: str, temperature: float, base_url: str | None):
    """Construct a LangChain LLM client for the given provider (no network call)."""
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model=model,
            temperature=temperature,
            #num_ctx=49152,
            num_ctn=16384,
            timeout=int(_LLM_CALL_TIMEOUT_S),
        )
        return llm.with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        if base_url == "" or base_url is None:
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                timeout=_LLM_CALL_TIMEOUT_S,  # alias: request_timeout
                max_retries=0,                # use Runnable-level retry for consistency
            )
        else:
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                base_url=base_url,
                timeout=_LLM_CALL_TIMEOUT_S,
                max_retries=0,
            )
        return llm.with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model=model,
            temperature=temperature,
            timeout=_LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )
        return llm.with_retry(stop_after_attempt=_LLM_RETRY_ATTEMPTS)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def get_model_config(tier: ModelTier) -> Dict[str, Any]:
    """Get the configuration for a specific model tier.
    
    Args:
        tier: The model tier to get configuration for
        
    Returns:
        Dictionary with model configuration
    """
    config = DEFAULT_CONFIG[tier].copy()
    
    # Override with environment variables if present
    prefix = ENV_PREFIXES[tier]
    for key in config.keys():
        env_key = f"{prefix}{key.upper()}"
        if env_key in os.environ:
            config[key] = os.environ[env_key]
            
    return config

def get_llm(tier: ModelTier):
    # Minimal LLM tier call counter (increments on every get_llm call)
    from utils.master_log import increment_llm_usage
    increment_llm_usage(tier)

    """Get a LangChain-compatible LLM for the specified tier.
    
    This function returns a properly configured LangChain LLM instance
    based on the provider specified in the configuration for the given tier.
    
    Args:
        tier: The model tier to use (SIMPLE, MEDIUM, or COMPLEX)
        
    Returns:
        A LangChain-compatible LLM instance
    """
    #logger.info(f"🤖 Getting LLM for tier: {tier.name}")
    
    # Check cache first
    if tier in _client_cache:
        llm_cached = _client_cache[tier]
        logger.debug(f"[LLM ROUTE][CACHE] tier={tier.name}")
        return llm_cached
    
    config = get_model_config(tier)
    provider = config["provider"]
    model = config["model"]
    temperature = config.get("temperature", 0.2)
    base_url = config.get("base_url")

    # --- LOG WHERE THE REQUEST IS GOING ---
    if provider == "ollama":
        logger.debug(f"[LLM REQUEST] Using Ollama (local) | Model: {model} | Base URL: {ollama_url}")
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
        _client_cache[tier] = llm
        logger.debug(f"✅ Initialized {provider} LLM for tier: {tier.name}")
        return llm

    except ImportError as e:
        logger.error(f"❌ Failed to import {provider} client: {e}")
        logger.error(f"Make sure you have installed the required package for {provider}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to initialize {provider} LLM: {e}")
        raise

# Tier-specific convenience functions
def get_simple_llm():
    """Get a LangChain-compatible LLM for simple tasks like classification or tagging."""
    logger.debug("🤖🔍 Getting LLM for SIMPLE tasks")
    return get_llm(ModelTier.SIMPLE)

def get_medium_llm():
    """Get a LangChain-compatible LLM for medium complexity tasks like summarization."""
    logger.debug("🤖📊 Getting LLM for MEDIUM tasks")
    return get_llm(ModelTier.MEDIUM)

def get_complex_llm():
    """Get a LangChain-compatible LLM for complex tasks like research generation."""
    logger.debug("🤖🧠 Getting LLM for COMPLEX tasks")
    return get_llm(ModelTier.COMPLEX)

def get_simple_long_context_llm():
    """Get a LangChain-compatible LLM for simple tasks with a long context window (e.g. GPT-5 Nano)."""
    logger.debug("🤖🧩 Getting LLM for SIMPLE_LONG_CONTEXT tasks (400k context)")
    return get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
