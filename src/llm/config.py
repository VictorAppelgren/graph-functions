"""Model Configuration for Argos Research Platform

Smart LLM Router with SQLite-based status tracking for optimal server selection.

4-Tier Architecture:
- SIMPLE: 20B model (local + :8686 + :8787) - Article ingestion, classification, relevance
- MEDIUM: 120B model (:3331) - Research writing, deeper analysis
- COMPLEX: DeepSeek v3.2 API - Strategic reasoning, complex synthesis
- FAST: Anthropic Claude - User-facing chat, quick rewrites (expensive but fast)

Automatic busy status tracking and round-robin load balancing for SIMPLE tier.
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
from src.observability.stats_client import track

logger = get_logger(__name__)

# --- Load .env file from victor_deployment ---
# This ensures API keys are available without manual sourcing
def _load_env_file():
    """Load .env file from victor_deployment if it exists."""
    try:
        from dotenv import load_dotenv
        # Find victor_deployment/.env relative to this file
        config_dir = Path(__file__).parent  # src/llm/
        graph_functions_dir = config_dir.parent.parent  # graph-functions/
        env_file = graph_functions_dir.parent / "victor_deployment" / ".env"

        if env_file.exists():
            load_dotenv(env_file)
            logger.debug(f"Loaded .env from {env_file}")
        else:
            # Also try graph-functions/.env as fallback
            local_env = graph_functions_dir / ".env"
            if local_env.exists():
                load_dotenv(local_env)
                logger.debug(f"Loaded .env from {local_env}")
    except ImportError:
        # python-dotenv not installed, skip
        pass
    except Exception as e:
        logger.warning(f"Failed to load .env file: {e}")

_load_env_file()

# --- Configuration ---
TOKEN_THRESHOLD = 3000  # Requests ≤3k tokens use local, >3k use external (SIMPLE tier)
LLM_CALL_TIMEOUT_S = 300.0
LLM_RETRY_ATTEMPTS = 2  # Reduced from 3 - we have fallback logic now
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY = 0.1

# OpenRouter free tier rate limiting (16 req/min = ~4s between calls)
OPENROUTER_MIN_DELAY_S = 4.0  # Minimum seconds between OpenRouter calls
_openrouter_last_call: float = 0.0  # Timestamp of last OpenRouter call

# Paid 20B cooldown (prevent overspending on SIMPLE tier fallback)
# At $0.03/M input + $0.14/M output, typical short calls ~$0.00001-0.0001 each
# 5000 calls/day ~= $0.05-0.50/day max (most calls are very short)
PAID_20B_DAILY_LIMIT = 5000  # Max calls per day to paid 20B
_paid_20b_calls_today: int = 0
_paid_20b_reset_date: str = ""  # ISO date string for reset tracking

# OpenRouter upstream rate limit backoff (when the free model is overloaded globally)
# Waits: 1m → 5m → 15m → 60m → 60m... (keeps trying hourly for 24/7 operation)
OPENROUTER_UPSTREAM_BACKOFF_S = [60, 300, 900, 3600, 3600, 3600, 3600, 3600]

# DeepSeek R1 Free has only 8K context - skip it for long prompts
DEEPSEEK_R1_CONTEXT_LIMIT = 6000  # Leave room for output tokens

# API Keys from environment (loaded from .env above)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model tier enum - 4 tiers for different use cases
class ModelTier(Enum):
    SIMPLE = "SIMPLE"              # 20B model - article work (cheap, bulk)
    MEDIUM = "MEDIUM"              # 120B model - research/writing (better quality)
    COMPLEX = "COMPLEX"            # DeepSeek v3.2 - strategic reasoning (thinker)
    FAST = "FAST"                  # Anthropic - user-facing (expensive but fast)
    SIMPLE_LONG_CONTEXT = "SIMPLE_LONG_CONTEXT"  # Deprecated - routes to SIMPLE

# --- Server Configuration ---
#
# SIMPLE tier: local + external_a + external_b (all 20B model)
# MEDIUM tier: external_120b (120B model on :3331)
# COMPLEX tier: deepseek (DeepSeek v3.2 API)
# FAST tier: anthropic (Claude for user-facing)
#
# Environment variables:
# - DISABLE_LOCAL_LLM=true: Skip local server (for cloud deployment)
# - LOCAL_LLM_ONLY=true: Only use local server (for offline/testing)
# - DEEPSEEK_API_KEY: Required for COMPLEX tier
# - ANTHROPIC_API_KEY: Required for FAST tier
# - OPENROUTER_API_KEY: Required for MEDIUM tier (OpenRouter)

# Check deployment mode
DISABLE_LOCAL_LLM = os.getenv("DISABLE_LOCAL_LLM", "false").lower() == "true"
LOCAL_LLM_ONLY = os.getenv("LOCAL_LLM_ONLY", "false").lower() == "true"

# Debug logging at module load time
import logging
_init_logger = logging.getLogger(__name__)
_init_logger.info(f"LLM CONFIG INIT: DISABLE_LOCAL_LLM={DISABLE_LOCAL_LLM}, LOCAL_LLM_ONLY={LOCAL_LLM_ONLY}")

SERVERS = {}

# --- SIMPLE tier servers (20B model) ---
# Only add local server if not disabled
if not DISABLE_LOCAL_LLM:
    SERVERS['local'] = {
        'provider': 'openai',  # llama.cpp server is OpenAI-compatible
        'base_url': 'http://127.0.0.1:8080/v1',
        'model': 'ggml-org/gpt-oss-20b-GGUF',
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added 'local' server (20B llama.cpp)")

# Add external 20B servers unless in local-only mode
if not LOCAL_LLM_ONLY:
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
        # Paid 20B fallback via OpenRouter (DeepInfra: $0.03/M input, $0.14/M output)
        'external_20b_paid': {
            'provider': 'openai',
            'base_url': 'https://openrouter.ai/api/v1',
            'model': 'openai/gpt-oss-20b',  # Non-free version
            'temperature': 0.2,
        },
    })
    _init_logger.info("LLM CONFIG: Added external_a, external_b (20B vLLM on :8686, :8787)")
    _init_logger.info("LLM CONFIG: Added external_20b_paid (20B via DeepInfra, $0.03/M)")

    # --- MEDIUM tier server (120B model via OpenRouter) ---
    # Local 120B server (commented out - boss using the server)
    # SERVERS['external_120b'] = {
    #     'provider': 'openai',
    #     'base_url': 'http://gate04.cfa.handels.gu.se:3331/v1',
    #     'model': 'openai/gpt-oss-120b',  # 120B model
    #     'temperature': 0.2,
    # }
    # _init_logger.info("LLM CONFIG: Added external_120b (120B vLLM on :3331)")

    # OpenRouter 120B (free tier - 1000 req/day shared across all free models)
    SERVERS['external_120b'] = {
        'provider': 'openai',
        'base_url': 'https://openrouter.ai/api/v1',
        'model': 'openai/gpt-oss-120b:free',
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added external_120b (120B via OpenRouter free tier)")

    # OpenRouter DeepSeek R1 (free tier - 1000 req/day shared, 8K context only!)
    SERVERS['deepseek_r1_free'] = {
        'provider': 'openai',
        'base_url': 'https://openrouter.ai/api/v1',
        'model': 'deepseek/deepseek-r1-0528:free',
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added deepseek_r1_free (DeepSeek R1 free, 8K context)")

    # OpenRouter 120B paid (GMICloud - very cheap: $0.02/M input, $0.10/M output)
    SERVERS['external_120b_paid'] = {
        'provider': 'openai',
        'base_url': 'https://openrouter.ai/api/v1',
        'model': 'openai/gpt-oss-120b',  # Non-free version
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added external_120b_paid (120B via GMICloud, $0.02/M)")

    # DeepSeek paid API (final fallback)
    SERVERS['deepseek_paid'] = {
        'provider': 'openai',
        'base_url': 'https://api.deepseek.com',
        'model': 'deepseek-chat',
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added deepseek_paid (DeepSeek v3.2 paid API)")

    # --- FAST tier server (Anthropic Claude) ---
    SERVERS['anthropic'] = {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514',  # Fast and capable
        'temperature': 0.2,
    }
    _init_logger.info("LLM CONFIG: Added anthropic (Claude for FAST tier)")

# Log final server configuration
_init_logger.info(f"🔧 LLM CONFIG: Final SERVERS = {list(SERVERS.keys())}")

# Database setup
DB_PATH = Path(__file__).parent / "router_status.db"
db_lock = Lock()


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-based heuristic."""
    return int(len(text.split()) * 1.3)


