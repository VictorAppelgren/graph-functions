"""
Exploration Agent - Autonomous Graph Explorer for Unseen Risks & Opportunities

This agent explores the knowledge graph iteratively, following connections
between topics to discover multi-hop risks and opportunities that would be
invisible to traditional analysis.

Usage:
    python -m src.exploration_agent.orchestrator eurusd risk
    python -m src.exploration_agent.orchestrator eurusd opportunity
    python -m src.exploration_agent.orchestrator --strategy strategy_id risk
"""

from src.exploration_agent.models import ExplorationResult, ExplorationMode
from src.exploration_agent.explorer.agent import ExplorationAgent
from src.exploration_agent.critic.agent import CriticAgent
from src.exploration_agent.critic.models import CriticVerdict

__all__ = [
    "ExplorationAgent", 
    "ExplorationResult", 
    "ExplorationMode",
    "CriticAgent",
    "CriticVerdict",
]
