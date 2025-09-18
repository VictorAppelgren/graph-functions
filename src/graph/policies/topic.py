"""
Topic taxonomy classifier for proposed Topics.
- Adapts the style of graph_articles/category_identifier.py but for topics.
- Maps to one of: ["macro_driver","asset","policy","geography","company","industry_vertical","ambiguous"].
- Returns STRICT JSON object: {"category": str, "motivation": str}
"""

import json
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils.app_logging import get_logger
from utils.app_logging import truncate_str
from llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.sanitizer import run_llm_decision, CheckTopicRelevance, ClassifyTopicImportance, FilterInterestingTopics, ClassifyTopicCategory

logger = get_logger(__name__)

CATEGORIES = [
    "macro_driver",
    "asset",
    "policy",
    "geography",
    "company",
    "industry_vertical",
    "ambiguous",
]

prompt_template = """
{system_mission}

YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC TAXONOMY CLASSIFIER working on the Saga Graph—a trading-focused macro knowledge graph.

TASK:
- Classify the proposed topic into EXACTLY ONE of: {categories}
- Output ONLY a single JSON object with EXACTLY two fields:
    - 'category': one of {categories}
    - 'motivation': Short justification for the category (first field in the object)

STRICT RULES:
- "industry_vertical" = sectors/sub-sectors/operational niches (e.g., packaging, logistics, advertising, sterilized packaging).
- If the topic is not clearly a macro driver, asset, policy, geography, or company, choose "ambiguous".
- Be strict; quality over recall. If in doubt, do NOT place in macro/asset/policy/geography/company.
- Output STRICT JSON. NO arrays, NO extra fields, NO commentary.

TOPIC CANDIDATE:
- id: {topic_id}
- name: {topic_name}
- type: {topic_type}
- motivation: {motivation}

ARTICLE SUMMARY (optional context):
{summary}

EXAMPLE OUTPUT:
{{"motivation": "Rates policy anchor, impacts asset pricing.", "category": "macro_driver"}}

YOUR RESPONSE (STRICT JSON ONLY):
"""

prompt = PromptTemplate(
    input_variables=[
        "system_mission",
        "categories",
        "topic_id",
        "topic_name",
        "topic_type",
        "motivation",
        "summary",
    ],
    template=prompt_template,
)


def classify_topic_category(
    topic_id: str,
    topic_name: str,
    topic_type: str,
    motivation: str | None,
    article_summary: str = "",
):
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    r = run_llm_decision(chain=chain, parser=parser, model=ClassifyTopicCategory)

    result = chain.invoke(
        {
            "system_mission": SYSTEM_MISSION,
            "categories": ", ".join(CATEGORIES),
            "topic_id": topic_id or "",
            "topic_name": topic_name or "",
            "topic_type": topic_type or "",
            "motivation": motivation or "",
            "summary": article_summary or "",
        }
    )
   
    return r.category, r.motivation



# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    demo = classify_topic_category(
        topic_id="us_inflation",
        topic_name="US Inflation",
        topic_type="macro",
        motivation="Inflation drives monetary policy and market pricing.",
        article_summary="US CPI rises above expectations; markets reprice Fed path.",
    )
    print(demo)


def llm_filter_all_interesting_topics(
    source_topic: dict, all_topics: list[dict]
) -> dict:
    """
    Use LLM to filter all_topics down to plausible candidates for strong relationships.
    Returns a dict: { 'candidate_ids': list[str], 'motivation': str | None }
    """
    
    prompt = f"""
    {SYSTEM_MISSION}
    {SYSTEM_CONTEXT}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - Given the source topic below and a list of all topics (names only), select all topics that could plausibly be strong INFLUENCES, CORRELATES_WITH, or PEERS to the source.
    - Only select topics where a strong, direct, or competitive relationship is possible.
    - Output a JSON object with two fields: 'motivation' (1-2 sentences, required, first field, justifying your shortlist) and 'candidates' (list of topic names). If none are plausible, output an empty list for 'candidates'.
    - ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN CANDIDATES. NO ADDITIONAL TEXT. STRICT JSON FORMAT.

    EXAMPLE OUTPUT:
    {{"motivation": "These topics are the most likely strong peers or influences based on the source topic\'s domain.", "candidates": ["EURUSD", "ECB Policy", "US Inflation"]}}

    SOURCE TOPIC:
    {name}

    ALL TOPICS:
    {all_names}

    YOUR RESPONSE IN JSON:
    """

    logger.debug("Prompt: %s", truncate_str(str(prompt), 100))
    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
    all_names = [n["name"] for n in all_topics]
    name = source_topic["name"]
    chain = llm | JsonOutputParser()

    r = run_llm_decision(chain=chain, prompt=prompt, model=FilterInterestingTopics)

    if r.motivation and r.candidates:

    logger.info(f"LLM candidate shortlist motivation: {motivation}")
    candidate_names = result.get("candidates", []) if isinstance(result, dict) else []
    name_to_id = {n["name"]: n["id"] for n in all_topics}
    candidate_ids = [name_to_id[name] for name in candidate_names if name in name_to_id]
    logger.info(f"Candidate IDs after mapping: {candidate_ids}")
    return {"candidate_ids": candidate_ids, "motivation": motivation}


