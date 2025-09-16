from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

from __future__ import annotations

import json
from typing import Any, Literal, Tuple, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable

logger = get_logger(__name__)

ImpactScore = Literal["hidden", 1, 2, 3]

class ImpactDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivation: str = Field(min_length=1, max_length=400)
    score: ImpactScore

def _coerce_json_object(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string and return a dict, else raise."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")

def _sanitize_impact(raw: Any) -> ImpactDecision:
    data = _coerce_json_object(raw)
    dec = ImpactDecision.model_validate(data)
    # normalize motivation (collapse whitespace, cap length)
    dec.motivation = " ".join(dec.motivation.split())[:400]
    return dec

def find_impact(article_text: str) -> tuple[str, ImpactScore]:
    """
    Ask the LLM to assess impact. Returns (motivation, score).
    Raises ValidationError/TypeError if the LLM output is malformed.
    """
    logger.info("Article text: %s%s", article_text[:200], "..." if len(article_text) > 200 else "")

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS IMPACT ASSESSOR working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - Output a SINGLE JSON OBJECT with exactly these two fields:
            - 'motivation' (first field): Reason for the score (1–2 sentences)
            - 'score': Impact score ('hidden' if not relevant, or 1=low, 2=medium, 3=high)
        - Output ONLY the JSON object, no extra text. If unsure, say so in motivation but still choose a score.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "The article directly impacts this node by reporting a major event.", "score": 3}}
        {{"motivation": "The article is not relevant to this node's scope.", "score": "hidden"}}

        YOUR RESPONSE:
    """

    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain: Runnable[dict[str, str], Any] = prompt | llm | parser

    raw = chain.invoke({
        "article_text": article_text,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })

    try:
        decision = _sanitize_impact(raw)
    except (ValidationError, TypeError, json.JSONDecodeError) as e:
        logger.error("Impact parsing failed: %s", str(e)[:200])
        # choose your policy: raise or fallback
        raise

    logger.info("Impact decision: score=%s", decision.score, extra={"context": decision.model_dump()})
    return decision.motivation, decision.score