"""
Critic Models - Mid-exploration feedback (50% progress)
"""
from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class CriticFeedback:
    """
    Feedback from mid-exploration critic.

    Agent is at 50% progress and has drafted a finding.
    Critic reviews it and provides actionable guidance.
    """

    # What the critic found
    citation_issues: List[str]           # e.g., "Claim about Fed has no citation"
    chain_gaps: List[str]                # e.g., "No evidence for: inflation → fed_policy"
    quality_score: float                 # 0.0-1.0 overall quality

    # What the agent should do
    suggestions: List[str]               # Actionable next steps
    verdict: Literal["continue_exploring", "revise_draft", "ready_to_finish"]

    # Explanation
    reasoning: str

    def __post_init__(self):
        """Ensure quality_score is in range."""
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(f"quality_score must be 0-1, got {self.quality_score}")
