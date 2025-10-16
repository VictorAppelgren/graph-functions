"""
LLM-powered ticker resolution for financial topics.
Uses existing sanitizer pattern for type-safe LLM responses.
"""

import os
import sys
from typing import Optional

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from .models import TickerResolution, AssetClass
from utils import app_logging

logger = app_logging.get_logger(__name__)

# Initialize LLM using centralized router
llm = get_llm(ModelTier.SIMPLE)

ENHANCED_TICKER_RESOLUTION_PROMPT = PromptTemplate.from_template("""
Determine if this topic has tradeable market data and resolve the Yahoo Finance ticker if appropriate.

Topic Name: {topic_name}
Topic Type: {topic_type}

IMPORTANT: Some topics are concepts, events, or abstract ideas that do NOT have market data.

Return JSON with EXACT fields (no extra fields, no missing fields):
{{
    "topic_name": "{topic_name}",
    "resolved_ticker": "EXACT_YAHOO_SYMBOL_OR_NULL",
    "asset_class": "stock|fx|rate|commodity|index|unknown", 
    "confidence": 0.0-1.0,
    "reason": "ticker_found|no_market_data|uncertain",
    "motivation": "brief explanation"
}}

RULES:
1. If topic is a tradeable asset/instrument -> return ticker with reason="ticker_found"
2. If topic is abstract/conceptual/event -> return null ticker with reason="no_market_data" 
3. If uncertain -> return null ticker with reason="uncertain"

Yahoo Finance Symbol Format:
- Stocks: "AAPL", "MSFT", "TSLA"
- FX Pairs: "EURUSD=X", "GBPUSD=X", "USDJPY=X" 
- Rates/Bonds: "^TNX" (10Y), "^FVX" (5Y), "^IRX" (3M)
- Indices: "^GSPC" (S&P 500), "^DJI" (Dow), "^IXIC" (Nasdaq)
- Commodities: "GC=F" (Gold), "CL=F" (Oil), "SI=F" (Silver)

EXAMPLES:

Input: "Apple Inc"
Output: {{"topic_name": "Apple Inc", "resolved_ticker": "AAPL", "asset_class": "stock", "confidence": 1.0, "reason": "ticker_found", "motivation": "Direct stock symbol"}}

Input: "EUR/USD" 
Output: {{"topic_name": "EUR/USD", "resolved_ticker": "EURUSD=X", "asset_class": "fx", "confidence": 1.0, "reason": "ticker_found", "motivation": "Yahoo FX format"}}

Input: "Fed Policy"
Output: {{"topic_name": "Fed Policy", "resolved_ticker": null, "asset_class": "unknown", "confidence": 0.95, "reason": "no_market_data", "motivation": "Abstract policy concept, not tradeable"}}

Input: "EU Defense Spending"
Output: {{"topic_name": "EU Defense Spending", "resolved_ticker": null, "asset_class": "unknown", "confidence": 0.90, "reason": "no_market_data", "motivation": "Economic concept, not a specific tradeable asset"}}

Input: "China Credit Impulse"
Output: {{"topic_name": "China Credit Impulse", "resolved_ticker": null, "asset_class": "unknown", "confidence": 0.85, "reason": "no_market_data", "motivation": "Economic indicator, not directly tradeable"}}

JSON:
""")


def resolve_ticker_llm(topic_name: str, topic_type: Optional[str] = None) -> TickerResolution:
    """
    Resolve ticker using LLM, return typed object.
    Uses established sanitizer pattern for type safety.
    LEGACY VERSION - use resolve_ticker_llm_enhanced for new code.
    """
    logger.info(f"Resolving ticker for topic: {topic_name}")
    
    # Use enhanced version internally
    return resolve_ticker_llm_enhanced(topic_name, topic_type)


def resolve_ticker_llm_enhanced(topic_name: str, topic_type: Optional[str] = None) -> TickerResolution:
    """
    Enhanced ticker resolution that can determine if market data is appropriate.
    Returns None ticker for abstract/conceptual topics.
    """
    logger.info(f"Enhanced ticker resolution for: {topic_name}")
    
    prompt = ENHANCED_TICKER_RESOLUTION_PROMPT.format(
        topic_name=topic_name,
        topic_type=topic_type or "unknown"
    )
    
    # Use existing LLM decision pattern from sanitizer
    result = run_llm_decision(
        chain=llm,
        prompt=prompt,
        model=TickerResolution
    )
    
    if result.resolved_ticker:
        logger.info(f"✅ Resolved {topic_name} -> {result.resolved_ticker} ({result.asset_class}) confidence={result.confidence}")
    else:
        logger.info(f"🚫 No market data for {topic_name} - reason: {result.reason} (confidence={result.confidence})")
    
    return result
