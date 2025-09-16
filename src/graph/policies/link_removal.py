from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.sanitizer import run_llm_decision, RemoveDecision
from typing import cast

logger = app_logging.get_logger(__name__)

def llm_select_link_to_remove(
    source_node: dict[str, str],
    existing_links: list[dict[str, str]],
    prioritized_link: dict[str, str],
) -> dict[str, object]:
    """
    Use LLM to select weakest link to remove if at max capacity.
    Returns a clean dict: {"motivation": str|None, "remove_link": str|None}
    """
    llm = get_llm(ModelTier.MEDIUM)
    chain = llm | JsonOutputParser()

    prompt = f'''
        {SYSTEM_MISSION}
        {SYSTEM_CONTEXT}

        YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

        TASK:
        - The maximum number of links of this type is already present.
        - Select the weakest link to remove, if any, to make room for the prioritized new link.
        - Output a JSON object with:
            - 'motivation' (required, first field): Short, research-grade, actionable reasoning (1-2 sentences max).
            - 'remove_link': target_id (the link to remove) or null if none.
        - ONLY THE JSON OBJECT. NO EXTRA TEXT. STRICT JSON FORMAT.

        EXAMPLE OUTPUT:
        {{"motivation": "This link is the weakest correlation and least supported by recent data.", "remove_link": "eurusd"}}

        SOURCE NODE:
        {source_node}

        CURRENT LINKS:
        {existing_links}

        PRIORITIZED NEW LINK:
        {prioritized_link}

        YOUR RESPONSE IN JSON:
    '''

    logger.info("source_node name: %s", source_node.get("name"))
    logger.info("existing_links: %s", existing_links)
    logger.info("prioritized_link: %s", prioritized_link)

    # Collect allowed ids from your link dicts (support a couple of common keys)

    logger.debug("Prompt: %s", truncate_str(str(prompt), 100))

    allowed_ids = {
        d.get("id") or d.get("target_id")
        for d in existing_links if isinstance(d, dict)
    }

    decision = run_llm_decision(
        chain=chain,
        prompt=prompt,
        allowed_ids=allowed_ids,
        model=RemoveDecision,  # the Pydantic model
        logger=logger,
    )

    logger.info("LLM removal decision: %s", decision.model_dump())
    if decision.motivation:
        logger.info("LLM removal motivation: %s", decision.motivation)

    # keep your return type as dict for compatibility with callers
    return decision.model_dump()
