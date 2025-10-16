#!/usr/bin/env python3
"""
Test script for fundamentals functionality.
Gets a random topic and processes it through the complete pipeline.
"""

import os
import sys
import random
from typing import Dict, Any, List

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.neo4j_client import run_cypher, execute_write
from src.market_data.fundamentals_processor import process_topic_fundamentals, print_fundamentals_results
from src.market_data.neo4j_updater import load_market_data_from_neo4j
from src.market_data.formatter import format_market_data_display
from src.market_data.models import MarketSnapshot, AssetClass
from datetime import date
from utils import app_logging

logger = app_logging.get_logger(__name__)


def list_all_topics() -> None:
    """List all topics in Neo4j for selection."""
    print(f"\n{'='*80}")
    print("📋 ALL TOPICS IN NEO4J DATABASE")
    print(f"{'='*80}")
    
    query = """
        MATCH (t:Topic)
        RETURN t.id as id, t.name as name, t.category as category
        ORDER BY t.name
        LIMIT 50
    """
    
    try:
        result = run_cypher(query, {})
        
        if not result:
            print("⚠️  No topics found in Neo4j database")
            return
            
        print(f"Found {len(result)} topics:")
        print(f"{'ID':<25} {'NAME':<40} {'CATEGORY':<15}")
        print("-" * 80)
        
        for record in result:
            topic_id = record.get('id') or 'N/A'
            topic_name = record.get('name') or 'N/A'
            category = record.get('category') or 'N/A'
            
            # Convert to strings and truncate long names for display
            topic_id = str(topic_id)
            topic_name = str(topic_name)
            category = str(category)
            
            display_name = topic_name[:37] + "..." if len(topic_name) > 40 else topic_name
            display_id = topic_id[:22] + "..." if len(topic_id) > 25 else topic_id
            
            print(f"{display_id:<25} {display_name:<40} {category:<15}")
            
        print(f"\n✅ Listed {len(result)} topics from Neo4j")
        
    except Exception as e:
        logger.error(f"Failed to list topics: {e}")
        print(f"❌ Error listing topics: {e}")


def get_random_topic() -> Dict[str, Any]:
    """Get a random topic from Neo4j."""
    logger.info("Fetching random topic from Neo4j...")
    
    query = """
        MATCH (t:Topic)
        WHERE t.name IS NOT NULL
        RETURN t.id as id, t.name as name, t.type as type
        ORDER BY rand()
        LIMIT 1
    """
    
    result = run_cypher(query)
    
    if not result:
        raise ValueError("No topics found in Neo4j database")
    
    # log all topics 
    for topic in result:
        logger.info(f"  - {topic['name']} (id: {topic['id']})")

    topic = result[0]
    logger.info(f"Selected topic: {topic['name']} (id: {topic['id']})")
    
    return topic


def get_sample_topics() -> List[Dict[str, Any]]:
    """Get a few sample topics for testing."""
    logger.info("Fetching sample topics from Neo4j...")
    
    query = """
        MATCH (t:Topic)
        WHERE t.name IS NOT NULL
        RETURN t.id as id, t.name as name, t.type as type
        LIMIT 5
    """
    
    result = run_cypher(query)
    
    if not result:
        raise ValueError("No topics found in Neo4j database")
    
    logger.info(f"Found {len(result)} sample topics")
    for topic in result:
        logger.info(f"  - {topic['name']} (id: {topic['id']})")
    
    return result


def test_specific_topic(topic_name: str) -> None:
    """Test fundamentals processing for a specific topic name."""
    logger.info(f"Testing specific topic: {topic_name}")
    
    # Create a mock topic for testing
    topic = {
        "id": f"test_{topic_name.lower().replace(' ', '_')}",
        "name": topic_name,
        "type": "test"
    }
    
    try:
        ticker_resolution, market_snapshot, neo4j_update = process_topic_fundamentals(
            topic_id=topic["id"],
            topic_name=topic["name"],
            topic_type=topic.get("type"),
            test_mode=True
        )
        
        print_fundamentals_results(ticker_resolution, market_snapshot, neo4j_update)
        
    except Exception as e:
        logger.error(f"Error processing {topic_name}: {e}")
        print(f"\n❌ ERROR processing {topic_name}: {e}")


