"""
Market data field mapping to standardized Neo4j properties.
Maps asset-specific field names to universal market_data_ prefixed properties.
"""

from typing import Dict, Any
from .models import AssetClass

# Universal market data field mapping
MARKET_DATA_FIELD_MAP = {
    # Price & Movement (universal)
    "price": "market_data_price_current",
    "spot_rate": "market_data_price_current", 
    "rate_current": "market_data_price_current",
    "change_pct": "market_data_change_daily_pct",
    "change_bp": "market_data_change_daily_bp",
    
    # Key Levels (timeframe-aware)
    "high_1w": "market_data_level_high_1w",
    "low_1w": "market_data_level_low_1w",
    "high_3m": "market_data_level_high_3m", 
    "low_3m": "market_data_level_low_3m",
    "high_52w": "market_data_level_high_52w",
    "low_52w": "market_data_level_low_52w",
    
    # Trend Indicators
    "ma_50d": "market_data_trend_ma_50d",
    "ma_200d": "market_data_trend_ma_200d", 
    "trend_strength": "market_data_trend_strength",
    "trend_direction": "market_data_trend_direction",
    
    # Volatility & Risk
    "volatility_30d": "market_data_vol_current",
    "volatility_rank": "market_data_vol_rank",
    "beta": "market_data_risk_beta",
    "rsi_14d": "market_data_momentum_rsi_14d",
    
    # Stock Fundamentals
    "pe_ratio": "market_data_valuation_pe",
    "market_cap_b": "market_data_valuation_market_cap_b",
    "eps_ttm": "market_data_earnings_eps_ttm",
    "eps_growth_3y": "market_data_growth_eps_3y",
    "revenue_ttm_b": "market_data_revenue_ttm_b", 
    "revenue_growth_3y": "market_data_growth_revenue_3y",
    "profit_margin": "market_data_health_profit_margin",
    "roe": "market_data_health_roe",
    "debt_to_equity": "market_data_health_debt_equity",
    "dividend_yield": "market_data_income_dividend_yield",
    
    # Market Structure (commodities/indices)
    "seasonal_factor": "market_data_structure_seasonal",
    "contango_level": "market_data_structure_contango",
    "breadth_ratio": "market_data_structure_breadth", 
    "fear_greed_index": "market_data_sentiment_fear_greed",
    "open_interest": "market_data_structure_open_interest"
}

# Reverse mapping for loading from Neo4j
NEO4J_TO_DISPLAY_MAP = {v: k for k, v in MARKET_DATA_FIELD_MAP.items()}


def map_to_neo4j_properties(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw market data fields to standardized Neo4j properties.
    
    Args:
        raw_data: Raw market data with asset-specific field names
        
    Returns:
        Dict with market_data_ prefixed property names
    """
    neo4j_props = {}
    
    for field_name, field_value in raw_data.items():
        # Skip base metadata fields
        if field_name in ["current_price", "currency", "last_updated"]:
            continue
            
        # Map to standardized Neo4j property name
        neo4j_field = MARKET_DATA_FIELD_MAP.get(field_name)
        if neo4j_field:
            neo4j_props[neo4j_field] = field_value
        else:
            # Fallback: prefix unmapped fields
            neo4j_props[f"market_data_raw_{field_name}"] = field_value
    
    return neo4j_props


def extract_market_data_from_neo4j(neo4j_props: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract market_data_ properties from Neo4j node and convert to display format.
    
    Args:
        neo4j_props: All properties from Neo4j node
        
    Returns:
        Dict with display-friendly field names and values
    """
    market_data = {}
    
    for prop_name, prop_value in neo4j_props.items():
        if prop_name.startswith("market_data_"):
            # Convert back to display field name
            display_field = NEO4J_TO_DISPLAY_MAP.get(prop_name)
            if display_field:
                market_data[display_field] = prop_value
            else:
                # Handle raw fields
                if prop_name.startswith("market_data_raw_"):
                    display_field = prop_name.replace("market_data_raw_", "")
                    market_data[display_field] = prop_value
    
    return market_data


def get_market_data_cypher_fragment() -> str:
    """
    Generate Cypher fragment to return all market_data_ properties.
    
    Returns:
        Cypher fragment for selecting market data properties
    """
    return """
    [key IN keys(t) WHERE key STARTS WITH 'market_data_' | 
     {field: key, value: t[key]}] AS market_data_properties
    """
