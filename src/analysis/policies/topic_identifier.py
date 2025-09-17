from __future__ import annotations

import json
from typing import Any, Iterable, Sequence, TypedDict, cast
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger

logger = get_logger(__name__)

# --- types --------------------------------------------------------------------


class NodeRow(TypedDict, total=False):
    id: str
    name: str
    importance: int
    last_updated: str


class NodeMappingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivation: str = Field(min_length=1, max_length=400)
    existing: list[str] | None = None  # IDs
    new: list[str] | None = None  # names


# --- helpers ------------------------------------------------------------------


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def _sanitize_node_mapping(
    raw: Any,
    allowed_existing_ids: Iterable[str],
    *,
    max_new: int = 1,
) -> NodeMappingDecision:
    """Parse + validate + enforce rules for mapping output."""
    data = _coerce_json_object(raw)
    dec = NodeMappingDecision.model_validate(data)

    # normalize motivation
    dec.motivation = " ".join(dec.motivation.split())[:400]

    # existing must be list of allowed IDs (drop unknowns)
    allowed = set(allowed_existing_ids)
    ex = [x for x in (dec.existing or []) if isinstance(x, str)]
    if allowed:
        ex = [x for x in ex if x in allowed]
    dec.existing = ex

    # new must be list of names (strings), max_new entries
    nw = [x for x in (dec.new or []) if isinstance(x, str)]
    if max_new >= 0:
        nw = nw[:max_new]
    dec.new = nw

    return dec


# --- main ---------------------------------------------------------------------


def find_topic_mapping(
    article_text: str,
    node_list: Sequence[NodeRow],
) -> tuple[str, list[str], list[str]]:
    """
    Map article to existing/new nodes.
    Returns: (motivation, existing_ids, new_names)
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )
    logger.info("Node list length: %d", len(node_list))

    # Build allowed existing IDs from node_list
    allowed_ids = [
        n["id"]
        for n in node_list
        if isinstance(n, dict) and "id" in n and isinstance(n["id"], str)
    ]

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC MAPPER for the NEO4j Graph.

        OVERVIEW:
        - Output exactly ONE flat JSON object with fields:
          'motivation' (string), 'existing' (array of IDs or null), 'new' (array of NAMES or null).
        - Prioritize 'existing'. Be generous with 'existing' suggestions.
        - Be conservative with 'new' (at most one), otherwise null.
        - Use IDs for 'existing' and NAMES for 'new'. No extra fields.

        EXISTING NODE NAMES AND IDS:
        {node_list}

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "Impact: FX; EUR/USD and Fed policy drive currency repricing.", "existing": ["eurusd", "fed_policy"], "new": null}}
        {{"motivation": "Impact: credit; Structured finance gap affects credit pricing.", "existing": null, "new": ["structured_finance"]}}
        {{"motivation": "Impact: rates; US inflation affects yields.", "existing": ["us_inflation"], "new": null}}
        {{"motivation": "Impact: none; No material mapping.", "existing": null, "new": null}}

        STRICT OUTPUT: Only the JSON object. No extra text.
        YOUR RESPONSE:
    """

    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
    parser = JsonOutputParser()
    chain: Runnable[dict[str, Any], Any] = prompt | llm | parser

    raw = chain.invoke(
        {
            "article_text": article_text,
            "node_list": node_list,  # the template prints it verbatim; OK for LLM context
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
        }
    )

    try:
        decision = _sanitize_node_mapping(
            raw, allowed_existing_ids=allowed_ids, max_new=1
        )
    except (ValidationError, TypeError, json.JSONDecodeError) as e:
        logger.error("Node mapping parse/validate failed: %s", str(e)[:200])
        # Safe fallback: no mapping
        return ("Unable to confidently map nodes.", [], [])

    logger.info("Node mapping decision: %s", decision.model_dump())
    # Always return lists (never None) to simplify callers
    return decision.motivation, decision.existing or [], decision.new or []
