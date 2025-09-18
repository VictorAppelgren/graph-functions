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
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict
from src.llm.prompts.propose_topic import propose_topic_prompt
from src.llm.sanitizer import run_llm_decision, ProposeTopic

logger = app_logging.get_logger(__name__)


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

    p = PromptTemplate.from_template(
        propose_topic_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            article=article,
            suggested_names=list(suggested_names or []),
            max_topics=max_topics,
            current_count=current_count,
            scope_text=scope_text,
            weakest_importance=weakest_importance,
            weakest_examples=weakest_examples
        )

    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=p, model=ProposeTopic)

    if r.id and r.model_config and r.motivation and r.name:
        
        data = _coerce_json_object(r.model_dump())
    
        proposal = TopicProposal.model_validate(data)
    
        return proposal
    
    else:
        return None
