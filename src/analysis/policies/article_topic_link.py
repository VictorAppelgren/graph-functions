import json
from typing import Any, TypedDict, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from pydantic import BaseModel
from __future__ import annotations

logger = get_logger(__name__)

# --- input typing (minimal) ---------------------------------------------------

class ArticleModel(TypedDict, total=False):
    title: str
    argos_summary: str

# --- output schema ------------------------------------------------------------

class RelevanceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    should_link: bool
    motivation: str = Field(min_length=1, max_length=600)

# --- small sanitizers ---------------------------------------------------------

def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")

def _sanitize_relevance(raw: Any) -> RelevanceDecision:
    data = _coerce_json_object(raw)
    dec = RelevanceDecision.model_validate(data)
    # normalize motivation (collapse whitespace / cap length)
    dec.motivation = " ".join(dec.motivation.split())[:600]
    return dec

# --- main ---------------------------------------------------------------------

def validate_article_topic_relevance(
    article: ArticleModel,
    topic_name: str,
    topic_id: str,
) -> tuple[bool, str]:
    """Deep LLM validation: does this article truly provide value to this topic?"""
    summary = article.get("argos_summary", "")
    title = article.get("title", "")

    logger.info(
        "Validating relevance: article '%s...' to topic '%s' (%s)",
        title[:50],
        topic_name,
        topic_id,
    )

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS FINANCIAL ANALYST validating if an article provides genuine value to a specific investment topic in the Saga Graph.

        TASK:
        - Output ONLY a single JSON object with EXACTLY two fields:
            - 'should_link': true/false (create the graph connection?)
            - 'motivation': Short reasoning (1–2 sentences) defending your decision

        ARTICLE TITLE: {title}
        ARTICLE SUMMARY: {summary}
        TARGET TOPIC: {topic_name} (ID: {topic_id})

        EXAMPLES:
        {{"should_link": true, "motivation": "Article provides specific inflation data and Fed policy implications directly relevant to US monetary policy analysis."}}
        {{"should_link": false, "motivation": "Mentions topic briefly but lacks analytical depth or actionable investment insights."}}

        STRICT JSON ONLY. NO EXTRA TEXT.
        YOUR RESPONSE:
    """

    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain: Runnable[dict[str, str], Any] = prompt | llm | parser

    raw = chain.invoke({
        "title": title,
        "summary": summary,
        "topic_name": topic_name,
        "topic_id": topic_id,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    try:
        decision = _sanitize_relevance(raw)
    except (ValidationError, TypeError, json.JSONDecodeError) as e:
        logger.error("Relevance parsing/validation failed: %s", str(e)[:200])
        # choose policy: fail-fast or safe fallback. Here’s a safe fallback:
        return (False, "Unable to validate confidently; not linking.")

    logger.info(
        "Validation result: link=%s, motivation=%s%s",
        decision.should_link,
        decision.motivation[:200],
        "..." if len(decision.motivation) > 200 else "",
    )
    return decision.should_link, decision.motivation


# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    article = {
        "title": "Fed Raises Interest Rates by 0.75% to Combat Inflation",
        "argos_summary": "The Federal Reserve raised interest rates by 75 basis points to 3.25%, the largest increase since 1994, as inflation remains near 40-year highs."
    }

    a = ArticleModel(
        title="Fed Raises Interest Rates by 0.75% to Combat Inflation", 
        summary="The Federal Reserve raised interest rates by 75 basis points to 3.25%, the largest increase since 1994, as inflation remains near 40-year highs."
        )
    
    should_link, motivation = validate_article_topic_relevance(
        a, "US Interest Rates", "us_interest_rates"
    )
    print(f"Should Link: {should_link}")
    print(f"Motivation: {motivation}")
