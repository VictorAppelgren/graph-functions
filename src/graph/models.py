"""
Type definitions for Neo4j query results and graph entities.
Provides strong typing for better code clarity and IDE support.
"""
from typing import TypedDict, Any, Optional, Union, List

# Basic Neo4j record type
Neo4jRecord = dict[str, Any]

# Common graph entity types
class TopicNode(TypedDict, total=False):
    """Neo4j Topic node properties"""
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

class ArticleNode(TypedDict, total=False):
    """Neo4j Article node properties"""
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

class Relationship(TypedDict, total=False):
    """Neo4j relationship properties"""
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

class TopicWithArticleCount(TopicNode, total=False):
    """Topic node with article count"""
    article_count: int

class ArticleWithTopics(ArticleNode, total=False):
    """Article node with related topics"""
    topics: List[str]

# Union types for polymorphic returns
GraphNode = Union[TopicNode, ArticleNode]
QueryResult = Union[Neo4jRecord, CountResult, IdResult, NodeExistsResult, TopicNode, ArticleNode]