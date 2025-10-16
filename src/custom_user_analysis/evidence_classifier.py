"""
Evidence Classifier for Custom User Analysis

Classifies analysis sections as supporting or contradicting user's thesis.
"""

from typing import List, Dict, Tuple
from pydantic import BaseModel
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.sanitizer import run_llm_decision
from src.observability.pipeline_logging import master_log


class EvidenceClassification(BaseModel):
    """LLM output for evidence classification."""
    classification: str  # "supporting", "contradicting", "neutral"
    confidence: float
    reasoning: str
    key_insight: str


def classify_evidence(
    material: Dict,
    asset_name: str,
    strategy_text: str,
    target: str
) -> Tuple[List[Dict], List[Dict]]:
    """
    Classify collected material as supporting or contradicting user's thesis.
    
    Returns:
        (supporting_evidence, contradicting_evidence)
    """
    master_log(f"Evidence classification started | asset={asset_name}")
    
    supporting = []
    contradicting = []
    
    # Classify each piece of analysis
    for category_name, category_data in material.items():
        for topic_id, topic_data in category_data.items():
            topic_name = topic_data.get("name", topic_id)
            
            for section_key, section_content in topic_data.items():
                if section_key == "name" or not section_content:
                    continue
                
                # Truncate for classification (first 800 chars)
                content_preview = section_content[:800]
                
                classification = _classify_section(
                    asset_name=asset_name,
                    strategy_text=strategy_text,
                    target=target,
                    topic_name=topic_name,
                    section_name=section_key,
                    content=content_preview
                )
                
                if classification.classification == "supporting" and classification.confidence > 0.6:
                    supporting.append({
                        "topic": topic_name,
                        "section": section_key.replace("_", " ").title(),
                        "insight": classification.key_insight,
                        "confidence": classification.confidence
                    })
                elif classification.classification == "contradicting" and classification.confidence > 0.6:
                    contradicting.append({
                        "topic": topic_name,
                        "section": section_key.replace("_", " ").title(),
                        "insight": classification.key_insight,
                        "confidence": classification.confidence
                    })
    
    # Sort by confidence
    supporting.sort(key=lambda x: x["confidence"], reverse=True)
    contradicting.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Limit to top items
    supporting = supporting[:10]
    contradicting = contradicting[:10]
    
    master_log(f"Evidence classified | supporting={len(supporting)} contradicting={len(contradicting)}")
    
    return supporting, contradicting


def _classify_section(
    asset_name: str,
    strategy_text: str,
    target: str,
    topic_name: str,
    section_name: str,
    content: str
) -> EvidenceClassification:
    """Classify a single analysis section."""
    
    prompt = f"""You are an expert financial analyst evaluating evidence relative to a user's trading thesis.

USER THESIS:
Asset: {asset_name}
Strategy: {strategy_text}
Target: {target}

ANALYSIS EXCERPT:
Topic: {topic_name}
Section: {section_name}
Content:
{content}

TASK: Classify this analysis relative to the user's thesis.

CLASSIFICATION CRITERIA:
• "supporting" - Evidence aligns with and supports the user's directional view
• "contradicting" - Evidence challenges or opposes the user's thesis
• "neutral" - Not directly relevant or mixed signals

OUTPUT JSON:
{{
  "classification": "supporting" | "contradicting" | "neutral",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of classification",
  "key_insight": "Most relevant insight for user (1 sentence, max 120 chars)"
}}"""

    llm = get_llm(ModelTier.FAST)
    
    result = run_llm_decision(
        llm,
        prompt,
        EvidenceClassification
    )
    
    return result
