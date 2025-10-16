"""
Type definitions for Neo4j query results and graph entities.
Provides strong typing for better code clarity and IDE support.
"""

from typing import TypedDict, Any, Optional, Union, List

# Basic Neo4j record type
Neo4jRecord = dict[str, Any]


# Common graph entity types
class Topic(TypedDict, total=False):
    """Neo4j Topic properties"""

    id: str  # required
    name: str  # required
    type: str  # e.g. "asset", "policy"
    level: str  # "main" | "driver"
    parent_id: Optional[str]
    status: str  # "active" | "hidden"
    last_updated: str  # ISO timestamp
    # Analysis fields
    fundamental_analysis: Optional[str]
    medium_analysis: Optional[str]
    current_analysis: Optional[str]
    implications: Optional[str]
    # Perspective-focused analysis fields
    risk_analysis: Optional[str]
    opportunity_analysis: Optional[str]
    trend_analysis: Optional[str]
    catalyst_analysis: Optional[str]


class Article(TypedDict, total=False):
    """Neo4j Article properties"""

    id: str  # required
    title: str  # required
    summary: Optional[str]
    source: str
    published_at: str  # ISO timestamp
    vector_id: Optional[str]
    type: Optional[str]
    temporal_horizon: Optional[str]  # "fundamental" | "medium" | "current"
    priority: Optional[str]  # "3" | "2" | "1" | "hidden"
    relevance_score: Optional[float]
    status: str  # "active" | "hidden"
    
    # Perspective importance scores (0-3, independent - can all be 3!)
    importance_risk: Optional[int]
    importance_opportunity: Optional[int]
    importance_trend: Optional[int]
    importance_catalyst: Optional[int]


class Link(TypedDict, total=False):
    """Neo4j link properties"""

    type: str  # "INFLUENCES" | "CORRELATES_WITH" | "PEERS" | "ABOUT"
    strength: Optional[float]
    evidence: Optional[str]
    created_at: str  # ISO timestamp


# Query result types for common patterns
class CountResult(TypedDict):
    """Result from COUNT queries"""

    count: int


class IdResult(TypedDict):
    """Result from queries returning just IDs"""

    id: str


class NodeExistsResult(TypedDict):
    """Result from node existence checks"""

    exists: bool


class TopicWithArticleCount(Topic, total=False):
    """Topic with article count"""

    article_count: int


class ArticleWithTopics(Article, total=False):
    """Article with related topics"""

    topics: List[str]


# Union types for polymorphic returns
GraphNode = Union[Topic, Article]
QueryResult = Union[
    Neo4jRecord, CountResult, IdResult, NodeExistsResult, Topic, Article
]
