"""
LLM-driven helper to decide if a new article should replace an existing one for a topic node.
Returns a dict with 'motivation' and 'id_to_replace'.
"""
from typing import List, Dict, Optional
from model_config import get_medium_llm
from langchain_core.output_parsers import JsonOutputParser
from utils import logging
from utils.logging import truncate_str
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = logging.get_logger(__name__)

# Per-timeframe policy (simple defaults)
MIN_PER_TIMEFRAME = 5
MAX_PER_TIMEFRAME = 10

def does_article_replace_old_llm(
    new_article_summary: str,
    existing_articles: List[Dict],
    test: bool = False,
    decision_instruction: str = "",
    context_text: Optional[str] = None,
) -> Dict:
    """
    Uses LLM to decide if the new article replaces any existing article for the topic.
    Each existing article is a dict with 'id' and 'argos_summary'.
    Returns a dict: {'motivation': str, 'tool': str, 'id': str or None}
    """
    if test:
        return {'motivation': 'Test mode: no action.', 'tool': 'none', 'id': None}
    llm = get_medium_llm()
    parser = JsonOutputParser()
    summaries = "\n".join([f"- {a['id']}: {a.get('argos_summary', '')}" for a in existing_articles])
    allowed_ids_str = ", ".join([a['id'] for a in existing_articles])
    context_block = f"\nOTHER TIMEFRAMES CONTEXT (read-only, do not act on these):\n{context_text}\n" if context_text else ""
    prompt = f"""
{SYSTEM_MISSION}
{SYSTEM_CONTEXT}

YOU ARE A WORLD-CLASS MACRO/MARKETS ARTICLE LIFECYCLE JUDGE for the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

TASK:
- Given the summary of a new article and all current articles for this topic (with their IDs and summaries), output a strict JSON object with THREE fields:
    - 'motivation' (required, first field): A short, specific, research-grade reasoning (1-2 sentences max) justifying your action. Motivation must be actionable, defensible to a top-tier financial analyst, and maximally useful for graph analytics and LLM reasoning.
    - 'tool': one of 'remove', 'hide', 'lower_priority', or 'none'.
    - 'id': the ID of the article to act on (or null if none).
- You may only ever act on one article per call. If no action is needed, use 'none' and null for id.
- Internally, reason as a top-tier financial analyst and knowledge engineer. Imagine you must defend every decision to a domain expert.
- Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields.

CONSTRAINTS:
- Allowed tools: remove | hide | lower_priority | none
- Choose 'id' ONLY from the Allowed IDs list below; otherwise set id to null.

DECISION INSTRUCTION:
{decision_instruction}

NEW ARTICLE SUMMARY:
{new_article_summary}

EXISTING ARTICLES:
{summaries}

ALLOWED IDS:
{allowed_ids_str}

{context_block}

EXAMPLES OF OUTPUT:
{{"motivation": "The new article is more comprehensive and up-to-date than article a123.", "tool": "remove", "id": "a123"}}
{{"motivation": "Article a124 is now less relevant, so its priority should be lowered.", "tool": "lower_priority", "id": "a124"}}
{{"motivation": "Article a125 is outdated and should be hidden.", "tool": "hide", "id": "a125"}}
{{"motivation": "The new article does not provide additional value over existing articles.", "tool": "none", "id": null}}

ONLY INCLUDE THE MOTIVATION, TOOL, AND ID FIELDS. NO ADDITIONAL TEXT. STRICT JSON FORMAT.

YOUR RESPONSE:
"""
    logger.debug("Prompt: %s", truncate_str(str(prompt), 120))
    chain = llm | parser
    result = chain.invoke(prompt)
    #logger.info(f"LLM article lifecycle result: {result}")
    return result
