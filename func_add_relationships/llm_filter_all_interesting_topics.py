from model_config import get_simple_long_context_llm
from langchain_core.output_parsers import JsonOutputParser
from utils import minimal_logging
from utils.minimal_logging import truncate_str
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = minimal_logging.get_logger(__name__)

def llm_filter_all_interesting_topics(source_node: dict, all_nodes: list[dict]) -> dict:
    """
    Use LLM to filter all_nodes down to plausible candidates for strong relationships.
    Returns a dict: { 'candidate_ids': list[str], 'motivation': str | None }
    """
    llm = get_simple_long_context_llm()
    all_names = [n['name'] for n in all_nodes]
    name = source_node['name']
    prompt = f'''
    {SYSTEM_MISSION}
    {SYSTEM_CONTEXT}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - Given the source topic below and a list of all topics (names only), select all nodes that could plausibly be strong INFLUENCES, CORRELATES_WITH, or PEERS to the source.
    - Only select nodes where a strong, direct, or competitive relationship is possible.
    - Output a JSON object with two fields: 'motivation' (1-2 sentences, required, first field, justifying your shortlist) and 'candidates' (list of topic names). If none are plausible, output an empty list for 'candidates'.
    - ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN CANDIDATES. NO ADDITIONAL TEXT. STRICT JSON FORMAT.

    EXAMPLE OUTPUT:
    {{"motivation": "These topics are the most likely strong peers or influences based on the source topic\'s domain.", "candidates": ["EURUSD", "ECB Policy", "US Inflation"]}}

    SOURCE NODE:
    {name}

    ALL TOPICS:
    {all_names}

    YOUR RESPONSE IN JSON:
    '''
    logger.debug("Prompt: %s", truncate_str(str(prompt), 100))
    chain = llm | JsonOutputParser()
    result = chain.invoke(prompt)
    motivation = result.get('motivation') if isinstance(result, dict) else None
    if motivation:
        logger.info(f"LLM candidate shortlist motivation: {motivation}")
    candidate_names = result.get('candidates', []) if isinstance(result, dict) else []
    name_to_id = {n['name']: n['id'] for n in all_nodes}
    candidate_ids = [name_to_id[name] for name in candidate_names if name in name_to_id]
    logger.info(f"Candidate IDs after mapping: {candidate_ids}")
    return {"candidate_ids": candidate_ids, "motivation": motivation}