def test_random_topic() -> None:
    """Test fundamentals processing for a random topic from Neo4j."""
    try:
        topic = get_random_topic()
        
        ticker_resolution, market_snapshot, neo4j_update = process_topic_fundamentals(
            topic_id=topic["id"],
            topic_name=topic["name"],
            topic_type=topic.get("type"),
            test_mode=True
        )
        
        print_fundamentals_results(ticker_resolution, market_snapshot, neo4j_update)
        
    except Exception as e:
        logger.error(f"Error in random topic test: {e}")
        print(f"\n❌ ERROR: {e}")


def test_sample_topics() -> None:
    """Test fundamentals processing for multiple sample topics."""
    try:
        topics = get_sample_topics()
        
        for i, topic in enumerate(topics, 1):
            print(f"\n{'='*20} TESTING TOPIC {i}/{len(topics)} {'='*20}")
            
            try:
                ticker_resolution, market_snapshot, neo4j_update = process_topic_fundamentals(
                    topic_id=topic["id"],
                    topic_name=topic["name"],
                    topic_type=topic.get("type"),
                    test_mode=True
                )
                
                print_fundamentals_results(ticker_resolution, market_snapshot, neo4j_update)
                
            except Exception as e:
                logger.error(f"Error processing topic {topic['name']}: {e}")
                print(f"\n❌ ERROR processing {topic['name']}: {e}")
                continue
    except Exception as e:
        logger.error(f"Error in sample topics test: {e}")
        print(f"\n❌ ERROR: {e}")


def test_hardcoded_tickers():
    """Test hardcoded ticker-friendly topics that should work reliably."""
    logger.info("Testing hardcoded ticker-friendly topics...")
    
    # Ticker-friendly test cases (topics that should resolve to valid Yahoo Finance symbols)
    test_cases = [
        ("EUR/USD", "fx", "eurusd_test"),
        ("WTI Crude Oil", "commodity", "wti_crude_test"), 
        ("10-Year Treasury", "rate", "treasury_10y_test"),
        ("S&P 500", "index", "sp500_test"),
        ("Gold", "commodity", "gold_test"),
        ("Tesla Inc", "stock", "tesla_test")
    ]
    
    for topic_name, expected_asset_class, topic_id in test_cases:
        print(f"\n{'='*60}")
        print(f"🧪 TESTING: {topic_name} (expected: {expected_asset_class})")
        print(f"{'='*60}")
        
        try:
            ticker_resolution, market_snapshot, neo4j_update = process_topic_fundamentals(
                topic_id=topic_id,
                topic_name=topic_name,
                test_mode=False  # ENABLE Neo4j writes
            )
            
            print(f"✅ SUCCESS: {topic_name}")
            print(f"   Ticker: {ticker_resolution.resolved_ticker}")
            print(f"   Asset Class: {ticker_resolution.asset_class.value}")
            print(f"   Confidence: {ticker_resolution.confidence:.2f}")
            print(f"   Market Data Fields: {len(market_snapshot.data)}")
            
            print_fundamentals_results(ticker_resolution, market_snapshot, neo4j_update)
                
        except Exception as e:
            logger.error(f"Error testing {topic_name}: {e}")
            print(f"❌ FAILED: {topic_name} - {e}")
            
    print(f"\n{'='*60}")
    print("🏁 HARDCODED TICKER TESTS COMPLETE")
    print(f"{'='*60}")


