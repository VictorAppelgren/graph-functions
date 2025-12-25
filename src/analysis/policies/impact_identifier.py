from __future__ import annotations
import json
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from typing import Any, Literal, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.runnables import Runnable
from src.llm.prompts.find_impact import find_impact_prompt
from src.llm.sanitizer import run_llm_decision, FindImpact

logger = get_logger("analysis.impact_identifier")

def _coerce_json_object(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string and return a dict, else raise."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def find_impact(article_text: str) -> FindImpact:
    """
    Ask the LLM to assess impact. Returns FindImpact object.
    Raises ValidationError/TypeError if the LLM output is malformed.
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )

    llm = get_llm(ModelTier.SIMPLE)  # Article work uses SIMPLE tier (20B)

    prompt = PromptTemplate.from_template(find_impact_prompt).format(
        article_text=article_text,
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT
    )
    
    return run_llm_decision(chain=llm, prompt=prompt, model=FindImpact)
