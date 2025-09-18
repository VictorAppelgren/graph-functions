import json

from __future__ import annotations
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from typing import Any, Literal, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.runnables import Runnable
from src.llm.prompts.find_impact import find_impact_prompt
from src.llm.sanitizer import run_llm_decision, FindImpact

logger = get_logger(__name__)

def _coerce_json_object(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string and return a dict, else raise."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def find_impact(article_text: str) -> tuple[str, int] | None:
    """
    Ask the LLM to assess impact. Returns (motivation, score).
    Raises ValidationError/TypeError if the LLM output is malformed.
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )

    # prompt_template = """
    #     {system_mission}
    #     {system_context}

    #     YOU ARE A WORLD-CLASS MACRO/MARKETS IMPACT ASSESSOR working on the Saga Graph—a knowledge graph for the global economy.

    #     TASK:
    #     - Output a SINGLE JSON OBJECT with exactly these two fields:
    #         - 'motivation' (first field): Reason for the score (1–2 sentences)
    #         - 'score': Impact score ('hidden' if not relevant, or 1=low, 2=medium, 3=high)
    #     - Output ONLY the JSON object, no extra text. If unsure, say so in motivation but still choose a score.

    #     ARTICLE TEXT:
    #     {article_text}

    #     EXAMPLES:
    #     {{"motivation": "The article directly impacts this node by reporting a major event.", "score": 3}}
    #     {{"motivation": "The article is not relevant to this node's scope.", "score": "hidden"}}

    #     YOUR RESPONSE:
    # """

    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        find_impact_prompt).format(
            article_text=article_text,
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT
        )
    
    r = run_llm_decision(chain=chain, prompt=p, model=FindImpact)

    if r.motivation:
        return r.motivation, r.score
    else:
        return None
