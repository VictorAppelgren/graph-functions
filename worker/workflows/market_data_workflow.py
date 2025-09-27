"""
Market Data Workflow - Processes all topics to fetch and save market data.

This workflow:
1. Loads all topics from Neo4j
2. For each topic, determines if market data is appropriate
3. Uses smart ticker resolution (existing vs LLM vs skip)
4. Fetches and saves market data with market_data_ prefixes
5. Tracks progress and skips inappropriate topics
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Canonical import block
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.graph.neo4j_client import run_cypher, execute_write
from utils import app_logging

logger = app_logging.get_logger(__name__)


class MarketDataWorkflow:
    """Workflow to process all topics for market data."""
    
    def __init__(self):
        self.stats = {
            "total_topics": 0,
            "existing_tickers": 0,
            "llm_resolved": 0,
            "no_ticker_appropriate": 0,
            "already_marked_no_ticker": 0,
            "data_fetched": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def run(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run the complete market data workflow."""
        logger.info("🚀 Starting Market Data Workflow")
        
        try:
            # Load all topics
            topics = self.load_all_topics(limit)
            self.stats["total_topics"] = len(topics)
            
            logger.info(f"📊 Processing {len(topics)} topics")
            
            # Process each topic
            for i, topic in enumerate(topics, 1):
                logger.info(f"🎯 [{i}/{len(topics)}] Processing: {topic['name']} (ID: {topic['id']})")
                
                try:
                    self.process_topic(topic)
                except Exception as e:
                    logger.error(f"❌ Error processing topic {topic['id']}: {e}")
                    self.stats["errors"] += 1
            
            # Log final stats
            self.log_final_stats()
            
            return self.stats
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            raise
    
    def load_all_topics(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load all topics from Neo4j."""
        query = """
            MATCH (t:Topic)
            RETURN t.id as id, t.name as name, t.market_data_yahoo_ticker as ticker
            ORDER BY t.name
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        result = run_cypher(query)
        
        if not result:
            logger.warning("⚠️  No topics found in Neo4j")
            return []
        
        logger.info(f"✅ Loaded {len(result)} topics from Neo4j")
        return result
    
    def process_topic(self, topic: Dict[str, Any]) -> None:
        """Process a single topic for market data."""
        topic_id = topic["id"]
        topic_name = topic["name"] or "Unknown"
        existing_ticker = topic.get("ticker")
        
        # Check if already marked as no ticker
        if existing_ticker == "NO_TICKER":
            logger.info(f"⏭️  Skipping {topic_name} - already marked as no market data")
            self.stats["already_marked_no_ticker"] += 1
            return
        
        # Check if has existing valid ticker
        if existing_ticker and existing_ticker != "NO_TICKER":
            logger.info(f"✅ Using existing ticker: {existing_ticker}")
            self.stats["existing_tickers"] += 1
            success = self.fetch_and_save_market_data(topic_id, topic_name, existing_ticker)
            if success:
                self.stats["data_fetched"] += 1
            return
        
        # Use LLM to determine if market data is appropriate
        logger.info(f"🤖 Using LLM to resolve ticker for: {topic_name}")
        
        try:
            from src.market_data.ticker_resolver import resolve_ticker_llm_enhanced
            
            resolution = resolve_ticker_llm_enhanced(topic_name)
            
            if resolution.resolved_ticker is None:
                # LLM determined no market data appropriate
                logger.info(f"🚫 LLM determined no market data for: {topic_name} (reason: {resolution.reason})")
                self.mark_topic_no_ticker(topic_id)
                self.stats["no_ticker_appropriate"] += 1
                return
            
            # LLM found a ticker
            if resolution.confidence < 0.8:
                logger.warning(f"⚠️  Low confidence ({resolution.confidence:.2f}) for {topic_name}, skipping")
                self.stats["skipped"] += 1
                return
            
            logger.info(f"✅ LLM resolved: {resolution.resolved_ticker} (confidence: {resolution.confidence:.2f})")
            self.stats["llm_resolved"] += 1
            
            # Save ticker and fetch data
            self.save_ticker(topic_id, resolution.resolved_ticker)
            success = self.fetch_and_save_market_data(topic_id, topic_name, resolution.resolved_ticker)
            if success:
                self.stats["data_fetched"] += 1
                
        except Exception as e:
            logger.error(f"❌ LLM resolution failed for {topic_name}: {e}")
            self.stats["errors"] += 1
    
    def fetch_and_save_market_data(self, topic_id: str, topic_name: str, ticker: str) -> bool:
        """Fetch market data and save to Neo4j."""
        try:
            from src.market_data.yahoo_provider import fetch_market_data_yahoo
            from src.market_data.neo4j_updater import create_neo4j_update_draft, apply_neo4j_update
            from src.market_data.models import AssetClass
            
            # Determine asset class from ticker pattern
            if "=" in ticker:
                asset_class = AssetClass.FX if ticker.endswith("=X") else AssetClass.COMMODITY
            elif ticker.startswith("^"):
                asset_class = AssetClass.INDEX if "SPX" in ticker or "GSPC" in ticker else AssetClass.RATE
            else:
                asset_class = AssetClass.STOCK
            
            # Fetch market data
            snapshot = fetch_market_data_yahoo(ticker, asset_class)
            logger.info(f"📊 Fetched {len(snapshot.data)} fields for {ticker}")
            
            # Save to Neo4j
            neo4j_update = create_neo4j_update_draft(topic_id, snapshot)
            success = apply_neo4j_update(neo4j_update)
            
            if success:
                logger.info(f"💾 Saved {len(neo4j_update.properties)} market data properties")
                return True
            else:
                logger.error(f"❌ Failed to save market data for {topic_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to fetch/save data for {topic_name}: {e}")
            return False
    
    def save_ticker(self, topic_id: str, ticker: str) -> None:
        """Save ticker to Neo4j topic."""
        query = """
            MATCH (t:Topic {id: $topic_id})
            SET t.market_data_yahoo_ticker = $ticker
            RETURN t.id as id
        """
        
        result = execute_write(query, {"topic_id": topic_id, "ticker": ticker})
        if not result:
            raise ValueError(f"Topic {topic_id} not found")
        
        logger.info(f"💾 Saved ticker: {ticker}")
    
    def mark_topic_no_ticker(self, topic_id: str) -> None:
        """Mark topic as having no appropriate market data."""
        query = """
            MATCH (t:Topic {id: $topic_id})
            SET t.market_data_yahoo_ticker = "NO_TICKER"
            RETURN t.id as id
        """
        
        result = execute_write(query, {"topic_id": topic_id, "ticker": "NO_TICKER"})
        if not result:
            raise ValueError(f"Topic {topic_id} not found")
        
        logger.info(f"🚫 Marked as no market data appropriate")
    
    def log_final_stats(self) -> None:
        """Log final workflow statistics."""
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 MARKET DATA WORKFLOW COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"📈 Total Topics: {self.stats['total_topics']}")
        logger.info(f"✅ Existing Tickers: {self.stats['existing_tickers']}")
        logger.info(f"🤖 LLM Resolved: {self.stats['llm_resolved']}")
        logger.info(f"🚫 No Market Data: {self.stats['no_ticker_appropriate']}")
        logger.info(f"⏭️  Already Marked: {self.stats['already_marked_no_ticker']}")
        logger.info(f"💾 Data Fetched: {self.stats['data_fetched']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info(f"❌ Errors: {self.stats['errors']}")
        logger.info(f"{'='*80}")


def run_market_data_workflow(limit: Optional[int] = None) -> Dict[str, Any]:
    """Run the market data workflow."""
    workflow = MarketDataWorkflow()
    return workflow.run(limit)


if __name__ == "__main__":
    # Run with limit for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Market Data Workflow")
    parser.add_argument("--limit", type=int, help="Limit number of topics to process")
    args = parser.parse_args()
    
    stats = run_market_data_workflow(args.limit)
    print(f"\n🎯 Workflow completed with stats: {stats}")
