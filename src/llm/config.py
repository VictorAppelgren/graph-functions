"""Model Configuration for Argos Research Platform

Smart LLM Router with SQLite-based status tracking for optimal server selection.
- Simple requests (<25k tokens): Try local first, fallback to external servers
- Complex requests: Skip local, use external servers with round-robin
- Automatic busy status tracking and round-robin load balancing
"""

import os
import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Optional

from enum import Enum
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.messages import BaseMessage
from langchain_core.language_models import LanguageModelInput
from typing import Any, Iterator, AsyncIterator

from utils.app_logging import get_logger

logger = get_logger(__name__)

# --- Configuration ---
TOKEN_THRESHOLD = 1700  # Requests ≤2k tokens use local, >2k use external
NANO_THRESHOLD = 999999  # Effectively disabled - don't use Nano
NANO_COOLDOWN_SECONDS = 60  # 60 seconds cooldown between Nano calls
LLM_CALL_TIMEOUT_S = 300.0
LLM_RETRY_ATTEMPTS = 2  # Reduced from 3 - we have fallback logic now
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY = 0.1

# Nano API Key - Set this for testing, will be moved to server env vars later
OPENAI_API_KEY = "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" #os.getenv("OPENAI_API_KEY_NANO", None)  # Use OPENAI_API_KEY_NANO env var

# Minimal model tier enum (local definition to avoid circular imports)
class ModelTier(Enum):
    SIMPLE = "SIMPLE"
    MEDIUM = "MEDIUM"  # routes like SIMPLE per current router
    COMPLEX = "COMPLEX"
    SIMPLE_LONG_CONTEXT = "SIMPLE_LONG_CONTEXT"

# Hardcoded server configuration
# ONLY 2 EXTERNAL SERVERS NOW: 8686 (external_a) and 8787 (external_b)
# External servers run vLLM with 10,240 token context limit
 
# Check if local LLM should be disabled (for server deployment)
DISABLE_LOCAL_LLM = os.getenv("DISABLE_LOCAL_LLM", "false").lower() == "true"

# Debug logging at module load time
import logging
_init_logger = logging.getLogger(__name__)
_init_logger.info(f"🔧 LLM CONFIG INIT: DISABLE_LOCAL_LLM={DISABLE_LOCAL_LLM} (from env: {os.getenv('DISABLE_LOCAL_LLM', 'NOT_SET')})")

SERVERS = {}

# Only add local server if not disabled
if not DISABLE_LOCAL_LLM:
    SERVERS['local'] = {
        'provider': 'ollama', 
        'base_url': 'http://localhost:11434', 
        'model': 'gpt-oss:20b',
        'temperature': 0.2,
    }
    _init_logger.info("🔧 LLM CONFIG: Added 'local' server to SERVERS")
else:
    _init_logger.info("🔧 LLM CONFIG: Skipped 'local' server (DISABLE_LOCAL_LLM=true)")

# Always add external servers
SERVERS.update({
    'external_a': {
        'provider': 'openai', 
        'base_url': 'http://gate04.cfa.handels.gu.se:8686/v1', 
        'model': 'openai/gpt-oss-20b',
        'temperature': 0.2,
    },
    'external_b': {
        'provider': 'openai', 
        'base_url': 'http://gate04.cfa.handels.gu.se:8787/v1', 
        'model': 'openai/gpt-oss-20b',
        'temperature': 0.2,
    },
    # 'external_c': {  # DISABLED - using 8686/8787 instead
    #     'provider': 'openai', 
    #     'base_url': 'http://gate04.cfa.handels.gu.se:8383/v1', 
    #     'model': 'openai/gpt-oss-20b',
    #     'temperature': 0.2,
    # },
    # 'external_d': {  # DISABLED - can't run 4 servers
    #     'provider': 'openai', 
    #     'base_url': 'http://gate04.cfa.handels.gu.se:8484/v1', 
    #     'model': 'openai/gpt-oss-20b',
    #     'temperature': 0.2,
    # },
    # 'nano': {  # DISABLED - not using external ChatGPT
    #     'provider': 'openai',
    #     'base_url': None,  # Use default OpenAI API
    #     'model': 'gpt-5-nano',
    #     'temperature': 0.2,
    # }
})

