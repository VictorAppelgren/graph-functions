"""
AlphaVantage data provider.
Minimal implementation with fail-fast behavior.
"""

import os
import sys
import requests
from typing import Dict, Any
from datetime import date

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from .models import MarketSnapshot, AssetClass
from .field_configs import get_fields_for_asset_class
from utils import app_logging

logger = app_logging.get_logger(__name__)

ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"


def fetch_market_data(ticker: str, asset_class: AssetClass) -> MarketSnapshot:
    """
    Fetch market data from AlphaVantage.
    Fail-fast on any error - no fallbacks.
    """
    if not ALPHAVANTAGE_API_KEY:
        raise ValueError("ALPHAVANTAGE_API_KEY environment variable not set")
    
    logger.info(f"Fetching {asset_class.value} data for {ticker}")
    
    # Route to appropriate fetcher
    if asset_class == AssetClass.STOCK:
        data = _fetch_stock_data(ticker)
    elif asset_class == AssetClass.FX:
        data = _fetch_fx_data(ticker)
    elif asset_class == AssetClass.RATE:
        data = _fetch_rate_data(ticker)
    elif asset_class == AssetClass.COMMODITY:
        data = _fetch_commodity_data(ticker)
    elif asset_class == AssetClass.INDEX:
        data = _fetch_index_data(ticker)
    else:
        raise ValueError(f"Unsupported asset class: {asset_class}")
    
    return MarketSnapshot(
        ticker=ticker,
        asset_class=asset_class,
        data=data,
        updated_at=date.today()
    )


def _fetch_stock_data(ticker: str) -> Dict[str, Any]:
    """Fetch stock data using GLOBAL_QUOTE + OVERVIEW."""
    
    # Get quote data
    quote_params = {
        "function": "GLOBAL_QUOTE",
        "symbol": ticker,
        "apikey": ALPHAVANTAGE_API_KEY
    }
    
    logger.debug(f"Calling AlphaVantage GLOBAL_QUOTE for {ticker}")
    quote_response = requests.get(BASE_URL, params=quote_params, timeout=10)
    quote_response.raise_for_status()
    quote_json = quote_response.json()
    
    if "Error Message" in quote_json:
        raise ValueError(f"AlphaVantage error: {quote_json['Error Message']}")
    
    quote_data = quote_json.get("Global Quote", {})
    if not quote_data:
        raise ValueError(f"No quote data returned for {ticker}")
    
    # Get overview data for fundamentals
    overview_params = {
        "function": "OVERVIEW", 
        "symbol": ticker,
        "apikey": ALPHAVANTAGE_API_KEY
    }
    
    logger.debug(f"Calling AlphaVantage OVERVIEW for {ticker}")
    overview_response = requests.get(BASE_URL, params=overview_params, timeout=10)
    overview_response.raise_for_status()
    overview_json = overview_response.json()
    
    if "Error Message" in overview_json:
        logger.warning(f"Overview error for {ticker}: {overview_json['Error Message']}")
        overview_json = {}  # Continue without fundamentals
    
    # Extract and validate required fields
    price = quote_data.get("05. price")
    change_pct = quote_data.get("10. change percent", "0%").rstrip("%")
    volume = quote_data.get("06. volume")
    
    if not price:
        raise ValueError(f"Missing price data for {ticker}")
    
    return {
        "price": float(price),
        "change_pct": float(change_pct),
        "pe_ratio": float(overview_json.get("PERatio", 0)) or None,
        "market_cap_b": float(overview_json.get("MarketCapitalization", 0)) / 1e9 if overview_json.get("MarketCapitalization") else None,
        "volume": int(volume) if volume else 0
    }


def _fetch_fx_data(ticker: str) -> Dict[str, Any]:
    """Fetch FX data using FX_DAILY."""
    
    # Parse currency pair (e.g., EURUSD -> EUR/USD)
    if len(ticker) != 6:
        raise ValueError(f"Invalid FX ticker format: {ticker} (expected 6 chars like EURUSD)")
    
    from_symbol = ticker[:3]
    to_symbol = ticker[3:]
    
    params = {
        "function": "FX_DAILY",
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "apikey": ALPHAVANTAGE_API_KEY
    }
    
    logger.debug(f"Calling AlphaVantage FX_DAILY for {from_symbol}/{to_symbol}")
    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if "Error Message" in data:
        raise ValueError(f"AlphaVantage error: {data['Error Message']}")
    
    time_series = data.get("Time Series FX (Daily)", {})
    if not time_series:
        raise ValueError(f"No FX data returned for {ticker}")
    
    # Get latest day's data
    latest_date = max(time_series.keys())
    latest = time_series[latest_date]
    
    current_rate = float(latest["4. close"])
    
    # Simple 1-day change calculation (if we have previous day)
    dates = sorted(time_series.keys(), reverse=True)
    change_1d_pct = 0.0
    if len(dates) > 1:
        prev_rate = float(time_series[dates[1]]["4. close"])
        change_1d_pct = ((current_rate - prev_rate) / prev_rate) * 100
    
    return {
        "spot_rate": current_rate,
        "change_1d_pct": change_1d_pct,
        "change_1w_pct": 0.0,  # Would need more data to calculate
        "volatility_20d": 0.0,  # Would need 20 days of data to calculate
        "last_update": latest_date
    }


def _fetch_rate_data(ticker: str) -> Dict[str, Any]:
    """Fetch rate/bond data. For now, use stock endpoint as fallback."""
    # Many rates are available as stock-like symbols (^TNX for 10Y Treasury)
    logger.warning(f"Using stock endpoint for rate ticker {ticker}")
    stock_data = _fetch_stock_data(ticker)
    
    # Convert stock format to rate format
    return {
        "rate_current": stock_data["price"],
        "change_1w_bp": 0,  # Would need historical data
        "change_1m_bp": 0,  # Would need historical data  
        "change_ytd_bp": 0,  # Would need historical data
        "last_update": str(date.today())
    }


def _fetch_commodity_data(ticker: str) -> Dict[str, Any]:
    """Fetch commodity data using stock endpoint."""
    logger.warning(f"Using stock endpoint for commodity ticker {ticker}")
    stock_data = _fetch_stock_data(ticker)
    
    # Convert stock format to commodity format
    return {
        "price": stock_data["price"],
        "change_1d_pct": stock_data["change_pct"],
        "change_1m_pct": 0.0,  # Would need historical data
        "high_52w": 0.0,  # Would need historical data
        "low_52w": 0.0   # Would need historical data
    }


def _fetch_index_data(ticker: str) -> Dict[str, Any]:
    """Fetch index data using stock endpoint."""
    stock_data = _fetch_stock_data(ticker)
    
    # Convert stock format to index format
    return {
        "price": stock_data["price"],
        "change_1d_pct": stock_data["change_pct"],
        "change_1w_pct": 0.0,  # Would need historical data
        "high_52w": 0.0,  # Would need historical data
        "volume": stock_data["volume"]
    }
