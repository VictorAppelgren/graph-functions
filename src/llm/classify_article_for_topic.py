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

2. importance_risk (0-3): How important is this article for understanding RISKS to this topic?
   - 0 = No real risk information for THIS topic
   - 1 = Minor / background risk information (filler tier)
   - 2 = Clear, meaningful risk signal (standard tier)
   - 3 = Critical risk information that could significantly impact this topic (premium tier)

3. importance_opportunity (0-3): How important is this article for understanding OPPORTUNITIES for this topic?
   - 0 = No real opportunity information for THIS topic
   - 1 = Minor / background opportunity information
   - 2 = Clear, meaningful opportunity signal
   - 3 = Major opportunity that could significantly benefit this topic

4. importance_trend (0-3): How important is this article for understanding TRENDS affecting this topic?
   - 0 = No real trend information for THIS topic
   - 1 = Weak / background trend information
   - 2 = Solid, meaningful trend signal
   - 3 = Critical trend that shapes the topic's trajectory

5. importance_catalyst (0-3): How important is this article as a CATALYST for this topic?
   - 0 = No catalyst potential for THIS topic
   - 1 = Weak / background catalyst
   - 2 = Clear, meaningful potential catalyst
   - 3 = Major catalyst that could trigger significant movement for this topic

6. motivation (1-2 sentences): WHY does this article matter for THIS specific topic?
   - Be SPECIFIC to the topic, not generic
   - Focus on the DIRECT connection to this topic
   - Explain the relevance clearly

7. implications (1-2 sentences): What could this MEAN for THIS topic going forward?
   - Think FORWARD-LOOKING and PREDICTIVE
   - What COULD happen next for this topic?
   - Be CONCRETE about potential outcomes
   - Connect to market impact, price action, or strategic positioning

CRITICAL RULES ABOUT IMPORTANCE SCORES (MUST FOLLOW):

- ALL importance_* fields MUST be integers in the CLOSED range 0–3.
- MAX IMPORTANCE VALUE IS 3. YOU MUST NEVER OUTPUT 4, 5, 6, 7, 8, 9, OR 10.
- Do NOT use any scale other than 0–3. This is NOT a 0–10 scale.
- If you instinctively think "this is like 7/10 importance", you MUST map it into this 0–3 system:
  - 0 = no meaningful information
  - 1 = weak / background (filler)
  - 2 = standard, solid importance
  - 3 = premium / critical importance, top-tier signal
- If you output ANY importance_* above 3, the downstream capacity manager WILL BREAK.
  You MUST strictly stay in 0–3.

ADDITIONAL RULES:

- At least ONE importance score should be > 0 (otherwise why is it linked?).
- motivation: Explain WHY relevant to THIS SPECIFIC TOPIC (not generic statements).
- implications: Think AHEAD - what could happen NEXT for THIS TOPIC?
- Be CONCRETE and SPECIFIC, avoid vague language.
- Keep motivation and implications to 1-2 sentences each.

GOOD EXAMPLE (valid 0–3 tiers, specific, forward-looking):
{{
    "timeframe": "current",
    "importance_risk": 3,
    "importance_opportunity": 1,
    "importance_trend": 2,
    "importance_catalyst": 3,
    "motivation": "Powell's unexpectedly hawkish tone implies rates may stay higher for longer, directly raising downside risk for US equities.",
    "implications": "Could trigger a short-term 5–8% SPX correction as valuations reprice; growth stocks are most exposed if this hawkish stance persists."
}}

BAD EXAMPLE (INVALID – NEVER DO THIS):
{{
    "timeframe": "current",
    "importance_risk": 8,
    "importance_opportunity": 5,
    "importance_trend": 7,
    "importance_catalyst": 9,
    "motivation": "This article discusses Federal Reserve policy and interest rate decisions.",
    "implications": "The Fed might change interest rates in the future, which could affect markets."
}}

- The BAD EXAMPLE is INVALID because importance_* values above 3 are STRICTLY FORBIDDEN.
- DO NOT copy those numbers. ALWAYS keep importance_* in 0–3.

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
    
    # Get LLM - article classification uses SIMPLE tier (20B)
    llm = get_llm(ModelTier.SIMPLE)
    
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
