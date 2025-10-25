"""
Classify an article FOR A SPECIFIC TOPIC.

This is called once per article-topic relationship to generate
context-aware, forward-looking motivation and implications.
"""

from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION
from src.llm.sanitizer import run_llm_decision
from src.llm.models import ArticleTopicClassification
from utils.app_logging import get_logger

logger = get_logger("llm.classify_article_for_topic")


# God-tier prompt for context-aware classification
CLASSIFY_ARTICLE_FOR_TOPIC_PROMPT = """
{system_mission}

You are analyzing how a financial article relates to a SPECIFIC topic/asset.

TOPIC CONTEXT:
Topic ID: {topic_id}
Topic Name: {topic_name}

Recent Analysis Context:
{topic_analysis_snippet}

ARTICLE TO CLASSIFY:
{article_summary}

TASK:
Classify this article FOR THIS SPECIFIC TOPIC ONLY.

Provide a JSON object with:

1. timeframe: Choose ONE:
   - "fundamental": Long-term structural changes (months to years)
   - "medium": Medium-term developments (weeks to months)
   - "current": Immediate/short-term events (days to weeks)

2. importance_risk (0-10): How important is this article for understanding RISKS to this topic?
   - 0 = No risk information
   - 10 = Critical risk information that could significantly impact the topic

3. importance_opportunity (0-10): How important is this article for understanding OPPORTUNITIES for this topic?
   - 0 = No opportunity information
   - 10 = Major opportunity that could significantly benefit the topic

4. importance_trend (0-10): How important is this article for understanding TRENDS affecting this topic?
   - 0 = No trend information
   - 10 = Reveals critical trend that shapes the topic's trajectory

5. importance_catalyst (0-10): How important is this article as a CATALYST for this topic?
   - 0 = No catalyst potential
   - 10 = Major catalyst that could trigger significant movement

6. motivation (1-2 sentences): WHY does this article matter for THIS specific topic?
   - Be SPECIFIC to the topic, not generic
   - Focus on the DIRECT connection to this topic
   - Explain the relevance clearly

7. implications (1-2 sentences): What could this MEAN for THIS topic going forward?
   - Think FORWARD-LOOKING and PREDICTIVE
   - What COULD happen next for this topic?
   - Be CONCRETE about potential outcomes
   - Connect to market impact, price action, or strategic positioning

CRITICAL RULES:
✓ motivation: Explain WHY relevant to THIS SPECIFIC TOPIC (not generic statements)
✓ implications: Think AHEAD - what could happen NEXT for THIS TOPIC?
✓ Be CONCRETE and SPECIFIC, avoid vague language
✓ Keep motivation and implications to 1-2 sentences each
✓ At least ONE importance score should be > 0 (otherwise why is it linked?)

GOOD EXAMPLE (specific, forward-looking):
{{
    "timeframe": "current",
    "importance_risk": 8,
    "importance_opportunity": 2,
    "importance_trend": 5,
    "importance_catalyst": 9,
    "motivation": "Powell's unexpectedly hawkish tone signals Fed may hold rates at 5.5% through Q3 2025, contradicting market pricing of cuts starting Q2.",
    "implications": "Could trigger 5-8% equity correction as markets reprice rate expectations, with growth stocks most vulnerable. SPX likely tests 4800 support if Fed maintains hawkish stance at next meeting."
}}

BAD EXAMPLE (generic, backward-looking):
{{
    "timeframe": "current",
    "importance_risk": 7,
    "importance_opportunity": 3,
    "importance_trend": 5,
    "importance_catalyst": 6,
    "motivation": "This article discusses Federal Reserve policy and interest rate decisions.",
    "implications": "The Fed might change interest rates in the future, which could affect markets."
}}

Output valid JSON only. No additional text.
"""


def classify_article_for_topic(
    article_summary: str,
    topic_id: str,
    topic_name: str,
    topic_analysis_snippet: str
) -> ArticleTopicClassification:
    """
    Classify an article FOR A SPECIFIC TOPIC.
    
    This is called ONCE PER TOPIC the article links to.
    Provides rich context so LLM can generate high-quality
    motivation and implications specific to this topic.
    
    Args:
        article_summary: The article summary text
        topic_id: Topic ID (e.g., "fed_policy")
        topic_name: Human-readable topic name (e.g., "Federal Reserve Policy")
        topic_analysis_snippet: Recent analysis excerpt for context (helps LLM be specific)
    
    Returns:
        ArticleTopicClassification with timeframe, importance scores, motivation, implications
    
    Example:
        >>> classification = classify_article_for_topic(
        ...     article_summary="Fed Chair Powell signals rates to stay higher for longer...",
        ...     topic_id="spx",
        ...     topic_name="S&P 500 Index",
        ...     topic_analysis_snippet="Recent analysis shows SPX trading near resistance..."
        ... )
        >>> print(classification.motivation)
        "Powell's hawkish tone signals Fed may hold rates higher..."
    """
    
    logger.info(f"Classifying article for topic: {topic_id} ({topic_name})")
    
    # Get LLM (use COMPLEX tier - needs large context for article + topic analysis)
    llm = get_llm(ModelTier.COMPLEX)
    
    # Format prompt
    prompt = PromptTemplate.from_template(CLASSIFY_ARTICLE_FOR_TOPIC_PROMPT).format(
        system_mission=SYSTEM_MISSION,
        article_summary=article_summary,
        topic_id=topic_id,
        topic_name=topic_name,
        topic_analysis_snippet=topic_analysis_snippet
    )
    
    # Get classification from LLM
    classification: ArticleTopicClassification = run_llm_decision(
        chain=llm,
        prompt=prompt,
        model=ArticleTopicClassification
    )
    
    logger.info(
        f"Classification complete: timeframe={classification.timeframe}, "
        f"importance=(R:{classification.importance_risk} O:{classification.importance_opportunity} "
        f"T:{classification.importance_trend} C:{classification.importance_catalyst})"
    )
    
    return classification
