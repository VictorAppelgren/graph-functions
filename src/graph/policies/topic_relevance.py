# graph_nodes/topic_relevance_gate.py
"""
LLM-based trading relevance gate for proposed Topic nodes.
- Input fields come directly from propose_new_topic_node: id, name, type, motivation
- Also takes optional article_summary/context for additional judgment
- Returns STRICT JSON: {"should_add": bool, "motivation": str}

Design goals: minimal, fail-fast, reusable (pre-insert and for cleanup scripts).
"""
from llm.llm_router import get_simple_llm
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = app_logging.get_logger(__name__)

RELEVANCE_POLICY = """
ALLOWED (must clearly support trading decisions):
- macro drivers (inflation, growth, jobs, rates, credit, trade, fiscal)
- tradable assets/instruments (FX pairs, indices, commodities, rates, bonds)
- macro policy/regulation regimes (central banks, fiscal/tariffs with market impact)
- geographies at macro level (countries/regions) when used as macro anchors

REJECT (do not add as topics):
- industry verticals or operational niches (e.g., sterilized packaging, logistics, advertising)
- product categories, vendor lists, micro supply chain segments, marketing/HR/operations
- vague/general groups, ambiguous or non-atomic concepts not defensible to a macro analyst

PRINCIPLES:
- Topic must help understand markets or make/plan trades.
- If unsure, REJECT. Be strict; quality over recall.
- Node must be atomic, human-readable, and non-duplicative with existing macro/asset anchors.
 - Minimal recall nudge: If there is any real, explicit trading relevance to our main interests (clear channel to pricing/liquidity/volatility) and the topic is a canonical asset/policy or macro transmitter, prefer should_add=true.
"""

template = PromptTemplate(
    template="""
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS MACRO/MARKETS RELEVANCE GATE for the Saga Graph (Neo4j-based, trading-focused).
Decide if the proposed Topic is suitable for a trading-focused macro knowledge graph.

RELEVANCE POLICY (STRICT):
{relevance_policy}

INPUTS:
- topic_id: {topic_id}
- topic_name: {topic_name}
- topic_type: {topic_type}
- motivation: {motivation}
- article_summary: {article_summary}
- context: {context}

OUTPUT STRICT JSON ONLY with EXACT fields:
{{
  "should_add": true|false,
  "motivation": "short, specific, research-grade justification",
}}
No extra fields. No commentary. If unsure, set should_add=false with a clear motivation.
""",
    input_variables=[
        "system_mission",
        "system_context",
        "relevance_policy",
        "topic_id",
        "topic_name",
        "topic_type",
        "motivation",
        "article_summary",
        "context",
    ],
)

def check_topic_relevance(
    topic_id: str,
    topic_name: str,
    topic_type: str,
    motivation: str,
    article_summary: str = "",
    context: str = "",
) -> dict:
    """Return a dict with keys: should_add(bool), motivation(str)"""
    logger.info("Running topic relevance gate for: %r (%s)", topic_name, topic_type)
    llm = get_simple_llm()
    parser = JsonOutputParser()
    chain = template | llm | parser  # exact style match
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "relevance_policy": RELEVANCE_POLICY,
        "topic_id": topic_id or "",
        "topic_name": topic_name or "",
        "topic_type": topic_type or "",
        "motivation": truncate_str(motivation or "", 800),
        "article_summary": truncate_str(article_summary or "", 1200),
        "context": truncate_str(context or "", 1200),
    })
    logger.info("Relevance gate result: %s", result)
    should_add = result["should_add"]
    motivation_for_relevance = result["motivation"]
    return should_add, motivation_for_relevance

# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    demo = check_topic_relevance(
        topic_id="us_inflation",
        topic_name="US Inflation",
        topic_type="macro",
        motivation="Inflation drives monetary policy and rates, impacting risk assets.",
        article_summary="US CPI rises above expectations; markets reprice Fed path.",
    )
    print(demo)
