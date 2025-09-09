"""
LLM-driven wide query generation for a new node/topic.
"""
from typing import Dict
from src.llm.llm_router import get_medium_llm
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from utils import app_logging
from utils.app_logging import truncate_str
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT

logger = app_logging.get_logger(__name__)

def create_wide_query(article_text: str) -> dict:
    """
    Uses LLM to generate a wide boolean search query for a given article/topic, based on formatted article text.
    Returns a dict with 'motivation' and 'query' keys containing the string.
    """
    logger.info("Generating wide query from article text for node/topic")
    llm = get_medium_llm()
    parser = JsonOutputParser()
    prompt_template = """
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS MACRO/MARKETS BOOLEAN QUERY ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics. This system is used for high-stakes investment research and analytics. Every node is a specific, atomic, user-defined anchor (never a general group, catch-all, or ambiguous entity). Your output will be used for downstream graph analytics, LLM reasoning, and expert decision-making.

TASK:
- Given the article text below, generate a wide, robust boolean search query string that would capture all relevant articles for this topic in a research database.
- Output a JSON object with:
    - 'motivation' (required, first field): A short, specific, research-grade reasoning (1-2 sentences max) justifying why this query is constructed this way. Motivation must be actionable, defensible to a top-tier financial analyst, and maximally useful for graph analytics and LLM reasoning.
    - 'query': the boolean query string.
- If no good query can be constructed, output null.
- Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields. If unsure, output null.

ARTICLE TEXT:
- Should capture all relevant synonyms, tickers, and related terms
- Must be strictly relevant to the article and node context

The query should:
- Cover all relevant synonyms, abbreviations, and related terms for the topic.
- Include both common and technical language, plurals, and case variants.
- Include relevant financial, economic, and news-related context (e.g., 'news', 'analysis', 'trend', 'market', etc.).
- Use wide boolean OR logic, grouping related terms in parentheses.
- Be robust enough to capture all relevant articles about the topic, without being too broad.

ARTICLE:
{article_text}

TWO EXAMPLES OF OUTPUT:
{{"query": "(EURUSD OR EURUSD) OR (euro OR Euro* OR EUR OR eur*) OR (dollar OR Dollar* OR USD OR usd*) OR (exchange OR rate OR currency OR currencies OR forex OR foreign OR market OR markets) OR (inflation OR inflat* OR interest OR rate OR rates OR monetary OR policy OR central OR bank OR ECB OR Fed OR economic OR economy OR growth OR GDP OR recession OR recovery) OR (news OR update OR breaking OR recent OR latest OR today OR report OR analysis OR forecast OR outlook OR trend OR movement OR volatility OR fluctuation OR change OR shift OR impact) OR (trade OR trades OR trading OR trader OR speculation OR speculator OR investment OR investor OR hedge OR hedging OR position OR positioning) OR (geopolitical OR political OR event OR events OR risk OR risks OR sentiment OR sentiment* OR confidence OR uncertainty OR crisis OR crises OR development OR developments)"}}

{{"query": "(AI_data_centers OR AI_data_centers* OR artificial intelligence data centers OR AI infrastructure OR AI computing facilities OR AI server farms OR AI cloud OR AI hosting OR AI storage) OR (investment OR investments OR funding OR fund* OR financing OR capital OR venture OR back* OR raise* OR round OR acquisition OR buyout OR partnership OR joint venture OR expansion OR growth OR development OR market OR markets OR opportunity OR opportunities OR entry OR launch OR build OR construction OR establish OR establish*) OR (news OR recent OR latest OR breaking OR break* OR today OR update OR announcement OR report OR release OR insight OR analysis OR trend OR trends OR forecast OR outlook OR overview) OR (data center OR data centers OR datacenter OR datacenters OR colocation OR colocation centers OR edge computing OR cloud computing OR hyperscale OR server OR servers OR infrastructure OR facility OR facilities OR network OR networks)"}}

NOTHING MORE THAN THE QUERY FIELD

YOUR RESPONSE IN JSON:
"""
    logger.debug("PromptTemplate: %s", truncate_str(str(prompt_template), 100))
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm | parser
    result = chain.invoke({
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
        "article_text": article_text,
    })
    logger.info(f"LLM query result: {result}")
    return result
