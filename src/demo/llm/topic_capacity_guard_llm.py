"""
LLM helper to enforce a max count of topics in demo mode.

Returns JSON dict with:
{
  "action": "add" | "replace" | "reject",
  "motivation": str,
  "id_to_remove": str | null
}
"""

import json
from enum import StrEnum
from typing import Dict, List, Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from src.graph.config import MAX_TOPICS, describe_interest_areas
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils.app_logging import truncate_str
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from pydantic import BaseModel
from src.llm.prompts.decide_topic_capacity import decide_topic_capacity_prompt
from src.llm.sanitizer import run_llm_decision, TopicCapacityModel

logger = app_logging.get_logger(__name__)


def decide_topic_capacity(
    candidate_topic: Dict[str, Any],
    existing_topics: List[Dict[str, Any]],
    test: bool = False,
) -> TopicCapacityModel:
    """
    candidate_topic: dict with at least {id?, name, importance, category?, motivation?}
    existing_topics: list of dicts like {id, name, importance, last_updated}
    """
    if test:
        return {
            "action": "add",
            "motivation": "Test mode: allow add",
            "id_to_remove": None,
        }

    scope_text = describe_interest_areas()
    existing_compact = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "importance": t.get("importance", 0),
            "last_updated": t.get("last_updated"),
        }
        for t in existing_topics
    ][
        : MAX_TOPICS + 10
    ]  # safety bound for prompt size

    p = PromptTemplate.from_template(
        decide_topic_capacity_prompt).format(
            system_mission=SYSTEM_MISSION, 
            system_context=SYSTEM_CONTEXT, 
            scope_text=scope_text, 
            existing_topics=existing_topics, 
            name=candidate_topic.get("name", ""),
            category=candidate_topic.get("category"),
            motivation=candidate_topic.get("motivation"),
            max_topics=MAX_TOPICS)
    
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser

    r = run_llm_decision(chain=chain, prompt=p, model=TopicCapacityModel)

    # Parser ensures dict, but normalize fields:
    if isinstance(result, str):
        result = json.loads(result)
    action = (result.get("action") or "").lower()
    if action not in ("add", "replace", "reject"):
        action = "reject"
    
    # Instrumentation: track replacement decisions in master stats/logs
    if r.action == "replace":
        cand_name = candidate_topic.get("name") or ""
        logger.info(
            f"Topic capacity decision: REPLACE | candidate={cand_name} | remove_id={r.id_to_remove} | "
            f"reason={truncate_str(t.motivation, 200)}"
        )

    return r
