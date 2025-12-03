"""
SAGA Graph Bidirectional Sync - Keep Local and Cloud in Sync

Syncs articles and Neo4j graph data between local development and cloud production.
Run this on your LOCAL machine periodically or after being offline.

Hierarchy: Cloud (production) is the master source of truth.
Local is for development and backup.

Strategy:
- Cloud → Local: Always accept (cloud is master)
- Local → Cloud: Upload new entities only (preserve cloud data)
- Conflicts: Cloud wins (master source of truth)

Usage:
    python sync_bidirectional.py --sync         # Full bidirectional sync
    python sync_bidirectional.py --dry-run      # Preview changes
    python sync_bidirectional.py --continuous   # Run continuously (for backup)

Requirements:
    pip install neo4j requests python-dotenv
"""

import os
import sys
import argparse
import json
import requests
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Use basic logging (no utils dependency for Docker container)
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables from graph-functions/.env
ENV_FILE = Path(PROJECT_ROOT) / ".env"
load_dotenv(ENV_FILE)

# ============ CONFIGURATION ============

# LOCAL (Development - Your Laptop)
LOCAL_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
LOCAL_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
LOCAL_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
LOCAL_BACKEND_API = os.getenv("LOCAL_BACKEND_API", "http://localhost:8000/api")

# CLOUD (Production Server - MASTER)
CLOUD_SERVER_IP = os.getenv("CLOUD_SERVER_IP", "YOUR_SERVER_IP_HERE")
CLOUD_NEO4J_URI = os.getenv("CLOUD_NEO4J_URI", f"bolt://{CLOUD_SERVER_IP}:7687")
CLOUD_NEO4J_USER = os.getenv("CLOUD_NEO4J_USER", os.getenv("NEO4J_USER", "neo4j"))
CLOUD_NEO4J_PASSWORD = os.getenv("CLOUD_NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", "password"))
CLOUD_BACKEND_API = os.getenv("CLOUD_BACKEND_API", f"http://{CLOUD_SERVER_IP}/api")

# API Key (same for both)
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "785fc6c1647ff650b6b611509cc0a8f47009e6b743340503519d433f111fcf12")

# Sync state file (tracks last sync time)
SYNC_STATE_FILE = Path.home() / ".saga_sync_state.json"

# ============ SYNC STATE MANAGER ============

