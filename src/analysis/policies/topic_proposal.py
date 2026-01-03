"""
LLM-driven proposal for new Topic node based on article content.
"""

import json
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from src.graph.config import describe_interest_areas
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict
from src.llm.prompts.propose_topic import propose_topic_prompt
from src.llm.sanitizer import run_llm_decision, ProposeTopic

logger = app_logging.get_logger("analysis.topic_proposal")


class TopicProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    motivation: str | None = None
    last_updated: str | None = None
    query: str | None = None
    type: str | None = None


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
    existing_topics: list[dict[str, Any]] | None = None,
) -> TopicProposal | None:
    """
    Uses an LLM to propose a new Topic node for the graph based on the article.
    Returns a TopicProposal or None if no proposal.
    """
    logger.info("Calling LLM to propose new Topic node based on article.")
    llm = get_llm(ModelTier.COMPLEX)

    scope_text = describe_interest_areas()
    existing_topics = existing_topics or []
    current_count = len(existing_topics)

    p = PromptTemplate.from_template(
        propose_topic_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            article=article,
            suggested_names=list(suggested_names or []),
            current_count=current_count,
            scope_text=scope_text,
        )

    r = run_llm_decision(chain=llm, prompt=p, model=ProposeTopic)

    if r.id and r.motivation and r.name:
        data = _coerce_json_object(r.model_dump())
        proposal = TopicProposal.model_validate(data)
        return proposal
    else:
        return None
