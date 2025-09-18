"""
LLM-driven proposal for new Topic node based on article content.
"""

import json
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from src.graph.config import MAX_TOPICS, describe_interest_areas
from src.graph.ops.topic import get_all_topics
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, ValidationError
from langchain_core.runnables import Runnable

logger = app_logging.get_logger(__name__)

template = PromptTemplate(
    template="""
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC NODE ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics. Every node is a specific, atomic, user-defined anchor (never a general group, catch-all, or ambiguous entity). Your output will be used for downstream graph analytics, LLM reasoning, and expert decision-making.

    CAPACITY CONTEXT:
    - Max topics allowed: {max_topics}
    - Current topics count: {current_count}
    - Areas of interest:
    {scope_text}
    - If capacity is full (current_count >= max_topics): Only propose a new topic if it is STRICTLY more important than the current weakest topic. If not, or if uncertain, return null.
    - Weakest topic importance (if full): {weakest_importance}
    - Examples of weakest topics (name, importance, last_updated): {weakest_examples}

    TASK:
    - Given the article below, propose a new Topic node for the graph if warranted. Output a JSON object with all required fields for a Topic node.
    - The output object MUST have:
        - 'motivation' (required, first field): Short, specific, research-grade reasoning (1-2 sentences) justifying why the new node is needed.
        - All other required fields for a Topic node (id, name, type).
    - If the article does not warrant a new node, output null.
    - Before output, PAUSE AND CHECK: Would this node satisfy a top-tier macro analyst and be maximally useful for graph analytics and LLM reasoning?
    - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields. If unsure, output null.

    STRICT TRADING RELEVANCE POLICY:
    - ALLOW topics that directly support trading decisions: macro drivers (inflation, growth, jobs, rates, credit), tradable assets (FX pairs, indices, commodities, rates), macro policy/regulation, macro-level geographies, or companies (only if central to macro/market impact).
    - REJECT topics that are industry verticals or operational niches, product categories, vendor lists, micro supply chain segments, or vague/ambiguous catch-alls.
    - Nodes must be atomic, human-readable, and defensible to a top-tier macro analyst.

    RECALL NUDGE (trading-first, minimal):
    - If the article surfaces a canonical tradable asset or policy anchor with a clear market-impact channel relevant to the Areas of interest above, prefer proposing the node.
    - If there is any real trading relevance to our main interests, it is acceptable to propose the node; otherwise output null.

    ARTICLE SUMMARY:
    {article}

    SUGGESTED NAMES:
    {suggested_names}

    EXAMPLE OUTPUT:
    {{"motivation": "The article introduces a new macro topic not yet present in the graph, requiring a new atomic node.", "id": "eurusd", "name": "EURUSD", "type": "asset"}}

    ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN ALL REQUIRED FIELDS. NO ADDITIONAL TEXT. STRICT JSON FORMAT.

    YOUR RESPONSE:
    The 'name' field must be human-readable (e.g., 'US Inflation', 'Eurozone Geopolitics', 'China').
    The 'type' field must be one of: macro, asset, company, policy, geography, etc.
    The 'motivation' field must be short and specific.
    All analysis fields can be empty strings.
    Return a JSON object with all required fields: id, name, type, motivation.


    YOUR RESPONSE IN JSON:
    """,
    input_variables=[
        "system_mission",
        "system_context",
        "article",
        "suggested_names",
        "max_topics",
        "current_count",
        "scope_text",
        "weakest_importance",
        "weakest_examples",
    ],
)


class TopicProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    type: str
    motivation: str | None = None
    importance: int = 0
    last_updated: str | None = None
    query: str | None = None
    importance_rationale: str | None = None


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    raise TypeError(f"Expected JSON object from LLM, got {type(raw).__name__}")


def propose_topic(
    article: str,
    suggested_names: Sequence[str] | None = None, 
) -> TopicProposal | None:
    """
    Uses an LLM to propose a new Topic node for the graph based on the article.
    Returns a dict with required fields for insertion, or None if no proposal.
    """
    logger.info("Calling LLM to propose new Topic node based on article.")
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()

    # compute context...
    scope_text = describe_interest_areas()
    try:
        existing_topics = get_all_topics(
            fields=["id", "name", "importance", "last_updated"]
        )
    except Exception as e:
        logger.warning("Failed to load existing topics for capacity context: %s", e)
        existing_topics = []

    current_count = len(existing_topics)
    max_topics = MAX_TOPICS
    capacity_full = current_count >= max_topics
    weakest_importance: int | None = None
    weakest_examples: list[dict[str, Any]] = []

    if capacity_full and existing_topics:
        try:
            sorted_all = sorted(
                existing_topics, key=lambda x: (x.get("importance") or 0)
            )
            weakest_importance = int(sorted_all[0].get("importance", 0))
            weakest_examples = [
                {
                    "name": t.get("name"),
                    "importance": t.get("importance", 0),
                    "last_updated": t.get("last_updated"),
                }
                for t in sorted_all[:3]
            ]
        except Exception as e:
            logger.warning("Failed to compute weakest topics: %s", e)
            weakest_importance = None
            weakest_examples = []

    # build your PromptTemplate as `template` earlier
    chain: Runnable[dict[str, Any], Any] = template | llm | parser
    raw = chain.invoke(
        {
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
            "article": article,
            "suggested_names": list(suggested_names or []),
            "max_topics": max_topics,
            "current_count": current_count,
            "scope_text": scope_text,
            "weakest_importance": weakest_importance,
            "weakest_examples": weakest_examples,
        }
    )

    if raw:
        return None

    try:
        data = _coerce_json_object(raw)
    except Exception as e:
        logger.error("LLM topic JSON parse failed: %s", e)
        return None

    try:
        proposal = TopicProposal.model_validate(data)
    except ValidationError as e:
        logger.error("LLM topic validation failed: %s", e)
        return None

    if proposal.motivation:
        logger.info("LLM topic node motivation: %s", proposal.motivation)

    return proposal
