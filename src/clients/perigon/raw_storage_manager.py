"""
Raw Storage Manager for News Ingestion.

This module handles the storage of raw article data from news sources,
focusing on efficient file-based storage and basic deduplication.
"""

import os
import json
import gzip
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# Import local modules
from . import config

from utils import app_logging
logger = app_logging.get_logger(__name__)

from .argos_id_generator import add_argos_id_to_article


class StorageError(Exception):
    """Exception raised for storage operations errors."""
    pass


class RawStorageManager:
    """
    Manages storage of raw article data.
    
    This class handles:
    1. Saving raw article data to JSON files
    2. Compressing data when configured
    3. Basic deduplication of articles
    4. Tracking article metadata for status reporting
    """
    
    def __init__(self):
        """
        Initialize the RawStorageManager.
        
        Raises:
            StorageError: If storage directories cannot be initialized
        """
        logger.info("Initializing RawStorageManager")
        
        # Set up storage paths
        self.raw_data_dir = config.RAW_DATA_DIR
        self.today_str = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = Path(self.raw_data_dir) / self.today_str
        
        # Ensure storage directories exist
        try:
            os.makedirs(self.today_dir, exist_ok=True)
            logger.debug(f"Storage directory ready: {self.today_dir}")
        except OSError as e:
            logger.error(f"Failed to create storage directories: {e}")
            raise StorageError(f"Failed to initialize storage: {e}")
        
        # Initialize article tracking
        self.article_ids = self._load_existing_article_ids()
        
        logger.info(f"RawStorageManager initialized with {len(self.article_ids)} tracked articles")
    
    def store_article(self, article_data: Dict[str, Any]) -> Optional[str]:
        """
        Store article data to a JSON file with a bulletproof unique 9-character argos_id.
        Args:
            article_data: Article data to store
        Returns:
            Path to stored file or None if storage failed
        Raises:
            ValueError: If article data is invalid
            StorageError: If storage operation fails
        """
        if not article_data:
            raise ValueError("Article data cannot be None or empty")
        if not isinstance(article_data, dict):
            raise ValueError("Article data must be a dictionary")

        # Extract the article from the wrapper if present
        article = article_data.get("data", article_data)

        # Add bulletproof unique argos_id if not present
        argos_id = add_argos_id_to_article(article)
        article_data["argos_id"] = argos_id
        # Also ensure 'argos_id' is present in the 'data' subdict for consistency
        if "data" in article_data:
            article_data["data"]["argos_id"] = argos_id

        # Create file path using the unique argos_id
        file_name = f"{argos_id}.json"
        file_path = self.today_dir / file_name

        try:
            # Serialize the data
            json_data = json.dumps(article_data, indent=config.JSON_INDENT)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)

            # Track the article ID
            self.article_ids.add(argos_id)

            logger.info(f"Article {argos_id} saved successfully to {file_path}")
            return str(file_path)

        except (IOError, OSError) as e:
            logger.error(f"Error storing article {argos_id}: {e}")
            raise StorageError(f"Failed to store article: {e}")
        
    def get_recent_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recently stored articles.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of article data ordered by most recent first
        """
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        
        # Find all json files in today's directory
        article_files = []
        for ext in [".json", ".json.gz"]:
            article_files.extend(list(self.today_dir.glob(f"*{ext}")))
        
        # Sort by modification time (newest first)
        article_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Load articles up to the limit
        articles = []
        for file_path in article_files[:limit]:
            try:
                if str(file_path).endswith('.gz'):
                    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                        articles.append(json.load(f))
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        articles.append(json.load(f))
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(f"Error loading article from {file_path}: {e}")
                continue
            
            if len(articles) >= limit:
                break
                
        return articles
    
    def is_duplicate_article(self, article: Dict[str, Any]) -> bool:
        """
        Check if an article is a duplicate of an already stored one.
        
        Args:
            article: Article data to check
            
        Returns:
            True if duplicate, False otherwise
        """
        article_id = self._get_article_id(article)
        return article_id in self.article_ids if article_id else False
    
    def _get_article_id(self, article: Dict[str, Any]) -> Optional[str]:
        """
        Generate a consistent ID for an article based on its content.
        
        Args:
            article: Article data
            
        Returns:
            Unique ID or None if required fields are missing
        """
        # Check if article has an explicit ID
        if article.get("articleId"):
            return article["articleId"]
        
        # For articles without an ID, generate one from title, source, and date
        title = article.get("title", "")
        source = article.get("source", {}).get("domain", "")
        pub_date = article.get("pubDate", "")
        
        if not (title and source):
            logger.warning("Cannot generate article ID: missing title or source")
            return None
        
        # Create a hash of the key fields
        id_string = f"{title}|{source}|{pub_date}"
        return hashlib.md5(id_string.encode('utf-8')).hexdigest()
    
    def _load_existing_article_ids(self) -> Set[str]:
        """
        Load IDs of all existing articles in storage.
        
        Returns:
            Set of article IDs
        """
        article_ids = set()
        
        # Find all json files in the data directory (including subdirectories)
        for root, _, files in os.walk(self.raw_data_dir):
            for file in files:
                if file.endswith('.json') or file.endswith('.json.gz'):
                    article_id = file.split('.')[0]  # Remove extensions
                    article_ids.add(article_id)
        
        return article_ids


if __name__ == "__main__":
    # Example usage when run directly
    try:
        # Set up simple logging for direct execution
        import logging
        app_logging.basicConfig(
            level=app_logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        
        # Test storage operations
        print("💾 Testing RawStorageManager")
        storage = RawStorageManager()
        
        # Create test article
        test_article = {
            "query_id": "test-query",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "title": "Test Article",
                "articleId": "test-article-" + str(int(datetime.now().timestamp())),
                "source": {"domain": "example.com"},
                "pubDate": datetime.now().isoformat(),
                "content": "This is a test article content.",
                "url": "https://example.com/test"
            },
            "summary": "This is a test summary of the article content."
        }
        
        # Store article
        print(f"📝 Storing test article: {test_article['data']['title']}")
        file_path = storage.store_article(test_article)
        
        print(f"✅ Article stored to: {file_path}")
        
        # Check if duplicate
        is_duplicate = storage.is_duplicate_article(test_article["data"])
        print(f"🔍 Is duplicate? {is_duplicate}")
        
        # Load article
        article_id = test_article["data"]["articleId"]
        loaded_article = storage.load_article(article_id)
        
        if loaded_article:
            print(f"📂 Successfully loaded article: {loaded_article['data']['title']}")
        else:
            print("❌ Failed to load article")
        
        # Test get_recent_articles
        print("\n📊 Testing get_recent_articles")
        recent_articles = storage.get_recent_articles(2)
        print(f"Found {len(recent_articles)} recent articles")
        
        for i, article in enumerate(recent_articles):
            print(f"\nArticle {i+1}:")
            print(f"  Title: {article.get('data', {}).get('title', 'Untitled')}")
            print(f"  Summary: {article.get('summary', 'No summary')}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
