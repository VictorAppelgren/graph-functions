"""
QA prompts and critic chain for reviewing tracker events.
Simplicity-first: constants in this file, single chain builder.
"""
import sys, os

# Canonical import pattern: ensure absolute imports work from any CWD
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import Dict

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from model_config import get_medium_llm
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT


# High-level project description embedded directly here (short but complete)
PROJECT_SUMMARY = (
    "Saga Macro Graph is a minimal, auditable knowledge graph for the global economy. "
    "All graph mutations (add/remove nodes and relationships, article ingestion) create a small, "
    "fully traceable tracker JSON with IDs in 'inputs' and rich LLM context in 'details'. "
    "Design principles: simplicity, determinism where possible, fail-fast, and maximum provenance. "
    "Topic nodes must be macro-relevant and correctly categorized. Relationships must be well-motivated. "
    "QA is simple and stateless: read tracker JSON, fetch referenced objects, judge decision quality, then pass "
    "or emit a crisp recommendation. "
    "Key modules and LLM touchpoints: "
    "graph_nodes/add_node.add_node (topic proposal & gating), "
    "graph_nodes/propose_new_topic_node.propose_topic_node (LLM proposal), "
    "graph_nodes/topic_relevance_gate.check_topic_relevance (LLM gate), "
    "graph_nodes/topic_category_classifier.classify_topic_category (LLM classifier), "
    "graph_nodes/topic_priority_classifier.classify_topic_importance (LLM ranking), "
    "graph_relationships/llm_select_one_new_link.llm_select_one_new_link (LLM link proposal), "
    "graph_relationships/llm_select_link_to_remove.llm_select_link_to_remove (LLM removal), "
    "graph_relationships/add_link.add_link (creation with dedup), graph_relationships/remove_link.remove_link (minimal removal), "
    "graph_relationships/get_existing_links.get_existing_links (snapshots), "
    "graph_articles/add_article.add_article (ingest + ABOUT logic), graph_articles/link_article (ABOUT edge helper), "
    "tracker/tracker.Tracker (generic event recorder), utils.load_article.load_article, "
    "graph_utils.get_node_by_id.get_node_by_id, utils.article_text_formatter.extract_text_from_json_article."
)

# Tailored guidance per action type (explicit checks tied to modules/functions)
ACTION_TYPE_GUIDE: Dict[str, str] = {
    "add_article": (
        "Verify macro relevance (no celebrity/noise). "
        "Ensure ABOUT edge logic adheres to rule: if article exists but not linked to topic, create ABOUT; skip only if ABOUT already exists; multiple topics allowed. "
        "Cross-check fields from utils.load_article.load_article and formatting via utils.article_text_formatter.extract_text_from_json_article. "
        "Require a clear priority/time-horizon rationale if present."
    ),
    "add_node": (
        "From graph_nodes/add_node.add_node and graph_nodes/propose_new_topic_node.propose_topic_node: "
        "- Name is atomic, human-readable, macro-relevant. "
        "- Category via graph_nodes/topic_category_classifier.classify_topic_category is one of {macro, asset, policy, geography, company} without sector leakage. "
        "- Relevance via graph_nodes/topic_relevance_gate.check_topic_relevance is affirmative with motivation. "
        "- Importance via graph_nodes/topic_priority_classifier.classify_topic_importance is coherent with article. "
        "- Uniqueness vs existing nodes; avoid dup aliases. Provide expected relationships plausibility."
    ),
    "add_relationship": (
        "From graph_relationships/add_link.add_link & llm_select_one_new_link.llm_select_one_new_link: "
        "- Motivation is specific and defensible (mechanistic/empirical). "
        "- candidate_ids, candidate_motivation, selection_motivation captured. "
        "- dedup_decision justified; no existing equivalent edge. "
        "- existing_links_before/after coherent; chosen type fits (INFLUENCES/PEERS/CORRELATES_WITH)."
    ),
    "remove_relationship": (
        "From graph_relationships/remove_link.remove_link & llm_select_link_to_remove.llm_select_link_to_remove: "
        "- Candidate set and prioritized_link selection is shown with motivations. "
        "- Avoids removing critical relationships; check degrees/importance if available. "
        "- Pre/post link snapshots align; user confirmation path respected."
    ),
}


def run_critic(
    *,
    project_summary: str,
    event_type: str,
    action_guide: str,
    event_inputs: str,
    event_details: str,
    article_text: str,
    start_node: str,
    end_node: str,
    extra_context: str,
):
    """
    Build the chain, invoke it with the provided context, and return the parsed dict
    with keys: status (pass|fail), motivation (string), recommendation (string).
    Fail-fast on invalid outputs.
    """
    template = """
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS QUALITY ASSURANCE CRITIC for the Saga Macro Graph.

PROJECT SUMMARY (MODULES/FUNCTIONS & LLM TOUCHPOINTS):
{project_summary}

ACTION TYPE: {event_type}
GUIDANCE (EXPLICIT CHECKLIST):
{action_guide}

EVENT INPUTS (IDs only):
{event_inputs}

EVENT DETAILS (LLM context and provenance):
{event_details}

FULL CONTEXT OBJECTS (send everything available without truncation):
- ARTICLE (formatted):
{article_text}

- START NODE (JSON):
{start_node}

- END NODE (JSON):
{end_node}

- EXTRA CONTEXT (JSON):
{extra_context}

AUDIT INSTRUCTIONS:
- Diagnose precisely: point to concrete fields or evidence that pass/fail the checklist. Reference functions/modules when relevant (e.g., add_node.add_node, classify_topic_category, llm_select_one_new_link).
- Be specific about what is missing or inconsistent (e.g., missing candidate_ids, weak selection_motivation, category=company for a product).
- If failing, propose actionable fixes that reference the exact module/function to change and the field to add/update in the tracker event.

REQUIRED OUTPUT FORMAT:
- Return a JSON object with at least the required keys below. Additional diagnostic keys are allowed and encouraged.
- Required keys:
  {{"status": "pass|fail", "motivation": "string", "recommendation": "string"}}
- Optional diagnostic keys (add only if helpful):
  {{
    "problem_locations": ["module:function", ...],
    "checks_failed": ["string", ...],
    "fields_missing": ["string", ...],
    "severity": "low|medium|high",
    "confidence": 0.0-1.0
  }}

YOUR JSON ONLY (no prose, no markdown):
"""
    prompt = PromptTemplate(
        input_variables=[
            "system_mission",
            "system_context",
            "project_summary",
            "event_type",
            "action_guide",
            "event_inputs",
            "event_details",
            "article_text",
            "start_node",
            "end_node",
            "extra_context",
        ],
        template=template,
    )
    llm = get_medium_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "project_summary": project_summary,
        "event_type": event_type,
        "action_guide": action_guide,
        "event_inputs": event_inputs,
        "event_details": event_details,
        "article_text": article_text,
        "start_node": start_node,
        "end_node": end_node,
        "extra_context": extra_context,
    })
    # log result
        
    # Fail-fast validation
    if not isinstance(result, dict):
        raise ValueError("Critic returned non-dict output")
    
    # if results has status and if status is pass, return result
    if result.get("status") == "pass":
        return result
    
    for k in ("status", "motivation", "recommendation"):
        if k not in result:
            raise ValueError(f"Critic output missing required key: {k}")
    status = str(result.get("status", "")).strip().lower()
    if status not in {"pass", "fail"}:
        raise ValueError("Critic status must be 'pass' or 'fail'")
    if status == "fail" and not result.get("recommendation"):
        raise ValueError("Critic 'fail' must include a recommendation")
    return result
