"""
Final Critic Models - End-of-exploration validation
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.exploration_agent.models import ExplorationResult


@dataclass
class FinalCriticInput:
    """Everything the final critic needs."""

    # The finding to evaluate
    finding: ExplorationResult

    # ALL source material:
    articles: Dict[str, str]              # source_id → full article text
    topic_analyses: Dict[str, dict]       # topic_id → {section_name: content}

    # Context for ranking:
    existing_items: List[dict]            # Current risks/opportunities (0-3)
    mode: str                             # "risk" or "opportunity"
    target_topic: str                     # e.g., "eurusd"


@dataclass
class FinalVerdict:
    """
    Binary accept/reject decision from final critic.

    All validation checks are internal to the accept decision:
    - Citation completeness and accuracy (LLM checks)
    - Chain validity (LLM checks)
    - Evidence quality (LLM checks)
    - Novelty (not duplicate of existing)
    - Importance (beats weakest if 3 exist)
    """

    accepted: bool                        # Pass/fail
    confidence: float                     # 0.0-1.0
    reasoning: str                        # Explanation

    # Ranking (only if accepted)
    replaces: Optional[int] = None        # None=add new, 1/2/3=replace that slot

    # Rejection details (only if not accepted)
    rejection_reasons: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.accepted and not self.rejection_reasons:
            self.rejection_reasons = ["No specific reason provided"]
        if self.accepted:
            self.rejection_reasons = []
