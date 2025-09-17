from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.sanitizer import run_llm_decision, RemoveDecision

logger = app_logging.get_logger(__name__)


def llm_select_link_to_remove(
    source_topic: dict[str, str],
    existing_links: list[dict[str, str]],
    prioritized_link: dict[str, str],
) -> dict[str, object]:
    """
    Use LLM to select weakest link to remove if at max capacity.
    Returns a clean dict: {"motivation": str|None, "remove_link": str|None}
    """
    llm = get_llm(ModelTier.MEDIUM)
    chain = llm | JsonOutputParser()

    prompt = f"""
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

        SOURCE TOPIC:
        {source_topic}

        CURRENT LINKS:
        {existing_links}

        PRIORITIZED NEW LINK:
        {prioritized_link}

        YOUR RESPONSE IN JSON:
    """

    logger.info("source_topic name: %s", source_topic.get("name"))
    logger.info("existing_links: %s", existing_links)
    logger.info("prioritized_link: %s", prioritized_link)

    # Collect allowed ids from your link dicts (support a couple of common keys)

    logger.debug("Prompt: %s", truncate_str(str(prompt), 100))

    allowed_ids = {
        d.get("id") or d.get("target_id") for d in existing_links if isinstance(d, dict)
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


def llm_select_one_new_link(
    source_topic: dict, candidate_topics: list[dict], existing_links: list[dict]
) -> dict:
    """
    Use LLM to propose the single strongest missing link.
    Returns: { "type": ..., "source": ..., "target": ..., "motivation": ... } or None
    """
    llm = get_llm(ModelTier.MEDIUM)
    # Format candidate topics as '- Name (id: id)'
    candidate_lines = "\n".join(
        [f"- {n['name']} (id: {n['id']})" for n in candidate_topics]
    )
    prompt_template = """
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - Given the source topic, candidate topics, and existing links, propose the single strongest missing link.
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

    SOURCE TOPIC:
    {source_name} (id: {source_id})

    CANDIDATE TOPICS:
    {candidate_lines}

    CURRENT LINKS:
    {existing_links}

    STRICT OUTPUT FORMAT:
    - Output exactly ONE JSON object with these REQUIRED keys only: "motivation", "type", "source", "target".
    - All four fields are REQUIRED and MUST be non-empty strings.
    - Do NOT include any other keys. Do NOT include any text before or after the JSON.

    YOUR RESPONSE IN JSON:
    """
    logger.debug(
        "[llm_propose_new_link] PromptTemplate: %s",
        truncate_str(str(prompt_template), 100),
    )
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm | JsonOutputParser()
    result = chain.invoke(
        {
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
            "source_name": source_topic["name"],
            "source_id": source_topic["id"],
            "candidate_lines": candidate_lines,
            "existing_links": existing_links,
        }
    )
    # Guard: LLM may output JSON null => parser returns None; or unexpected non-dict
    if result is None:
        logger.info("LLM proposed no link (null). Skipping new link creation.")
        return None
    if not isinstance(result, dict):
        logger.warning(
            f"Unexpected LLM result type {type(result).__name__}; skipping. result={truncate_str(str(result), 200)}"
        )
        master_log_error("LLM link proposal non-dict result; skipping")
        return None
    # Minimal schema validation: required keys must exist and be non-empty strings
    required = ["type", "source", "target", "motivation"]
    missing = [k for k in required if k not in result or not str(result[k]).strip()]
    if missing:
        logger.warning(
            f"LLM link proposal missing required fields {missing}; skipping. result={result}"
        )
        master_log_error(
            f"LLM link proposal missing required fields {missing}; skipping"
        )
        return None
    motivation = result.get("motivation") if isinstance(result, dict) else None
    if motivation:
        logger.info(f"LLM proposed link motivation: {motivation}")
    logger.info(f"[llm_propose_new_link] LLM proposed new link: {result}")
    return result