def test_save_market_data():
    """SAVE ONLY: Fetch and save market data to Neo4j with market_data_ prefixes."""
    print(f"\n\n{'='*80}")
    print("💾 SAVE MARKET DATA TO NEO4J")
    print(f"{'='*80}")
    
    # Real topics from Neo4j with variety
    test_topics = [
        ("eurusd", "EURUSD"),
        ("spx", "S&P 500"), 
        ("gold", "Gold"),
        ("ust10y", "US 10Y Treasury Yield"),
        ("ba", "Boeing")
    ]
    
    for topic_id, topic_name in test_topics:
        print(f"\n{'='*60}")
        print(f"💾 SAVING: {topic_name} (ID: {topic_id})")
        print(f"{'='*60}")
        
        try:
            # Check existing ticker
            existing_ticker = check_existing_yahoo_ticker(topic_id)
            
            if existing_ticker:
                print(f"✅ Found existing ticker: {existing_ticker}")
                success = save_market_data_for_topic(topic_id, topic_name, existing_ticker)
            else:
                print(f"🔍 No existing ticker, using LLM resolution...")
                success = save_market_data_for_topic(topic_id, topic_name)
                
            if success:
                print(f"✅ SAVED: {topic_name}")
            else:
                print(f"❌ FAILED: {topic_name}")
                
        except Exception as e:
            logger.error(f"Error saving {topic_name}: {e}")
            print(f"❌ ERROR: {topic_name} - {e}")
    
    print(f"\n{'='*80}")
    print("💾 SAVE MARKET DATA COMPLETE")
    print(f"{'='*80}")


def test_load_market_data():
    """LOAD ONLY: Load and format market data from Neo4j."""
    print(f"\n\n{'='*80}")
    print("📊 LOAD MARKET DATA FROM NEO4J")
    print(f"{'='*80}")
    
    # Same topics to load
    test_topics = [
        ("eurusd", "EURUSD"),
        ("spx", "S&P 500"), 
        ("gold", "Gold"),
        ("ust10y", "US 10Y Treasury Yield"),
        ("ba", "Boeing")
    ]
    
    for topic_id, topic_name in test_topics:
        print(f"\n{'='*60}")
        print(f"📊 LOADING: {topic_name} (ID: {topic_id})")
        print(f"{'='*60}")
        
        try:
            # Load market data from Neo4j
            neo4j_data = load_market_data_from_neo4j(topic_id)
            
            if not neo4j_data or not neo4j_data.get("market_data"):
                print(f"⚠️  No market data found in Neo4j for {topic_name}")
                continue
                
            # Convert to MarketSnapshot for formatting
            asset_class = AssetClass(neo4j_data["asset_class"])
            snapshot = MarketSnapshot(
                ticker=neo4j_data["ticker"],
                asset_class=asset_class,
                data=neo4j_data["market_data"],
                updated_at=date.today(),
                source=neo4j_data["source"]
            )
            
            # Format and display
            formatted_display = format_market_data_display(snapshot)
            print(f"\n📊 FORMATTED DATA:")
            print(formatted_display)
            
            print(f"\n✅ Successfully loaded and formatted {len(snapshot.data)} fields")
            
        except Exception as e:
            logger.error(f"Error loading {topic_name}: {e}")
            print(f"❌ ERROR: {topic_name} - {e}")
    
    print(f"\n{'='*80}")
    print("📊 LOAD MARKET DATA COMPLETE")
    print(f"{'='*80}")


def save_market_data_for_topic(topic_id: str, topic_name: str, existing_ticker: str = None) -> bool:
    """Save market data for a single topic."""
    
    if existing_ticker:
        # Use existing ticker, skip LLM
        print(f"🚀 Using existing ticker: {existing_ticker}")
        
        # Determine asset class from ticker pattern
        if "=" in existing_ticker:
            asset_class = AssetClass.FX if existing_ticker.endswith("=X") else AssetClass.COMMODITY
        elif existing_ticker.startswith("^"):
            asset_class = AssetClass.INDEX if "SPX" in existing_ticker or "GSPC" in existing_ticker else AssetClass.RATE
        else:
            asset_class = AssetClass.STOCK
            
        ticker_to_fetch = existing_ticker
        
    else:
        # Use LLM resolution
        print(f"🤖 Resolving ticker with LLM...")
        from src.fundamentals.ticker_resolver import resolve_ticker_llm
        
        resolution = resolve_ticker_llm(topic_name)
        
        if resolution.confidence < 0.8:
            print(f"❌ Low confidence ({resolution.confidence:.2f}), skipping")
            return False
            
        print(f"✅ LLM resolved: {resolution.resolved_ticker} (confidence: {resolution.confidence:.2f})")
        ticker_to_fetch = resolution.resolved_ticker
        asset_class = resolution.asset_class
    
    # Fetch market data to verify ticker works
    print(f"📊 Fetching market data for {ticker_to_fetch}...")
    from src.fundamentals.yahoo_provider import fetch_market_data_yahoo
    
    try:
        snapshot = fetch_market_data_yahoo(ticker_to_fetch, asset_class)
        print(f"✅ Successfully fetched {len(snapshot.data)} fields")
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return False
    
    # Save ticker to Neo4j (only after successful fetch)
    if not existing_ticker:
        print(f"💾 Saving Yahoo ticker to Neo4j...")
        save_yahoo_ticker(topic_id, ticker_to_fetch)
    
    # Save market data with market_data_ prefixes
    print(f"💾 Saving market data to Neo4j...")
    from src.fundamentals.neo4j_updater import create_neo4j_update_draft, apply_neo4j_update
    
    neo4j_update = create_neo4j_update_draft(topic_id, snapshot)
    success = apply_neo4j_update(neo4j_update)
    
    if success:
        print(f"✅ Saved {len(neo4j_update.properties)} market data properties")
        return True
    else:
        print(f"❌ Failed to save market data")
        return False


