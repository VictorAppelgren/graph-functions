"""
LLM-driven wide query generation for a new node/topic.
"""
import logging
import json
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from typing import Any, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from __future__ import annotations

logger = app_logging.get_logger(__name__)

class WideQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # motivation optional but nice to have
    motivation: str | None = Field(default=None, max_length=400)
    # query is required for a “success”; when the model can’t produce one, set to None
    query: str | None

def _coerce_json_object(raw: Any) -> dict[str, Any]:
    """Accept dict or JSON string and return a dict, else raise."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")

def _sanitize_wide_query(raw: Any, logger: logging.Logger) -> WideQuery:
    data = _coerce_json_object(raw)

    # allow models that output only {"query": "..."} (motivation omitted)
    try:
        wq = WideQuery.model_validate(data)
    except ValidationError as e:
        logger.warning("WideQuery schema validation failed: %s", str(e)[:200])
        # graceful fallback: no query
        return WideQuery(motivation=None, query=None)

    # normalize motivation
    if wq.motivation:
        wq.motivation = " ".join(wq.motivation.split())[:400]

    # normalize query (strip empties to None)
    if wq.query is not None:
        q = wq.query.strip()
        wq.query = q if q else None

    return wq

def create_wide_query(article_text: str) -> dict[str, Any]:
    """
    Uses LLM to generate a wide boolean search query for a given article/topic.
    Returns: {"motivation": str|None, "query": str|None}
    """
    logger.info("Generating wide query from article text for node/topic")

    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()

    prompt_template = """
{system_mission}
{system_context}
YOU ARE A WORLD-CLASS MACRO/MARKETS BOOLEAN QUERY ENGINEER working on the Saga Graph…

TASK:
- Given the article text below, generate a wide boolean search query.
- Output a JSON object with:
    - 'motivation' (first field): short, research-grade justification.
    - 'query': the boolean query string.
- If no good query can be constructed, output null for 'query'.
- ONLY the JSON object. NO extra text/fields.

ARTICLE:
{article_text}

YOUR RESPONSE IN JSON:
"""
    logger.debug("PromptTemplate: %s", truncate_str(prompt_template, 100))
    prompt = PromptTemplate.from_template(prompt_template)

    chain: Runnable[dict[str, str], Any] = prompt | llm | parser
    raw = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "article_text": article_text,
    })

    wq = _sanitize_wide_query(raw, logger)
    logger.info("LLM wide query sanitized: %s", wq.model_dump())

    # If you prefer to return the model, change return type to WideQuery
    return wq.model_dump()