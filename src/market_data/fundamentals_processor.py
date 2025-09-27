"""
Main fundamentals processor - orchestrates the complete flow.
"""

import os
import sys
from typing import Dict, Any, Tuple

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from .ticker_resolver import resolve_ticker_llm
from .yahoo_provider import fetch_market_data_yahoo
# from .alphavantage_provider import fetch_market_data as fetch_market_data_alphavantage
from .formatter import format_market_data_display, format_market_data_for_analysis
from .neo4j_updater import create_neo4j_update_draft, apply_neo4j_update, preview_neo4j_update
from .models import TickerResolution, MarketSnapshot, Neo4jUpdate, AssetClass
from utils import app_logging

logger = app_logging.get_logger(__name__)


def process_topic_fundamentals(
    topic_id: str, 
    topic_name: str, 
    topic_type: str = None,
    test_mode: bool = True
) -> Tuple[TickerResolution, MarketSnapshot, Neo4jUpdate]:
    """
    Complete fundamentals processing pipeline for a topic.
    
    Args:
        topic_id: Neo4j topic ID
        topic_name: Human-readable topic name
        topic_type: Optional topic type hint
        test_mode: If True, don't write to Neo4j
    
    Returns:
        Tuple of (ticker_resolution, market_snapshot, neo4j_update_draft)
    """
    logger.info("=" * 80)
    logger.info("🚀 === FUNDAMENTALS PROCESSING PIPELINE STARTED ===")
    logger.info("=" * 80)
    logger.info(f"🏷️  Topic ID: {topic_id}")
    logger.info(f"📝 Topic Name: {topic_name}")
    logger.info(f"🧪 Test Mode: {test_mode}")
    logger.info(f"🔧 Topic Type: {topic_type or 'Auto-detect'}")
    
    # Step 1: Resolve ticker using LLM
    logger.info("=" * 60)
    logger.info("=== STEP 1: LLM TICKER RESOLUTION ===")
    logger.info("=" * 60)
    logger.info(f"🤖 Using smart LLM router for ticker resolution")
    logger.info(f"🎯 Input Topic: '{topic_name}'")
    logger.info(f"🔄 Calling LLM...")
    
    ticker_resolution = resolve_ticker_llm(topic_name, topic_type)
    
    logger.info("=" * 40)
    logger.info("✅ LLM TICKER RESOLUTION COMPLETE!")
    logger.info("=" * 40)
    logger.info(f"🎯 Resolved Ticker: {ticker_resolution.resolved_ticker}")
    logger.info(f"📈 Asset Class: {ticker_resolution.asset_class.value}")
    logger.info(f"🎯 Confidence: {ticker_resolution.confidence:.2f}")
    logger.info(f"💭 LLM Reasoning: {ticker_resolution.motivation}")
    
    if ticker_resolution.confidence < 0.7:
        logger.error("=" * 40)
        logger.error("❌ LOW CONFIDENCE TICKER RESOLUTION!")
        logger.error("=" * 40)
        logger.error(f"🎯 Confidence: {ticker_resolution.confidence:.2f} < 0.7 threshold")
        raise ValueError(f"Low confidence ticker resolution: {ticker_resolution.confidence}")
    
    if ticker_resolution.asset_class == AssetClass.UNKNOWN:
        logger.error("=" * 40)
        logger.error("❌ UNKNOWN ASSET CLASS!")
        logger.error("=" * 40)
        logger.error(f"🎯 Topic: {topic_name}")
        raise ValueError(f"Could not determine asset class for {topic_name}")
    
    # Step 2: Fetch market data from Yahoo Finance
    logger.info("=" * 60)
    logger.info("=== STEP 2: FETCHING MARKET DATA ===")
    logger.info("=" * 60)
    logger.info(f"📊 Data Source: Yahoo Finance (free, no API key needed)")
    logger.info(f"🎯 Target Ticker: {ticker_resolution.resolved_ticker}")
    logger.info(f"📈 Asset Class: {ticker_resolution.asset_class.value}")
    
    try:
        logger.info("🔄 Connecting to Yahoo Finance...")
        market_snapshot = fetch_market_data_yahoo(
            ticker_resolution.resolved_ticker,
            ticker_resolution.asset_class
        )
        logger.info("=" * 40)
        logger.info("✅ YAHOO FINANCE SUCCESS!")
        logger.info("=" * 40)
        logger.info(f"📊 Fetched {len(market_snapshot.data)} data fields")
        logger.info(f"💰 Current Price: {market_snapshot.data.get('current_price', 'N/A')}")
        logger.info(f"💱 Currency: {market_snapshot.data.get('currency', 'N/A')}")
        logger.info(f"🕒 Source: {market_snapshot.source}")
    
    except Exception as yahoo_error:
        logger.error("=" * 40)
        logger.error("❌ YAHOO FINANCE FAILED!")
        logger.error("=" * 40)
        logger.error(f"💥 Error: {yahoo_error}")
        logger.error(f"🎯 Ticker: {ticker_resolution.resolved_ticker}")
        logger.error(f"📈 Asset Class: {ticker_resolution.asset_class.value}")
        raise ValueError(f"Yahoo Finance failed for {ticker_resolution.resolved_ticker}: {yahoo_error}")
    
    if not market_snapshot:
        raise ValueError("No market data could be fetched")
    
    # Step 3: Create Neo4j update draft
    logger.info("=" * 60)
    logger.info("=== STEP 3: NEO4J UPDATE PREPARATION ===")
    logger.info("=" * 60)
    logger.info(f"🗄️  Target Topic ID: {topic_id}")
    logger.info(f"📊 Market Data Fields: {len(market_snapshot.data)}")
    logger.info(f"🔄 Creating Neo4j update draft...")
    
    neo4j_update = create_neo4j_update_draft(topic_id, market_snapshot)
    
    logger.info("=" * 40)
    logger.info("✅ NEO4J UPDATE DRAFT CREATED!")
    logger.info("=" * 40)
    logger.info(f"🗄️  Update Type: {neo4j_update.update_type}")
    logger.info(f"📝 Properties Count: {len(neo4j_update.properties)}")
    
    if test_mode:
        logger.info("🧪 TEST MODE: Neo4j update created but NOT executed")
        logger.info("💡 To execute: Set test_mode=False")
    else:
        logger.info("🚀 PRODUCTION MODE: Writing to Neo4j database...")
        success = apply_neo4j_update(neo4j_update)
        if success:
            logger.info("✅ Successfully wrote market data to Neo4j!")
        else:
            logger.error("❌ Failed to write market data to Neo4j")
    
    logger.info("=" * 80)
    logger.info("🎉 === FUNDAMENTALS PROCESSING PIPELINE COMPLETE ===")
    logger.info("=" * 80)
    logger.info(f"✅ Ticker Resolution: {ticker_resolution.resolved_ticker}")
    logger.info(f"✅ Market Data: {len(market_snapshot.data)} fields from {market_snapshot.source}")
    logger.info(f"✅ Neo4j Update: Ready for topic {topic_id}")
    logger.info("=" * 80)
    
    return ticker_resolution, market_snapshot, neo4j_update