# Log final server configuration
_init_logger.info(f"🔧 LLM CONFIG: Final SERVERS = {list(SERVERS.keys())}")

# Database setup
DB_PATH = Path(__file__).parent / "router_status.db"
db_lock = Lock()


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-based heuristic."""
    return int(len(text.split()) * 1.3)


class RouterDB:
    """Simple SQLite-based router status manager with retry logic."""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize database with retry logic."""
        for attempt in range(DB_RETRY_ATTEMPTS):
            try:
                with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS router_status (
                            key TEXT PRIMARY KEY,
                            value TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    # Initialize default values if they don't exist
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('local_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('last_external', 'external_a')
                    """)
                    # Initialize external server status
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_a_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_b_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_a_last_call', datetime('now'))
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_b_last_call', datetime('now'))
                    """)
                    # Initialize external_c status
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_c_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_c_last_call', datetime('now'))
                    """)
                    # Initialize external_d status
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_d_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('external_d_last_call', datetime('now'))
                    """)
                    # Initialize nano cooldown tracking
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value) 
                        VALUES ('nano_last_call', datetime('1970-01-01'))
                    """)
                    conn.commit()
                logger.debug("Router database initialized")
                return
            except sqlite3.OperationalError as e:
                if attempt < DB_RETRY_ATTEMPTS - 1:
                    logger.debug(f"DB init attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(DB_RETRY_DELAY * (2 ** attempt))
                else:
                    logger.error(f"Failed to initialize router database after {DB_RETRY_ATTEMPTS} attempts: {e}")
                    raise
    
    def _execute_with_retry(self, query: str, params: tuple = (), fetch: bool = False):
        """Execute database operation with retry logic."""
        for attempt in range(DB_RETRY_ATTEMPTS):
            try:
                with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
                    cursor = conn.execute(query, params)
                    if fetch:
                        result = cursor.fetchone()
                        return result[0] if result else None
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if attempt < DB_RETRY_ATTEMPTS - 1:
                    logger.debug(f"DB operation attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(DB_RETRY_DELAY * (2 ** attempt))
                else:
                    logger.warning(f"Database operation failed after {DB_RETRY_ATTEMPTS} attempts: {e}")
                    raise
    
    def is_local_busy(self) -> bool:
        """Check if local server is busy."""
        try:
            result = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'local_busy'", 
                fetch=True
            )
            return result == '1' if result else False
        except Exception:
            return False  # Assume not busy if can't check
    
    def set_local_busy(self, busy: bool):
        """Set local server busy status."""
        try:
            self._execute_with_retry(
                "UPDATE router_status SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'local_busy'",
                ('1' if busy else '0',)
            )
        except Exception as e:
            logger.warning(f"Failed to update local busy status: {e}")
    
    def is_external_busy(self, server_id: str) -> bool:
        """Check if external server is busy."""
        try:
            result = self._execute_with_retry(
                f"SELECT value FROM router_status WHERE key = '{server_id}_busy'", 
                fetch=True
            )
            return result == '1' if result else False
        except Exception:
            return False

    def set_external_busy(self, server_id: str, busy: bool):
        """Set external server busy status."""
        try:
            # Update busy status
            self._execute_with_retry(
                f"INSERT OR REPLACE INTO router_status (key, value, updated_at) VALUES ('{server_id}_busy', ?, CURRENT_TIMESTAMP)",
                ('1' if busy else '0',)
            )
            # Update last call timestamp if setting to busy
            if busy:
                self._execute_with_retry(
                    f"INSERT OR REPLACE INTO router_status (key, value, updated_at) VALUES ('{server_id}_last_call', datetime('now'), CURRENT_TIMESTAMP)",
                    ()
                )
        except Exception as e:
            logger.warning(f"Failed to update {server_id} busy status: {e}")

    def get_least_recently_used_external(self) -> str:
        """Get external server that was called longest ago (ONLY 2 servers now)."""
        try:
            # Get last call times for ONLY 2 active servers: 8686 and 8787
            times = {}
            for server in ['external_a', 'external_b']:
                time_val = self._execute_with_retry(
                    f"SELECT value FROM router_status WHERE key = '{server}_last_call'", 
                    fetch=True
                )
                if time_val:
                    times[server] = time_val
            
            # If we don't have all timestamps, fall back to round-robin
            if len(times) < 2:
                return self.get_next_external()
            
            # Return the one called longest ago (earliest timestamp)
            return min(times.items(), key=lambda x: x[1])[0]
            
        except Exception as e:
            logger.warning(f"Failed to get least recently used external: {e}")
            return self.get_next_external()  # Fallback to round-robin

    def get_next_external_smart(self, exclude: set[str] = None) -> str:
        """Smart external server selection with busy tracking (ONLY 2 servers now).
        
        Uses round-robin to spread load evenly, skipping busy servers.
        
        Args:
            exclude: Set of server IDs to exclude from selection (e.g., failed servers)
        """
        exclude = exclude or set()
        try:
            # Start from the next server in round-robin order
            last = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'last_external'", 
                fetch=True
            )
            
            # Define rotation order - ONLY 2 servers now: 8686 and 8787
            rotation = ['external_a', 'external_b']
            start_idx = rotation.index(last) if last in rotation else 0
            
            # Check servers starting from next in rotation
            for i in range(2):
                idx = (start_idx + i + 1) % 2
                server = rotation[idx]
                if server not in exclude and not self.is_external_busy(server):
                    if exclude:
                        logger.debug(f"{server} is free (round-robin position {idx}), selecting it (excluded: {exclude})")
                    else:
                        logger.debug(f"{server} is free (round-robin position {idx}), selecting it")
                    # Update last_external to maintain round-robin state
                    self._execute_with_retry(
                        "UPDATE router_status SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_external'",
                        (server,)
                    )
                    return server
            
            # All busy - pick least recently used
            server = self.get_least_recently_used_external()
            logger.debug(f"All external servers busy, selecting least recently used: {server}")
            return server
            
        except Exception as e:
            logger.warning(f"Smart external selection failed: {e}, falling back to round-robin")
            return self.get_next_external()  # Fallback to simple round-robin

    def get_next_external(self) -> str:
        """Get next external server using round-robin (ONLY 2 servers now)."""
        try:
            last = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'last_external'", 
                fetch=True
            )
            # Round-robin through ONLY 2 servers: a → b → a (8686 → 8787 → 8686)
            rotation = {
                'external_a': 'external_b',
                'external_b': 'external_a'
            }
            next_server = rotation.get(last, 'external_a')
            
            self._execute_with_retry(
                "UPDATE router_status SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_external'",
                (next_server,)
            )
            return next_server
        except Exception as e:
            logger.warning(f"Failed to get next external server: {e}")
            return 'external_a'
    
    def get_next_any_server(self) -> str:
        """Get next free server, checking in order: local → external_a → external_b."""
        # Check each server in order, return first free one
        # Only check local if it exists in SERVERS
        if 'local' in SERVERS and not self.is_local_busy():
            return 'local'
        
        if not self.is_external_busy('external_a'):
            return 'external_a'
        
        if not self.is_external_busy('external_b'):
            return 'external_b'
        
        # All busy - fallback to external_a (or local if available)
        return 'local' if 'local' in SERVERS else 'external_a'
    
    def can_use_nano(self) -> bool:
        """Check if enough time has passed since last Nano call (60 sec cooldown)."""
        try:
            last_call = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'nano_last_call'", 
                fetch=True
            )
            if not last_call:
                return True
            
            # Parse timestamp and check if 60 seconds have passed
            from datetime import datetime
            last_time = datetime.fromisoformat(last_call.replace(' ', 'T'))
            now = datetime.now()
            elapsed = (now - last_time).total_seconds()
            
            can_use = elapsed >= NANO_COOLDOWN_SECONDS
            if not can_use:
                logger.debug(f"Nano cooldown active: {elapsed:.1f}s / {NANO_COOLDOWN_SECONDS}s")
            return can_use
        except Exception as e:
            logger.warning(f"Failed to check nano cooldown: {e}")
            return False  # Conservative: don't use if can't verify
    
    def mark_nano_used(self):
        """Mark that Nano was just used."""
        try:
            self._execute_with_retry(
                "INSERT OR REPLACE INTO router_status (key, value, updated_at) VALUES ('nano_last_call', datetime('now'), CURRENT_TIMESTAMP)",
                ()
            )
            logger.info("Nano marked as used, 60-second cooldown started")
        except Exception as e:
            logger.warning(f"Failed to mark nano used: {e}")
    
    def get_nano_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds (0 if ready to use)."""
        try:
            last_call = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'nano_last_call'", 
                fetch=True
            )
            if not last_call:
                return 0.0
            
            # Parse timestamp and calculate remaining time
            from datetime import datetime
            last_time = datetime.fromisoformat(last_call.replace(' ', 'T'))
            now = datetime.now()
            elapsed = (now - last_time).total_seconds()
            
            remaining = max(0.0, NANO_COOLDOWN_SECONDS - elapsed)
            return remaining
        except Exception as e:
            logger.warning(f"Failed to get nano cooldown remaining: {e}")
            return 0.0  # Assume ready if can't check


