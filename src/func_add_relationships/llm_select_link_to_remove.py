from model_config import get_medium_llm
from langchain_core.output_parsers import JsonOutputParser
from utils import logging
from utils.logging import truncate_str
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = logging.get_logger(__name__)

def llm_select_link_to_remove(source_node: dict, existing_links: list[dict], prioritized_link: dict) -> dict:
    """
    Use LLM to select weakest link to remove if at max capacity.
    Returns: { "remove_link": target_id, "motivation": ... } or None
    """
    llm = get_medium_llm()
    prompt = f'''
    {SYSTEM_MISSION}
    {SYSTEM_CONTEXT}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - The maximum number of links of this type is already present.
    - Select the weakest link to remove, if any, to make room for the prioritized new link.
    - Output a JSON object with:
        - 'motivation' (required, first field): Short, research-grade, actionable reasoning (1-2 sentences max) justifying why this link should be removed. Motivation must be defensible to a top-tier financial analyst and maximally useful for graph analytics and LLM reasoning.
        - 'remove_link': target_id (the link to remove).
    - ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN REMOVE_LINK. NO ADDITIONAL TEXT. STRICT JSON FORMAT. Output null if no link should be removed.

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

    logger.info("source_node name: %s", source_node.get('name'))
    logger.info("existing_links: %s", existing_links)
    logger.info("prioritized_link: %s", prioritized_link)

    logger.debug("Prompt: %s", truncate_str(str(prompt), 100))
    chain = llm | JsonOutputParser()
    result = chain.invoke(prompt)
    logger.info("LLM removal result: %s", result)
    motivation = result.get('motivation') if isinstance(result, dict) else None
    if motivation:
        logger.info(f"LLM removal motivation: {motivation}")
    logger.info(f"LLM removal decision: {result}")
    return result
