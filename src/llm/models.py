"""
Pydantic models for LLM outputs - type-safe classification results
"""
from pydantic import BaseModel, Field
from typing import Literal, List

class ArticleTopicClassification(BaseModel):
    """
    Classification of an article FOR A SPECIFIC TOPIC.
    
    This is used to create rich ABOUT relationships with context-aware
    motivation and forward-looking implications.
    """
    
    timeframe: Literal["fundamental", "medium", "current"] = Field(
        description="Time horizon of this article's relevance to THIS specific topic"
    )
    
    importance_risk: int = Field(
        ge=0, le=10,
        description="How important is this article for understanding RISK to this topic (0-10)"
    )
    
    importance_opportunity: int = Field(
        ge=0, le=10,
        description="How important is this article for understanding OPPORTUNITY for this topic (0-10)"
    )
    
    importance_trend: int = Field(
        ge=0, le=10,
        description="How important is this article for understanding TRENDS affecting this topic (0-10)"
    )
    
    importance_catalyst: int = Field(
        ge=0, le=10,
        description="How important is this article as a CATALYST for this topic (0-10)"
    )
    
    motivation: str = Field(
        description=(
            "In 1-2 sentences: WHY does this article matter for THIS specific topic? "
            "Be specific, not generic. Focus on the connection to THIS topic."
        )
    )
    
    implications: str = Field(
        description=(
            "In 1-2 sentences: What could this MEAN for THIS topic going forward? "
            "Think predictively and forward-looking. What COULD happen next?"
        )
    )
    
    @property
    def overall_importance(self) -> int:
        """Calculate overall importance as max of all perspective scores."""
        return max(
            self.importance_risk,
            self.importance_opportunity,
            self.importance_trend,
            self.importance_catalyst
        )
