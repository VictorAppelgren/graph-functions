"""
News API Client Module.

This module provides a client for interacting with the news API,
with proper error handling, rate limiting, and request management.
"""

import os
import time
import json
import sys
import requests
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Import local modules
from . import config

from utils import minimal_logging
from utils.master_log import master_log_error
logger = minimal_logging.get_logger(__name__)


class NewsApiError(Exception):
    """Exception raised for News API errors."""
    pass


class RateLimitError(NewsApiError):
    """Exception raised when API rate limit is reached."""
    pass


class AuthenticationError(NewsApiError):
    """Exception raised for authentication errors."""
    pass


class NewsApiClient:
    """
    Client for interacting with the News API.
    
    This class handles authentication, request formatting,
    rate limiting, and response parsing.
    """
    
    @minimal_logging.log_execution(logger)
    def __init__(self):
        """
        Initialize the NewsApiClient.
        
        Raises:
            AuthenticationError: If API key is not set or invalid
        """
        logger.info("Initializing NewsApiClient")
        
        # Get API key with validation
        try:
            self.api_key = config.get_api_key()
        except ValueError as e:
            logger.error(f"API key validation failed: {e}")
            raise AuthenticationError(f"API key error: {e}")
        
        # Set base URL
        self.base_url = "https://api.perigon.io/v1/"

        # Set up session with common headers
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": self.api_key,
            "User-Agent": config.USER_AGENT,
            "Content-Type": "application/json"
        })
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds
        
        logger.info("NewsApiClient initialized successfully")
    
    @minimal_logging.log_execution(logger)
    def search_articles(self, query: str, max_results: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Search for articles using the news API.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional query parameters
            
        Returns:
            Dict with API response
            
        Raises:
            ValueError: On invalid input parameters
            RateLimitError: On API rate limit exceeded
            AuthenticationError: On authentication errors
            NewsApiError: On other API errors
        """
        if not query:
            logger.error("Empty query provided")
            raise ValueError("Query cannot be empty")
        
        if max_results < 1:
            logger.error(f"Invalid max_results: {max_results}")
            raise ValueError("max_results must be at least 1")
        
        # Truncate long queries in logs to reduce noise
        _q = minimal_logging.truncate_str(query, max_len=200)
        logger.info(f"Searching articles with query: '{_q}' (max: {max_results})")
        
        # Build request parameters
        params = {
            "q": query,
            "size": max_results,
            "sortBy": kwargs.get("sort_by", "date"),
            "from": kwargs.get("from_date", ""),
            "to": kwargs.get("to_date", "")
        }
        
        # Implement source group rotation for robust financial news coverage
        source_groups = ["top25finance", "top100", "top50tech", "top10"]
        now = datetime.now()
        rotation_index = (now.weekday() * 24 * 60 + now.hour * 60 + now.minute) % len(source_groups)
        params["sourceGroup"] = source_groups[rotation_index]
        logger.info(f"📰 Using source group: {params['sourceGroup']} (rotation index: {rotation_index})")

        # Add additional filters if provided
        if "sources" in kwargs and kwargs["sources"]:
            params["sources"] = ",".join(kwargs["sources"])
        
        if "languages" in kwargs and kwargs["languages"]:
            params["language"] = ",".join(kwargs["languages"])
        
        # Execute request with retry logic
        return self._execute_request("all", params)
    
    @minimal_logging.log_execution(logger)
    def vector_search(self, vector_query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Perform a vector search using the news API.
        
        Args:
            vector_query: Vector search query
            max_results: Maximum number of results to return
            
        Returns:
            Dict with API response
            
        Raises:
            ValueError: On invalid input parameters
            RateLimitError: On API rate limit exceeded
            AuthenticationError: On authentication errors
            NewsApiError: On other API errors
        """
        if not vector_query:
            logger.error("Empty vector query provided")
            raise ValueError("Vector query cannot be empty")
        
        # Truncate long vector queries in logs to reduce noise
        _vq = minimal_logging.truncate_str(vector_query, max_len=200)
        logger.info(f"Performing vector search with query: '{_vq}' (max: {max_results})")
        
        # Build request parameters
        params = {
            "q": vector_query,
            "size": max_results,
            "sortBy": "relevance"
        }
        
        # Execute request with retry logic
        return self._execute_request("semantic", params)
    
    @minimal_logging.log_execution(logger)
    def _execute_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a request to the news API with rate limiting and retries.
        
        Args:
            endpoint: API endpoint to call
            params: Request parameters
            
        Returns:
            Dict with API response
            
        Raises:
            RateLimitError: On API rate limit exceeded
            AuthenticationError: On authentication errors
            NewsApiError: On other API errors
        """
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Build URL
        url = f"{self.base_url}/{endpoint}"
        
        # Minimal fail-fast policy
        # - Retry ONLY for transient network issues
        # - Exit immediately on provider-side rate limit/quota/billing problems
        TRANSIENT_MARKERS = (
            "connection reset", "timed out", "timeout", "temporarily unavailable",
            "connection aborted", "network is unreachable", "dns", "connect error", "httpx",
        )

        def _is_transient(msg: str) -> bool:
            m = msg.lower()
            return any(tok in m for tok in TRANSIENT_MARKERS)

        # Execute request with retries
        for attempt in range(config.MAX_RETRIES):
            try:
                response = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
                
                # Handle rate limiting
                if response.status_code == 429:
                    # Provider refuses service due to rate limit/quota -> hard stop
                    master_log_error(f"Fatal provider error | news_api | rate limit 429 Retry-After={response.headers.get('Retry-After')}")
                    logger.error(f"FATAL News API rate limit: 429")
                    sys.exit(4)
                
                # Handle authentication errors
                if response.status_code == 401 or response.status_code == 403:
                    logger.error(f"Authentication error: {response.status_code}")
                    raise AuthenticationError(f"API authentication error: {response.text}")
                
                # Handle other errors
                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    
                    if attempt < config.MAX_RETRIES - 1:
                        retry_delay = config.RETRY_DELAY * (attempt + 1)
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    
                    raise NewsApiError(f"API error: {response.status_code} - {response.text}")
                
                # Parse response
                try:
                    result = response.json()
                    logger.info(f"Request successful: found {len(result.get('articles', []))} articles")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing API response: {e}")
                    raise NewsApiError(f"Invalid API response: {e}")
            
            except requests.RequestException as e:
                logger.error(f"Request error: {e}")
                msg = str(e)
                # Only retry for transient network errors; otherwise hard stop
                if _is_transient(msg):
                    if attempt < config.MAX_RETRIES - 1:
                        retry_delay = config.RETRY_DELAY * (attempt + 1)
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    # Transient persisted after retries -> hard stop
                    master_log_error(f"Fatal provider error | news_api | transient persisted: {e}")
                    logger.error(f"FATAL News API transient error persisted: {e}")
                    sys.exit(5)
                else:
                    # Non-transient provider/network error -> hard stop immediately
                    master_log_error(f"Fatal provider error | news_api | {e}")
                    logger.error(f"FATAL News API error: {e}")
                    sys.exit(6)
        
        # This should not be reached due to the exception handling above
        raise NewsApiError("Maximum retries exceeded")
    
    @minimal_logging.log_execution(logger)
    def _apply_rate_limit(self) -> None:
        """
        Apply rate limiting to prevent API abuse.
        
        This method ensures that requests are spaced by at least
        min_request_interval seconds.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


if __name__ == "__main__":
    # Example usage when run directly
    try:
        # Set up simple logging for direct execution
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        
        # Test API client
        print("🔍 Testing NewsApiClient")
        client = NewsApiClient()
        
        test_query = "EURUSD OR Euro OR Dollar"
        print(f"📰 Searching for: '{test_query}'")
        
        result = client.search_articles(test_query, max_results=5)
        articles = result.get("articles", [])
        
        print(f"✅ Found {len(articles)} articles:")
        for i, article in enumerate(articles):
            print(f"\n--- Article {i+1} ---")
            print(f"Title: {article.get('title', 'N/A')}")
            print(f"Source: {article.get('source', {}).get('domain', 'N/A')}")
            print(f"Date: {article.get('pubDate', 'N/A')}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
