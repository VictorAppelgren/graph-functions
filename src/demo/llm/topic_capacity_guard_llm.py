"""
LLM helper to enforce a max count of topics in demo mode.

Returns JSON dict with:
{
  "action": "add" | "replace" | "reject",
  "motivation": str,
  "id_to_remove": str | null
}
"""
from typing import Dict, List, Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from utils import app_logging
from graph.config import MAX_TOPICS, describe_interest_areas
from llm.llm_router import get_medium_llm  # cost-aware
from utils.app_logging import truncate_str
from llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from observability.pipeline_logging import master_log

logger = app_logging.get_logger(__name__)

def decide_topic_capacity(candidate_topic: Dict[str, Any],
                         existing_topics: List[Dict[str, Any]],
                         test: bool = False) -> Dict[str, Any]:
    """
    candidate_topic: dict with at least {id?, name, importance, category?, motivation?}
    existing_topics: list of dicts like {id, name, importance, last_updated}
    """
    if test:
        return {"action": "add", "motivation": "Test mode: allow add", "id_to_remove": None}

    scope_text = describe_interest_areas()
    existing_compact = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "importance": t.get("importance", 0),
            "last_updated": t.get("last_updated"),
        }
        for t in existing_topics
    ][:MAX_TOPICS + 10]  # safety bound for prompt size

    prompt_template = """
{system_mission}
{system_context}

You are a capacity gatekeeper for a demo-mode macro graph. You MUST return a strict JSON object.

CONTEXT:
{scope_text}

CURRENT TOPICS (truncated):
{existing_topics}

CANDIDATE TOPIC:
{name}: importance={importance}, category={category}, motivation={motivation}

RULES:
- Max topics allowed: {max_topics}.
- If current count < max, action="add".
- If at capacity, compare candidate vs the least important existing topic.
  - If candidate is clearly more important/relevant to the scope than the weakest topic, action="replace" and set id_to_remove=that topic's id.
  - Otherwise action="reject".
- Priority weights: Priority 1 areas outrank Priority 2 if comparable importance.
- Be conservative on replace: only replace when confident the candidate is stronger for this demo scope.

OUTPUT FORMAT (STRICT JSON, NO EXTRA TEXT):
{{
  "action": "add" | "replace" | "reject",
  "motivation": "short reason (1-2 sentences)",
  "id_to_remove": "topic_id_or_null"
}}
"""
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    variables = {
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "scope_text": scope_text,
        "existing_topics": truncate_str(str(existing_compact), 3000),
        "name": candidate_topic.get("name", ""),
        "importance": candidate_topic.get("importance", 0),
        "category": candidate_topic.get("category"),
        "motivation": candidate_topic.get("motivation"),
        "max_topics": MAX_TOPICS,
    }

    logger.info("topic_capacity_guard vars: %s", truncate_str(str(variables), 500))
    result = chain.invoke(variables)

    # Parser ensures dict, but normalize fields:
    if isinstance(result, str):
        import json
        result = json.loads(result)
    action = (result.get("action") or "").lower()
    if action not in ("add", "replace", "reject"):
        action = "reject"
    out = {
        "action": action,
        "motivation": result.get("motivation") or "",
        "id_to_remove": result.get("id_to_remove"),
    }

    # Instrumentation: track replacement decisions in master stats/logs
    if action == "replace":
        cand_name = candidate_topic.get("name") or ""
        to_remove = out.get("id_to_remove")
        msg = (
            f"Topic capacity decision: REPLACE | candidate={cand_name} | remove_id={to_remove} | "
            f"reason={truncate_str(out['motivation'], 200)}"
        )
        master_log(msg, topic_replacements_decided=1)

    return out