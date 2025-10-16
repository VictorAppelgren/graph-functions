"""
Type-safe models for custom user analysis.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class DiscoveredTopics:
    """Topics discovered for user strategy analysis."""
    primary: List[str]  # Direct assets user is trading
    drivers: List[str]  # Macro/policy drivers
    correlated: List[str]  # Related assets
    reasoning: str  # LLM explanation of selection


@dataclass
class EvidenceItem:
    """Single piece of evidence supporting or contradicting thesis."""
    topic: str
    section: str
    insight: str
    confidence: float


@dataclass
class AnalysisResults:
    """Generated analysis sections."""
    fundamental: str
    current: str
    risks: str
    drivers: str
    supporting_evidence: List[EvidenceItem]
    contradicting_evidence: List[EvidenceItem]
    related_topics: List[str]
