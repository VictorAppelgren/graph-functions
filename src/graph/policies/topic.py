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
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.llm.sanitizer import run_llm_decision, CheckTopicRelevance, ClassifyTopicImportance, FilterInterestingTopics, ClassifyTopicCategory, TopicCategory
from src.llm.prompts.classify_topic_category import classify_topic_category_prompt
from src.llm.prompts.classify_topic_importance import classify_topic_importance_prompt
from src.llm.prompts.llm_filter_all_interesting_topics import llm_filter_all_interesting_topics_prompt
from src.graph.policies.priority import PRIORITY_POLICY

logger = get_logger(__name__)

def classify_topic_category(
    topic_id: str,
    topic_name: str,
    topic_type: str,
    motivation: str | None,
    article_summary: str = "",
) -> tuple[str, str]:
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        classify_topic_category_prompt).format(
            system_mission=SYSTEM_MISSION,
            topic_id=topic_id,
            topic_name=topic_name,
            topic_type=topic_type,
            motivation=motivation,
            categories=list[TopicCategory],
            summary=article_summary
        )

    r = run_llm_decision(chain=chain, prompt=p, model=ClassifyTopicCategory)

    return r.category, r.motivation


def llm_filter_all_interesting_topics(
    source_topic: dict, all_topics: list[dict]
) -> dict[str, str] | None:
    """
    Use LLM to filter all_topics down to plausible candidates for strong relationships.
    Returns a dict: { 'candidate_ids': list[str], 'motivation': str | None }
    """

    logger.debug("Prompt: %s", truncate_str(str(p), 100))
    llm = get_llm(ModelTier.SIMPLE_LONG_CONTEXT)
    all_names = [n["name"] for n in all_topics]
    name = source_topic["name"]
    parser = JsonOutputParser()
    chain = llm | parser

    p = PromptTemplate.from_template(
        llm_filter_all_interesting_topics_prompt).format(
            system_mission=SYSTEM_MISSION, 
            system_context=SYSTEM_CONTEXT,
            name=name,
            all_names=all_names)

    r = run_llm_decision(chain=chain, prompt=p, model=FilterInterestingTopics)

    if r.motivation and r.candidates:

        logger.info(f"LLM candidate shortlist motivation: {r.motivation}")
        candidate_names = r.candidates
        name_to_id = {n["name"]: n["id"] for n in all_topics}
        candidate_ids = [name_to_id[name] for name in candidate_names if name in name_to_id]
        logger.info(f"Candidate IDs after mapping: {candidate_ids}")
        return {"candidate_ids": candidate_ids, "motivation": r.motivation}
    else:
        return None


def classify_topic_importance(
    topic_name: str, topic_type: str = "", context: str = ""
) -> tuple[int | str, str] | None:
    
    policy_text = "\n".join(
    f"{lvl}: every {cfg['interval_seconds']}s | {cfg['label']} | {cfg['characteristics']}"
    for lvl, cfg in sorted(PRIORITY_POLICY.items())
    )

    logger.info("Classifying topic importance: input follows")
    logger.info("policy_text:\n%s", policy_text)
    logger.info("topic_name: %r", topic_name)
    logger.info("topic_type: %r", topic_type)
    logger.info("context: %r", truncate_str(context, 2000))
    llm = get_llm(ModelTier.MEDIUM)
    parser = JsonOutputParser()
    chain = llm | parser  # exact style match

    p = PromptTemplate.from_template(
        classify_topic_importance_prompt).format(
            system_mission=SYSTEM_MISSION,
            system_context=SYSTEM_CONTEXT,
            policy_text=policy_text,
            topic_name=topic_name,
            topic_type=topic_type,
            context=context
        )

    r = run_llm_decision(chain=chain, prompt=p, model=ClassifyTopicImportance)

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
