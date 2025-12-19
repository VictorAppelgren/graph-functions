"""
Critic Models - Simplified input/output for the critic agent.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.exploration_agent.models import ExplorationResult


@dataclass
class CriticInput:
    """Everything the critic needs to evaluate a finding."""
    
    # The finding to evaluate
    finding: ExplorationResult
    
    # ALL source material the explorer had access to:
    articles: Dict[str, str]              # source_id → full article text
    topic_analyses: Dict[str, dict]       # topic_id → {section_name: content}
    
    # Context for ranking decision:
    existing_items: List[dict]            # Current risks/opportunities (0-3)
    mode: str                             # "risk" or "opportunity"
    target_topic: str                     # e.g., "eurusd"


@dataclass
class CriticVerdict:
    """
    Simplified critic output - binary accept/reject with reasoning.
    
    All verification checks are internal to the accept decision:
    - Citation verification (every claim has source)
    - Source accuracy (citations actually support claims)
    - Chain validity (logical flow between hops)
    - Novelty (not duplicate of existing)
    - Importance (beats weakest existing if 3 already exist)
    """
    
    accepted: bool                        # Pass/fail - all checks must pass
    confidence: float                     # 0.0-1.0 strength of evidence
    reasoning: str                        # Explanation of decision
    
    # Ranking decision (only relevant if accepted AND existing_items present)
    replaces: Optional[int] = None        # None=add new, 1/2/3=replace that slot
    
    # Rejection details (only if not accepted)
    rejection_reasons: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.accepted and not self.rejection_reasons:
            self.rejection_reasons = ["No specific reason provided"]
        if self.accepted:
            self.rejection_reasons = []
