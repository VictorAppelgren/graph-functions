#!/usr/bin/env python3
"""
News Ingestion Pipeline Runner

This script runs the complete news ingestion pipeline:
1. Load and execute queries
2. Retrieve articles from news API
3. Scrape article content and linked sources
4. Generate summaries
5. Store to raw storage

Usage:
    python run.py [--max-articles N] [--debug]
"""

import argparse
import sys
import logging
from datetime import datetime

# --- Canonical import block for absolute imports (Argos_Graph_v1.md) ---
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import local modules (now using perigon, not news_ingestion)
from perigon.ingestion_orchestrator import NewsIngestionOrchestrator
from utils import logging
logger = logging.get_logger(__name__)


def main():
    """Run the news ingestion pipeline."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run news ingestion pipeline')
    parser.add_argument('--max-articles', type=int, default=5,
                        help='Maximum number of articles per query (default: 5)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode with more verbose output')
    args = parser.parse_args()
    
    # Set up logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    else:
        logging.getLogger().setLevel(logging.INFO)
    
    try:
        logger.info("Starting news ingestion pipeline")
        
        # Initialize the orchestrator
        orchestrator = NewsIngestionOrchestrator(debug=args.debug)
        
        # Start time for performance tracking
        start_time = datetime.now()
        
        # Run the complete end-to-end test
        logger.info(f"Running news ingestion with max {args.max_articles} articles per query")
        results = orchestrator.run_complete_test()
        
        # Calculate elapsed time
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # Print summary
        print("\n" + "="*50)
        print(f"📊 NEWS INGESTION COMPLETE - {elapsed_time:.2f}s elapsed")
        print("="*50)
        
        # Statistics
        stats = results["statistics"]
        print(f"\n📈 STATISTICS:")
        print(f"  • Queries executed:     {stats['queries_executed']}")
        print(f"  • Articles retrieved:   {stats['articles_retrieved']}")
        print(f"  • Articles scraped:     {stats['articles_scraped']}")
        print(f"  • Summaries generated:  {stats['articles_summarized']}")
        print(f"  • Articles stored:      {stats['articles_stored']}")
        print(f"  • Errors:               {stats['errors']}")
        
        # Sample articles
        if results["sample_articles"]:
            print("\n📝 SAMPLE ARTICLES:")
            for i, article in enumerate(results["sample_articles"]):
                print(f"\n  ARTICLE {i+1}: {article['title']}")
                print(f"  {'Source:':<12} {article['source']}")
                print(f"  {'Date:':<12} {article['date']}")
                print(f"  {'Content:':<12} {len(article.get('content',''))} chars")
                print(f"  {'Sources:':<12} {article['num_sources_scraped']} linked sources scraped")
                
                # Show summary with increased character limit (200 chars)
                summary = article.get('summary', '')
                if summary:
                    if len(summary) > 200:
                        print(f"  {'Summary:':<12} {summary[:200]}...")
                    else:
                        print(f"  {'Summary:':<12} {summary}")
                
                # Show Argos summary if available
                argos_summary = article.get('argos_summary', '')
                if argos_summary:
                    if len(argos_summary) > 200:
                        print(f"  {'AI Summary:':<12} {argos_summary[:200]}...")
                    else:
                        print(f"  {'AI Summary:':<12} {argos_summary}")
        
        print("\n✅ Pipeline execution successful")
        return 0
    
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=args.debug)
        return 1


if __name__ == "__main__":
    sys.exit(main())
