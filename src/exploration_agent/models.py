"""
Exploration Agent - Pydantic Models

Defines the data structures for exploration state, tool calls, and results.

Key concepts:
- TEMPORARY content: Articles/sections loaded via read tools. Auto-deleted on next non-save action.
- SAVED excerpts: Permanently saved evidence. Survives topic moves and builds the finding.
- Each article/section gets its own message with unique ID for selective deletion.
"""

from typing import List, Optional, Literal, Set
from pydantic import BaseModel, Field
from enum import Enum


class ExplorationMode(str, Enum):
    """What the agent is hunting for"""
    RISK = "risk"
    OPPORTUNITY = "opportunity"


# =============================================================================
# SAVED EVIDENCE MODEL
# =============================================================================

class SavedExcerpt(BaseModel):
    """A permanently saved piece of evidence from exploration"""
    excerpt: str  # The actual text/fact saved
    source_id: str  # "art_ABC123" or "sec_eurusd_executive_summary"
    source_type: Literal["article", "section"]
    why_relevant: str  # How this connects to the chain
    saved_at_topic: str  # Which topic the agent was on when saving
    saved_at_step: int  # Which step it was saved


# =============================================================================
# TOOL CALL MODELS (what the LLM outputs)
# =============================================================================

class ReadSectionCall(BaseModel):
    """Read a specific analysis section from the current topic"""
    tool: Literal["read_section"] = "read_section"
    section: str = Field(..., description="Section name to read (e.g., 'executive_summary', 'chain_reaction_map')")


class ReadArticlesCall(BaseModel):
    """Read articles from the current topic"""
    tool: Literal["read_articles"] = "read_articles"
    limit: int = Field(3, description="Max articles to return (1-5)")


class MoveToTopicCall(BaseModel):
    """Move to a connected topic to explore further"""
    tool: Literal["move_to_topic"] = "move_to_topic"
    topic_id: str = Field(..., description="ID of the connected topic to move to")
    reason: str = Field(..., description="Why this topic is interesting for our exploration")


class SaveExcerptCall(BaseModel):
    """Save specific excerpt(s) from temporary content to permanent memory"""
    tool: Literal["save_excerpt"] = "save_excerpt"
    saves: List[dict] = Field(..., description="List of {source_id, excerpt, why_relevant} to save")


class DraftFindingCall(BaseModel):
    """Draft a finding (risk or opportunity) based on exploration so far"""
    tool: Literal["draft_finding"] = "draft_finding"
    headline: str = Field(..., description="Short headline like 'China Stimulus → Copper → Fed Inflation Risk'")
    rationale: str = Field(..., description="2-3 sentences explaining WHY this matters")
    flow_path: str = Field(..., description="The logical chain, e.g., 'china_stimulus → copper_demand → inflation_pressure → fed_policy → eurusd'")


class FinishCall(BaseModel):
    """Finish exploration - agent is satisfied with the finding"""
    tool: Literal["finish"] = "finish"


class ThinkCall(BaseModel):
    """Explicitly reason without taking action - stays in conversation history"""
    tool: Literal["think"] = "think"
    thought: str = Field(..., description="Your reasoning about current state, what you've learned, and next steps")


class SuggestLinkCall(BaseModel):
    """Suggest a new link between topics (for future implementation)"""
    tool: Literal["suggest_link"] = "suggest_link"
    source_topic: str
    target_topic: str
    relationship_type: Literal["INFLUENCES", "CORRELATES_WITH", "PEERS", "COMPONENT_OF", "HEDGES"]
    reason: str


# Union of all tool calls
ToolCall = ReadSectionCall | ReadArticlesCall | MoveToTopicCall | SaveExcerptCall | DraftFindingCall | FinishCall | ThinkCall | SuggestLinkCall


class AgentResponse(BaseModel):
    """What the LLM returns each step"""
    thinking: str = Field(..., description="Brief reasoning about what to do next")
    tool_call: ToolCall = Field(..., description="The tool to execute")


# =============================================================================
# STATE MODELS
# =============================================================================

class TopicSnapshot(BaseModel):
    """Current state of a topic for the agent"""
    id: str
    name: str
    executive_summary: Optional[str] = None
    connected_topics: List[dict] = Field(default_factory=list)  # [{id, name, relationship_type}]


class MessageEntry(BaseModel):
    """A single message in the conversation history"""
    role: Literal["system", "user", "assistant"] 
    content: str
    msg_id: Optional[str] = None  # For pruning: "article_ABC123", "section_chain_reaction_map"
    prunable: bool = False  # If True, can be removed after processing


class ExplorationState(BaseModel):
    """Full state of an exploration session"""
    target_topic_id: str  # Original topic we're exploring FOR
    target_strategy_id: Optional[str] = None  # If exploring for a strategy
    mode: ExplorationMode
    current_topic: TopicSnapshot
    visited_topics: List[str] = Field(default_factory=list)
    
    # PERMANENT: Saved excerpts survive the whole exploration
    saved_excerpts: List[SavedExcerpt] = Field(default_factory=list)
    
    # TEMPORARY: IDs of content loaded this step (will be deleted on non-save action)
    temp_content_ids: List[str] = Field(default_factory=list)  # ["art_ABC", "art_DEF"] or ["sec_topic_section"]
    
    # Conversation history
    messages: List[MessageEntry] = Field(default_factory=list)
    
    draft_finding: Optional[dict] = None  # {headline, rationale, flow_path}
    critic_feedback_received: bool = False  # Track if critic has run (run once per exploration)
    step_count: int = 0
    max_steps: int = 20


# =============================================================================
# RESULT MODEL
# =============================================================================

class ExplorationResult(BaseModel):
    """Final output of an exploration session"""
    headline: str = Field(..., description="Short headline like 'China Stimulus → Copper → Fed Inflation Risk'")
    rationale: str = Field(..., description="2-3 sentences explaining WHY this matters")
    flow_path: str = Field(..., description="The logical chain as a formatted string")
    evidence: List[SavedExcerpt] = Field(default_factory=list, description="Saved excerpts with citations")
    target_topic_id: str = Field(..., description="Original topic this finding is FOR")
    target_strategy_id: Optional[str] = Field(None, description="Strategy ID if exploring for a strategy")
    mode: ExplorationMode = Field(..., description="Whether this is a risk or opportunity")
    exploration_steps: int = Field(..., description="How many iterations it took")
    success: bool = Field(True, description="Whether exploration completed successfully")
    error: Optional[str] = Field(None, description="Error message if failed")
