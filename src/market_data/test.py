"""
Simple test script for market data functionality.
Tests the market data orchestrator with excellent logging.

Usage:
    python -m src.market_data.test --limit 5
"""

import sys
import os

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env file FIRST before any other imports
from utils.env_loader import load_env
load_env()

import argparse
from datetime import datetime

from src.market_data.market_data_entrypoint import (
    run_market_data_orchestrator,
    run_market_data_if_needed
)
from src.graph.neo4j_client import run_cypher
from utils import app_logging

logger = app_logging.get_logger(__name__)


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def test_orchestrator(limit: int = None):
    """Test the market data orchestrator directly."""
    print_separator()
    if limit:
        print(f"🧪 TEST: Market Data Orchestrator (limit={limit})")
    else:
        print(f"🧪 TEST: Market Data Orchestrator (ALL TOPICS)")
    print_separator()
    print(f"⏰ Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()
    
    try:
        # Run orchestrator
        if limit:
            logger.info(f"🚀 Running market data orchestrator with limit={limit}")
        else:
            logger.info(f"🚀 Running market data orchestrator for ALL topics")
        results = run_market_data_orchestrator(limit=limit)
        
        # Print results
        print_separator("-")
        print("📊 RESULTS:")
        print_separator("-")
        print(f"✅ Total topics processed: {results['total_topics']}")
        print(f"✅ Existing tickers used: {results['existing_tickers']}")
        print(f"🤖 LLM resolved tickers: {results['llm_resolved']}")
        print(f"🚫 No market data appropriate: {results['no_ticker_appropriate']}")
        print(f"⏭️  Already marked NO_TICKER: {results['already_marked_no_ticker']}")
        print(f"💾 Data successfully fetched: {results['data_fetched']}")
        print(f"⏭️  Skipped (low confidence): {results['skipped']}")
        print(f"❌ Errors: {results['errors']}")
        print_separator("-")
        
        # Success rate
        if results['total_topics'] > 0:
            success_rate = (results['data_fetched'] / results['total_topics']) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        print()
        print(f"⏰ Completed at: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print_separator()
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        print_separator()
        print(f"❌ TEST FAILED: {e}")
        print_separator()
        raise


def test_entrypoint():
    """Test the run_market_data_if_needed entrypoint."""
    print_separator()
    print("🧪 TEST: Market Data Entrypoint (run_market_data_if_needed)")
    print_separator()
    print(f"⏰ Started at: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"⏰ Current hour: {datetime.now().hour}")
    print()
    
    try:
        logger.info("🚀 Testing run_market_data_if_needed()")
        results = run_market_data_if_needed()
        
        print_separator("-")
        if results is None:
            print("⏭️  SKIPPED: Not the right hour or already completed today")
            print("   (Market data runs at 6am, 10am, 4pm)")
        else:
            print("✅ EXECUTED: Market data update ran")
            print(f"   • Topics updated: {results['data_fetched']}/{results['total_topics']}")
        print_separator("-")
        
        print()
        print(f"⏰ Completed at: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print_separator()
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        print_separator()
        print(f"❌ TEST FAILED: {e}")
        print_separator()
        raise


def verify_topic_data(topic_id: str):
    """Verify market data was saved for a specific topic."""
    print_separator()
    print(f"🔍 VERIFY: Market data for topic '{topic_id}'")
    print_separator()
    
    query = """
        MATCH (t:Topic {id: $topic_id})
        RETURN 
            t.market_data_yahoo_ticker as ticker,
            t.market_data_asset_class as asset_class,
            t.market_data_spot_rate as spot_rate,
            t.market_data_price as price,
            t.market_data_rate_current as rate,
            t.market_data_change_1d_pct as change_pct,
            t.market_data_last_updated as last_updated,
            keys(t) as all_keys
    """
    
    try:
        result = run_cypher(query, {"topic_id": topic_id})
        
        if not result:
            print(f"❌ Topic '{topic_id}' not found in Neo4j")
            print_separator()
            return
        
        data = result[0]
        
        print(f"📊 Topic: {topic_id}")
        print(f"   • Ticker: {data.get('ticker', 'N/A')}")
        print(f"   • Asset Class: {data.get('asset_class', 'N/A')}")
        
        # Show price based on asset class
        if data.get('spot_rate'):
            print(f"   • Spot Rate: {data['spot_rate']}")
        elif data.get('price'):
            print(f"   • Price: {data['price']}")
        elif data.get('rate'):
            print(f"   • Rate: {data['rate']}")
        
        if data.get('change_pct'):
            print(f"   • Daily Change: {data['change_pct']}%")
        
        print(f"   • Last Updated: {data.get('last_updated', 'N/A')}")
        
        # Count market_data_ fields
        market_data_fields = [k for k in data['all_keys'] if k.startswith('market_data_')]
        print(f"   • Total market_data_ fields: {len(market_data_fields)}")
        
        print_separator()
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        print(f"❌ ERROR: {e}")
        print_separator()


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test market data functionality")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of topics to process (default: all topics)"
    )
    parser.add_argument(
        "--test-entrypoint",
        action="store_true",
        help="Test the run_market_data_if_needed entrypoint"
    )
    parser.add_argument(
        "--verify",
        type=str,
        help="Verify market data for a specific topic ID (e.g., 'eurusd')"
    )
    
    args = parser.parse_args()
    
    print()
    print("=" * 80)
    print("🧪 MARKET DATA TEST SUITE")
    print("=" * 80)
    print()
    
    try:
        if args.verify:
            # Verify specific topic
            verify_topic_data(args.verify)
        
        elif args.test_entrypoint:
            # Test entrypoint
            test_entrypoint()
        
        else:
            # Test orchestrator
            results = test_orchestrator(limit=args.limit)
            
            # Suggest verification
            if results['data_fetched'] > 0:
                print()
                print("💡 TIP: Verify a topic with:")
                print("   python -m src.market_data.test --verify eurusd")
                print()
                print("💡 TIP: Test with limit:")
                print("   python -m src.market_data.test --limit 5")
                print()
        
        print()
        print("=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ TESTS FAILED")
        print("=" * 80)
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
