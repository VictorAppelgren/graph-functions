"""
News Ingestion Orchestrator.

This module orchestrates the news ingestion process, coordinating
query execution, article scraping, summarization, and raw storage operations.
Following the simplified approach, it focuses only on:
1. Loading and executing queries
2. Retrieving articles
3. Scraping article content and linked sources
4. Generating summaries
5. Storing enriched raw data
"""
import os
import sys

# Canonical import pattern to ensure absolute imports work everywhere
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
from datetime import datetime
from typing import Dict, List, Any

# Import local modules
from src.clients.perigon.query_eurusd import get_query as query1
from src.clients.perigon.query_ai_data import get_query as query2
from src.clients.perigon.news_api_client import NewsApiClient
from src.clients.perigon.raw_storage_manager import RawStorageManager
from src.clients.perigon.source_scraper import scrape_article_and_sources_sync, is_article_good
from src.clients.perigon.text_summarizer import summarize_article

# Set up logger for this module
from utils import app_logging
logger = app_logging.get_logger("news_ingestion_orchestrator")
from src.observability.pipeline_logging import master_log, master_log_error, problem_log


def set_third_party_log_levels(debug: bool) -> None:
    """
    Control noisy third-party loggers. Show INFO only in debug mode; otherwise quiet them.
    """
    httpx_level = app_logging.INFO if debug else app_logging.WARNING
    httpcore_level = app_logging.INFO if debug else app_logging.WARNING
    trafilatura_level = app_logging.WARNING if debug else app_logging.ERROR

    app_logging.getLogger("httpx").setLevel(httpx_level)
    app_logging.getLogger("httpcore").setLevel(httpcore_level)
    app_logging.getLogger("trafilatura").setLevel(trafilatura_level)
    app_logging.getLogger("trafilatura.core").setLevel(trafilatura_level)
    app_logging.getLogger("trafilatura.utils").setLevel(trafilatura_level)


