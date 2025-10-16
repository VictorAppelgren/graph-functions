"""
Pydantic models for LLM outputs - type-safe classification results
"""
from pydantic import BaseModel, Field
from typing import Literal, List


class ArticleClassification(BaseModel):
    """Complete article classification from unified LLM call"""
    
    motivation: str = Field(..., description="Classification reasoning")
    
    temporal_horizon: Literal["fundamental", "medium", "current", "invalid"]
    category: str
    
    # Per-perspective importance (0-3, INDEPENDENT scoring - can all be 3!)
    importance_risk: int = Field(..., ge=0, le=3)
    importance_opportunity: int = Field(..., ge=0, le=3)
    importance_trend: int = Field(..., ge=0, le=3)
    importance_catalyst: int = Field(..., ge=0, le=3)
    
    @property
    def primary_perspectives(self) -> List[str]:
        """All perspectives with score ≥2 (NO LIMIT - can be all 4!)"""
        perspectives = []
        if self.importance_risk >= 2:
            perspectives.append("risk")
        if self.importance_opportunity >= 2:
            perspectives.append("opportunity")
        if self.importance_trend >= 2:
            perspectives.append("trend")
        if self.importance_catalyst >= 2:
            perspectives.append("catalyst")
        return perspectives
    
    @property
    def dominant_perspective(self) -> str:
        """Highest scoring perspective (for primary tagging)"""
        scores = {
            "risk": self.importance_risk,
            "opportunity": self.importance_opportunity,
            "trend": self.importance_trend,
            "catalyst": self.importance_catalyst
        }
        max_score = max(scores.values())
        return max(scores, key=scores.get) if max_score > 0 else "info"
    
    @property
    def overall_importance(self) -> int:
        """Max score across all perspectives"""
        return max(
            self.importance_risk,
            self.importance_opportunity,
            self.importance_trend,
            self.importance_catalyst
        )
