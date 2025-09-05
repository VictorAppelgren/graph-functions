from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from model_config import get_simple_long_context_llm
from argos_description import SYSTEM_MISSION, SYSTEM_CONTEXT
from utils.minimal_logging import get_logger

logger = get_logger(__name__)

def find_node_mapping(article_text: str, node_list: list):

    # preview of the summary
    logger.info(f"Article text: {article_text[:200]}{'...' if len(article_text) > 200 else ''}")
    logger.info(f"Node list length: {len(node_list)}")

    prompt_template = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC MAPPER for the NEO4j Graph of the world. Nodes/ topics are specific, atomic, user-defined anchors. Your output drives graph analytics and trading research.

        OVERVIEW:
        - Output exactly ONE flat JSON object with fields: 'motivation' (string), 'existing' (array of IDs or null), 'new' (array of NAMES or null).
        - Prioritize 'existing'. Be generous with 'existing' suggestions! We want all topics that are affected by this article. 
        - Be much more limited with 'new' suggestions, only if really needed should you mention new, otherwise set it to null. And only returns some existing nodes that are affected.
        - Use IDs for 'existing' and NAMES for 'new'. No extra fields.

        EXISTING NODE NAMES AND IDS:
        {node_list}

        CONSTRAINTS FOR "new" (macro/trading only — be conservative):
        1) Default to none: set "new": null unless ALL are true:
           (a) Existing IDs don’t cover the core topic,
           (b) The topic is directly tradeable/used in trading,
           (c) You can name an immediate market-impact channel.
        2) Allowed archetypes (examples): macro indicators (CPI/GDP/jobs/PMIs); policy/CB (Fed/ECB/YCC/QE/QT); asset classes/instruments (EURUSD, US 10Y, WTI, IG/HY spreads); market structure/regimes (liquidity, vol regime, curve shape); broad sector exposures (e.g., US homebuilders, global energy).
        3) Excluded (unless tied to an immediate index/sector/FX/rates impact): companies/products/startups; medical/biotech (drugs/therapies/devices/trials); niche tech/academic ideas; local micro events.
        4) Motivation format: begin with "Impact: <rates|FX|equities|commodities|credit|liquidity>; ..." If no credible channel, set "new": null.
        5) Scarcity: at most one item in "new". If in doubt, use null.
        6) Existing-over-new: if existing IDs cover ≥80% of the article’s core topic, set "new": null.
        Recall nudge (minimal): If a clear canonical market anchor/policy handle or market transmitter with real trading relevance to our main interests is missing from "existing", you MAY include exactly one item in "new" (prefer canonical/desks-traded forms; allow market plumbing with explicit price/liquidity/volatility channels).

        QUALITY BAR:
        - Motivation: 1–2 sentences, research-grade, defensible to a top-tier macro analyst.
        - Final check: would a world-class macro analyst accept this mapping?

        MENTION ALL NODES THAT ARE RELATED TO THE ARTICLE. ALMOST NEVER LEAVE "existing": null.
        If no "existing" matches but there is a clear canonical market anchor with real trading relevance to our main interests, set "new" to that single anchor.

        FOR EXISTING NODES YOU MUST USE THE ID, NOT THE NAME
        FOR NEW SUGGESTIONS YOU MUST USE THE NAME, IT WILL NOT HAVE AN ID

        ARTICLE TEXT:
        {article_text}

        EXAMPLES OF OUTPUT:
        {{"motivation": "Impact: FX; EUR/USD and Fed policy drive currency repricing.", "existing": ["eurusd", "fed_policy"], "new": null}}
        {{"motivation": "Impact: credit; Structured finance gap affects credit pricing.", "existing": null, "new": ["structured_finance"]}}
        {{"motivation": "Impact: rates; US inflation and supply chains affect yields.", "existing": ["us_inflation"], "new": ["supply_chain_disruption"]}}
        {{"motivation": "Impact: none; No material mapping.", "existing": null, "new": null}}

        Strict output rules:
        - Return ONLY the JSON object. No markdown, headers, commentary, or extra text before/after.

        YOUR RESPONSE:
    """
    prompt = PromptTemplate.from_template(prompt_template)
    llm = get_simple_long_context_llm()
    parser = JsonOutputParser()
    chain = prompt | llm | parser
    result = chain.invoke({
        "article_text": article_text,
        "node_list": node_list,
        "system_mission": SYSTEM_MISSION,
        "system_context": SYSTEM_CONTEXT,
    })
    
    #logger.info("----- results node identifier: ------")
    #logger.info(result)
    #logger.info("----- end results node identifier ------")

    if isinstance(result, str):
        import json
        result = json.loads(result)
    motivation = result.get('motivation', '')
    existing = result.get('existing')
    new = result.get('new')

    # Enforce: must be lists, never None
    if existing is None:
        existing = []
    elif not isinstance(existing, list):
        existing = [existing]
    if new is None:
        new = []
    elif not isinstance(new, list):
        new = [new]

    return motivation, existing, new


# ----- SIMPLE MAIN TO TEST -----
if __name__ == "__main__":
    # Fake data for quick test
    article = {"data": {"article_text": "US inflation surged to a 40-year high in June, affecting bond yields."}}
    node_list = ["us_inflation", "us_bond_yields", "us_gdp", "us_interest_rates", "us_unemployment", "eurusd", "structured_finance", "eur_inflation", "eur_bond_yields", "eur_gdp", "eur_interest_rates", "eur_unemployment", "gbp_inflation", "gbp_bond_yields", "gbp_gdp", "gbp_interest_rates", "gbp_unemployment", "jpy_inflation", "jpy_bond_yields", "jpy_gdp", "jpy_interest_rates", "jpy_unemployment", "aud_inflation", "aud_bond_yields", "aud_gdp", "aud_interest_rates", "aud_unemployment", "cad_inflation", "cad_bond_yields", "cad_gdp", "cad_interest_rates", "cad_unemployment", "chf_inflation", "chf_bond_yields", "chf_gdp", "chf_interest_rates", "chf_unemployment", "nzd_inflation", "nzd_bond_yields", "nzd_gdp", "nzd_interest_rates", "nzd_unemployment"]
    motivation, existing, new = find_node_mapping(article, node_list)
    print("Motivation:", motivation)
    print("Existing:", existing)
    print("New:", new)