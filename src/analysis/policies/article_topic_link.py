import json
from typing import Any, TypedDict, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.runnables import Runnable
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from src.llm.prompts.validate_article_topic_relevance import validate_article_topic_relevance_prompt
from src.llm.sanitizer import run_llm_decision, ValidateRelevance

logger = get_logger("analysis.article_topic_link")

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
) -> tuple[bool, str] | None:
    """Deep LLM validation: does this article truly provide value to this topic?"""
    summary = article.get("argos_summary", "")
    title = article.get("title", "")

    logger.info(
        "Validating relevance: article '%s...' to topic '%s' (%s)",
        title[:50],
        topic_name,
        topic_id,
    )

    llm = get_llm(ModelTier.MEDIUM)

    prompt = PromptTemplate.from_template(validate_article_topic_relevance_prompt).format(
        topic_name=topic_name, 
        summary=summary, 
        title=title
    )

    r = run_llm_decision(chain=llm, prompt=prompt, model=ValidateRelevance)

    if r.motivation:
        return r.should_link, r.motivation
    else:
        return None


# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    article = {
        "title": "Fed Raises Interest Rates by 0.75% to Combat Inflation",
        "argos_summary": "The Federal Reserve raised interest rates by 75 basis points to 3.25%, the largest increase since 1994, as inflation remains near 40-year highs.",
    }

    a = ArticleModel(
        title="Fed Raises Interest Rates by 0.75% to Combat Inflation",
        argos_summary="The Federal Reserve raised interest rates by 75 basis points to 3.25%, the largest increase since 1994, as inflation remains near 40-year highs.",
    )

    should_link, motivation = validate_article_topic_relevance(
        a, "US Interest Rates", "us_interest_rates"
    )
    print(f"Should Link: {should_link}")
    print(f"Motivation: {motivation}")
