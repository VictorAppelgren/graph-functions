"""
Minimal, powerful logging for Argos Graph.
- Console only (no file output)
- ISO timestamps, level, module, message
- Supports context (asset, stage, domain) via logger.extra
- Simple decorator for timing and error logging

Usage:
    from minimal_logging import get_logger, log_execution
    logger = get_logger(__name__)
    logger.info("Hello")
    with logger.context(asset="EURUSD", stage="F02_GAP_DETECTION"):
        logger.info("Context-aware log")
    
    @log_execution(logger)
    def foo():
        ...
"""
import logging
import os
import sys
from datetime import datetime
from contextlib import contextmanager
from functools import wraps

class MinimalFormatter(logging.Formatter):
    def format(self, record):
        iso_time = datetime.fromtimestamp(record.created).isoformat()
        level = record.levelname
        name = record.name
        msg = record.getMessage()
        # Add context if present
        ctx = getattr(record, 'context', None)
        ctx_str = f" | context: {ctx}" if ctx else ""
        base = f"{iso_time} | {level:<8} | {name:<30} | {msg}{ctx_str}"
        # Append traceback if present
        if record.exc_info:
            try:
                exc_text = self.formatException(record.exc_info)
                return f"{base}\n{exc_text}"
            except Exception:
                return base
        return base

class ContextLogger(logging.Logger):
    @contextmanager
    def context(self, **kwargs):
        old_ctx = getattr(self, '_log_ctx', None)
        self._log_ctx = kwargs
        try:
            yield
        finally:
            self._log_ctx = old_ctx
    def makeRecord(self, *args, **kwargs):
        record = super().makeRecord(*args, **kwargs)
        if hasattr(self, '_log_ctx') and self._log_ctx:
            record.context = self._log_ctx
        else:
            record.context = None
        return record

# 
def _level_from_env(default_level: int) -> int:
    lvl = os.environ.get("ARGOS_LOG_LEVEL", "").upper().strip()
    mapping = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }
    return mapping.get(lvl, default_level)


def get_logger(name: str, level=logging.INFO) -> ContextLogger:
    logging.setLoggerClass(ContextLogger)
    logger = logging.getLogger(name)
    # Resolve effective level (env can override)
    effective_level = _level_from_env(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(MinimalFormatter())
        handler.setLevel(effective_level)
        logger.addHandler(handler)
        logger.setLevel(effective_level)
        logger.propagate = False
    else:
        # Ensure existing logger/handlers respect env override
        logger.setLevel(effective_level)
        for h in logger.handlers:
            h.setLevel(effective_level)
    return logger

def truncate_str(s, max_len=100):
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

def log_execution(logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = datetime.now()
            logger.debug(f"Entering {func.__name__}")
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start).total_seconds()
                logger.debug(f"Completed {func.__name__} in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = (datetime.now() - start).total_seconds()
                logger.exception(f"Error in {func.__name__} after {elapsed:.2f}s")
                raise
        return wrapper
    return decorator
