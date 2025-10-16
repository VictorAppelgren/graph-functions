"""
Configuration for News Ingestion Module.

This module centralizes all configuration settings and provides
validation for required environment variables.
"""

import os
from pathlib import Path

# Base Directory Configuration
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw_news"
SCRAPED_DATA_DIR = DATA_DIR / "scraped_content"

# Ensure directories exist
os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(SCRAPED_DATA_DIR, exist_ok=True)

# Environment validation
PERIGON_API_KEY = "42d445d4-0839-450f-a747-901e63b89bb2"


# API Configuration
def get_api_key():
    """Get API key for Perigon News API.
    Returns the NEWS_API_KEY environment variable if set, otherwise uses the PERIGON_API_KEY constant.
    """
    return os.environ.get("NEWS_API_KEY") or PERIGON_API_KEY


# HTTP Request Settings
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Scraping Settings
MAX_CONCURRENT_REQUESTS = 5
MAX_SOURCE_LINKS_TO_SCRAPE = 10  # Maximum number of links to scrape per article

# Storage Settings
JSON_INDENT = 2  # For readable JSON files
