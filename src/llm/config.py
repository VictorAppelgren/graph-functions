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
TOKEN_THRESHOLD = 2000  # If working/ using the laptop and minimize load on my system
#TOKEN_THRESHOLD = 20000  # Simple vs Complex routing threshold
LLM_CALL_TIMEOUT_S = 300.0
LLM_RETRY_ATTEMPTS = 3
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY = 0.1

# Minimal model tier enum (local definition to avoid circular imports)
class ModelTier(Enum):
    SIMPLE = "SIMPLE"
    MEDIUM = "MEDIUM"  # routes like SIMPLE per current router
    COMPLEX = "COMPLEX"
    SIMPLE_LONG_CONTEXT = "SIMPLE_LONG_CONTEXT"

# Hardcoded server configuration
SERVERS = {
    'local': {
        'provider': 'ollama', 
        'base_url': 'http://localhost:11434', 
        'model': 'gpt-oss:20b',
        'temperature': 0.2,
    },
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
    }
}

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
            return False  # Assume not busy if can't check

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
        """Get external server that was called longest ago."""
        try:
            # Get last call times for both servers
            a_time = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'external_a_last_call'", 
                fetch=True
            )
            b_time = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'external_b_last_call'", 
                fetch=True
            )
            
            # If we don't have timestamps, fall back to round-robin
            if not a_time or not b_time:
                return self.get_next_external()
            
            # Return the one called longest ago (earlier timestamp)
            return 'external_a' if a_time < b_time else 'external_b'
            
        except Exception as e:
            logger.warning(f"Failed to get least recently used external: {e}")
            return self.get_next_external()  # Fallback to round-robin

    def get_next_external_smart(self) -> str:
        """Smart external server selection with busy tracking."""
        try:
            # Check if external_a is free
            if not self.is_external_busy('external_a'):
                logger.debug("external_a is free, selecting it")
                return 'external_a'
            
            # Check if external_b is free
            if not self.is_external_busy('external_b'):
                logger.debug("external_b is free, selecting it")
                return 'external_b'
            
            # Both busy - pick least recently used
            server = self.get_least_recently_used_external()
            logger.debug(f"Both external servers busy, selecting least recently used: {server}")
            return server
            
        except Exception as e:
            logger.warning(f"Smart external selection failed: {e}, falling back to round-robin")
            return self.get_next_external()  # Fallback to simple round-robin

    def get_next_external(self) -> str:
        """Get next external server using round-robin."""
        try:
            last = self._execute_with_retry(
                "SELECT value FROM router_status WHERE key = 'last_external'", 
                fetch=True
            )
            next_server = 'external_b' if last == 'external_a' else 'external_a'
            
            self._execute_with_retry(
                "UPDATE router_status SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_external'",
                (next_server,)
            )
            return next_server
        except Exception as e:
            logger.warning(f"Failed to get next external server: {e}")
            return 'external_a'  # Default fallback


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
    elif server_id in ['external_a', 'external_b']:
        # Track external server busy status
        try:
            router_db.set_external_busy(server_id, True)
            logger.debug(f"Marked {server_id} as busy")
            yield
        finally:
            router_db.set_external_busy(server_id, False)
            logger.debug(f"Marked {server_id} as free")
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


def _route_request(tier: ModelTier, estimated_tokens: int = 0) -> str:
    """Route request to appropriate server based on tier and token count with smart busy tracking."""
    
    if tier == ModelTier.COMPLEX:
        # Complex requests always go to external servers - pick the best available
        server_id = router_db.get_next_external_smart()
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
            server_id = router_db.get_next_external_smart()
            logger.debug(f"SIMPLE tier → {server_id} (tokens: {estimated_tokens} > {TOKEN_THRESHOLD})")
            return server_id
        
        # Small request - try local first
        if not router_db.is_local_busy():
            logger.debug(f"SIMPLE tier → local (tokens: {estimated_tokens}, local free)")
            return 'local'
        
        # Local is busy - check external servers
        if not router_db.is_external_busy('external_a'):
            logger.debug(f"SIMPLE tier → external_a (local busy, external_a free)")
            return 'external_a'
        elif not router_db.is_external_busy('external_b'):
            logger.debug(f"SIMPLE tier → external_b (local busy, external_b free)")
            return 'external_b'
        else:
            # All servers busy - spread load by using local anyway
            logger.debug(f"SIMPLE tier → local (all servers busy, spreading load)")
            return 'local'
    
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
        
        # Estimate tokens and route to appropriate server
        estimated_tokens = estimate_tokens(input_text) if input_text else 0
        server_id = _route_request(self.tier, estimated_tokens)
        
        # Log the routing decision and target
        try:
            sc = SERVERS.get(server_id, {})
            logger.info(
                f"[LLM INVOKE] server={server_id} provider={sc.get('provider')} model={sc.get('model')} url={sc.get('base_url')} tokens={estimated_tokens}"
            )
        except Exception:
            pass
        
        # Get LLM for selected server and invoke with busy tracking
        llm = self._get_llm_for_server(server_id)
        with _mark_server_busy(server_id):
            return llm.invoke(input, config, **kwargs)
    
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