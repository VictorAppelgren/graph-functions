from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from src.llm.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.analysis.orchestration.analysis_rewriter import SECTION_FOCUS

from utils.app_logging import get_logger

logger = get_logger("generate_keywords_llm")


def _clean_list(items: List[str]) -> List[str]:
    """Normalize, dedupe, and drop overly long/joined phrases.
    - lowercase, strip
    - keep up to 3 words; drop items > 20 chars with no separators (likely joined junk)
    """
    seen = set()
    out: List[str] = []
    for x in items:
        s = str(x).strip().lower()
        if not s:
            continue
        # drop overly long joined tokens without spaces
        if len(s) > 20 and (" " not in s):
            continue
        # cap phrases to max 3 words
        if len(s.split()) > 3:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def generate_keywords(topic_name: str, section: str) -> List[str]:
    """Generate a flat list (target 25–35) of short newsroom-surface keywords for scanning news."""
    focus = SECTION_FOCUS[section]
    prompt_template = """
    {system_mission}
    {system_context}

    You are a lead macro/markets editor. Write a professional, research‑grade keyword checklist.

    PURPOSE (downstream matcher)
    - We scan concatenated text: title + summary/description + argos_summary, lowercased.
    - Matching is tolerant: spaces, hyphens, or slashes between tokens are treated as optional (e.g., eurusd ~= eur/usd ~= eur-usd ~= eur usd).
    - Each keyword counts at most once per article; duplicates don't add score.
    - An article becomes a candidate when it contains ≥ 3–4 DISTINCT keyword hits.
    - Your list should maximize recall of truly on‑topic articles while avoiding generic noise.

    TASK
    Return a single flat list of short newsroom‑surface keywords to find articles about "{topic_name}" in the "{section}" timeframe.
    These must be terms that realistically appear in headlines or summaries, pointing clearly toward the intended topic—neither generic nor overly narrow.

    QUALITY BAR
    - Prefer canonical market tokens, entities, policy names, indicators, and tradable instruments.
    - Avoid generic words with weak signal (e.g., "price", "market", "stocks", "update").
    - Heavily prefer single‑word action tokens and two‑word anchors; do NOT output three‑word event composites like "oil price slump".
    - Include common inflections as separate items when natural (e.g., decline/declined/declining; slump/slumps/slumped; drop/drops/dropped; fall/falls/fell).
    - Use standard 1–2 word forms; allow 3 words only if truly standardized (rare) and never for [anchor + action] blends.
    - Avoid long composites and joined variants (no "globalgdpgrowthslowdown"; no tailing "-structural").

    PATTERN EXAMPLES (illustrative, adapt to the actual topic)
    - If you would have written 3‑word phrases like "oil price decline" or "crude oil slump", instead produce:
      • two‑word anchors: "oil price", "crude oil", "brent", "wti"
      • single‑word actions: "decline", "drop", "fall", "slump", "dip", "slide", "selloff", "sell-off", "plunge", "tumble"
      • keep them as separate items in the list so any combination can trigger ≥3–4 distinct hits

    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    CRITICAL JSON FORMAT REQUIREMENTS - FAILURE TO FOLLOW EXACTLY WILL BREAK THE SYSTEM:
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    1. RETURN ONLY JSON - NO TEXT BEFORE OR AFTER
    2. NO MARKDOWN CODE FENCES (```) - JUST RAW JSON
    3. NO EXPLANATIONS, NO COMMENTS, NO ROLE LABELS
    4. EXACTLY ONE JSON OBJECT WITH EXACTLY ONE KEY CALLED "list"
    5. THE "list" KEY MUST CONTAIN AN ARRAY OF STRINGS
    6. USE DOUBLE QUOTES ONLY - NO SINGLE QUOTES
    7. NO TRAILING COMMAS ANYWHERE
    8. 15-40 ITEMS IN THE ARRAY
    9. ALL LOWERCASE STRINGS
    10. NO EMPTY STRINGS IN THE ARRAY

    CORRECT EXAMPLES:
    {{"list":["fed", "rate", "cut", "powell", "jackson hole", "september", "inflation", "unemployment", "policy", "dovish", "hawkish", "basis points", "federal reserve", "fomc", "meeting"]}}

    {{"list":["oil", "crude", "brent", "wti", "opec", "production", "inventory", "barrel", "energy", "petroleum", "refinery", "gasoline", "diesel", "pipeline", "drilling", "rig count", "shale", "fracking"]}}

    {{"list":["eurusd", "eur/usd", "euro", "dollar", "ecb", "fed", "draghi", "powell", "rate", "policy", "divergence", "parity", "forex", "currency", "exchange", "monetary", "stimulus", "tightening"]}}

    WRONG EXAMPLES (DO NOT DO THIS):
    ```json
    {{"list":["fed", "rate"]}}
    ```

    Here are some keywords for your topic: ["fed", "rate"]

    {{"list":["fed", "rate",]}}

    {{"list":['fed', 'rate']}}

    {{"list":[]}}

    topic: "{topic_name}"
    timeframe: "{section}"
    section focus: {focus}

    BUILD A PERFECT LIST FOR THIS TOPIC SO THAT 3-4 HITS STRONGLY IMPLY RELEVANCE.

    RESPOND WITH ONLY THE JSON OBJECT - NOTHING ELSE:
    """
    prompt = PromptTemplate(
        input_variables=[
            "topic_name",
            "section",
            "focus",
            "system_mission",
            "system_context",
        ],
        template=prompt_template,
    )
    logger.info("will generate keywords")
    llm = get_llm(ModelTier.SIMPLE)
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke(
        {
            "topic_name": topic_name,
            "section": section,
            "focus": focus,
            "system_mission": SYSTEM_MISSION,
            "system_context": SYSTEM_CONTEXT,
        }
    )
    logger.debug("------------------------------------")
    logger.debug("generated keywords: ")
    logger.info(f"{result}")
    logger.debug("------------------------------------")

    # Basic validation and error handling
    if not isinstance(result, dict) or "list" not in result:
        logger.error(f"Invalid LLM response format: {result}")
        return []

    list_result = result["list"]
    if not isinstance(list_result, list):
        logger.error(f"Expected list, got {type(list_result)}: {list_result}")
        return []

    try:
        cleaned = _clean_list(list_result)  # Fix: pass list_result, not result
        logger.info(
            f"Generated {len(cleaned)} keywords from {len(list_result)} raw keywords"
        )
        return cleaned[:40]
    except Exception as e:
        logger.error(f"Error cleaning keywords: {e}")
        return []