def test_smart_market_data_flow():
    """Smart market data flow: check existing ticker, resolve if needed, save, load back."""
    print(f"\n\n{'='*80}")
    print("🧠 SMART MARKET DATA FLOW TEST")
    print(f"{'='*80}")
    
    # Real topics from Neo4j with variety
    test_topics = [
        ("eurusd", "EURUSD"),
        ("spx", "S&P 500"), 
        ("gold", "Gold"),
        ("ust10y", "US 10Y Treasury Yield"),
        ("ba", "Boeing")
    ]
    
    for topic_id, topic_name in test_topics:
        print(f"\n{'='*60}")
        print(f"🎯 PROCESSING: {topic_name} (ID: {topic_id})")
        print(f"{'='*60}")
        
        try:
            # Step 1: Check if topic has existing Yahoo ticker
            existing_ticker = check_existing_yahoo_ticker(topic_id)
            
            if existing_ticker:
                print(f"✅ Found existing ticker: {existing_ticker}")
                ticker_to_use = existing_ticker
                skip_llm = True
            else:
                print(f"🔍 No existing ticker, using LLM resolution...")
                skip_llm = False
                
            # Step 2: Process with smart flow
            success = process_topic_smart_flow(topic_id, topic_name, ticker_to_use if skip_llm else None)
            
            if success:
                print(f"✅ SUCCESS: {topic_name}")
                
                # Step 3: Load back and format
                neo4j_data = load_market_data_from_neo4j(topic_id)
                if neo4j_data and neo4j_data.get("market_data"):
                    asset_class = AssetClass(neo4j_data["asset_class"])
                    snapshot = MarketSnapshot(
                        ticker=neo4j_data["ticker"],
                        asset_class=asset_class,
                        data=neo4j_data["market_data"],
                        updated_at=date.today(),
                        source=neo4j_data["source"]
                    )
                    formatted_display = format_market_data_display(snapshot)
                    print(f"\n📊 FORMATTED DATA:")
                    print(formatted_display)
                else:
                    print(f"⚠️  Could not load back market data")
            else:
                print(f"❌ FAILED: {topic_name}")
                
        except Exception as e:
            logger.error(f"Error processing {topic_name}: {e}")
            print(f"❌ ERROR: {topic_name} - {e}")
    
    print(f"\n{'='*80}")
    print("🎯 SMART MARKET DATA FLOW COMPLETE")
    print(f"{'='*80}")


