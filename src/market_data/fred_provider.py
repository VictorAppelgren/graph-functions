"""
FRED (Federal Reserve Economic Data) provider.
Fallback for US rates and economic data not available on Yahoo Finance.

Free API: https://fred.stlouisfed.org/docs/api/fred/
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

# FRED API key (free from https://fred.stlouisfed.org/docs/api/api_key.html)
FRED_API_KEY = os.getenv("FRED_API_KEY")


def fetch_market_data_fred(fred_id: str, asset_class: AssetClass) -> MarketSnapshot:
    """
    Fetch economic/rate data from FRED.

    Args:
        fred_id: FRED series ID (e.g., "SOFR", "DGS10", "FEDFUNDS")
        asset_class: Asset class for the data

    Returns:
        MarketSnapshot with the fetched data
    """
    import requests

    if not FRED_API_KEY:
        raise ValueError("FRED_API_KEY not set. Get free key from https://fred.stlouisfed.org/docs/api/api_key.html")

    logger.info(f"Fetching {asset_class.value} data for {fred_id} from FRED")

    # Fetch last 30 days of data
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": fred_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date.isoformat(),
        "observation_end": end_date.isoformat(),
        "sort_order": "desc",
        "limit": 10
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        observations = data.get("observations", [])
        if not observations:
            raise ValueError(f"No data found for FRED series {fred_id}")

        # Get most recent value
        latest = observations[0]
        current_value = float(latest["value"]) if latest["value"] != "." else None

        if current_value is None:
            raise ValueError(f"No valid data point for {fred_id}")

        # Build data dict
        result_data = {
            "current_price": str(current_value),
            "rate_current": str(current_value),
            "last_updated": latest["date"],
            "source": "FRED",
            "fred_series_id": fred_id
        }

        # Calculate change if we have multiple observations
        if len(observations) >= 2:
            prev = observations[1]
            prev_value = float(prev["value"]) if prev["value"] != "." else None
            if prev_value and current_value:
                change = current_value - prev_value
                change_bp = change * 100  # Convert to basis points for rates
                result_data["change_bp"] = str(round(change_bp, 2))

        # Get high/low from observations
        valid_values = [float(o["value"]) for o in observations if o["value"] != "."]
        if valid_values:
            result_data["high_1w"] = str(max(valid_values[:5])) if len(valid_values) >= 5 else str(max(valid_values))
            result_data["low_1w"] = str(min(valid_values[:5])) if len(valid_values) >= 5 else str(min(valid_values))

        snapshot = MarketSnapshot(
            ticker=fred_id,
            asset_class=asset_class,
            data=result_data,
            updated_at=date.today(),
            source="fred"
        )

        logger.info(f"FRED: Fetched {fred_id} = {current_value}")
        return snapshot

    except requests.RequestException as e:
        logger.error(f"FRED API request failed for {fred_id}: {e}")
        raise ValueError(f"FRED fetch failed for {fred_id}: {e}")
    except Exception as e:
        logger.error(f"FRED data processing failed for {fred_id}: {e}")
        raise ValueError(f"FRED processing failed for {fred_id}: {e}")


def test_fred_connection(series_id: str = "DGS10") -> bool:
    """Test FRED API connection."""
    try:
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not set")
            return False
        snapshot = fetch_market_data_fred(series_id, AssetClass.RATE)
        return snapshot is not None
    except Exception as e:
        logger.error(f"FRED connection test failed: {e}")
        return False