# Global router instance
router_db = RouterDB()


@contextmanager
def _mark_server_busy(server_id: str):
    """Context manager to mark server as busy during request."""
    if server_id == 'local':
        try:
            router_db.set_local_busy(True)
            logger.debug(f"Marked {server_id} as busy")
            yield
        finally:
            router_db.set_local_busy(False)
            logger.debug(f"Marked {server_id} as free")
    elif server_id in ['external_a', 'external_b', 'external_c', 'external_d']:
        # Track external server busy status
        try:
            router_db.set_external_busy(server_id, True)
            logger.debug(f"Marked {server_id} as busy")
            yield
        finally:
            router_db.set_external_busy(server_id, False)
            logger.debug(f"Marked {server_id} as free")
    elif server_id == 'nano':
        # Nano uses cooldown instead of busy tracking
        try:
            router_db.mark_nano_used()
            logger.debug(f"Marked {server_id} as used (cooldown started)")
            yield
        finally:
            logger.debug(f"Nano request completed")
    else:
        # Unknown server, just yield without tracking
        yield


def _build_llm(server_id: str) -> Runnable[LanguageModelInput, BaseMessage]:
    """Build LangChain LLM client for the specified server."""
    config = SERVERS[server_id]
    provider = config['provider']
    model = config['model']
    temperature = config['temperature']
    base_url = config.get('base_url')
    
    # Special handling for Nano (real OpenAI API)
    if server_id == 'nano':
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set! Set OPENAI_API_KEY_NANO environment variable for testing.")
        
        logger.info(f"Building Nano LLM with model: {model}")
        # NO RETRIES for Nano - billing/quota errors should fail fast, not retry
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            timeout=LLM_CALL_TIMEOUT_S,
            max_retries=0,
            api_key=OPENAI_API_KEY
        )
    
    # Temporary visibility log for routing target
    
    if provider == "ollama":
        # Log target for Ollama
        return ChatOllama(
            model=model,
            temperature=temperature,
            timeout=int(LLM_CALL_TIMEOUT_S),
            request_timeout=LLM_CALL_TIMEOUT_S,
        ).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)
    
    elif provider == "openai":
        kwargs = dict(
            model=model,
            temperature=temperature,
            timeout=LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )
        if base_url:
            kwargs["base_url"] = base_url
            # LangChain's ChatOpenAI still requires an api_key even when using a custom base_url.
            # Provide a harmless dummy to avoid touching global env vars.
            kwargs["api_key"] = os.getenv("OPENAI_API_KEY", "sk-noop")

        return ChatOpenAI(**kwargs).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)
    
    elif provider == "anthropic":
        return ChatAnthropic(
            model_name=model,
            timeout=LLM_CALL_TIMEOUT_S,
            max_retries=0,
            stop=None,
        ).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)
    
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _route_request(tier: ModelTier, estimated_tokens: int = 0, exclude: set[str] = None) -> str:
    """Route request to appropriate server based on tier and token count with smart busy tracking.
    
    Args:
        tier: Model tier (SIMPLE, COMPLEX, etc.)
        estimated_tokens: Estimated token count for the request
        exclude: Set of server IDs to exclude from selection (e.g., failed servers)
    """
    exclude = exclude or set()
    
    # CHECK FIRST: If request exceeds max context, route to Nano (with cooldown check)
    if estimated_tokens > NANO_THRESHOLD:
        if router_db.can_use_nano():
            logger.info(f"🚀 Request too large ({estimated_tokens} > {NANO_THRESHOLD}), routing to Nano")
            return 'nano'
        else:
            # WAIT for cooldown instead of crashing
            logger.warning(f"⚠️ Request needs Nano ({estimated_tokens} tokens) but cooldown active, waiting...")
            wait_time = router_db.get_nano_cooldown_remaining()
            if wait_time > 0:
                logger.info(f"⏳ Waiting {wait_time:.1f}s for Nano cooldown...")
                time.sleep(wait_time + 0.5)  # Add 0.5s buffer
            logger.info(f"✅ Cooldown complete, routing to Nano")
            return 'nano'
    
    if tier == ModelTier.COMPLEX:
        # Complex requests always go to external servers - pick the best available
        server_id = router_db.get_next_external_smart(exclude=exclude)
        logger.debug(f"COMPLEX tier → {server_id} (smart external selection)")
        return server_id
    
    elif tier in (ModelTier.SIMPLE, ModelTier.MEDIUM, ModelTier.SIMPLE_LONG_CONTEXT):
        if tier == ModelTier.MEDIUM:
            logger.debug("MEDIUM tier → routing as SIMPLE (deprecation path)")
        elif tier == ModelTier.SIMPLE_LONG_CONTEXT:
            logger.debug("SIMPLE_LONG_CONTEXT tier → routing as SIMPLE")
        
        # Check if request is small enough for local
        if estimated_tokens > TOKEN_THRESHOLD:
            # Large request - go external
            server_id = router_db.get_next_external_smart(exclude=exclude)
            logger.debug(f"SIMPLE tier → {server_id} (tokens: {estimated_tokens} > {TOKEN_THRESHOLD})")
            return server_id
        
        # Small request - round-robin across ALL servers (local + external)
        # This naturally distributes load across multiple processes
        return router_db.get_next_any_server()
    
    else:
        raise ValueError(f"Unknown tier: {tier}")