class NewsIngestionOrchestrator:
    """
    Orchestrates the news ingestion process.
    
    This class coordinates the execution of queries against the news API,
    the scraping of article content and linked sources, and the storage
    of raw article data.
    """
    
    @app_logging.log_execution(logger)
    def __init__(self, debug: bool = False):
        """
        Initialize the NewsIngestionOrchestrator.
        
        Args:
            debug: Enable debug mode for more verbose output
        """
        logger.info("🔍 Initializing NewsIngestionOrchestrator")
        
        # Set debug mode
        if debug:
            logger.setLevel(10)  # DEBUG level
            logger.debug("Debug mode enabled")
        # Adjust third-party logger verbosity
        set_third_party_log_levels(debug)


        # Initialize API client
        self.api_client = NewsApiClient()
        
        # Initialize storage manager
        self.storage_manager = RawStorageManager()
        
        # Initialize statistics
        self.stats = {
            "queries_executed": 0,
            "articles_retrieved": 0,
            "articles_scraped": 0,
            "articles_summarized": 0,
            "articles_stored": 0,
            "errors": 0
        }
        
        logger.info("✅ Initialized NewsIngestionOrchestrator successfully")
    
    def run_query(self, node: str, query_text: str, max_articles: int = 10, test: bool = False) -> List[Dict[str, Any]]:
        """
        Execute a query against the news API and process the results.
        
        Args:
            node: The node name
            query_text: The query string to execute
            max_articles: Maximum number of articles to retrieve
            
        Returns:
            List of processed articles
            
        Raises:
            ValueError: If query is empty
            RuntimeError: If API client fails
        """
        if not query_text:
            raise ValueError("Query text cannot be empty")
                
        query_id = f"query-{int(time.time())}"
        start_time = time.time()
        
        # Execute query
        try:
            raw_results = self.api_client.search_articles(
                query=query_text,
                max_results=max_articles
            )
            
            if not raw_results or "articles" not in raw_results:
                logger.warning("⚠️ No articles found or invalid API response")
                return []
            
            articles = raw_results["articles"]
            logger.info(f"Retrieved {len(articles)} articles from API for node {node}")
            master_log(f"Retrieved articles | {node} | Retrieved {len(articles)} from API", queries=1, articles=len(articles))
            self.stats["queries_executed"] += 1
            self.stats["articles_retrieved"] += len(articles)
            # If the query returned zero results, record as a problem (simple, observable)
            if len(articles) == 0:
                problem_log(problem="Zero results", topic=node, details={"query": query_text, "max_results": max_articles})
                # Nothing more to process for this query
                return []
            
            # Process articles
            processed_articles = self._process_articles(articles, query_id)

            # If not testing, trigger add_article for each processed article
            if not test:
                from articles.ingest_article import add_article
                for article in processed_articles:
                    try:
                        article_id = article['argos_id']
                        add_article(article_id=article_id, test=False)
                    except Exception as e:
                        logger.error("Error triggering add_article for article %s: %r", article_id, e)
            else:
                logger.info("❌❌❌ Test mode enabled, skipping add_article")

            duration = time.time() - start_time
            logger.info(f"✅ Processed {len(processed_articles)} articles in {duration:.2f}s")
            return processed_articles
        except Exception as e:
            # Handle NewsApiError with 414 status as warning (do not crash)
            if hasattr(e, 'args') and e.args and '414' in str(e.args[0]):
                logger.warning(f"⚠️ Skipping query for node {node}: 414 Request-URI Too Large")
                return []
            self.stats["errors"] += 1
            master_log_error(f"Query error | {node} | {e}")
            logger.error(f"❌ Error executing query: {e}")
            raise RuntimeError(f"Failed to execute query: {e}")

    @app_logging.log_execution(logger)
    def run_complete_test(self) -> Dict[str, Any]:
        """
        Run a minimal end-to-end test: execute two queries in test mode, collect saved IDs, and return stats.
        """
        logger.info("🧪 Running complete end-to-end test")
        max_results = 10
        saved_article_ids = []

        for name, get_query in [("test_query_1", query1), ("test_query_2", query2)]:
            # Fail fast: let exceptions propagate so we see the root cause
            processed = self.run_query(name, get_query(), max_articles=max_results, test=True)
            saved_article_ids.extend([a.get("argos_id") for a in processed if a.get("argos_id")])

        logger.info("✅ Test finished with %d articles saved", len(saved_article_ids))
        return {"statistics": self.stats, "saved_article_ids": saved_article_ids, "sample_articles": []}
 
  
    @app_logging.log_execution(logger)
    def _process_articles(self, articles: List[Dict[str, Any]], query_id: str) -> List[Dict[str, Any]]:
        """
        Process a list of articles: scrape content, summarize, and store raw data.
        
        Args:
            articles: List of articles from the API
            query_id: Unique ID for this query
            
        Returns:
            List of processed articles
        """
        processed_articles = []
        
        for i, article in enumerate(articles):
            try:
                logger.debug("============================================================================")
                logger.debug(f"ARTICLE: {article.get('title', 'Untitled')}")
                logger.debug(f"⚙️ Processing article {i+1}/{len(articles)}: {article.get('title', 'Untitled')}")

                # Skip duplicate articles
                if self.storage_manager.is_duplicate_article(article):
                    logger.debug(f"👯 Skipping duplicate article: {article.get('title', 'Untitled')}")
                    continue

                # Prepare metadata
                timestamp = datetime.utcnow().isoformat()

                # --- Extract and QA Perigon main text BEFORE scraping ---
                perigon_description = article["description"]
                logger.debug(f"PERIGON MAIN TEXT (description):\n{perigon_description}\n")
                perigon_text = article["content"] 
                MAX_LOG_TEXT_LEN = 1200
                if len(perigon_text) > MAX_LOG_TEXT_LEN:
                    log_text = perigon_text[:MAX_LOG_TEXT_LEN] + '\n... [truncated]'
                else:
                    log_text = perigon_text

                logger.debug(f"PERIGON MAIN TEXT (full):\n{log_text}\n")
                
                # Skip initial QA check - scrape first, then QA on better content
                title = article.get('title', 'Untitled')
                title_sample = (title[:77] + '...') if len(title) > 80 else title

                # No longer attach main article text under scraped_content; only use top-level 'content'.

                # Scrape article content and sources
                logger.debug(f"🔍 Scraping article content and sources")
                enriched_article = scrape_article_and_sources_sync(article)
                self.stats["articles_scraped"] += 1
                sources_list = enriched_article.get("scraped_sources", [])
                logger.debug(f"Sources scraped: {len(sources_list)}")

                # --- Quality Assurance: Check main article text (scraped) ---
                # Use only the top-level 'content' for main article text after scraping
                main_text = enriched_article.get("content", "")
                num_sources = len(sources_list)
                main_text_quality = is_article_good(main_text)
                logger.debug(f"SCRAPED MAIN TEXT QA: {main_text_quality}")
                logger.debug(f"Number of sources added: {num_sources}")
                # Log the article quality
                logger.debug(f"Article quality: {main_text_quality}")
                if not main_text_quality:
                    logger.warning(f"❌ Article: '{title_sample}' | QA: {main_text_quality} | Failed QA after scraping and will be skipped. Reason: low-quality or corrupted text.")
                    self.stats["errors"] += 1
                    continue
                logger.debug(f"✅ Article: '{title_sample}' | QA: {main_text_quality} | Passed QA check after scraping.")

                # Generate summary from scraped content
                logger.debug("summarizing...")
                logger.debug(f"📝 Generating article summary")
                summarized_article = summarize_article(enriched_article)
                self.stats["articles_summarized"] += 1
                # Single per-article INFO line summarizing scraping result
                logger.info(f"Article: '{title_sample}' scraped {num_sources} sources, summary generated!")

                # Store the enriched and summarized article
                logger.debug("saving...")
                stored_path = self.storage_manager.store_article(summarized_article)
                if stored_path:
                    logger.debug(f"💾 Stored article to {stored_path}")
                    self.stats["articles_stored"] += 1
                    processed_articles.append(summarized_article)

                logger.debug("============================================================================")

            except Exception as e:
                logger.exception("❌ Error processing article %s ('%s')", i + 1, article.get('title', 'Untitled'))
                self.stats["errors"] += 1
                # Continue processing other articles to avoid losing good data from batch failures
                # Note: This trades fail-fast for data preservation - one bad article won't kill 9 good ones
                logger.error(f"BATCH_PROCESSING_ERROR: Skipping failed article and continuing with remaining {len(articles) - i - 1} articles")
                continue
        
        return processed_articles


if __name__ == "__main__":
    import logging
    app_logging.basicConfig(
        level=app_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("📰 Starting News Ingestion Test Run")
    orchestrator = NewsIngestionOrchestrator(debug=True)
    orchestrator.run_complete_test()
