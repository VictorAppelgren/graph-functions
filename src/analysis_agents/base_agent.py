"""
Base Agent - Abstract interface for all analysis agents.

Each agent:
1. Explores graph (via graph_strategy)
2. Formats data for LLM
3. Calls LLM with specialized prompt
4. Returns structured output

Philosophy: SIMPLEST POSSIBLE - no over-engineering.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel
from utils import app_logging


class BaseAgent(ABC):
    """
    Abstract base class for all analysis agents.
    
    Each agent must implement:
    - run(): Main execution method
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = app_logging.get_logger(f"src.analysis_agents.{agent_name}")
    
    @abstractmethod
    def run(self, topic_id: str, section: str, **kwargs) -> BaseModel:
        """
        Run the agent.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (fundamental/medium/current)
            **kwargs: Additional context
        
        Returns:
            Pydantic model with agent's output
        """
        pass
    
    def _log(self, message: str):
        """Simple logging helper"""
        self.logger.info(message)