def _check_paid_20b_cooldown() -> bool:
    """Check if we can use paid 20B (under daily limit).

    Returns True if under limit and increments counter.
    Returns False if limit reached (don't use paid 20B).
    """
    global _paid_20b_calls_today, _paid_20b_reset_date

    today = datetime.now().strftime("%Y-%m-%d")

    # Reset counter at midnight
    if _paid_20b_reset_date != today:
        _paid_20b_calls_today = 0
        _paid_20b_reset_date = today
        logger.info(f"🔄 Paid 20B daily counter reset for {today}")

    # Check limit
    if _paid_20b_calls_today >= PAID_20B_DAILY_LIMIT:
        logger.warning(f"⚠️  Paid 20B daily limit reached ({_paid_20b_calls_today}/{PAID_20B_DAILY_LIMIT})")
        return False

    # Increment and allow
    _paid_20b_calls_today += 1
    if _paid_20b_calls_today % 50 == 0:  # Log every 50 calls
        logger.info(f"💰 Paid 20B usage: {_paid_20b_calls_today}/{PAID_20B_DAILY_LIMIT} calls today")

    return True


class RouterDB:
    """Simple SQLite-based router status manager for SIMPLE tier load balancing."""

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
                    # Initialize default values for SIMPLE tier load balancing
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value)
                        VALUES ('local_busy', '0')
                    """)
                    conn.execute("""
                        INSERT OR IGNORE INTO router_status (key, value)
                        VALUES ('last_external', 'external_a')
                    """)
                    # Initialize external server status (20B servers for SIMPLE tier)
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
        """Get next free server for SIMPLE tier: local → external_a → external_b."""
        # Check each server in order, return first free one
        if 'local' in SERVERS and not self.is_local_busy():
            return 'local'

        if 'external_a' in SERVERS and not self.is_external_busy('external_a'):
            return 'external_a'

        if 'external_b' in SERVERS and not self.is_external_busy('external_b'):
            return 'external_b'

        # All busy - fallback to local if available, else external_a
        if 'local' in SERVERS:
            return 'local'
        return 'external_a' if 'external_a' in SERVERS else 'local'


# Global router instance
router_db = RouterDB()


@contextmanager
def _mark_server_busy(server_id: str):
    """Context manager to mark server as busy during request.

    Only tracks busy status for SIMPLE tier servers (local, external_a, external_b).
    Other servers (external_120b, deepseek, anthropic) don't need busy tracking.
    """
    if server_id == 'local':
        try:
            router_db.set_local_busy(True)
            logger.debug(f"Marked {server_id} as busy")
            yield
        finally:
            router_db.set_local_busy(False)
            logger.debug(f"Marked {server_id} as free")
    elif server_id in ['external_a', 'external_b']:
        # Track external server busy status for SIMPLE tier load balancing
        try:
            router_db.set_external_busy(server_id, True)
            logger.debug(f"Marked {server_id} as busy")
            yield
        finally:
            router_db.set_external_busy(server_id, False)
            logger.debug(f"Marked {server_id} as free")
    else:
        # Other servers (external_120b, deepseek, anthropic) - no busy tracking needed
        yield


def _build_llm(server_id: str) -> Runnable[LanguageModelInput, BaseMessage]:
    """Build LangChain LLM client for the specified server."""
    config = SERVERS[server_id]
    provider = config['provider']
    model = config['model']
    temperature = config['temperature']
    base_url = config.get('base_url')

    if provider == "ollama":
        # num_predict caps output tokens to prevent infinite generation loops
        return ChatOllama(
            model=model,
            temperature=temperature,
            timeout=int(LLM_CALL_TIMEOUT_S),
            request_timeout=LLM_CALL_TIMEOUT_S,
            num_predict=2048,
        ).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)

    elif provider == "openai":
        kwargs = dict(
            model=model,
            temperature=temperature,
            timeout=LLM_CALL_TIMEOUT_S,
            max_retries=0,
        )

        # Handle DeepSeek paid API (uses OpenAI-compatible endpoint)
        if server_id == 'deepseek_paid':
            if not DEEPSEEK_API_KEY:
                raise ValueError("DEEPSEEK_API_KEY not set! Required for paid DeepSeek.")
            kwargs["base_url"] = base_url
            kwargs["api_key"] = DEEPSEEK_API_KEY
            kwargs["max_tokens"] = 8192
        # Handle OpenRouter APIs (external_120b and deepseek_r1_free)
        elif 'openrouter.ai' in (base_url or ''):
            if not OPENROUTER_API_KEY:
                raise ValueError("OPENROUTER_API_KEY not set! Required for OpenRouter.")
            kwargs["base_url"] = base_url
            kwargs["api_key"] = OPENROUTER_API_KEY
            kwargs["max_tokens"] = 8192
        elif base_url:
            # Local vLLM servers (local, external_a, external_b)
            # These run 20B models with ~32k context
            # Don't set max_tokens - let model decide based on input size
            kwargs["base_url"] = base_url
            kwargs["api_key"] = os.getenv("OPENAI_API_KEY", "sk-noop")
            # max_tokens NOT set - avoids truncation issues with large inputs

        return ChatOpenAI(**kwargs).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)

    elif provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set! Required for FAST tier.")
        return ChatAnthropic(
            model_name=model,
            timeout=LLM_CALL_TIMEOUT_S,
            max_retries=0,
            stop=None,
        ).with_retry(stop_after_attempt=LLM_RETRY_ATTEMPTS)

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _route_request(tier: ModelTier, estimated_tokens: int = 0, exclude: set[str] = None) -> str:
    """Route request to appropriate server based on tier and token count.

    Routing chains (tries in order, skips excluded/unavailable):
    - FAST: anthropic
    - COMPLEX/MEDIUM: deepseek_r1_free (if <6K tokens) → external_120b → external_120b_paid → deepseek_paid
    - SIMPLE: local → external_a → external_b (with load balancing)
    """
    exclude = exclude or set()

    # --- FAST tier: Anthropic Claude ---
    if tier == ModelTier.FAST:
        if 'anthropic' in SERVERS:
            return 'anthropic'
        logger.warning("FAST: anthropic unavailable, falling back to MEDIUM")
        return _route_request(ModelTier.MEDIUM, estimated_tokens, exclude)

    # --- COMPLEX/MEDIUM tier: Same fallback chain, token-aware ---
    if tier in (ModelTier.COMPLEX, ModelTier.MEDIUM):
        # DeepSeek R1 free: only for short prompts (<6K tokens)
        if (estimated_tokens < DEEPSEEK_R1_CONTEXT_LIMIT and
            'deepseek_r1_free' in SERVERS and
            'deepseek_r1_free' not in exclude):
            logger.debug(f"{tier.value} → deepseek_r1_free (tokens={estimated_tokens} < {DEEPSEEK_R1_CONTEXT_LIMIT})")
            return 'deepseek_r1_free'

        # 120B free (long context, but limited to 1000 req/day shared)
        if 'external_120b' in SERVERS and 'external_120b' not in exclude:
            logger.debug(f"{tier.value} → external_120b (free, 131K context)")
            return 'external_120b'

        # 120B paid (cheap fallback: $0.02/M)
        if 'external_120b_paid' in SERVERS and 'external_120b_paid' not in exclude:
            logger.debug(f"{tier.value} → external_120b_paid (paid, $0.02/M)")
            return 'external_120b_paid'

        # DeepSeek paid (final fallback)
        if 'deepseek_paid' in SERVERS and 'deepseek_paid' not in exclude:
            logger.debug(f"{tier.value} → deepseek_paid (final fallback)")
            return 'deepseek_paid'

        logger.warning(f"{tier.value}: no servers available, falling back to SIMPLE")
        return _route_request(ModelTier.SIMPLE, estimated_tokens, exclude)

    # --- SIMPLE tier: 20B models with load balancing ---
    # Fallback chain: local → external_a → external_b → external_20b_paid (with cooldown)
    if tier in (ModelTier.SIMPLE, ModelTier.SIMPLE_LONG_CONTEXT):
        if estimated_tokens > TOKEN_THRESHOLD:
            server_id = router_db.get_next_external_smart(exclude=exclude)
            logger.debug(f"SIMPLE → {server_id} (tokens={estimated_tokens} > {TOKEN_THRESHOLD})")
            return server_id

        # Try free servers first
        free_server = router_db.get_next_any_server()

        # If all free servers have been tried (in exclude set), fall back to paid 20B
        free_servers = {'local', 'external_a', 'external_b'} & set(SERVERS.keys())
        if free_servers and free_servers.issubset(exclude):
            # All free servers failed - try paid 20B if under cooldown limit
            if 'external_20b_paid' in SERVERS and 'external_20b_paid' not in exclude:
                if _check_paid_20b_cooldown():
                    logger.info(f"SIMPLE → external_20b_paid (all free servers exhausted)")
                    return 'external_20b_paid'
                else:
                    logger.warning(f"SIMPLE: All free servers exhausted, paid 20B at daily limit")

        return free_server

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
        global _openrouter_last_call

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
            
            # Get LLM for selected server and invoke with busy tracking
            llm = self._get_llm_for_server(server_id)
            with _mark_server_busy(server_id):
                try:
                    # OpenRouter free tier rate limiting (applies to all OpenRouter servers)
                    if 'openrouter.ai' in SERVERS.get(server_id, {}).get('base_url', ''):
                        elapsed = time.time() - _openrouter_last_call
                        if elapsed < OPENROUTER_MIN_DELAY_S:
                            wait_time = OPENROUTER_MIN_DELAY_S - elapsed
                            logger.debug(f"⏳ OpenRouter rate limit: waiting {wait_time:.1f}s")
                            time.sleep(wait_time)
                        _openrouter_last_call = time.time()

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
                    
                    # Success! Track the call (tier + server, no message = no master log spam)
                    track(f"llm_{self.tier.value.lower()}")  # Tier total: llm_simple, llm_medium, etc.
                    track(f"llm_server_{server_id}")  # Per-server: llm_server_external_a, etc.

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
                    
                    # Check for specific error patterns and handle with fallback

                    # Context/token limit exceeded (400 error) - try next server
                    if ('exceed' in error_msg or 'max_num_tokens' in error_msg or
                        ('context' in error_msg and 'length' in error_msg)):
                        logger.warning(f"CONTEXT EXCEEDED on {server_id} - trying fallback")
                        exclude_servers.add(server_id)
                        if attempt < 1:
                            continue  # Retry with different server

                    if 'timeout' in error_msg:
                        logger.error(f"TIMEOUT ERROR - Request took longer than {LLM_CALL_TIMEOUT_S}s")
                    elif 'connection' in error_msg:
                        logger.error(f"CONNECTION ERROR - Cannot reach server")
                    elif 'token' in error_msg and 'limit' in error_msg:
                        logger.error(f"TOKEN LIMIT ERROR - Request may exceed server capacity")
                    elif 'memory' in error_msg or 'oom' in error_msg:
                        logger.error(f"MEMORY ERROR - Server out of memory")
                    elif 'rate' in error_msg and 'limit' in error_msg:
                        logger.error(f"RATE LIMIT ERROR - Too many requests")

                        # OpenRouter upstream rate limit - the free model is overloaded globally
                        # This requires longer waits (minutes to hours) since it's not our rate limit
                        is_openrouter = 'openrouter.ai' in SERVERS.get(server_id, {}).get('base_url', '')
                        if is_openrouter and ('upstream' in error_msg or 'temporarily' in error_msg):
                            for backoff_attempt, wait_seconds in enumerate(OPENROUTER_UPSTREAM_BACKOFF_S):
                                wait_mins = wait_seconds / 60
                                logger.warning(
                                    f"⏳ OpenRouter upstream rate limit - waiting {wait_mins:.0f}m "
                                    f"(attempt {backoff_attempt + 1}/{len(OPENROUTER_UPSTREAM_BACKOFF_S)})"
                                )
                                time.sleep(wait_seconds)

                                # Retry the request
                                try:
                                    _openrouter_last_call = time.time()
                                    result = llm.invoke(input, config, **kwargs)
                                    logger.info(f"✅ OpenRouter recovered after {wait_mins:.0f}m wait")
                                    return result
                                except Exception as retry_e:
                                    retry_msg = str(retry_e).lower()
                                    if '429' in str(retry_e) or 'rate' in retry_msg:
                                        logger.warning(f"⏳ Still rate limited, will retry...")
                                        continue
                                    else:
                                        # Different error - re-raise
                                        raise retry_e

                            # Exhausted all backoff attempts
                            logger.error(f"❌ OpenRouter still rate limited after {sum(OPENROUTER_UPSTREAM_BACKOFF_S)/3600:.1f}h of retries")
                            raise

                    # Fail fast on billing/quota errors (no point retrying)
                    if any(keyword in error_msg for keyword in ['quota', 'billing', 'insufficient', 'credits']):
                        logger.error(f"BILLING/QUOTA error for {server_id}: {e}")
                        raise

                    # For any server error - try fallback if we have attempts left
                    exclude_servers.add(server_id)
                    if attempt < 1:
                        logger.info(f"🔄 RETRYING with different server (excluding {server_id})...")
                        continue

                    # All attempts exhausted
                    logger.error(f"ALL SERVERS FAILED | excluded={list(exclude_servers)} | last_error={error_type}")
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

    4-Tier Architecture:
    - SIMPLE: 20B model (local + :8686 + :8787) - Article ingestion, classification
    - MEDIUM: 120B model (:3331) - Research writing, deeper analysis
    - COMPLEX: DeepSeek v3.2 - Strategic reasoning, complex synthesis
    - FAST: Anthropic Claude - User-facing chat, quick rewrites

    Args:
        tier: The model tier to use (SIMPLE, MEDIUM, COMPLEX, FAST)

    Returns:
        A RoutedLLM instance that routes to the appropriate server
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