from src.llm.llm_router import get_medium_llm
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.observability.pipeline_logging import master_log_error

logger = app_logging.get_logger(__name__)

def llm_select_one_new_link(source_node: dict, candidate_nodes: list[dict], existing_links: list[dict]) -> dict:
    """
    Use LLM to propose the single strongest missing link.
    Returns: { "type": ..., "source": ..., "target": ..., "motivation": ... } or None
    """
    llm = get_medium_llm()
    # Format candidate nodes as '- Name (id: id)'
    candidate_lines = '\n'.join([f"- {n['name']} (id: {n['id']})" for n in candidate_nodes])
    prompt_template = """
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - Given the source node, candidate nodes, and existing links, propose the single strongest missing link.
    - Output a JSON object with:
        - 'motivation' (required, first field): Short, research-grade, actionable reasoning (1-2 sentences max) justifying why this link should be created. Motivation must be defensible to a top-tier financial analyst and maximally useful for graph analytics and LLM reasoning.
        - All other required fields (type, source, target, etc.).
    - ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN ALL REQUIRED FIELDS. NO ADDITIONAL TEXT. STRICT JSON FORMAT. Output null if no link should be created.

    EXAMPLE OUTPUT:
    {{"motivation": "This link connects two highly correlated macro drivers not yet linked in the graph.", "type": "INFLUENCES", "source": "eurusd", "target": "ecb_policy"}}

    LINK TYPES:
    - INFLUENCES: A → B means A is a major driver or cause of B. Directional.
    - PEERS: A ↔ B means A and B are direct competitors, alternatives, or fulfill the same role in a market or system. Bi-directional, “true peer” only.
    - COMPONENT_OF: A is a component of B. Directional.
    - CORRELATES_WITH: A and B are correlated. Bi-directional. Moves together to some large degree.  

    SOURCE NODE:
    {source_name} (id: {source_id})

    CANDIDATE NODES:
    {candidate_lines}

    CURRENT LINKS:
    {existing_links}

    STRICT OUTPUT FORMAT:
    - Output exactly ONE JSON object with these REQUIRED keys only: "motivation", "type", "source", "target".
    - All four fields are REQUIRED and MUST be non-empty strings.
    - Do NOT include any other keys. Do NOT include any text before or after the JSON.

    YOUR RESPONSE IN JSON:
    """
    logger.debug("[llm_propose_new_link] PromptTemplate: %s", truncate_str(str(prompt_template), 100))
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm | JsonOutputParser()
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "source_name": source_node['name'],
        "source_id": source_node['id'],
        "candidate_lines": candidate_lines,
        "existing_links": existing_links,
    })
    # Guard: LLM may output JSON null => parser returns None; or unexpected non-dict
    if result is None:
        logger.info("LLM proposed no link (null). Skipping new link creation.")
        return None
    if not isinstance(result, dict):
        logger.warning(f"Unexpected LLM result type {type(result).__name__}; skipping. result={truncate_str(str(result), 200)}")
        master_log_error("LLM link proposal non-dict result; skipping")
        return None
    # Minimal schema validation: required keys must exist and be non-empty strings
    required = ["type", "source", "target", "motivation"]
    missing = [k for k in required if k not in result or not str(result[k]).strip()]
    if missing:
        logger.warning(f"LLM link proposal missing required fields {missing}; skipping. result={result}")
        master_log_error(f"LLM link proposal missing required fields {missing}; skipping")
        return None
    motivation = result.get('motivation') if isinstance(result, dict) else None
    if motivation:
        logger.info(f"LLM proposed link motivation: {motivation}")
    logger.info(f"[llm_propose_new_link] LLM proposed new link: {result}")
    return result
