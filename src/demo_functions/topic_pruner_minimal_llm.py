"""
Super minimal LLM-based topic pruner (non-prioritizing).

Process:
1) Load all Topic nodes (id, name, type, importance, level, last_updated)
2) Ask LLM, given SYSTEM_MISSION + SYSTEM_CONTEXT, to return ALL topic ids that are NOT crucial
3) If PREVIEW_ONLY: print ids. Else: print and remove them via remove_node()

No fallbacks. No try/except. Absolute imports guaranteed via canonical bootstrap.
"""

# --- Canonical import pattern (see Saga_Graph_v2.md §8a) ---
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# -----------------------------------------------------------------

from typing import List, Dict, Any
import json
from datetime import datetime, date

from utils import logging
from graph_utils.get_all_nodes import get_all_nodes
from graph_nodes.remove_node import remove_node
from model_config import get_medium_llm
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.get_logger(__name__)


def _select_not_crucial_topics_llm(candidates: List[Dict[str, Any]]) -> List[str]:
    """Return ALL candidate topic IDs that are NOT crucial to the macro graph.
    Output must be EXACTLY: {"ids_to_remove": ["<id>", ...]}
    """
    def _json_safe(v):
        # Convert datetime-like objects to ISO strings; fallback to str for unknown types
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        try:
            # neo4j.time.DateTime has iso_format() or isoformat-like behaviour via str()
            if hasattr(v, "isoformat"):
                return v.isoformat()
        except Exception:
            pass
        return v if v is None or isinstance(v, (str, int, float, bool, list, dict)) else str(v)

    compact = [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "type": t.get("type"),
            "importance": t.get("importance", 0),
            "level": t.get("level"),
            "last_updated": _json_safe(t.get("last_updated")),
        }
        for t in candidates
    ]
    candidate_ids = [t.get("id") for t in compact if t.get("id")]
    candidates_json = json.dumps(compact, ensure_ascii=False)
    candidate_ids_json = json.dumps(candidate_ids, ensure_ascii=False)

    prompt_template = """
{system_mission}
{system_context}

You must identify all Topic IDs that are NOT crucial to the macro graph.
A topic IS crucial if it clearly fits the mission and Interest Areas AND maps to market handles with a causal path and catalysts, or adds pillar diversification.
Reject as NOT crucial if off-scope, micro/local with no scalable macro path, no handle mapping, no catalysts, duplicates/near-duplicates, or weak/no pillar contribution.

Output must be ONLY a valid JSON object. No prose, no markdown, no backticks, no comments.
Return exactly this shape:
{{"ids_to_remove": ["<id1>", "<id2>", "..."]}}

Hard requirements:
- All IDs MUST come from the whitelist candidate_ids.
- You may return zero or more IDs.
- Do NOT include any other fields or text.

Whitelist candidate IDs (return only from this list):
candidate_ids = {candidate_ids}

Candidate details (context only, do not output):
{candidates}

Now output ONLY the JSON object described above.
"""
    parser = JsonOutputParser()
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_medium_llm()
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "candidate_ids": candidate_ids_json,
        "candidates": candidates_json,
    })
    return result["ids_to_remove"]


if __name__ == "__main__":
    # Single hardcoded toggle. True = only print. False = print and remove.
    PREVIEW_ONLY = True

    fields = ["id", "name", "type", "importance", "level", "last_updated"]
    topics = get_all_nodes(fields=fields)
    logger.info("Loaded %d topics for minimal prune check", len(topics))

    ids = _select_not_crucial_topics_llm(topics)

    if PREVIEW_ONLY:
        logger.info("Preview (not crucial): %d ids", len(ids))
        print(ids)
    else:
        logger.info("Removing %d topics: %s", len(ids), ids)
        print(ids)
        for tid in ids:
            remove_node(tid, reason="minimal_prune_not_crucial")
