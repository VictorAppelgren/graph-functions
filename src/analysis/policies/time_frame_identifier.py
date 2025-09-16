from __future__ import annotations

import json
from typing import Any, Literal, Tuple, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier

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

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TIME FRAME IDENTIFIER working on the Saga Graph.

        TASK:
        - Output a SINGLE JSON OBJECT with exactly:
            - 'motivation' (first field): 1–2 sentences explaining the choice
            - 'horizon': one of: fundamental | medium | current
        - Only the JSON object. If unsure, say so in motivation but still pick one (default to "fundamental").

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "Discusses long-term structural drivers.", "horizon": "fundamental"}}
        {{"motivation": "Focuses on immediate market events.", "horizon": "current"}}

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
        decision = _sanitize_timeframe(raw)
    except (ValidationError, TypeError, json.JSONDecodeError) as e:
        logger.error("Time frame parsing failed: %s", str(e)[:200])
        raise

    logger.info("Time frame decision: %s", decision.model_dump())
    return decision.motivation, decision.horizon