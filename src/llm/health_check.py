"""LLM Health Check - Ensures LLMs are available before starting workers.

This module provides a simple health check function that blocks until LLMs are responding.
Used by both main.py and main_top_sources.py to prevent crash loops when LLM servers are down.
"""

import time
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils.app_logging import get_logger

logger = get_logger(__name__)

HEALTH_CHECK_INTERVAL_SECONDS = 1800  # 30 minutes


def wait_for_llm_health():
    """
    Test if LLMs are available. If not, wait 30 minutes and retry.
    Blocks until LLMs are healthy.
    
    This prevents workers from crash-looping when LLM servers are down.
    Docker will restart the worker, but this function will pause it until
    LLMs are back online.
    """
    while True:
        try:
            logger.info("🔍 Checking LLM health...")
            llm = get_llm(ModelTier.SIMPLE)
            result = llm.invoke("test")
            
            # Verify we got a response
            if hasattr(result, 'content') and result.content:
                logger.info("✅ LLM health check PASSED - servers are responding")
                return  # Success! Continue to main pipeline
            else:
                logger.warning("⚠️ LLM returned empty response")
                raise Exception("Empty LLM response")
                
        except Exception as e:
            logger.error(f"❌ LLM health check FAILED: {e}")
            logger.info(f"⏳ Waiting {HEALTH_CHECK_INTERVAL_SECONDS}s (30 min) before retry...")
            time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
            logger.info("🔄 Retrying health check...")
