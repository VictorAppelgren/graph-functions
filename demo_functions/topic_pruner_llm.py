"""
Minimal, stateless LLM-assisted topic pruner.

Run this file directly. Configure PREVIEW_ONLY at the bottom.
- PREVIEW_ONLY=True: print selected IDs once.
- PREVIEW_ONLY=False: remove selected IDs and loop until within capacity.
"""
from __future__ import annotations
from typing import List, Dict, Any

import os, sys, json
_CURRENT_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils import minimal_logging
from graph_utils.get_all_nodes import get_all_nodes
from graph_nodes.remove_node import remove_node
from graph_config import MAX_TOPICS, describe_interest_areas
from model_config import get_medium_llm

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = minimal_logging.get_logger(__name__)
 


def _select_topics_to_remove_llm(candidates: List[Dict[str, Any]], remove_count: int) -> List[str]:
    """Ask the LLM to pick which candidate topic ids to remove.
    Minimal version: no try/except, no fallbacks.
    """
    scope_text = describe_interest_areas()
    compact = [
        {"id": t.get("id"), "name": t.get("name"), "importance": t.get("importance", 0), "type": t.get("type")}
        for t in candidates
    ]
    candidate_ids = [t.get("id") for t in compact if t.get("id")]
    candidates_json = json.dumps(compact, ensure_ascii=False)
    candidate_ids_json = json.dumps(candidate_ids, ensure_ascii=False)

    prompt_template = """
{system_mission}
{system_context}

You are selecting Topic IDs to remove to meet capacity.
Output must be ONLY valid JSON. No prose, no markdown, no backticks, no comments.

{format_instructions}

Return exactly this JSON shape:
{{"ids_to_remove": ["<id1>", "<id2>", "..."]}}

Hard requirements:
- Return a maximum {remove_count} unique IDs.
- Each ID MUST be from the whitelist candidate_ids (see below).
- Do NOT include any other fields.
- Do NOT include explanations or extra text.
- If you include anything other than the exact JSON object, your answer will be discarded.

Selection policy (for decision quality; do not output this):
- Prefer the lowest importance first (ascending).
- Break ties by oldest last_updated first (ascending time).
- If importance or last_updated is missing, treat importance=0 and last_updated="1970-01-01T00:00:00".

Candidate whitelist (you may ONLY output IDs from this list):
candidate_ids = {candidate_ids}

Candidate details (context only, do not output):
{candidates}

Interest scope (for guidance only; do not output this):
{scope_text}
THESE ARE THE ONLY INTERESTS WE HAVE! SO ANYTHING NOT FULLY RELEVANT TO THESE TOPICS SHOULD BE REMOVED! 

FOCUS ON IDENTIFYING THE LEAST INTERESTING TOPICS TO REMOVE.

Now output ONLY the JSON object described above.
"""
    parser = JsonOutputParser()
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm().bind(response_format={"type": "json_object"})
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "format_instructions": parser.get_format_instructions(),
        "remove_count": remove_count,
        "scope_text": scope_text,
        "candidate_ids": candidate_ids_json,
        "candidates": candidates_json,
    })
    return result.get("ids_to_remove") or []


if __name__ == "__main__":
    # Minimal runner controlled by a single toggle.
    # True: run once, print selected IDs.
    # False: log and remove, then loop again until within capacity.
    PREVIEW_ONLY = False

    while True:
        fields = ["id", "name", "type", "importance", "level", "last_updated"]
        all_topics = get_all_nodes(fields=fields)
        total = len(all_topics)
        max_allowed = int(MAX_TOPICS)
        if total <= max_allowed:
            # Log all current nodes in a nice list 
            for t in all_topics:
                logger.info("Current topic: %s", t.get("name"))
            break

        need_remove = total - max_allowed
        remove_now = 20 if need_remove > 20 else need_remove
        logger.info("Capacity loop: before_total=%d, max=%d, need_remove=%d, batch=%d", total, max_allowed, need_remove, remove_now)
        ranked = sorted(all_topics, key=lambda t: (int(t.get("importance") or 0), str(t.get("last_updated") or "1970-01-01")))
        candidates = [
            {"id": t.get("id"), "name": t.get("name"), "importance": t.get("importance", 0), "type": t.get("type")}
            for t in ranked[: min(100, len(ranked))]
            if t.get("id")
        ]
        ids = _select_topics_to_remove_llm(candidates, remove_now)

        if PREVIEW_ONLY:
            logger.info("Preview: before_total=%d, selected=%d, after_total=%d", total, len(ids), max(total - len(ids), 0))
            print(ids)
            break

        logger.info("Removing %d topics: %s", len(ids), ids)
        for tid in ids:
            remove_node(tid, reason="capacity_prune_min")

        # Loop again with fresh state
        all_topics_after = get_all_nodes(fields=fields)
        after_total = len([t for t in all_topics_after if (t.get("level") or "main") == "main"])
        logger.info("After prune: after_total=%d (removed=%d)", after_total, len(ids))


 
