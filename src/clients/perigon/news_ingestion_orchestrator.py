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
import logging

# Import local modules
from src.clients.perigon.query_eurusd import get_query as query1
from src.clients.perigon.query_ai_data import get_query as query2
from src.clients.perigon.news_api_client import NewsApiClient
from src.clients.perigon.source_scraper import (
    scrape_article_and_sources_sync,
    is_article_good,
)
from src.clients.perigon.text_summarizer import summarize_article
from src.api.backend_client import ingest_article

# Set up logger for this module
from utils import app_logging

logger = app_logging.get_logger("news_ingestion_orchestrator")


def set_third_party_log_levels(debug: bool) -> None:
    """
    Control noisy third-party loggers. Show INFO only in debug mode; otherwise quiet them.
    """
    httpx_level = logging.INFO if debug else logging.WARNING
    httpcore_level = logging.INFO if debug else logging.WARNING
    trafilatura_level = logging.WARNING if debug else logging.ERROR

    app_logging.get_logger("httpx").setLevel(httpx_level)
    app_logging.get_logger("httpcore").setLevel(httpcore_level)
    app_logging.get_logger("trafilatura").setLevel(trafilatura_level)
    app_logging.get_logger("trafilatura.core").setLevel(trafilatura_level)
    app_logging.get_logger("trafilatura.utils").setLevel(trafilatura_level)


