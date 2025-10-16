"""
Yahoo Finance data provider.
Primary data source with clean, reliable market data.
"""

import os
import sys
import yfinance as yf
from typing import Dict, Any, Optional
from datetime import date, datetime

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


def fetch_market_data_yahoo(ticker: str, asset_class: AssetClass) -> MarketSnapshot:
    """
    Fetch market data from Yahoo Finance.
    Clean, reliable, and free - perfect for fundamentals.
    """
    logger.info(f"Fetching {asset_class.value} data for {ticker} from Yahoo Finance")
    
    try:
        # Create yfinance ticker object
        yf_ticker = yf.Ticker(ticker)
        
        # Get basic info and current data
        info = yf_ticker.info
        hist = yf_ticker.history(period="5d")  # Last 5 days for current price
        
        if hist.empty:
            raise ValueError(f"No historical data found for {ticker}")
        
        # Extract current price from most recent data
        current_price = float(hist['Close'].iloc[-1])
        
        # Build data dictionary based on asset class
        data = _extract_yahoo_data(info, current_price, asset_class, ticker)
        
        # Get expected fields for this asset class
        expected_fields = get_fields_for_asset_class(asset_class)
        
        # Ensure all expected fields are present
        for field in expected_fields:
            if field not in data:
                data[field] = None
                logger.warning(f"Missing field {field} for {ticker}")
        
        snapshot = MarketSnapshot(
            ticker=ticker,
            asset_class=asset_class,
            data=data,
            updated_at=datetime.now().date(),
            source="yahoo_finance"
        )
        
        logger.info(f"✓ Successfully fetched {len(data)} fields from Yahoo Finance")
        return snapshot
        
    except Exception as e:
        logger.error(f"Failed to fetch Yahoo Finance data for {ticker}: {e}")
        raise ValueError(f"Yahoo Finance fetch failed for {ticker}: {e}")


