"""
Base Agent for Strategy Analysis

Provides common functionality for all strategy agents.
"""

from typing import Any
from utils import app_logging

logger = app_logging.get_logger(__name__)


class BaseStrategyAgent:
    """Base class for all strategy agents."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = app_logging.get_logger(f"strategy_agents.{agent_name}")
    
    def _log(self, message: str, level: str = "info"):
        """Log message with agent context."""
        if level == "info":
            self.logger.info(f"[{self.agent_name}] {message}")
        elif level == "warning":
            self.logger.warning(f"[{self.agent_name}] {message}")
        elif level == "error":
            self.logger.error(f"[{self.agent_name}] {message}")
        elif level == "debug":
            self.logger.debug(f"[{self.agent_name}] {message}")
    
    def run(self, *args, **kwargs) -> Any:
        """
        Main execution method - must be implemented by subclasses.
        """
        raise NotImplementedError(f"{self.agent_name} must implement run() method")
