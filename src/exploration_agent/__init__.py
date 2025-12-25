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
from src.exploration_agent.critic.models import CriticFeedback
from src.exploration_agent.final_critic.agent import FinalCriticAgent
from src.exploration_agent.final_critic.models import FinalVerdict

__all__ = [
    "ExplorationAgent",
    "ExplorationResult",
    "ExplorationMode",
    "CriticAgent",
    "CriticFeedback",
    "FinalCriticAgent",
    "FinalVerdict",
]
