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
from collections.abc import Callable
from typing import TypeVar, ParamSpec, Any, Iterator, cast

P = ParamSpec("P")  # captures parameter types of wrapped function
R = TypeVar("R")    # captures return type of wrapped function

class MinimalFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record into a human-readable string with ISO timestamp,
        log level, logger name, and optional context.
        """
        iso_time = datetime.fromtimestamp(record.created).isoformat()
        level: str = record.levelname
        name: str = record.name
        msg: str = record.getMessage()

        # record.context is expected to be dict[str, object] | None
        ctx = cast("dict[str, object] | None", getattr(record, "context", None))
        ctx_str = f" | context: {ctx}" if ctx is not None else ""

        base = f"{iso_time} | {level:<8} | {name:<30} | {msg}{ctx_str}"

        if record.exc_info:
            try:
                exc_text = self.formatException(record.exc_info)
                return f"{base}\n{exc_text}"
            except Exception:
                return base
        return base

class ContextLogger(logging.Logger):

    _log_ctx: dict[str, object] | None  # <-- explicitly declare type

    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        super().__init__(name, level)
        self._log_ctx = None  # initialize it

    @contextmanager
    def context(self, **kwargs: object) -> Iterator[None]:
        """
        Temporarily attach key/value context to all log records emitted within the block.
        Usage:
            with logger.context(user="alice", job_id="42"):
                logger.info("starting")
        """
        old_ctx = self._log_ctx
        self._log_ctx = kwargs 
        try:
            yield
        finally:
            self._log_ctx = old_ctx

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


def get_logger(name: str, level: int = logging.INFO) -> ContextLogger:
    logging.setLoggerClass(ContextLogger)
    logger = cast(ContextLogger, logging.getLogger(name))  # getLogger returns Logger, so cast
    effective_level = _level_from_env(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(MinimalFormatter())
        handler.setLevel(effective_level)
        logger.addHandler(handler)
        logger.setLevel(effective_level)
        logger.propagate = False
    else:
        logger.setLevel(effective_level)
        for h in logger.handlers:
            h.setLevel(effective_level)
    return logger

def truncate_str(s: str, max_len:int = 100) -> str:
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

def log_execution(logger: logging.Logger) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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