class SyncStateManager:
    """Tracks last sync timestamps for incremental sync"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load sync state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_sync": None,
            "local_last_change": None,
            "cloud_last_change": None
        }
    
    def save_state(self):
        """Save sync state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_last_sync(self) -> Optional[str]:
        """Get last successful sync timestamp"""
        return self.state.get("last_sync")
    
    def update_sync_time(self):
        """Update last sync timestamp to now"""
        self.state["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.save_state()
    
    def is_first_sync(self) -> bool:
        """Check if this is the first sync"""
        return self.state.get("last_sync") is None


# ============ ARTICLE BIDIRECTIONAL SYNC ============

class ArticleBidirectionalSyncer:
    """Syncs articles in both directions using Backend API"""
    
    def __init__(
        self, 
        local_api: str, 
        cloud_api: str, 
        api_key: str,
        dry_run: bool = False
    ):
        self.local_api = local_api
        self.cloud_api = cloud_api
        self.api_key = api_key
        self.dry_run = dry_run
        self.stats = {
            "local_to_cloud": 0,
            "cloud_to_local": 0,
            "errors": 0
        }
    
    def sync(self):
        """Bidirectional sync of articles"""
        logger.info("=" * 50)
        logger.info("📄 Syncing Articles (Bidirectional)")
        logger.info("=" * 50)
        
        try:
            # Get article IDs from both sides
            local_ids = self._get_article_ids(self.local_api)
            cloud_ids = self._get_article_ids(self.cloud_api)
            
            logger.info(f"Local articles: {len(local_ids)}")
            logger.info(f"Cloud articles: {len(cloud_ids)}")
            
            # SAFETY CHECK: Prevent uploading everything if cloud appears empty
            if len(local_ids) > 1000 and len(cloud_ids) < len(local_ids) * 0.5:
                logger.error("🚨 SAFETY CHECK FAILED!")
                logger.error(f"   Local: {len(local_ids)} articles")
                logger.error(f"   Cloud: {len(cloud_ids)} articles (< 50% of local)")
                logger.error("   This suggests server error, not actual state.")
                logger.error("   Aborting sync to prevent mass upload!")
                raise Exception("Cloud article count suspiciously low - server may be unavailable")
            
            # Find differences
            only_local = local_ids - cloud_ids
            only_cloud = cloud_ids - local_ids
            
            logger.info(f"Only on local: {len(only_local)}")
            logger.info(f"Only on cloud: {len(only_cloud)}")
            
            # Upload local-only articles to cloud
            if only_local:
                logger.info(f"⬆️  Uploading {len(only_local)} articles to cloud...")
                BATCH_SIZE = 100
                local_list = list(only_local)
                
                for i in range(0, len(local_list), BATCH_SIZE):
                    batch_ids = local_list[i:i + BATCH_SIZE]
                    articles = []
                    
                    # Download batch
                    for article_id in batch_ids:
                        article = self._download_article(self.local_api, article_id)
                        if article:
                            articles.append(article)
                    
                    # Upload batch to cloud
                    if articles:
                        imported = self._upload_batch(self.cloud_api, articles)
                        self.stats["local_to_cloud"] += imported
                        logger.info(f"   Batch {i//BATCH_SIZE + 1}: {imported} imported")
            
            # Download cloud-only articles to local (cloud is master)
            if only_cloud:
                logger.info(f"⬇️  Downloading {len(only_cloud)} articles from cloud...")
                BATCH_SIZE = 100
                cloud_list = list(only_cloud)
                
                for i in range(0, len(cloud_list), BATCH_SIZE):
                    batch_ids = cloud_list[i:i + BATCH_SIZE]
                    articles = []
                    
                    # Download batch
                    for article_id in batch_ids:
                        article = self._download_article(self.cloud_api, article_id)
                        if article:
                            articles.append(article)
                    
                    logger.info(f"   Batch {i//BATCH_SIZE + 1}: Downloaded {len(articles)}/{len(batch_ids)} articles")
                    
                    # Upload batch to local
                    if articles:
                        imported = self._upload_batch(self.local_api, articles)
                        self.stats["cloud_to_local"] += imported
                        logger.info(f"   Batch {i//BATCH_SIZE + 1}: {imported} imported")
                    else:
                        logger.warning(f"   Batch {i//BATCH_SIZE + 1}: No articles to upload!")
            
            logger.info("📊 Article Sync Summary:")
            logger.info(f"   Local → Cloud: {self.stats['local_to_cloud']}")
            logger.info(f"   Cloud → Local: {self.stats['cloud_to_local']}")
            logger.info(f"   Errors:        {self.stats['errors']}")
            
        except Exception as e:
            logger.error(f"Article sync failed: {e}", exc_info=True)
            raise
    
    def _get_article_ids(self, api_url: str) -> Set[str]:
        """Get all article IDs using pagination"""
        all_ids = set()
        offset = 0
        
        while True:
            try:
                url = f"{api_url}/articles/ids"
                logger.info(f"   Fetching from: {url}")
                response = requests.get(
                    url,
                    headers={"X-API-Key": self.api_key},
                    params={"offset": offset},
                    timeout=60
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get IDs from {url}: {response.status_code}")
                    logger.error(f"Response: {response.text[:200]}")
                    
                    # Detect server unavailable (502/503) - don't assume empty!
                    if response.status_code in [502, 503, 504]:
                        logger.error("⚠️  Server unavailable (502/503/504) - aborting sync to prevent data loss!")
                        logger.error("   Server may be restarting. Wait and try again.")
                        raise Exception(f"Server unavailable ({response.status_code})")
                    
                    break
                
                data = response.json()
                all_ids.update(data["article_ids"])
                
                # Check if more pages
                if not data.get("has_more", False):
                    break
                
                offset += data["count"]
                
            except Exception as e:
                logger.error(f"Error fetching IDs: {e}")
                break
        
        return all_ids
    
    def _download_article(self, api_url: str, article_id: str) -> Optional[Dict]:
        """Download single article"""
        try:
            url = f"{api_url}/articles/{article_id}"
            response = requests.get(
                url,
                headers={"X-API-Key": self.api_key},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to download {article_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error downloading {article_id}: {e}")
            return None
    
    def _upload_batch(self, api_url: str, articles: List[Dict]) -> int:
        """Upload articles using bulk endpoint"""
        try:
            url = f"{api_url}/articles/bulk"
            response = requests.post(
                url,
                headers={"X-API-Key": self.api_key},
                params={"overwrite": False},
                json=articles,
                timeout=120
            )
            if response.status_code == 200:
                result = response.json()
                imported = result.get("imported", 0)
                skipped = result.get("skipped", 0)
                errors = result.get("errors", 0)
                logger.info(f"      Bulk result: {imported} imported, {skipped} skipped, {errors} errors")
                return imported
            else:
                logger.error(f"Bulk upload failed: {response.status_code} - {response.text[:200]}")
                return 0
        except Exception as e:
            logger.error(f"Bulk upload exception: {e}")
            return 0
    
    def _sync_article_to_cloud(self, article_id: str) -> bool:
        """Upload article from local to cloud"""
        try:
            # Get from local
            response = requests.get(
                f"{self.local_api}/articles/{article_id}",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            article = response.json()
            
            if self.dry_run:
                logger.debug(f"Would upload: {article_id}")
                return True
            
            # Upload to cloud
            response = requests.post(
                f"{self.cloud_api}/articles",
                headers={"X-API-Key": self.api_key},
                json=article,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.debug(f"✅ Uploaded: {article_id}")
                return True
            else:
                logger.warning(f"Failed to upload {article_id}: {response.status_code}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error uploading {article_id}: {e}")
            self.stats["errors"] += 1
            return False
    
    def _sync_article_to_local(self, article_id: str) -> bool:
        """Download article from cloud to local"""
        try:
            # Get from cloud
            response = requests.get(
                f"{self.cloud_api}/articles/{article_id}",
                headers={"X-API-Key": self.api_key},
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            article = response.json()
            
            if self.dry_run:
                logger.debug(f"Would download: {article_id}")
                return True
            
            # Upload to local
            response = requests.post(
                f"{self.local_api}/articles",
                headers={"X-API-Key": self.api_key},
                json=article,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.debug(f"✅ Downloaded: {article_id}")
                return True
            else:
                logger.warning(f"Failed to download {article_id}: {response.status_code}")
                self.stats["errors"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error downloading {article_id}: {e}")
            self.stats["errors"] += 1
            return False


# ============ STATS/LOGS SYNC (Cloud → Local Only) ============

class StatsLogsSyncer:
    """Syncs stats and logs from cloud to local (one-way download)"""
    
    def __init__(self, cloud_api: str, local_dir: Path, api_key: str = None, dry_run: bool = False):
        self.cloud_api = cloud_api
        self.local_dir = local_dir
        self.api_key = api_key
        self.dry_run = dry_run
        self.headers = {"X-API-Key": api_key} if api_key else {}
    
    def sync_stats(self):
        """Download stats files from server"""
        logger.info("📊 Syncing stats files...")
        stats_dir = self.local_dir / "master_stats"
        stats_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get list of files
            response = requests.get(
                f"{self.cloud_api}/admin/stats/list",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            files = response.json().get("files", [])
            
            logger.info(f"   Found {len(files)} stats files on server")
            
            for filename in files:
                if self.dry_run:
                    logger.info(f"   [DRY RUN] Would download: {filename}")
                    continue
                
                # Download file
                response = requests.get(
                    f"{self.cloud_api}/admin/stats/download/{filename}",
                    headers=self.headers,
                    timeout=10
                )
                if response.status_code == 200:
                    file_path = stats_dir / filename
                    file_path.write_bytes(response.content)
                    logger.debug(f"   ✅ {filename}")
            
            logger.info(f"✅ Stats sync complete")
        except Exception as e:
            logger.error(f"Stats sync failed: {e}")
    
    def sync_logs(self):
        """Download log files from server (last 7 days only)"""
        logger.info("📝 Syncing log files...")
        logs_dir = self.local_dir / "master_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get list of files
            response = requests.get(
                f"{self.cloud_api}/admin/logs/list",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            files = response.json().get("files", [])
            
            # Only sync recent logs (last 7 days)
            recent_files = files[-7:] if len(files) > 7 else files
            logger.info(f"   Found {len(files)} log files, syncing last {len(recent_files)}")
            
            for filename in recent_files:
                if self.dry_run:
                    logger.info(f"   [DRY RUN] Would download: {filename}")
                    continue
                
                # Download file
                response = requests.get(
                    f"{self.cloud_api}/admin/logs/download/{filename}",
                    headers=self.headers,
                    timeout=10
                )
                if response.status_code == 200:
                    file_path = logs_dir / filename
                    file_path.write_bytes(response.content)
                    logger.debug(f"   ✅ {filename}")
            
            logger.info(f"✅ Logs sync complete")
        except Exception as e:
            logger.error(f"Logs sync failed: {e}")


# ============ NEO4J BIDIRECTIONAL SYNC ============

class Neo4jBidirectionalSyncer:
    """Syncs Neo4j graph - ALL properties including analysis (cloud is master)"""
    
    def __init__(
        self,
        local_uri: str,
        cloud_uri: str,
        user: str,
        password: str,
        dry_run: bool = False
    ):
        self.local_uri = local_uri
        self.cloud_uri = cloud_uri
        self.user = user
        self.password = password
        self.dry_run = dry_run
        self.stats = {
            "local_to_cloud_topics": 0,
            "cloud_to_local_topics": 0,
            "local_to_cloud_articles": 0,
            "cloud_to_local_articles": 0,
            "local_to_cloud_rels": 0,
            "cloud_to_local_rels": 0,
            "cloud_overwrites": 0,
            "errors": 0
        }
    
    def sync(self):
        """Bidirectional sync of Neo4j graph"""
        logger.info("=" * 50)
        logger.info("🔷 Syncing Neo4j Graph (Bidirectional)")
        logger.info("=" * 50)
        logger.info(f"   Local:  {self.local_uri}")
        logger.info(f"   Cloud:  {self.cloud_uri}")
        
        try:
            # Connect to both databases
            local_driver = GraphDatabase.driver(
                self.local_uri,
                auth=(self.user, self.password)
            )
            
            cloud_driver = GraphDatabase.driver(
                self.cloud_uri,
                auth=(self.user, self.password)
            )
            
            # Test connections
            with local_driver.session() as session:
                session.run("RETURN 1").single()
            logger.info("✅ Connected to local Neo4j")
            
            with cloud_driver.session() as session:
                session.run("RETURN 1").single()
            logger.info("✅ Connected to cloud Neo4j")
            
            # Sync in order
            self._sync_topics_bidirectional(local_driver, cloud_driver)
            self._sync_articles_bidirectional(local_driver, cloud_driver)
            self._sync_relationships_bidirectional(local_driver, cloud_driver)
            
            # Close connections
            local_driver.close()
            cloud_driver.close()
            
            logger.info("📊 Neo4j Sync Summary:")
            logger.info(f"   Topics:  {self.stats['local_to_cloud_topics']}⬆️  {self.stats['cloud_to_local_topics']}⬇️")
            logger.info(f"   Articles: {self.stats['local_to_cloud_articles']}⬆️  {self.stats['cloud_to_local_articles']}⬇️")
            logger.info(f"   Relationships: {self.stats['local_to_cloud_rels']}⬆️  {self.stats['cloud_to_local_rels']}⬇️")
            logger.info(f"   Cloud overwrites (master): {self.stats['cloud_overwrites']}")
            logger.info(f"   Errors: {self.stats['errors']}")
            
        except Exception as e:
            logger.error(f"Neo4j sync failed: {e}", exc_info=True)
            raise
    
    def _sync_topics_bidirectional(self, local_driver, cloud_driver):
        """Sync topics in both directions (cloud is master for conflicts)"""
        logger.info("📌 Syncing Topics (Bidirectional)...")
        
        # Get all topics from both sides
        with local_driver.session() as session:
            local_topics = {
                t["id"]: t 
                for t in session.run("""
                    MATCH (t:Topic)
                    RETURN t.id as id, properties(t) as props, 
                           coalesce(t.last_updated, '1970-01-01T00:00:00') as last_updated
                """).data()
            }
        
        with cloud_driver.session() as session:
            cloud_topics = {
                t["id"]: t
                for t in session.run("""
                    MATCH (t:Topic)
                    RETURN t.id as id, properties(t) as props,
                           coalesce(t.last_updated, '1970-01-01T00:00:00') as last_updated
                """).data()
            }
        
        logger.info(f"   Local topics: {len(local_topics)}")
        logger.info(f"   Cloud topics: {len(cloud_topics)}")
        
        # Find differences
        local_ids = set(local_topics.keys())
        cloud_ids = set(cloud_topics.keys())
        
        only_local = local_ids - cloud_ids
        only_cloud = cloud_ids - local_ids
        both = local_ids & cloud_ids
        
        logger.info(f"   Only local: {len(only_local)}, Only cloud: {len(only_cloud)}, Both: {len(both)}")
        
        if self.dry_run:
            logger.info(f"   🔍 Would sync {len(only_local)} topics to cloud")
            logger.info(f"   🔍 Would sync {len(only_cloud)} topics to local")
            logger.info(f"   🔍 Would check {len(both)} topics for conflicts")
            self.stats["local_to_cloud_topics"] = len(only_local)
            self.stats["cloud_to_local_topics"] = len(only_cloud)
            return
        
        # Upload local-only topics to cloud
        if only_local:
            with cloud_driver.session() as session:
                for topic_id in only_local:
                    try:
                        session.run("""
                            MERGE (t:Topic {id: $id})
                            SET t = $props
                        """, {
                            "id": topic_id,
                            "props": local_topics[topic_id]["props"]
                        })
                        self.stats["local_to_cloud_topics"] += 1
                    except Exception as e:
                        logger.error(f"Error uploading topic {topic_id}: {e}")
                        self.stats["errors"] += 1
        
        # Download cloud-only topics to local (ALL properties including analysis)
        if only_cloud:
            with local_driver.session() as session:
                for topic_id in only_cloud:
                    try:
                        # SET t = $props replaces ALL properties (analysis included)
                        session.run("""
                            MERGE (t:Topic {id: $id})
                            SET t = $props
                        """, id=topic_id, props=cloud_topics[topic_id]["props"])
                        self.stats["cloud_to_local_topics"] += 1
                    except Exception as e:
                        logger.error(f"Failed to sync topic {topic_id} to local: {e}")
                        self.stats["errors"] += 1
        
        # For topics on both sides: Cloud is master, always overwrite local
        if both:
            with local_driver.session() as session:
                for topic_id in both:
                    local_time = local_topics[topic_id]["last_updated"]
                    cloud_time = cloud_topics[topic_id]["last_updated"]
                    
                    # If cloud is different, overwrite local (cloud is master)
                    if cloud_time != local_time:
                        try:
                            session.run("""
                                MERGE (t:Topic {id: $id})
                                SET t = $props
                            """, {
                                "id": topic_id,
                                "props": cloud_topics[topic_id]["props"]
                            })
                            self.stats["cloud_overwrites"] += 1
                            logger.debug(f"Cloud overwrote local for topic: {topic_id}")
                        except Exception as e:
                            logger.error(f"Error syncing topic {topic_id}: {e}")
                            self.stats["errors"] += 1
        
        logger.info(f"   ✅ Topics synced: {self.stats['local_to_cloud_topics']}⬆️  {self.stats['cloud_to_local_topics']}⬇️")
    
    def _sync_articles_bidirectional(self, local_driver, cloud_driver):
        """Sync article nodes (articles are immutable)"""
        logger.info("📰 Syncing Article Nodes (Bidirectional)...")
        
        # Get article IDs from both sides
        with local_driver.session() as session:
            local_article_ids = {
                r["id"] for r in session.run("MATCH (a:Article) RETURN a.id as id").data()
            }
        
        with cloud_driver.session() as session:
            cloud_article_ids = {
                r["id"] for r in session.run("MATCH (a:Article) RETURN a.id as id").data()
            }
        
        only_local = local_article_ids - cloud_article_ids
        only_cloud = cloud_article_ids - local_article_ids
        
        logger.info(f"   Local: {len(local_article_ids)} | Cloud: {len(cloud_article_ids)}")
        logger.info(f"   Only local: {len(only_local)}, Only cloud: {len(only_cloud)}")
        
        if self.dry_run:
            logger.info(f"   🔍 Would sync {len(only_local)} article nodes to cloud")
            logger.info(f"   🔍 Would sync {len(only_cloud)} article nodes to local")
            return
        
        # Upload local-only articles to cloud
        if only_local:
            with local_driver.session() as local_session:
                articles = local_session.run("""
                    MATCH (a:Article)
                    WHERE a.id IN $ids
                    RETURN a.id as id, properties(a) as props
                """, {"ids": list(only_local)}).data()
                
                with cloud_driver.session() as cloud_session:
                    for article in articles:
                        try:
                            cloud_session.run("""
                                MERGE (a:Article {id: $id})
                                SET a = $props
                            """, article)
                            self.stats["local_to_cloud_articles"] += 1
                        except Exception as e:
                            logger.error(f"Error uploading article node: {e}")
                            self.stats["errors"] += 1
        
        # Download cloud-only articles to local
        if only_cloud:
            with cloud_driver.session() as cloud_session:
                articles = cloud_session.run("""
                    MATCH (a:Article)
                    WHERE a.id IN $ids
                    RETURN a.id as id, properties(a) as props
                """, {"ids": list(only_cloud)}).data()
                
                with local_driver.session() as local_session:
                    for article in articles:
                        try:
                            local_session.run("""
                                MERGE (a:Article {id: $id})
                                SET a = $props
                            """, article)
                            self.stats["cloud_to_local_articles"] += 1
                        except Exception as e:
                            logger.error(f"Error downloading article node: {e}")
                            self.stats["errors"] += 1
        
        logger.info(f"   ✅ Articles synced: {self.stats['local_to_cloud_articles']}⬆️  {self.stats['cloud_to_local_articles']}⬇️")
    
    def _sync_relationships_bidirectional(self, local_driver, cloud_driver):
        """Sync relationships (additive, cloud is master for conflicts)"""
        logger.info("🔗 Syncing Relationships (Bidirectional)...")
        
        # Get relationship signatures from both sides
        def get_rel_signatures(driver):
            with driver.session() as session:
                return {
                    (r["start_id"], r["rel_type"], r["end_id"])
                    for r in session.run("""
                        MATCH (a)-[r]->(b)
                        RETURN a.id as start_id, type(r) as rel_type, b.id as end_id
                    """).data()
                }
        
        local_rels = get_rel_signatures(local_driver)
        cloud_rels = get_rel_signatures(cloud_driver)
        
        only_local = local_rels - cloud_rels
        only_cloud = cloud_rels - local_rels
        
        logger.info(f"   Local: {len(local_rels)} | Cloud: {len(cloud_rels)}")
        logger.info(f"   Only local: {len(only_local)}, Only cloud: {len(only_cloud)}")
        
        if self.dry_run:
            logger.info(f"   🔍 Would sync {len(only_local)} relationships to cloud")
            logger.info(f"   🔍 Would sync {len(only_cloud)} relationships to local")
            return
        
        # Upload local-only relationships to cloud
        if only_local:
            with local_driver.session() as local_session:
                rels = local_session.run("""
                    MATCH (a)-[r]->(b)
                    RETURN 
                        a.id as start_id,
                        labels(a)[0] as start_label,
                        type(r) as rel_type,
                        properties(r) as rel_props,
                        b.id as end_id,
                        labels(b)[0] as end_label
                """).data()
                
                with cloud_driver.session() as cloud_session:
                    for rel in rels:
                        sig = (rel["start_id"], rel["rel_type"], rel["end_id"])
                        if sig in only_local:
                            try:
                                query = f"""
                                    MATCH (a:{rel['start_label']} {{id: $start_id}})
                                    MATCH (b:{rel['end_label']} {{id: $end_id}})
                                    MERGE (a)-[r:{rel['rel_type']}]->(b)
                                    SET r = $props
                                """
                                cloud_session.run(query, {
                                    "start_id": rel["start_id"],
                                    "end_id": rel["end_id"],
                                    "props": rel["rel_props"] or {}
                                })
                                self.stats["local_to_cloud_rels"] += 1
                            except Exception as e:
                                logger.error(f"Error uploading relationship: {e}")
                                self.stats["errors"] += 1
        
        # Download cloud-only relationships to local
        if only_cloud:
            with cloud_driver.session() as cloud_session:
                rels = cloud_session.run("""
                    MATCH (a)-[r]->(b)
                    RETURN 
                        a.id as start_id,
                        labels(a)[0] as start_label,
                        type(r) as rel_type,
                        properties(r) as rel_props,
                        b.id as end_id,
                        labels(b)[0] as end_label
                """).data()
                
                with local_driver.session() as local_session:
                    for rel in rels:
                        sig = (rel["start_id"], rel["rel_type"], rel["end_id"])
                        if sig in only_cloud:
                            try:
                                query = f"""
                                    MATCH (a:{rel['start_label']} {{id: $start_id}})
                                    MATCH (b:{rel['end_label']} {{id: $end_id}})
                                    MERGE (a)-[r:{rel['rel_type']}]->(b)
                                    SET r = $props
                                """
                                local_session.run(query, {
                                    "start_id": rel["start_id"],
                                    "end_id": rel["end_id"],
                                    "props": rel["rel_props"] or {}
                                })
                                self.stats["cloud_to_local_rels"] += 1
                            except Exception as e:
                                logger.error(f"Error downloading relationship: {e}")
                                self.stats["errors"] += 1
        
        logger.info(f"   ✅ Relationships synced: {self.stats['local_to_cloud_rels']}⬆️  {self.stats['cloud_to_local_rels']}⬇️")


# ============ CONTINUOUS SYNC ============

def run_continuous_sync(interval: int = 300):
    """Run sync continuously for backup - simple and minimal"""
    import time
    import signal
    
    shutdown = False
    
    def signal_handler(sig, frame):
        nonlocal shutdown
        shutdown = True
        logger.info("Shutdown requested...")
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("="*60)
    logger.info("🔄 SAGA Continuous Sync Started")
    logger.info(f"Interval: {interval}s | Local → Cloud (bidirectional)")
    logger.info("="*60)
    
    sync_count = 0
    
    while not shutdown:
        sync_count += 1
        logger.info(f"\n{'='*60}")
        logger.info(f"Sync #{sync_count} - {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"{'='*60}")
        
        try:
            # Neo4j sync (ALL properties including analysis)
            neo4j_syncer = Neo4jBidirectionalSyncer(
                LOCAL_NEO4J_URI, CLOUD_NEO4J_URI,
                LOCAL_NEO4J_USER, LOCAL_NEO4J_PASSWORD,
                dry_run=False
            )
            neo4j_syncer.sync()
            
            # Article sync
            article_syncer = ArticleBidirectionalSyncer(
                LOCAL_BACKEND_API, CLOUD_BACKEND_API, BACKEND_API_KEY,
                dry_run=False
            )
            article_syncer.sync()
            
            # Stats/Logs sync (cloud → local only)
            stats_logs_syncer = StatsLogsSyncer(
                CLOUD_BACKEND_API,
                Path(PROJECT_ROOT),
                api_key=BACKEND_API_KEY,
                dry_run=False
            )
            stats_logs_syncer.sync_stats()
            stats_logs_syncer.sync_logs()
            
            logger.info(f"✅ Sync #{sync_count} complete")
        except Exception as e:
            logger.error(f"❌ Sync #{sync_count} failed: {e}", exc_info=True)
        
        if not shutdown:
            logger.info(f"⏳ Next sync in {interval}s...")
            time.sleep(interval)
    
    logger.info("Sync stopped gracefully")


# ============ MAIN CLI ============

def main():
    parser = argparse.ArgumentParser(
        description="Bidirectional sync between local and cloud SAGA Graph"
    )
    parser.add_argument("--sync", action="store_true", help="Run full sync")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--catch-up", action="store_true", help="After offline")
    parser.add_argument("--continuous", action="store_true", help="Run continuously (for backup)")
    parser.add_argument("--interval", type=int, default=300, help="Sync interval in seconds")
    parser.add_argument(
        "--articles-only",
        action="store_true",
        help="Sync only articles"
    )
    parser.add_argument(
        "--neo4j-only",
        action="store_true",
        help="Sync only Neo4j graph"
    )
    
    args = parser.parse_args()
    
    # Handle continuous mode
    if args.continuous:
        run_continuous_sync(args.interval)
        return
    
    # Determine what to sync
    sync_all = args.sync or args.catch_up or (not args.articles_only and not args.neo4j_only)
    sync_articles = args.articles_only or sync_all
    sync_neo4j = args.neo4j_only or sync_all
    
    # Validate configuration
    if CLOUD_SERVER_IP == "YOUR_SERVER_IP_HERE":
        logger.error("Please configure CLOUD_SERVER_IP environment variable!")
        sys.exit(1)
    
    # Load sync state
    state_manager = SyncStateManager(SYNC_STATE_FILE)
    last_sync = state_manager.get_last_sync()
    
    logger.info("=" * 50)
    logger.info("🔄 SAGA Graph Bidirectional Sync")
    logger.info("=" * 50)
    logger.info(f"Local:  {LOCAL_BACKEND_API}")
    logger.info(f"Cloud:  {CLOUD_BACKEND_API} (MASTER)")
    logger.info(f"Mode:   {'DRY RUN' if args.dry_run else 'LIVE SYNC'}")
    if last_sync:
        logger.info(f"Last sync: {last_sync}")
    else:
        logger.info("Last sync: Never (first sync)")
    logger.info("=" * 50)
    
    try:
        # Sync articles
        if sync_articles:
            article_syncer = ArticleBidirectionalSyncer(
                LOCAL_BACKEND_API,
                CLOUD_BACKEND_API,
                BACKEND_API_KEY,
                dry_run=args.dry_run
            )
            article_syncer.sync()
        
        # Sync Neo4j
        if sync_neo4j:
            neo4j_syncer = Neo4jBidirectionalSyncer(
                LOCAL_NEO4J_URI,
                CLOUD_NEO4J_URI,
                LOCAL_NEO4J_USER,
                LOCAL_NEO4J_PASSWORD,
                dry_run=args.dry_run
            )
            neo4j_syncer.sync()
        
        # Sync Stats/Logs (cloud → local only)
        if sync_all or sync_articles:  # Include with article sync
            logger.info("=" * 50)
            logger.info("📊 Syncing Stats & Logs (Cloud → Local)")
            logger.info("=" * 50)
            stats_logs_syncer = StatsLogsSyncer(
                CLOUD_BACKEND_API,
                Path(PROJECT_ROOT),
                api_key=BACKEND_API_KEY,
                dry_run=args.dry_run
            )
            stats_logs_syncer.sync_stats()
            stats_logs_syncer.sync_logs()
        
        # Update sync state
        if not args.dry_run:
            state_manager.update_sync_time()
            logger.info(f"💾 Sync state saved to: {SYNC_STATE_FILE}")
        
        logger.info("=" * 50)
        logger.info("✅ Bidirectional sync completed!")
        logger.info("=" * 50)
        
    except KeyboardInterrupt:
        logger.warning("Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
