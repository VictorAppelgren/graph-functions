"""
Stooq data provider.
Fallback for European rates and indices not available on Yahoo Finance.

Free data from: https://stooq.com/
Uses pandas_datareader for easy access.
"""

import os
import sys
from typing import Dict, Any
from datetime import datetime, date, timedelta

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from .models import MarketSnapshot, AssetClass
from utils import app_logging

logger = app_logging.get_logger(__name__)


def fetch_market_data_stooq(ticker: str, asset_class: AssetClass) -> MarketSnapshot:
    """
    Fetch market data from Stooq.

    Args:
        ticker: Stooq ticker (e.g., "EURUSD", "^SPX", "EURIBOR3M.B")
        asset_class: Asset class for the data

    Returns:
        MarketSnapshot with the fetched data
    """
    import pandas as pd

    logger.info(f"Fetching {asset_class.value} data for {ticker} from Stooq")

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    try:
        # Stooq URL format
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&d1={start_date.strftime('%Y%m%d')}&d2={end_date.strftime('%Y%m%d')}"

        df = pd.read_csv(url)

        if df.empty:
            raise ValueError(f"No data found for Stooq ticker {ticker}")

        # Stooq returns columns: Date, Open, High, Low, Close, Volume
        df.columns = [c.lower() for c in df.columns]

        if 'close' not in df.columns:
            raise ValueError(f"Invalid data format for {ticker}")

        # Get most recent data
        current_price = float(df['close'].iloc[-1])

        result_data = {
            "current_price": str(current_price),
            "last_updated": datetime.now().isoformat(),
            "source": "Stooq",
            "stooq_ticker": ticker
        }

        # Add rate-specific fields
        if asset_class == AssetClass.RATE:
            result_data["rate_current"] = str(current_price)

        # Add FX-specific fields
        if asset_class == AssetClass.FX:
            result_data["spot_rate"] = str(current_price)

        # Calculate change
        if len(df) >= 2:
            prev_close = float(df['close'].iloc[-2])
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0
            result_data["change_pct"] = str(round(change_pct, 4))
            if asset_class == AssetClass.RATE:
                result_data["change_bp"] = str(round(change * 100, 2))

        # High/Low from recent data
        recent = df.tail(5)
        if 'high' in df.columns:
            result_data["high_1w"] = str(recent['high'].max())
        if 'low' in df.columns:
            result_data["low_1w"] = str(recent['low'].min())

        snapshot = MarketSnapshot(
            ticker=ticker,
            asset_class=asset_class,
            data=result_data,
            updated_at=date.today(),
            source="stooq"
        )

        logger.info(f"Stooq: Fetched {ticker} = {current_price}")
        return snapshot

    except Exception as e:
        logger.error(f"Stooq fetch failed for {ticker}: {e}")
        raise ValueError(f"Stooq fetch failed for {ticker}: {e}")


def test_stooq_connection(ticker: str = "^SPX") -> bool:
    """Test Stooq connection."""
    try:
        snapshot = fetch_market_data_stooq(ticker, AssetClass.INDEX)
        return snapshot is not None
    except Exception as e:
        logger.error(f"Stooq connection test failed: {e}")
        return False
