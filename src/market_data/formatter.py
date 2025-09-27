"""
Format market data for display and analysis integration.
"""

from typing import Dict, Any
from .models import MarketSnapshot, AssetClass


def format_market_data_display(snapshot: MarketSnapshot) -> str:
    """
    Format market data for human-readable display.
    """
    lines = [
        f"=== MARKET DATA: {snapshot.ticker} ({snapshot.asset_class.value.upper()}) ===",
        f"Updated: {snapshot.updated_at}",
        f"Source: {snapshot.source}",
        ""
    ]
    
    # Format each field with appropriate units and precision
    for field, value in snapshot.data.items():
        if value is None:
            continue
            
        formatted_value = _format_field_value(field, value, snapshot.asset_class)
        lines.append(f"{field.replace('_', ' ').title()}: {formatted_value}")
    
    return "\n".join(lines)


def format_market_data_for_analysis(snapshot: MarketSnapshot) -> str:
    """
    Format market data for LLM analysis context.
    Concise format suitable for prompt injection.
    """
    ticker = snapshot.ticker
    asset_class = snapshot.asset_class.value.upper()
    
    data_items = []
    for field, value in snapshot.data.items():
        if value is None:
            continue
        formatted_value = _format_field_value(field, value, snapshot.asset_class)
        data_items.append(f"{field}: {formatted_value}")
    
    return f"MARKET DATA ({ticker} - {asset_class}): {' | '.join(data_items)}"