def check_existing_yahoo_ticker(topic_id: str) -> str:
    """Check if topic already has a Yahoo ticker saved."""
    query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN t.market_data_yahoo_ticker as ticker
    """
    
    result = run_cypher(query, {"topic_id": topic_id})
    if result and result[0].get("ticker"):
        return result[0]["ticker"]
    return None


def process_topic_smart_flow(topic_id: str, topic_name: str, existing_ticker: str = None) -> bool:
    """Smart processing: use existing ticker or resolve with LLM, then save everything."""
    
    if existing_ticker:
        # Use existing ticker, skip LLM
        print(f"🚀 Using existing ticker: {existing_ticker}")
        
        # Determine asset class from ticker pattern
        if "=" in existing_ticker:
            asset_class = AssetClass.FX if existing_ticker.endswith("=X") else AssetClass.COMMODITY
        elif existing_ticker.startswith("^"):
            asset_class = AssetClass.INDEX if "SPX" in existing_ticker or "GSPC" in existing_ticker else AssetClass.RATE
        else:
            asset_class = AssetClass.STOCK
            
        ticker_to_fetch = existing_ticker
        
    else:
        # Use LLM resolution
        print(f"🤖 Resolving ticker with LLM...")
        from src.fundamentals.ticker_resolver import resolve_ticker_llm
        
        resolution = resolve_ticker_llm(topic_name)
        
        if resolution.confidence < 0.8:
            print(f"❌ Low confidence ({resolution.confidence:.2f}), skipping")
            return False
            
        print(f"✅ LLM resolved: {resolution.resolved_ticker} (confidence: {resolution.confidence:.2f})")
        ticker_to_fetch = resolution.resolved_ticker
        asset_class = resolution.asset_class
    
    # Fetch market data to verify ticker works
    print(f"📊 Fetching market data for {ticker_to_fetch}...")
    from src.fundamentals.yahoo_provider import fetch_market_data_yahoo
    
    try:
        snapshot = fetch_market_data_yahoo(ticker_to_fetch, asset_class)
        print(f"✅ Successfully fetched {len(snapshot.data)} fields")
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return False
    
    # Save ticker to Neo4j (only after successful fetch)
    if not existing_ticker:
        print(f"💾 Saving Yahoo ticker to Neo4j...")
        save_yahoo_ticker(topic_id, ticker_to_fetch)
    
    # Save market data with market_data_ prefixes
    print(f"💾 Saving market data to Neo4j...")
    from src.fundamentals.neo4j_updater import create_neo4j_update_draft, apply_neo4j_update
    
    neo4j_update = create_neo4j_update_draft(topic_id, snapshot)
    success = apply_neo4j_update(neo4j_update)
    
    if success:
        print(f"✅ Saved {len(neo4j_update.properties)} market data properties")
        return True
    else:
        print(f"❌ Failed to save market data")
        return False


def save_yahoo_ticker(topic_id: str, ticker: str) -> None:
    """Save Yahoo ticker to Neo4j topic."""
    query = """
        MATCH (t:Topic {id: $topic_id})
        SET t.market_data_yahoo_ticker = $ticker
        RETURN t.id as id
    """
    
    result = execute_write(query, {"topic_id": topic_id, "ticker": ticker})
    if not result:
        raise ValueError(f"Topic {topic_id} not found")
        
    print(f"✅ Saved Yahoo ticker: {ticker}")


def test_show_all_market_data():
    """Show formatted market data for ALL topics that have tickers."""
    print(f"\n\n{'='*80}")
    print("📊 ALL TOPICS WITH MARKET DATA")
    print(f"{'='*80}")
    
    # Load all topics with their ticker status
    query = """
        MATCH (t:Topic)
        WHERE t.name IS NOT NULL
        RETURN t.id as id, t.name as name, t.market_data_yahoo_ticker as ticker
        ORDER BY t.name
    """
    
    try:
        result = run_cypher(query)
        
        if not result:
            print("⚠️  No topics found in Neo4j database")
            return
        
        print(f"📋 Found {len(result)} total topics")
        
        # Categorize topics
        has_ticker = []
        no_ticker = []
        not_processed = []
        
        for topic in result:
            ticker = topic.get('ticker')
            if ticker == "NO_TICKER":
                no_ticker.append(topic)
            elif ticker:
                has_ticker.append(topic)
            else:
                not_processed.append(topic)
        
        print(f"✅ Topics with tickers: {len(has_ticker)}")
        print(f"🚫 Topics marked NO_TICKER: {len(no_ticker)}")
        print(f"⏳ Topics not yet processed: {len(not_processed)}")
        
        # Show formatted data for topics with tickers
        if has_ticker:
            print(f"\n{'='*80}")
            print("📊 FORMATTED MARKET DATA FOR ALL TOPICS WITH TICKERS")
            print(f"{'='*80}")
            
            for i, topic in enumerate(has_ticker, 1):
                topic_id = topic['id']
                topic_name = topic['name']
                ticker = topic['ticker']
                
                print(f"\n{'='*100}")
                print(f"📈 [{i}/{len(has_ticker)}] {topic_name} ({ticker})")
                print(f"{'='*100}")
                
                try:
                    # Load market data from Neo4j
                    neo4j_data = load_market_data_from_neo4j(topic_id)
                    
                    if not neo4j_data or not neo4j_data.get("market_data"):
                        print(f"⚠️  No market data found for {topic_name}")
                        continue
                    
                    # Convert to MarketSnapshot for formatting
                    from src.market_data.models import AssetClass, MarketSnapshot
                    from src.market_data.formatter import format_market_data_display
                    
                    asset_class = AssetClass(neo4j_data["asset_class"])
                    snapshot = MarketSnapshot(
                        ticker=neo4j_data["ticker"],
                        asset_class=asset_class,
                        data=neo4j_data["market_data"],
                        updated_at=date.today(),
                        source=neo4j_data["source"]
                    )
                    
                    # Format and display
                    formatted_display = format_market_data_display(snapshot)
                    print(formatted_display)
                    
                    print(f"\n✅ Displayed {len(snapshot.data)} market data fields")
                    
                except Exception as e:
                    logger.error(f"Error loading {topic_name}: {e}")
                    print(f"❌ ERROR loading {topic_name}: {e}")
        
        # Show summary of topics without tickers
        if no_ticker:
            print(f"\n{'='*80}")
            print(f"🚫 TOPICS MARKED AS NO MARKET DATA ({len(no_ticker)} topics)")
            print(f"{'='*80}")
            for topic in no_ticker[:10]:  # Show first 10
                print(f"  • {topic['name']}")
            if len(no_ticker) > 10:
                print(f"  ... and {len(no_ticker) - 10} more")
        
        # Show summary of unprocessed topics
        if not_processed:
            print(f"\n{'='*80}")
            print(f"⏳ TOPICS NOT YET PROCESSED ({len(not_processed)} topics)")
            print(f"{'='*80}")
            print("💡 Run the market data workflow to process these:")
            print("   python run_market_data_workflow.py")
            for topic in not_processed[:5]:  # Show first 5
                print(f"  • {topic['name']}")
            if len(not_processed) > 5:
                print(f"  ... and {len(not_processed) - 5} more")
        
        print(f"\n{'='*80}")
        print("📊 ALL MARKET DATA DISPLAY COMPLETE")
        print(f"{'='*80}")
        
    except Exception as e:
        logger.error(f"Error in show all market data: {e}")
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    print("🚀 FUNDAMENTALS TESTING")
    print("=" * 50)
    
    # First, show all available topics
    list_all_topics()
    
    # Test options
    test_mode = input("\nSelect test mode:\n1. Random topic from Neo4j\n2. Sample topics from Neo4j\n3. Specific test topics\n4. Hardcoded ticker-friendly tests\n5. SAVE Market Data to Neo4j\n6. LOAD Market Data from Neo4j\n7. Complete Flow (Save + Load)\n8. SHOW ALL Topics with Market Data\nChoice (1-8): ").strip()
    
    if test_mode == "1":
        test_random_topic()
    elif test_mode == "2":
        test_sample_topics()
    elif test_mode == "3":
        # Test some known topics
        test_topics = ["Apple Inc", "EUR/USD", "S&P 500", "10-Year Treasury", "Gold"]
        for topic_name in test_topics:
            print(f"\n{'='*20} TESTING {topic_name} {'='*20}")
            try:
                ticker_resolution, market_snapshot, neo4j_update = process_topic_fundamentals(
                    topic_id=f"test_{topic_name.lower().replace(' ', '_').replace('&', 'and')}",
                    topic_name=topic_name,
                    test_mode=True
                )
                print_fundamentals_results(ticker_resolution, market_snapshot, neo4j_update)
            except Exception as e:
                logger.error(f"Error testing {topic_name}: {e}")
                print(f"\n❌ ERROR: {e}")
    elif test_mode == "4":
        test_hardcoded_tickers()
    elif test_mode == "5":
        test_save_market_data()
    elif test_mode == "6":
        test_load_market_data()
    elif test_mode == "7":
        test_smart_market_data_flow()
    elif test_mode == "8":
        test_show_all_market_data()
    else:
        print("Invalid choice. Exiting.")
