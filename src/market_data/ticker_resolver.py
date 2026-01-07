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

from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from .models import TickerResolution, AssetClass
from utils import app_logging

logger = app_logging.get_logger(__name__)

# Initialize LLM using centralized router
llm = get_llm(ModelTier.SIMPLE)

ENHANCED_TICKER_RESOLUTION_PROMPT = PromptTemplate.from_template("""
Determine if this topic has tradeable market data and resolve tickers for multiple providers.

Topic Name: {topic_name}
Topic Type: {topic_type}

IMPORTANT: Some topics are concepts, events, or abstract ideas that do NOT have market data.

Return JSON with EXACT fields:
{{
    "topic_name": "{topic_name}",
    "resolved_ticker": "YAHOO_SYMBOL_OR_NULL",
    "fred_id": "FRED_SERIES_ID_OR_NULL",
    "stooq_ticker": "STOOQ_TICKER_OR_NULL",
    "asset_class": "stock|fx|rate|commodity|index|unknown",
    "confidence": 0.0-1.0,
    "reason": "ticker_found|no_market_data|uncertain",
    "motivation": "brief explanation"
}}

PROVIDER FORMATS:

Yahoo Finance:
- Stocks: "AAPL", "MSFT"
- FX: "EURUSD=X", "GBPUSD=X"
- Rates: "^TNX" (10Y), "^FVX" (5Y)
- Indices: "^GSPC", "^DJI"
- Commodities: "GC=F" (Gold), "CL=F" (Oil)

FRED (Federal Reserve Economic Data) - BEST for US rates:
- SOFR: "SOFR"
- Fed Funds: "DFF" or "FEDFUNDS"
- 10Y Treasury: "DGS10"
- 2Y Treasury: "DGS2"
- 3M T-Bill: "DTB3"
- Mortgage rates: "MORTGAGE30US"
- CPI: "CPIAUCSL"
- Unemployment: "UNRATE"

Stooq - Good for European rates & indices:
- EURIBOR: "EURIBOR3M.B"
- STIBOR: Not available
- Indices: "^SPX", "^DAX"
- FX: "EURUSD", "GBPUSD"

RULES:
1. Provide ALL applicable tickers (Yahoo, FRED, Stooq) when available
2. For US rates/economic data -> always include fred_id
3. If topic is abstract/conceptual -> return all tickers as null
4. If Yahoo unavailable but FRED/Stooq works -> still provide those

EXAMPLES:

Input: "SOFR"
Output: {{"topic_name": "SOFR", "resolved_ticker": null, "fred_id": "SOFR", "stooq_ticker": null, "asset_class": "rate", "confidence": 1.0, "reason": "ticker_found", "motivation": "SOFR available on FRED, not Yahoo"}}

Input: "10Y Treasury"
Output: {{"topic_name": "10Y Treasury", "resolved_ticker": "^TNX", "fred_id": "DGS10", "stooq_ticker": null, "asset_class": "rate", "confidence": 1.0, "reason": "ticker_found", "motivation": "Available on both Yahoo and FRED"}}

Input: "EUR/USD"
Output: {{"topic_name": "EUR/USD", "resolved_ticker": "EURUSD=X", "fred_id": null, "stooq_ticker": "EURUSD", "asset_class": "fx", "confidence": 1.0, "reason": "ticker_found", "motivation": "FX pair available on Yahoo and Stooq"}}

Input: "Fed Policy"
Output: {{"topic_name": "Fed Policy", "resolved_ticker": null, "fred_id": null, "stooq_ticker": null, "asset_class": "unknown", "confidence": 0.95, "reason": "no_market_data", "motivation": "Abstract policy concept"}}

RESPOND WITH ONLY VALID JSON. NO EXPLANATION.
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