class NewsIngestionOrchestrator:
    """
    Orchestrates the news ingestion process.

    This class coordinates the execution of queries against the news API,
    the scraping of article content and linked sources, and the storage
    of raw article data.
    """

    @app_logging.log_execution(logger)
    def __init__(self, debug: bool = False, scrape_enabled: bool = False):
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

        # Scrape toggle (constructor-only, default False for simplicity)
        self.scrape_enabled = bool(scrape_enabled)
        logger.debug("Scrape enabled: %s", self.scrape_enabled)

        # Initialize statistics
        self.stats = {
            "queries_executed": 0,
            "articles_retrieved": 0,
            "articles_scraped": 0,
            "articles_summarized": 0,
            "articles_stored": 0,
            "errors": 0,
        }

        logger.info("✅ Initialized NewsIngestionOrchestrator successfully")

    def run_query(
        self, topic: str, query_text: str, max_articles: int = 10, test: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a query against the news API and process the results.

        Args:
            topic: The topic name
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

        start_time = time.time()

        # Execute query
        try:
            raw_results = self.api_client.search_articles(
                query=query_text, max_results=max_articles
            )
            
            # Track query execution (done in news_api_client)
            self.stats["queries_executed"] += 1

            if not raw_results or "articles" not in raw_results:
                logger.warning("⚠️ No articles found or invalid API response")
                return []

            articles = raw_results["articles"]
            logger.info(
                f"Retrieved {len(articles)} articles from API for topic {topic}"
            )
            # Query already tracked in news_api_client
            self.stats["articles_retrieved"] += len(articles)
            # If the query returned zero results, nothing more to process
            if len(articles) == 0:
                logger.warning(f"Zero results for topic {topic}")
                return []

            # Process articles
            processed_articles = self._process_articles(articles)

            # If not testing, trigger add_article for each processed article
            if not test:
                from src.articles.ingest_article import add_article

                for article in processed_articles:
                    article_id = article["argos_id"]
                    try:
                        add_article(article_id=article_id, test=False)
                    except Exception as e:
                        # Log full error details including traceback
                        import traceback
                        logger.error(
                            f"Failed to add article {article_id} | "
                            f"error={type(e).__name__}: {e} | "
                            f"title={article.get('title', 'N/A')[:100]}"
                        )
                        logger.error(f"Traceback:\n{traceback.format_exc()}")
            else:
                logger.info("❌❌❌ Test mode enabled, skipping add_article")

            duration = time.time() - start_time
            logger.info(
                f"✅ Processed {len(processed_articles)} articles in {duration:.2f}s"
            )
            return processed_articles

        except Exception as e:
            # Handle NewsApiError with 414 status as warning (do not crash)
            if hasattr(e, "args") and e.args and "414" in str(e.args[0]):
                logger.warning(
                    f"⚠️ Skipping query for topic {topic}: 414 Request-URI Too Large"
                )
                return []
            self.stats["errors"] += 1
            logger.error(f"❌ Error executing query: {e}")
            raise RuntimeError(f"Failed to execute query: {e}")

    # --- helpers -------------------------------------------------------------
    def _fast_store(self, article: Dict[str, Any], title: str, title_sample: str) -> Dict[str, Any] | None:
        """
        Store API article, generating summary if API summary missing.
        Uses backend /ingest endpoint for automatic deduplication.
        Returns stored payload dict on success, None if failed.
        """
        summary = article.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            logger.info(
                "📝 Missing API summary; generating summary for '%s'", title_sample
            )
            # Generate summary using our LLM summarizer
            try:
                generated_summary = summarize_article(article)
                if generated_summary and generated_summary.strip():
                    summary = generated_summary.strip()
                    self.stats["articles_summarized"] += 1
                    logger.info(
                        "✅ Generated summary for '%s' | len=%d chars", title_sample, len(summary)
                    )
                else:
                    logger.warning(
                        "❌ Failed to generate summary for '%s'; skipping", title_sample
                    )
                    self.stats["errors"] += 1
                    return None
            except Exception as e:
                logger.warning(
                    "❌ Summary generation failed for '%s': %s", title_sample, str(e)
                )
                self.stats["errors"] += 1
                return None
        
        # Prepare payload with summary
        payload: Dict[str, Any] = dict(article)
        payload["argos_summary"] = summary.strip()
        payload.setdefault("argos_topic", title)
        
        # Send to backend for deduplication and storage
        # Backend will generate ID if new, or return existing ID if duplicate
        try:
            result = ingest_article(payload)
            argos_id = result["argos_id"]
            status = result["status"]
            
            # Add ID to payload for return
            payload["argos_id"] = argos_id
            
            if status == "existing":
                logger.info(f"Duplicate detected: '{title_sample}' → {argos_id}")
            else:
                logger.info(f"New article stored: '{title_sample}' → {argos_id}")
                self.stats["articles_stored"] += 1
            
            return payload
            
        except Exception as e:
            logger.error(f"Failed to ingest article '{title_sample}': {e}")
            self.stats["errors"] += 1
            return None

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
            processed = self.run_query(
                name, get_query(), max_articles=max_results, test=True
            )
            saved_article_ids.extend(
                [a.get("argos_id") for a in processed if a.get("argos_id")]
            )

        logger.info("✅ Test finished with %d articles saved", len(saved_article_ids))
        return {
            "statistics": self.stats,
            "saved_article_ids": saved_article_ids,
            "sample_articles": [],
        }

    @app_logging.log_execution(logger)
    def _process_articles(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                logger.debug(
                    "============================================================================"
                )
                logger.debug(f"ARTICLE: {article.get('title', 'Untitled')}")
                logger.debug(
                    f"⚙️ Processing article {i+1}/{len(articles)}: {article.get('title', 'Untitled')}"
                )

                # Note: Duplicate checking now handled by backend /ingest endpoint
                # No need for local duplicate check anymore

                # Prepare metadata
                datetime.utcnow().isoformat()

                # --- Extract and QA Perigon main text BEFORE scraping ---
                perigon_description = article["description"]
                logger.debug(
                    f"PERIGON MAIN TEXT (description):\n{perigon_description}\n"
                )
                perigon_text = article["content"]
                MAX_LOG_TEXT_LEN = 1200
                if len(perigon_text) > MAX_LOG_TEXT_LEN:
                    log_text = perigon_text[:MAX_LOG_TEXT_LEN] + "\n... [truncated]"
                else:
                    log_text = perigon_text

                logger.debug(f"PERIGON MAIN TEXT (full):\n{log_text}\n")

                # Skip initial QA check - scrape first, then QA on better content
                title = article.get("title", "Untitled")
                title_sample = (title[:77] + "...") if len(title) > 80 else title

                # No longer attach main article text under scraped_content; only use top-level 'content'.

                if not self.scrape_enabled:
                    # Fast path: skip scraping & summarization; use API data only
                    stored = self._fast_store(article, title, title_sample)
                    if stored is not None:
                        processed_articles.append(stored)
                    continue

                # Scrape article content and sources (slow path)
                logger.debug("🔍 Scraping article content and sources")
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
                    logger.warning(
                        f"❌ Article: '{title_sample}' | QA: {main_text_quality} | Failed QA after scraping and will be skipped. Reason: low-quality or corrupted text."
                    )
                    self.stats["errors"] += 1
                    continue
                logger.debug(
                    f"✅ Article: '{title_sample}' | QA: {main_text_quality} | Passed QA check after scraping."
                )

                # Generate summary from scraped content
                logger.debug("summarizing...")
                logger.debug("📝 Generating article summary")
                summary = summarize_article(enriched_article)
                logger.debug(
                    "summary generation complete | type=%s | len=%s",
                    type(summary),
                    (len(summary) if isinstance(summary, str) else "NA"),
                )
                if not isinstance(summary, str) or not summary.strip():
                    logger.warning(
                        "❌ Summary missing or invalid type; skipping article '%s'",
                        title_sample,
                    )
                    self.stats["errors"] += 1
                    continue
                self.stats["articles_summarized"] += 1
                # Single per-article INFO line summarizing scraping result
                logger.info(
                    f"Article: '{title_sample}' scraped {num_sources} sources, summary generated!"
                )

                # Build strict dict payload for storage: merge enriched article + argos_summary
                payload: Dict[str, Any] = dict(enriched_article)
                payload["argos_summary"] = summary
                # Minimal provenance
                payload.setdefault("argos_topic", title)
                # Debug the payload shape before storage
                logger.debug(
                    "storage payload | type=%s | keys_sample=%s",
                    type(payload),
                    list(payload.keys())[:12],
                )

                # Store the enriched and summarized article via backend
                logger.debug("saving...")
                try:
                    result = ingest_article(payload)
                    argos_id = result["argos_id"]
                    status = result["status"]
                    
                    # Add ID to payload
                    payload["argos_id"] = argos_id
                    
                    if status == "existing":
                        logger.info(f"Duplicate detected: '{title_sample}' → {argos_id}")
                    else:
                        logger.debug(f"💾 Stored article: {argos_id}")
                        self.stats["articles_stored"] += 1
                    
                    processed_articles.append(payload)
                    
                except Exception as e:
                    logger.error(f"Failed to ingest article '{title_sample}': {e}")
                    self.stats["errors"] += 1

                logger.debug(
                    "============================================================================"
                )

            except Exception:
                logger.exception(
                    "❌ Error processing article %s ('%s')",
                    i + 1,
                    article.get("title", "Untitled"),
                )
                self.stats["errors"] += 1
                # Continue processing other articles to avoid losing good data from batch failures
                # Note: This trades fail-fast for data preservation - one bad article won't kill 9 good ones
                logger.error(
                    f"BATCH_PROCESSING_ERROR: Skipping failed article and continuing with remaining {len(articles) - i - 1} articles"
                )
                continue

        return processed_articles


if __name__ == "__main__":
    import logging

    app_logging.basicConfig(
        level=app_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("📰 Starting News Ingestion Test Run")
    orchestrator = NewsIngestionOrchestrator(debug=True)
    orchestrator.run_complete_test()
