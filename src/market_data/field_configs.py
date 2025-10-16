"""
Field configuration for different asset classes.
Maximum 5 fields per asset type as requested.
"""

from typing import Dict, List
from .models import AssetClass

# Swing Trading / Long-term Analysis Field Configs
FIELD_CONFIGS: Dict[AssetClass, List[str]] = {
    AssetClass.STOCK: [
        "price",           # Current stock price
        "change_pct",      # Daily change %
        "pe_ratio",        # P/E ratio TTM
        "market_cap_b",    # Market cap in billions
        "high_3m",         # 3-month high
        "low_3m",          # 3-month low
        "high_52w",        # 52-week high
        "low_52w",         # 52-week low
        "ma_50d",          # 50-day moving average
        "ma_200d",         # 200-day moving average
        "dividend_yield",  # Dividend yield %
        "beta",            # Beta coefficient
        "eps_ttm",         # Earnings per share TTM
        "eps_growth_3y",   # 3-year EPS growth rate
        "revenue_ttm_b",   # Revenue TTM in billions
        "revenue_growth_3y", # 3-year revenue growth rate
        "profit_margin",   # Net profit margin %
        "roe",             # Return on equity %
        "debt_to_equity",  # Debt to equity ratio
        "rsi_14d"          # 14-day RSI
    ],
    
    AssetClass.FX: [
        "spot_rate",       # Current exchange rate
        "change_pct",      # Daily change %
        "high_1w",         # 1-week high
        "low_1w",          # 1-week low
        "high_3m",         # 3-month high
        "low_3m",          # 3-month low
        "high_52w",        # 52-week high
        "low_52w",         # 52-week low
        "ma_50d",          # 50-day moving average
        "ma_200d",         # 200-day moving average
        "volatility_30d",  # 30-day volatility
        "trend_strength"   # Trend strength indicator
    ],
    
    AssetClass.RATE: [
        "rate_current",    # Current yield/rate %
        "change_bp",       # Daily change in basis points
        "high_1w",         # 1-week high
        "low_1w",          # 1-week low
        "high_3m",         # 3-month high
        "low_3m",          # 3-month low
        "high_52w",        # 52-week high
        "low_52w",         # 52-week low
        "ma_50d",          # 50-day moving average
        "ma_200d",         # 200-day moving average
        "trend_direction", # Up/Down/Sideways
        "volatility_rank"  # Volatility percentile rank
    ],
    
    AssetClass.COMMODITY: [
        "price",           # Current price
        "change_pct",      # Daily change %
        "high_1w",         # 1-week high
        "low_1w",          # 1-week low
        "high_3m",         # 3-month high
        "low_3m",          # 3-month low
        "high_52w",        # 52-week high
        "low_52w",         # 52-week low
        "ma_50d",          # 50-day moving average
        "ma_200d",         # 200-day moving average
        "seasonal_factor", # Seasonal strength
        "contango_level"   # Futures curve shape
    ],
    
    AssetClass.INDEX: [
        "price",           # Current index level
        "change_pct",      # Daily change %
        "high_1w",         # 1-week high
        "low_1w",          # 1-week low
        "high_3m",         # 3-month high
        "low_3m",          # 3-month low
        "high_52w",        # 52-week high
        "low_52w",         # 52-week low
        "ma_50d",          # 50-day moving average
        "ma_200d",         # 200-day moving average
        "breadth_ratio",   # Advance/decline ratio
        "fear_greed_index" # Market sentiment
    ]
}


def get_fields_for_asset_class(asset_class: AssetClass) -> List[str]:
    """Get the predefined fields for an asset class."""
    return FIELD_CONFIGS.get(asset_class, [])
