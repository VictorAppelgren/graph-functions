"""
Type-safe models for fundamentals data.
Following the established Pydantic pattern from sanitizer.py.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import date
from enum import Enum


class AssetClass(str, Enum):
    STOCK = "stock"
    FX = "fx" 
    RATE = "rate"
    COMMODITY = "commodity"
    INDEX = "index"
    UNKNOWN = "unknown"


class TickerResolution(BaseModel):
    topic_name: str
    resolved_ticker: Optional[str]  # Can be None for abstract topics
    asset_class: AssetClass
    confidence: float
    reason: str = "ticker_found"  # ticker_found|no_market_data|uncertain
    motivation: str
    # Alternative tickers for fallback providers
    fred_id: Optional[str] = None  # FRED series ID (e.g., "SOFR", "DFF")
    stooq_ticker: Optional[str] = None  # Stooq ticker (e.g., "^spx", "eurusd")


class MarketSnapshot(BaseModel):
    ticker: str
    asset_class: AssetClass
    data: Dict[str, Any]
    updated_at: date
    source: str = "alphavantage"


class Neo4jUpdate(BaseModel):
    topic_id: str
    resolved_ticker: str
    asset_class: AssetClass
    market_data: Dict[str, Any]
    last_market_update: str
    update_type: str = "MERGE"
    properties: Dict[str, Any] = {}
