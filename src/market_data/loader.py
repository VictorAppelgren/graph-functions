"""
Market data loader utility for analysis agents.
Provides formatted market context strings for agent prompts.
"""

from typing import Optional, Dict, Any
from utils import app_logging

logger = app_logging.get_logger(__name__)


def load_market_context(topic_id: str) -> Optional[str]:
    """
    Load market data for a topic and format as concise context string.
    
    Args:
        topic_id: Topic ID to load market data for
        
    Returns:
        Formatted string with current market data, or None if no data exists
        
    Example outputs:
        "EURUSD=X: 1.0550 | 1D: -0.25% | MA50: 1.0580 | MA200: 1.0620 | Vol: 8.5% | RSI: 45 | 52W: 1.0450-1.1200 | 1W: 1.0520-1.0600 | 3M: 1.0450-1.0850 | Updated: 2025-11-24"
        "AAPL: $185.50 | 1D: +1.2% | MA50: 182.30 | MA200: 175.80 | Vol: 22.3% | RSI: 68 | 52W: 164.08-199.62 | Updated: 2025-11-24"
        None (if no market data)
    """
    from src.market_data.neo4j_updater import load_market_data_from_neo4j
    
    try:
        data = load_market_data_from_neo4j(topic_id)
        
        # No data or marked as NO_TICKER
        if not data or data.get('ticker') == 'NO_TICKER':
            logger.debug(f"No market data available for topic: {topic_id}")
            return None
        
        ticker = data.get('ticker', 'Unknown')
        asset_class = data.get('asset_class', 'unknown')
        market_data = data.get('market_data', {})
        
        if not market_data:
            logger.debug(f"Empty market data for topic: {topic_id}")
            return None
        
        # Build context string
        parts = []
        
        # 1. Ticker and current price
        price_str = _format_current_price(ticker, asset_class, market_data)
        if price_str:
            parts.append(price_str)
        
        # 2. Daily change
        change_str = _format_daily_change(market_data)
        if change_str:
            parts.append(change_str)
        
        # 3. Moving averages
        ma_str = _format_moving_averages(market_data)
        if ma_str:
            parts.append(ma_str)
        
        # 4. Volatility & momentum
        vol_str = _format_volatility_momentum(market_data)
        if vol_str:
            parts.append(vol_str)
        
        # 5. 52-week range
        range_str = _format_52w_range(market_data)
        if range_str:
            parts.append(range_str)
        
        # 6. Recent highs/lows (1W, 3M)
        recent_str = _format_recent_levels(market_data)
        if recent_str:
            parts.append(recent_str)
        
        # 7. Last update date
        last_update = data.get('last_update', '')
        if last_update and isinstance(last_update, str):
            # Extract date only (YYYY-MM-DD)
            date_part = last_update.split('T')[0] if 'T' in last_update else last_update[:10]
            parts.append(f"Updated: {date_part}")
        
        if not parts:
            logger.debug(f"No formattable market data for topic: {topic_id}")
            return None
        
        context = " | ".join(parts)
        logger.debug(f"Market context for {topic_id}: {context}")
        return context
        
    except Exception as e:
        logger.warning(f"Failed to load market context for {topic_id}: {e}")
        return None


def _format_current_price(ticker: str, asset_class: str, market_data: Dict[str, Any]) -> Optional[str]:
    """Format current price based on asset class."""
    try:
        if asset_class == 'fx':
            # FX: Show spot rate with 4 decimals
            spot_rate = market_data.get('spot_rate')
            if spot_rate is not None:
                return f"{ticker}: {float(spot_rate):.4f}"
        
        elif asset_class in ['stock', 'index', 'commodity']:
            # Stocks/indices/commodities: Show price with 2 decimals
            price = market_data.get('price')
            if price is not None:
                return f"{ticker}: ${float(price):.2f}"
        
        elif asset_class == 'rate':
            # Interest rates: Show as percentage
            rate = market_data.get('rate_current')
            if rate is not None:
                return f"{ticker}: {float(rate):.2f}%"
    except (ValueError, TypeError):
        pass
    
    return None


def _format_daily_change(market_data: Dict[str, Any]) -> Optional[str]:
    """Format daily change percentage."""
    try:
        change = market_data.get('change_pct') or market_data.get('change_1d_pct')
        if change is not None:
            change_float = float(change)
            sign = '+' if change_float > 0 else ''
            return f"1D: {sign}{change_float:.2f}%"
    except (ValueError, TypeError):
        pass
    return None


def _format_moving_averages(market_data: Dict[str, Any]) -> Optional[str]:
    """Format moving averages (MA50 and MA200)."""
    parts = []
    
    try:
        ma50 = market_data.get('ma_50d')
        if ma50 is not None:
            parts.append(f"MA50: {float(ma50):.2f}")
    except (ValueError, TypeError):
        pass
    
    try:
        ma200 = market_data.get('ma_200d')
        if ma200 is not None:
            parts.append(f"MA200: {float(ma200):.2f}")
    except (ValueError, TypeError):
        pass
    
    return " | ".join(parts) if parts else None


def _format_volatility_momentum(market_data: Dict[str, Any]) -> Optional[str]:
    """Format volatility and momentum indicators."""
    parts = []
    
    try:
        vol = market_data.get('volatility_30d')
        if vol is not None:
            parts.append(f"Vol: {float(vol):.1f}%")
    except (ValueError, TypeError):
        pass
    
    try:
        rsi = market_data.get('rsi_14d')
        if rsi is not None:
            parts.append(f"RSI: {float(rsi):.0f}")
    except (ValueError, TypeError):
        pass
    
    return " | ".join(parts) if parts else None


def _format_52w_range(market_data: Dict[str, Any]) -> Optional[str]:
    """Format 52-week high/low range."""
    try:
        high_52w = market_data.get('high_52w')
        low_52w = market_data.get('low_52w')
        
        if high_52w is not None and low_52w is not None:
            return f"52W: {float(low_52w):.2f}-{float(high_52w):.2f}"
    except (ValueError, TypeError):
        pass
    
    return None


def _format_recent_levels(market_data: Dict[str, Any]) -> Optional[str]:
    """Format recent highs/lows (1W, 3M)."""
    parts = []
    
    try:
        high_1w = market_data.get('high_1w')
        low_1w = market_data.get('low_1w')
        if high_1w is not None and low_1w is not None:
            parts.append(f"1W: {float(low_1w):.2f}-{float(high_1w):.2f}")
    except (ValueError, TypeError):
        pass
    
    try:
        high_3m = market_data.get('high_3m')
        low_3m = market_data.get('low_3m')
        if high_3m is not None and low_3m is not None:
            parts.append(f"3M: {float(low_3m):.2f}-{float(high_3m):.2f}")
    except (ValueError, TypeError):
        pass
    
    return " | ".join(parts) if parts else None


def get_market_context_for_prompt(topic_id: str) -> str:
    """
    Get market context string for agent prompts.
    Returns formatted context or fallback message.
    
    This is the main function agents should call.
    
    Args:
        topic_id: Topic ID to load market data for
        
    Returns:
        Formatted market context or "No current market data available"
    """
    context = load_market_context(topic_id)
    return context if context else "No current market data available"