class RoutedLLM(Runnable[LanguageModelInput, BaseMessage]):
    """Smart LLM router that defers server selection until invoke time.
    
    Maintains exact same API as old router but adds intelligent routing:
    - Routes based on actual input text size at invoke time
    - Handles busy status tracking and round-robin load balancing
    - Fully compatible with LangChain chains (llm | parser)
    """
    
    def __init__(self, tier: ModelTier):
        self.tier = tier
        self._llm_cache = {}  # Cache LLM instances by server_id
    
    def _get_llm_for_server(self, server_id: str) -> Runnable[LanguageModelInput, BaseMessage]:
        """Get or create LLM instance for specific server."""
        if server_id not in self._llm_cache:
            self._llm_cache[server_id] = _build_llm(server_id)
        return self._llm_cache[server_id]
    
    def invoke(
        self, 
        input: LanguageModelInput, 
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> BaseMessage:
        """Invoke LLM with smart routing based on actual input size."""
        
        # Extract text from input for token estimation
        input_text = ""
        if isinstance(input, str):
            input_text = input
        elif isinstance(input, list) and len(input) > 0:
            # Handle message list - extract content from last message
            last_msg = input[-1]
            if hasattr(last_msg, 'content'):
                input_text = str(last_msg.content)
        
        # Estimate tokens
        estimated_tokens = estimate_tokens(input_text) if input_text else 0
        
        # Track failed servers for this request
        exclude_servers = set()
        
        # Try up to 2 times (primary + 1 fallback)
        for attempt in range(2):
            # Route to appropriate server (excluding failed ones)
            server_id = _route_request(self.tier, estimated_tokens, exclude=exclude_servers)
            
            # Log the routing decision and target
            try:
                sc = SERVERS.get(server_id, {})
                attempt_info = f"attempt={attempt+1}/2" if attempt > 0 else "attempt=1/2"
                excluded_info = f" (excluded={list(exclude_servers)})" if exclude_servers else ""
                logger.info(
                    f"[LLM INVOKE] {attempt_info} server={server_id} provider={sc.get('provider')} "
                    f"model={sc.get('model')} url={sc.get('base_url')} tokens={estimated_tokens}{excluded_info}"
                )
            except Exception:
                pass
            
            # LLM usage tracking removed - not critical for flow visibility
            
            # Get LLM for selected server and invoke with busy tracking
            llm = self._get_llm_for_server(server_id)
            with _mark_server_busy(server_id):
                try:
                    result = llm.invoke(input, config, **kwargs)
                    
                    # Detailed logging of what we got back
                    result_type = type(result).__name__
                    has_content = hasattr(result, 'content')
                    
                    if has_content:
                        content = str(result.content).strip()
                        content_length = len(content)
                        content_preview = content[:200] if content else "(empty)"
                        
                        logger.debug(
                            f"📥 LLM RESPONSE | server={server_id} | "
                            f"type={result_type} | has_content={has_content} | "
                            f"length={content_length} | preview={content_preview}..."
                        )
                        
                        # Check for empty response
                        if not content:
                            logger.error(
                                f"❌ SERVER FAILED: {server_id} returned EMPTY response | "
                                f"url={SERVERS.get(server_id, {}).get('base_url')} | "
                                f"result_type={result_type} | has_content_attr={has_content} | "
                                f"content_value='{result.content}' | content_length=0 | "
                                f"This server may be down, overloaded, or hit token limit"
                            )
                            
                            # Log additional result attributes for debugging
                            try:
                                result_attrs = {k: v for k, v in vars(result).items() if not k.startswith('_')}
                                logger.error(f"📋 Result attributes: {result_attrs}")
                            except:
                                pass
                            
                            exclude_servers.add(server_id)
                            
                            if attempt < 1:  # Have more attempts
                                logger.info(f"🔄 RETRYING with different server (excluding {server_id})...")
                                continue  # Try again with different server
                            else:
                                logger.warning(
                                    f"⚠️  All attempts exhausted - returning empty response | "
                                    f"failed_servers={list(exclude_servers)}"
                                )
                                # Return empty result - sanitizer will handle it
                    else:
                        # Result doesn't have content attribute
                        logger.error(
                            f"❌ UNEXPECTED RESULT FORMAT: {server_id} | "
                            f"result_type={result_type} | has_content={has_content} | "
                            f"result_value={str(result)[:200]}"
                        )
                    
                    # Success!
                    if attempt > 0:
                        logger.info(
                            f"✅ SUCCESS after retry | server={server_id} worked after {list(exclude_servers)} failed | "
                            f"response_length={content_length if has_content else 'N/A'}"
                        )
                    return result
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    error_type = type(e).__name__
                    error_full = str(e)
                    
                    # Log detailed error information
                    logger.error(
                        f"❌ LLM EXCEPTION | server={server_id} | "
                        f"error_type={error_type} | "
                        f"url={SERVERS.get(server_id, {}).get('base_url')} | "
                        f"tokens={estimated_tokens}"
                    )
                    logger.error(f"📋 Error details: {error_full[:500]}")
                    
                    # Check for specific error patterns
                    if 'timeout' in error_msg:
                        logger.error(f"⏱️  TIMEOUT ERROR - Request took longer than {LLM_CALL_TIMEOUT_S}s")
                    elif 'connection' in error_msg:
                        logger.error(f"🔌 CONNECTION ERROR - Cannot reach server")
                    elif 'token' in error_msg and 'limit' in error_msg:
                        logger.error(f"📏 TOKEN LIMIT ERROR - Request may exceed server capacity")
                    elif 'memory' in error_msg or 'oom' in error_msg:
                        logger.error(f"💾 MEMORY ERROR - Server out of memory")
                    elif 'rate' in error_msg and 'limit' in error_msg:
                        logger.error(f"🚦 RATE LIMIT ERROR - Too many requests")
                    
                    # Special handling for Nano billing/quota errors - FAIL FAST
                    if server_id == 'nano':
                        if any(keyword in error_msg for keyword in ['quota', 'billing', 'insufficient', 'credits', 'rate limit']):
                            logger.error(f"💳 Nano billing/quota error: {e}")
                            logger.error("⛔ Out of Nano credits or rate limited - request FAILED")
                            raise  # Re-raise to fail the request (don't retry)
                    
                    # For external servers - log failure and try fallback
                    if server_id.startswith('external_'):
                        exclude_servers.add(server_id)
                        
                        if attempt < 1:  # Have more attempts
                            logger.info(f"🔄 RETRYING with different server (excluding {server_id})...")
                            continue  # Try again with different server
                        else:
                            logger.error(
                                f"⛔ ALL SERVERS FAILED | failed_servers={list(exclude_servers)} | "
                                f"last_error={error_type}: {error_full[:200]}"
                            )
                    
                    # Re-raise on last attempt or non-external servers
                    raise
    
    async def ainvoke(
        self, 
        input: LanguageModelInput, 
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> BaseMessage:
        """Async invoke with smart routing (no busy tracking for async)."""
        # Same routing logic as invoke
        input_text = ""
        if isinstance(input, str):
            input_text = input
        elif isinstance(input, list) and len(input) > 0:
            last_msg = input[-1]
            if hasattr(last_msg, 'content'):
                input_text = str(last_msg.content)
        
        estimated_tokens = estimate_tokens(input_text) if input_text else 0
        server_id = _route_request(self.tier, estimated_tokens)
        llm = self._get_llm_for_server(server_id)
        return await llm.ainvoke(input, config, **kwargs)
    
    def stream(
        self, 
        input: LanguageModelInput, 
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> Iterator[BaseMessage]:
        """Stream with smart routing and busy tracking."""
        # Same routing logic as invoke
        input_text = ""
        if isinstance(input, str):
            input_text = input
        elif isinstance(input, list) and len(input) > 0:
            last_msg = input[-1]
            if hasattr(last_msg, 'content'):
                input_text = str(last_msg.content)
        
        estimated_tokens = estimate_tokens(input_text) if input_text else 0
        server_id = _route_request(self.tier, estimated_tokens)
        llm = self._get_llm_for_server(server_id)
        
        with _mark_server_busy(server_id):
            yield from llm.stream(input, config, **kwargs)
    
    async def astream(
        self, 
        input: LanguageModelInput, 
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> AsyncIterator[BaseMessage]:
        """Async stream with smart routing (no busy tracking for async)."""
        # Same routing logic as invoke
        input_text = ""
        if isinstance(input, str):
            input_text = input
        elif isinstance(input, list) and len(input) > 0:
            last_msg = input[-1]
            if hasattr(last_msg, 'content'):
                input_text = str(last_msg.content)
        
        estimated_tokens = estimate_tokens(input_text) if input_text else 0
        server_id = _route_request(self.tier, estimated_tokens)
        llm = self._get_llm_for_server(server_id)
        
        async for chunk in llm.astream(input, config, **kwargs):
            yield chunk
    
    # For any other methods, we need to route at call time
    # This is tricky since we don't have input, so we'll use a default routing
    def __getattr__(self, name):
        # Default to local for unknown method calls (best effort)
        server_id = 'local' if not router_db.is_local_busy() else router_db.get_next_external()
        llm = self._get_llm_for_server(server_id)
        return getattr(llm, name)


def get_llm(tier: ModelTier) -> RoutedLLM:
    """Get a smart-routed LLM for the specified tier.
    
    Exact same API as the old router but with intelligent routing:
    - Server selection happens at invoke() time based on actual input size
    - Supports TOKEN_THRESHOLD for laptop-friendly routing
    - Round-robin load balancing across external servers
    
    Args:
        tier: The model tier to use (SIMPLE, MEDIUM, COMPLEX, SIMPLE_LONG_CONTEXT)
        
    Returns:
        A RoutedLLM instance that routes intelligently at invoke time
    """
    try:
        logger.debug(f"Creating smart router for tier: {tier.name}")
        return RoutedLLM(tier)
        
    except Exception as e:
        logger.error(f"Failed to create smart router: {e}")
        # Fallback - still return a RoutedLLM but it will use external_a
        logger.warning("Falling back to basic routing due to error")
        return RoutedLLM(tier)


# Backward compatibility - maintain the same interface
def get_llm_for_tier(tier: ModelTier) -> RoutedLLM:
    """Backward compatibility alias."""
    return get_llm(tier)