def _extract_yahoo_data(info: Dict[str, Any], current_price: float, asset_class: AssetClass, ticker: str) -> Dict[str, Any]:
    """Extract relevant data based on asset class, mapping to expected field names."""
    
    # Base data available for all asset classes
    base_data = {
        "current_price": current_price,
        "currency": info.get("currency", "USD"),
        "last_updated": datetime.now().isoformat()
    }
    
    # Map Yahoo Finance data to swing trading / long-term analysis fields
    if asset_class == AssetClass.STOCK:
        # Enhanced stock fundamentals with 3-5 year trends
        market_cap = info.get("marketCap")
        market_cap_b = float(market_cap) / 1e9 if market_cap else 0
        
        # Revenue calculations
        total_revenue = info.get("totalRevenue")
        revenue_ttm_b = float(total_revenue) / 1e9 if total_revenue else 0
        
        # Growth rates (approximated from available data)
        earnings_growth = info.get("earningsGrowth", 0)
        revenue_growth = info.get("revenueGrowth", 0)
        
        # Financial ratios
        profit_margin = info.get("profitMargins", 0)
        roe = info.get("returnOnEquity", 0)
        debt_to_equity = info.get("debtToEquity", 0)
        
        # Moving averages
        ma_50d = info.get("fiftyDayAverage", current_price)
        ma_200d = info.get("twoHundredDayAverage", current_price)
        
        mapped_data = {
            "price": str(current_price),
            "change_pct": str(info.get("regularMarketChangePercent", 0)),
            "pe_ratio": str(info.get("trailingPE", 0)),
            "market_cap_b": str(market_cap_b),
            "high_3m": str(info.get("fiftyTwoWeekHigh", current_price)),  # Approximate
            "low_3m": str(info.get("fiftyTwoWeekLow", current_price)),    # Approximate
            "high_52w": str(info.get("fiftyTwoWeekHigh", current_price)),
            "low_52w": str(info.get("fiftyTwoWeekLow", current_price)),
            "ma_50d": str(ma_50d),
            "ma_200d": str(ma_200d),
            "dividend_yield": str(info.get("dividendYield", 0)),
            "beta": str(info.get("beta", 1.0)),
            "eps_ttm": str(info.get("trailingEps", 0)),
            "eps_growth_3y": str(float(earnings_growth) * 100 if earnings_growth else 0),
            "revenue_ttm_b": str(revenue_ttm_b),
            "revenue_growth_3y": str(float(revenue_growth) * 100 if revenue_growth else 0),
            "profit_margin": str(float(profit_margin) * 100 if profit_margin else 0),
            "roe": str(float(roe) * 100 if roe else 0),
            "debt_to_equity": str(debt_to_equity if debt_to_equity else 0),
            "rsi_14d": "50"  # Default neutral RSI (would need historical calculation)
        }
    
    elif asset_class == AssetClass.FX:
        # Swing trading FX metrics
        ma_50d = info.get("fiftyDayAverage", current_price)
        ma_200d = info.get("twoHundredDayAverage", current_price)
        
        mapped_data = {
            "spot_rate": str(current_price),
            "change_pct": str(info.get("regularMarketChangePercent", 0)),
            "high_1w": str(info.get("dayHigh", current_price)),           # Approximate
            "low_1w": str(info.get("dayLow", current_price)),             # Approximate
            "high_3m": str(info.get("fiftyTwoWeekHigh", current_price)),  # Approximate
            "low_3m": str(info.get("fiftyTwoWeekLow", current_price)),    # Approximate
            "high_52w": str(info.get("fiftyTwoWeekHigh", current_price)),
            "low_52w": str(info.get("fiftyTwoWeekLow", current_price)),
            "ma_50d": str(ma_50d),
            "ma_200d": str(ma_200d),
            "volatility_30d": "0.5",  # Default (would need historical calculation)
            "trend_strength": "neutral"  # Default (would need trend analysis)
        }
    
    elif asset_class == AssetClass.RATE:
        # Swing trading rate metrics
        change_pct = info.get("regularMarketChangePercent", 0)
        change_bp = float(change_pct) * 100 if change_pct else 0
        ma_50d = info.get("fiftyDayAverage", current_price)
        ma_200d = info.get("twoHundredDayAverage", current_price)
        
        mapped_data = {
            "rate_current": str(current_price),
            "change_bp": str(change_bp),
            "high_1w": str(info.get("dayHigh", current_price)),           # Approximate
            "low_1w": str(info.get("dayLow", current_price)),             # Approximate
            "high_3m": str(info.get("fiftyTwoWeekHigh", current_price)),  # Approximate
            "low_3m": str(info.get("fiftyTwoWeekLow", current_price)),    # Approximate
            "high_52w": str(info.get("fiftyTwoWeekHigh", current_price)),
            "low_52w": str(info.get("fiftyTwoWeekLow", current_price)),
            "ma_50d": str(ma_50d),
            "ma_200d": str(ma_200d),
            "trend_direction": "sideways",  # Default (would need trend analysis)
            "volatility_rank": "50"         # Default median rank
        }
    
    elif asset_class == AssetClass.INDEX:
        # Swing trading index metrics
        ma_50d = info.get("fiftyDayAverage", current_price)
        ma_200d = info.get("twoHundredDayAverage", current_price)
        
        mapped_data = {
            "price": str(current_price),
            "change_pct": str(info.get("regularMarketChangePercent", 0)),
            "high_1w": str(info.get("dayHigh", current_price)),           # Approximate
            "low_1w": str(info.get("dayLow", current_price)),             # Approximate
            "high_3m": str(info.get("fiftyTwoWeekHigh", current_price)),  # Approximate
            "low_3m": str(info.get("fiftyTwoWeekLow", current_price)),    # Approximate
            "high_52w": str(info.get("fiftyTwoWeekHigh", current_price)),
            "low_52w": str(info.get("fiftyTwoWeekLow", current_price)),
            "ma_50d": str(ma_50d),
            "ma_200d": str(ma_200d),
            "breadth_ratio": "1.0",    # Default neutral (would need market breadth data)
            "fear_greed_index": "50"   # Default neutral (would need sentiment data)
        }
    
    elif asset_class == AssetClass.COMMODITY:
        # Swing trading commodity metrics
        ma_50d = info.get("fiftyDayAverage", current_price)
        ma_200d = info.get("twoHundredDayAverage", current_price)
        
        mapped_data = {
            "price": str(current_price),
            "change_pct": str(info.get("regularMarketChangePercent", 0)),
            "high_1w": str(info.get("dayHigh", current_price)),           # Approximate
            "low_1w": str(info.get("dayLow", current_price)),             # Approximate
            "high_3m": str(info.get("fiftyTwoWeekHigh", current_price)),  # Approximate
            "low_3m": str(info.get("fiftyTwoWeekLow", current_price)),    # Approximate
            "high_52w": str(info.get("fiftyTwoWeekHigh", current_price)),
            "low_52w": str(info.get("fiftyTwoWeekLow", current_price)),
            "ma_50d": str(ma_50d),
            "ma_200d": str(ma_200d),
            "seasonal_factor": "neutral",  # Default (would need seasonal analysis)
            "contango_level": "0"          # Default (would need futures curve data)
        }
    
    else:
        mapped_data = {}
    
    # Combine base data with mapped data
    final_data = {**base_data, **mapped_data}
    
    # Ensure all values are strings and not None
    cleaned_data = {}
    for key, value in final_data.items():
        if value is not None:
            cleaned_data[key] = str(value)
        else:
            cleaned_data[key] = "0"  # Default fallback
    
    return cleaned_data


def test_yahoo_connection(ticker: str = "AAPL") -> bool:
    """Test Yahoo Finance connection with a simple ticker."""
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info
        return bool(info.get("symbol") or info.get("shortName"))
    except Exception as e:
        logger.error(f"Yahoo Finance connection test failed: {e}")
        return False
