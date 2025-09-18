from __future__ import annotations

import json
from typing import Any, Literal, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.find_time_frame import find_time_frame_prompt
from src.llm.sanitizer import run_llm_decision, TimeFrame

# Configure logging
logger = app_logging.get_logger(__name__)

Horizon = Literal["fundamental", "medium", "current"]


class TimeframeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivation: str = Field(min_length=1, max_length=400)
    horizon: Horizon


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def _sanitize_timeframe(raw: Any) -> TimeframeDecision:
    data = _coerce_json_object(raw)
    dec = TimeframeDecision.model_validate(data)
    dec.motivation = " ".join(dec.motivation.split())[:400]  # normalize
    # horizon is validated by Literal, so it’s guaranteed correct here
    return dec


def find_time_frame(article_text: str) -> tuple[str, Horizon]:
    """
    Classify an article's time frame. Returns (motivation, horizon).
    Raises on malformed LLM output.
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )

    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        find_time_frame_prompt).format(
            article_text=article_text,
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT
        )
    
    r = run_llm_decision(chain=chain, prompt=p, model=TimeFrame)

    try:
        decision = _sanitize_timeframe(r)
    except (ValidationError, TypeError, json.JSONDecodeError) as e:
        logger.error("Time frame parsing failed: %s", str(e)[:200])
        raise

    logger.info("Time frame decision: %s", decision.model_dump())
    return decision.motivation, decision.horizon
