from __future__ import annotations

from typing import Any, Sequence
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.app_logging import get_logger
from src.llm.sanitizer import run_llm_decision, TopicMapping
from src.llm.prompts.find_topic_mapping import find_topic_mapping_prompt

logger = get_logger(__name__)

# --- types --------------------------------------------------------------------


class NodeRow(BaseModel):
    id: str = ""
    name: str = ""
    importance: int | None = None
    last_updated: str | None = None


# --- main ---------------------------------------------------------------------


def find_topic_mapping(
    article_text: str,
    node_list: Sequence[NodeRow],
) -> TopicMapping:
    """
    Map article to existing/new nodes.
    Returns: TopicMapping object with motivation, existing, and new fields.
    """
    logger.info(
        "Article text: %s%s",
        article_text[:200],
        "..." if len(article_text) > 200 else "",
    )
    logger.info("Node list length: %d", len(node_list))

    # Build allowed existing IDs from node_list (accept NodeRow or dict rows)
    allowed_ids: list[str] = []
    for n in node_list:
        id_val = None
        if isinstance(n, dict):
            id_val = n.get("id")
        elif hasattr(n, "id"):
            id_val = getattr(n, "id")
        if isinstance(id_val, str):
            allowed_ids.append(id_val)
    logger.debug("Allowed topic IDs count: %d", len(allowed_ids))

    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)

    prompt = PromptTemplate.from_template(find_topic_mapping_prompt).format(
        article_text=article_text,
        node_list=node_list,
        system_mission=SYSTEM_MISSION,
        system_context=SYSTEM_CONTEXT,
    )

    # Use validated Pydantic model directly
    r: TopicMapping = run_llm_decision(chain=llm, prompt=prompt, model=TopicMapping)
    
    logger.info("Node mapping decision: %s", r.model_dump())
    
    return r