policy_text = "\n".join(
    f"{lvl}: every {cfg['interval_seconds']}s | {cfg['label']} | {cfg['characteristics']}"
    for lvl, cfg in sorted(PRIORITY_POLICY.items())
)

template = PromptTemplate(
    template="""
{system_mission}
{system_context}

YOU ARE A MASTER-LEVEL MACRO ECONOMIST AND PORTFOLIO STRATEGIST for the Saga Graph.

TASK:
- Assign an 'importance' integer in [1..5] to the given Topic.
- Use this policy (no defaults, no hedging):
{policy_text}

TYPE GUIDANCE (not absolute, but strong):
- macro, currency, commodity, asset are usually 1.
- index, theme, driver are usually 2.
- company is usually 3.
- policy, event, sector, supporting, structural, geography are usually 4.
- Assign an importance rating based on best judgment, even if context is limited.

HARD RULES:
- Output STRICT JSON with fields: importance (1..5 or "REMOVE"), rationale (string).
- importance=5 is RESERVED for legitimate structural macro anchors (slow-moving, foundational drivers) — not a catch‑all for uncertainty.
- Use importance="REMOVE" whenever the topic does NOT contribute to macro/markets understanding or actionable trading decisions (e.g., celebrity/entertainment, pop culture, general crime/legal gossip, memes, local human‑interest with no market link).
- If inputs are insufficient AND the topic appears non‑market/irrelevant, prefer importance="REMOVE". Only default to a numeric importance when it is a legitimate market topic.

TOPIC:
- name: {topic_name}
- type: {topic_type}
- context: {context}

WARNING! Some bad data has made it into the graph.
If something is clearly misclassified or irrelevant to markets (e.g., celebrities, entertainment casting, sports injuries with no market linkage, local traffic/incidents), output importance="REMOVE".
Do NOT use 5 as a dump bin. 5 should reflect genuine structural macro anchors (e.g., demographics trend, secular policy regime, long‑run productivity trajectory).

THE MORE IT HELPS US UNDERSTAND THE FINANCIAL MARKET AND MAKE TRADES, THE HIGHER THE IMPORTANCE.
IF IT DOES NOT SUPPORT ACTIONABLE FINANCIAL DECISIONS, PREFER importance="REMOVE".

RETURN STRICT JSON ONLY. ONLY TWO FIELDS: importance (1..5 or "REMOVE") and rationale (string).
""",
    input_variables=[
        "system_mission",
        "system_context",
        "policy_text",
        "topic_name",
        "topic_type",
        "context",
    ],
)


def classify_topic_importance(
    topic_name: str, topic_type: str = "", context: str = ""
) -> tuple[int | str, str] | None:
    logger.info("Classifying topic importance: input follows")
    logger.info("policy_text:\n%s", policy_text)
    logger.info("topic_name: %r", topic_name)
    logger.info("topic_type: %r", topic_type)
    logger.info("context: %r", truncate_str(context, 2000))
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser  # exact style match

    r = run_llm_decision(chain=chain, prompt=template.format(), model=ClassifyTopicImportance)

    logger.info("Importance classification result: %s", r)
    # Expected: {"importance": 1..5, "rationale": "..."} or null importance
    if r.importance and r.rationale:
        return r.importance, r.rationale
    else:
        return None


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
- Topic must be atomic, human-readable, and non-duplicative with existing macro/asset anchors.
 - Minimal recall nudge: If there is any real, explicit trading relevance to our main interests (clear channel to pricing/liquidity/volatility) and the topic is a canonical asset/policy or macro transmitter, prefer should_add=true.
"""


def check_topic_relevance(
    topic_id: str,
    topic_name: str,
    topic_type: str,
    motivation: str | None,
    article_summary: str = "",
    context: str = "",
) -> tuple[bool, str]:
    """Return a dict with keys: should_add(bool), motivation(str)"""
    logger.info("Running topic relevance gate for: %r (%s)", topic_name, topic_type)

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
        """
    
    prompt = PromptTemplate.from_template(template)
    formatted = prompt.format(
    system_mission=SYSTEM_MISSION,
    system_context=SYSTEM_CONTEXT,
    relevance_policy=RELEVANCE_POLICY,
    topic_id=topic_id,
    topic_name=topic_name,
    topic_type=topic_type,
    motivation=motivation,
    article_summary=article_summary,
    context=context,
)
    
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = llm | parser

    res = run_llm_decision(chain=chain, prompt=formatted, model=CheckTopicRelevance, logger=logger)

    logger.info("Relevance gate result: %s", res)
    should_add = res.should_add
    motivation_for_relevance = res.motivation
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