def _format_field_value(field: str, value: Any, asset_class: AssetClass) -> str:
    """Format individual field values with appropriate units and context."""
    
    if value is None:
        return "N/A"
    
    # Convert string values to float for processing
    try:
        if isinstance(value, str) and value.replace('.', '').replace('-', '').replace('+', '').isdigit():
            numeric_value = float(value)
        elif isinstance(value, (int, float)):
            numeric_value = float(value)
        else:
            numeric_value = None
    except:
        numeric_value = None
    
    # Percentage fields with timeframe context
    if "change_pct" in field:
        if numeric_value is not None:
            return f"{numeric_value:+.2f}% (daily change)"
        return f"{value}% (daily change)"
    
    # Basis points fields with context
    if "bp" in field or "change_bp" in field:
        if numeric_value is not None:
            return f"{numeric_value:+.0f}bp (daily change)"
        return f"{value}bp (daily change)"
    
    # Price/rate fields
    if field in ["price", "spot_rate", "rate_current"]:
        if numeric_value is not None:
            if asset_class == AssetClass.FX:
                return f"{numeric_value:.4f} (current rate)"
            elif asset_class == AssetClass.RATE:
                return f"{numeric_value:.2f}% (current yield)"
            else:
                return f"${numeric_value:,.2f} (current price)"
        return str(value)
    
    # Market cap in billions
    if field == "market_cap_b":
        if numeric_value is not None:
            return f"${numeric_value:.1f}B (market capitalization)"
        return f"${value}B (market cap)"
    
    # Moving averages with context
    if field in ["ma_50d", "ma_200d"]:
        period = "50-day" if "50d" in field else "200-day"
        if numeric_value is not None:
            if asset_class == AssetClass.FX:
                return f"{numeric_value:.4f} ({period} MA)"
            elif asset_class == AssetClass.RATE:
                return f"{numeric_value:.2f}% ({period} MA)"
            else:
                return f"${numeric_value:,.2f} ({period} MA)"
        return f"{value} ({period} MA)"
    
    # Volatility fields with context
    if field == "volatility_30d":
        if numeric_value is not None:
            return f"{numeric_value:.1f}% (30-day annualized volatility)"
        return f"{value}% (30-day volatility)"
    
    if field == "volatility_rank":
        if numeric_value is not None:
            return f"{numeric_value:.0f}/100 (volatility percentile rank)"
        return f"{value}/100 (volatility rank)"
    
    # RSI with context
    if field == "rsi_14d":
        if numeric_value is not None:
            level = "oversold" if numeric_value < 30 else "overbought" if numeric_value > 70 else "neutral"
            return f"{numeric_value:.0f} (14-day RSI, {level})"
        return f"{value} (14-day RSI)"
    
    # Trend indicators with explanations
    if field == "trend_strength":
        return f"{value} (price vs MA trend analysis)"
    
    if field == "trend_direction":
        return f"{value} (rate trend analysis)"
    
    # Commodity-specific indicators
    if field == "seasonal_factor":
        return f"{value} (seasonal price tendency)"
    
    if field == "contango_level":
        if numeric_value is not None:
            if numeric_value > 0:
                return f"+{numeric_value:.1f}% (contango - futures > spot)"
            elif numeric_value < 0:
                return f"{numeric_value:.1f}% (backwardation - futures < spot)"
            else:
                return "0% (flat futures curve)"
        return f"{value} (futures curve shape)"
    
    # Index-specific indicators
    if field == "breadth_ratio":
        if numeric_value is not None:
            if numeric_value > 1.0:
                return f"{numeric_value:.2f} (more stocks advancing)"
            elif numeric_value < 1.0:
                return f"{numeric_value:.2f} (more stocks declining)"
            else:
                return f"{numeric_value:.2f} (balanced market breadth)"
        return f"{value} (advance/decline ratio)"
    
    if field == "fear_greed_index":
        if numeric_value is not None:
            if numeric_value < 25:
                sentiment = "extreme fear"
            elif numeric_value < 45:
                sentiment = "fear"
            elif numeric_value < 55:
                sentiment = "neutral"
            elif numeric_value < 75:
                sentiment = "greed"
            else:
                sentiment = "extreme greed"
            return f"{numeric_value:.0f}/100 (market sentiment: {sentiment})"
        return f"{value}/100 (fear/greed index)"
    
    # Volume
    if field == "volume":
        if numeric_value is not None:
            if numeric_value >= 1e9:
                return f"{numeric_value/1e9:.1f}B shares (daily volume)"
            elif numeric_value >= 1e6:
                return f"{numeric_value/1e6:.1f}M shares (daily volume)"
            elif numeric_value >= 1e3:
                return f"{numeric_value/1e3:.1f}K shares (daily volume)"
            else:
                return f"{numeric_value:,.0f} shares (daily volume)"
        return f"{value} (daily volume)"
    
    # PE ratio
    if field == "pe_ratio":
        if numeric_value is not None:
            valuation = "expensive" if numeric_value > 25 else "cheap" if numeric_value < 15 else "fair"
            return f"{numeric_value:.1f}x (P/E ratio, {valuation})"
        return f"{value}x (P/E ratio)"
    
    # Beta with context
    if field == "beta":
        if numeric_value is not None:
            risk = "high volatility" if numeric_value > 1.5 else "low volatility" if numeric_value < 0.8 else "market volatility"
            return f"{numeric_value:.2f} (beta vs market, {risk})"
        return f"{value} (beta)"
    
    # Dividend yield
    if field == "dividend_yield":
        if numeric_value is not None:
            return f"{numeric_value:.2f}% (annual dividend yield)"
        return f"{value}% (dividend yield)"
    
    # EPS and growth
    if field == "eps_ttm":
        if numeric_value is not None:
            return f"${numeric_value:.2f} (earnings per share TTM)"
        return f"${value} (EPS TTM)"
    
    if field == "eps_growth_3y":
        if numeric_value is not None:
            trend = "growing" if numeric_value > 10 else "declining" if numeric_value < -5 else "stable"
            return f"{numeric_value:+.1f}% (3-year EPS growth, {trend})"
        return f"{value}% (3-year EPS growth)"
    
    # Revenue metrics
    if field == "revenue_ttm_b":
        if numeric_value is not None:
            return f"${numeric_value:.1f}B (revenue TTM)"
        return f"${value}B (revenue TTM)"
    
    if field == "revenue_growth_3y":
        if numeric_value is not None:
            trend = "expanding" if numeric_value > 15 else "contracting" if numeric_value < 0 else "steady"
            return f"{numeric_value:+.1f}% (3-year revenue growth, {trend})"
        return f"{value}% (3-year revenue growth)"
    
    # Financial health ratios
    if field == "profit_margin":
        if numeric_value is not None:
            health = "excellent" if numeric_value > 20 else "good" if numeric_value > 10 else "poor" if numeric_value < 5 else "fair"
            return f"{numeric_value:.1f}% (net profit margin, {health})"
        return f"{value}% (profit margin)"
    
    if field == "roe":
        if numeric_value is not None:
            performance = "excellent" if numeric_value > 20 else "good" if numeric_value > 15 else "poor" if numeric_value < 10 else "fair"
            return f"{numeric_value:.1f}% (return on equity, {performance})"
        return f"{value}% (ROE)"
    
    if field == "debt_to_equity":
        if numeric_value is not None:
            risk = "high debt" if numeric_value > 1.0 else "moderate debt" if numeric_value > 0.5 else "low debt"
            return f"{numeric_value:.2f} (debt/equity ratio, {risk})"
        return f"{value} (debt/equity ratio)"
    
    # High/low values with timeframe
    if "high_" in field or "low_" in field:
        timeframe_map = {
            "1w": "1-week",
            "3m": "3-month", 
            "52w": "52-week"
        }
        
        timeframe = "period"
        for key, label in timeframe_map.items():
            if key in field:
                timeframe = label
                break
        
        if numeric_value is not None:
            if asset_class == AssetClass.FX:
                return f"{numeric_value:.4f} ({timeframe} {'high' if 'high' in field else 'low'})"
            elif asset_class == AssetClass.RATE:
                return f"{numeric_value:.2f}% ({timeframe} {'high' if 'high' in field else 'low'})"
            else:
                return f"${numeric_value:,.2f} ({timeframe} {'high' if 'high' in field else 'low'})"
        return f"{value} ({timeframe} {'high' if 'high' in field else 'low'})"
    
    # Default: return as-is
    return str(value)