def print_fundamentals_results(
    ticker_resolution: TickerResolution,
    market_snapshot: MarketSnapshot,
    neo4j_update: Neo4jUpdate
) -> None:
    """
    Print formatted results of fundamentals processing.
    """
    print("\n" + "="*60)
    print("FUNDAMENTALS PROCESSING RESULTS")
    print("="*60)
    
    # Ticker Resolution
    print(f"\n1. TICKER RESOLUTION:")
    print(f"   Topic: {ticker_resolution.topic_name}")
    print(f"   Resolved: {ticker_resolution.resolved_ticker}")
    print(f"   Asset Class: {ticker_resolution.asset_class.value}")
    print(f"   Confidence: {ticker_resolution.confidence:.2f}")
    print(f"   Motivation: {ticker_resolution.motivation}")
    
    # Market Data
    print(f"\n2. MARKET DATA:")
    market_display = format_market_data_display(market_snapshot)
    for line in market_display.split('\n'):
        print(f"   {line}")
    
    # Analysis Format
    print(f"\n3. ANALYSIS FORMAT:")
    analysis_format = format_market_data_for_analysis(market_snapshot)
    print(f"   {analysis_format}")
    
    # Neo4j Preview
    print(f"\n4. NEO4J UPDATE PREVIEW:")
    neo4j_preview = preview_neo4j_update(neo4j_update)
    for line in neo4j_preview.split('\n'):
        print(f"   {line}")
    
    print("\n" + "="*60)
