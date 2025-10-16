"""
ULTRA-SIMPLE Top Sources Pipeline - Maximum Data Ingestion

Just loop through top sources, query everything, save articles.
No complexity, no topic processing, just pure data ingestion.
"""

import os
import sys
import datetime
from typing import List
import time
import random

# Import from V1 using absolute imports
from src.clients.perigon.news_ingestion_orchestrator import NewsIngestionOrchestrator
from src.articles.ingest_article import add_article
from utils import app_logging

logger = app_logging.get_logger(__name__)

# TOP PREMIUM SOURCES - The absolute best sources worldwide
TOP_PREMIUM_SOURCES = [
    # Core US/Global (existing)
    "bloomberg.com",
    "ft.com",                  # Financial Times (EU/Global)
    "wsj.com",                 # Wall Street Journal
    "reuters.com",
    "cnn.com",
    "bbc.com",                 # UK/Global
    "economist.com",           # UK/Global
    "nytimes.com",
    "washingtonpost.com",
    "cnbc.com",
    "marketwatch.com",
    "forbes.com",
    "businessinsider.com",
    "theguardian.com",         # UK
    "apnews.com",
    "axios.com",
    "politico.com",
    "npr.org",
    "abc.com",                 # US ABC
    "cbsnews.com",
    "nbcnews.com",
    "usatoday.com",
    "time.com",
    "newsweek.com",
    "theatlantic.com",

    # Europe (a few more, high signal)
    "spiegel.de",              # Germany
    "lemonde.fr",              # France
    "lesechos.fr",             # France (business)
    "handelsblatt.com",        # Germany (business)
    "faz.net",                 # Germany
    "elpais.com",              # Spain
    "thetimes.co.uk",          # UK
    "telegraph.co.uk",         # UK

    # Asia (some, focused on business/politics)
    "asia.nikkei.com",         # Japan/Asia business
    "scmp.com",                # Hong Kong
    "straitstimes.com",        # Singapore
    "channelnewsasia.com",     # Singapore (CNA)
    "japantimes.co.jp",        # Japan
    "caixin.com",              # China (business)
    "thehindu.com",            # India
    "timesofindia.com",        # India
    "koreatimes.co.kr",        # South Korea

    # Australia (very few)
    "afr.com",                 # Australian Financial Review
    "smh.com.au",              # Sydney Morning Herald
    "abc.net.au",              # ABC Australia
]


def run_simple_sources_pipeline():
    """
    ULTRA-SIMPLE: Just loop through sources, get articles, save them.
    No topics, no complexity, just maximum data ingestion.
    """
    
    orchestrator = NewsIngestionOrchestrator(debug=False, scrape_enabled=False)
    
    # Shuffle sources for variety
    sources = TOP_PREMIUM_SOURCES.copy()
    random.shuffle(sources)
    
    logger.info(f"🚀 Starting SIMPLE sources pipeline with {len(sources)} sources")
    logger.info(f"First 5 sources: {sources[:5]}")
    
    cycle_count = 0
    total_articles = 0
    
    while True:
        cycle_count += 1
        cycle_start = datetime.datetime.now()
        cycle_articles = 0
        
        logger.info(f"📰 Starting cycle #{cycle_count} at {cycle_start:%H:%M:%S}")
        
        for i, source in enumerate(sources, 1):
            logger.info(f"[{i}/{len(sources)}] Processing {source}")
            
            try:
                # Query EVERYTHING from this specific source using wildcard via API client
                result = orchestrator.api_client.search_articles(
                    query="*",
                    max_results=50,
                    sources=[source],
                )
                raw_articles = result.get("articles", [])
                # Store/process to raw storage (returns processed payloads with argos_id)
                articles = orchestrator._process_articles(raw_articles)
                
                # Process each article through the pipeline
                articles_added = 0
                for article in articles:
                    try:
                        argos_id = article.get("argos_id")
                        if not argos_id:
                            logger.warning("Skipping article without argos_id")
                            continue
                        # Trigger add_article by ID (loads from storage and links to topics)
                        add_article(argos_id)
                        articles_added += 1
                    except Exception as e:
                        logger.warning(f"Failed to ingest article: {e}")
                        continue
                
                cycle_articles += articles_added
                logger.info(f"✅ {source}: {articles_added}/{len(articles)} articles added")
                
            except Exception as e:
                logger.error(f"❌ Error with {source}: {e}")
                continue
        
        total_articles += cycle_articles
        cycle_duration = (datetime.datetime.now() - cycle_start).total_seconds()
        
        logger.info(f"✅ Cycle #{cycle_count} completed: {cycle_articles} articles in {cycle_duration:.1f}s")
        logger.info(f"📊 Total articles processed: {total_articles}")
        
        # Re-shuffle for next cycle
        random.shuffle(sources)
        
        # Brief pause between cycles
        logger.info("😴 Sleeping 30s before next cycle...")
        time.sleep(30)


if __name__ == "__main__":
    try:
        run_simple_sources_pipeline()
    except KeyboardInterrupt:
        logger.info("Pipeline stopped by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise