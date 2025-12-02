"""
Topic Mapper - LLM Prompt

MISSION: Map user's strategy to relevant graph topics.
"""

TOPIC_MAPPER_PROMPT = """
You are an expert financial analyst mapping user strategies to market topics.

USER ASSET: {asset_text}

USER STRATEGY:
{strategy_text}

USER POSITION:
{position_text}

AVAILABLE TOPICS (id | name):
{topics_list}

TASK: Identify the most relevant topics for analyzing this strategy.

SELECTION CRITERIA:
1. PRIMARY TOPICS (6-10): Direct assets AND closely related instruments
   - Core assets: Exact matches to user's description
   - Related indices: If user mentions "US market", include SPX, NDX, DJI, Russell 2000
   - Sector exposure: If broad market, include key sector indices (XLK, XLF, XLE, XLV)
   - Regional variants: If international, include regional indices (SX5E, DAX, FTSE)
   - Volatility: Include VIX for equity strategies
   - Currency pairs: Include base and quote currencies, plus related crosses
   - Be EXPANSIVE but stay under 10 topics - quality over quantity

2. DRIVER TOPICS (4-8): Macro/policy factors that drive the primary assets
   - Central bank policy (FED_POLICY, ECB_POLICY, etc.)
   - Economic themes (inflation, growth, employment)
   - Structural factors user mentioned
   - Second-order drivers (what drives the drivers)
   - Transmission mechanisms (how drivers affect primary assets)

3. Prioritize topics with clear transmission mechanisms to user's thesis

EXAMPLES:

Example 1:
User Asset: "Overall US market"
Primary Topics: ["spx", "ndx", "dji", "russell_2000", "xlk", "xlf", "xle", "vix"]
Driver Topics: ["fed_policy", "us_inflation", "us_core_pce", "ust10y", "us_corporate_earnings"]
Reasoning: Broad market exposure requires major indices + key sectors + volatility + macro drivers

Example 2:
User Asset: "EURUSD"
Primary Topics: ["eurusd", "dxy", "eur", "usd", "eurgbp", "eurjpy"]
Driver Topics: ["fed_policy", "ecb_policy", "us_inflation", "eurozone_inflation"]
Reasoning: Direct pair + components + related crosses + central bank policies

Example 3:
User Asset: "Fed policy impact on bonds"
Primary Topics: ["fed_policy", "ust10y", "ust2y", "ust5y", "ust30y", "tips"]
Driver Topics: ["us_inflation", "us_core_pce", "us_unemployment", "fed_balance_sheet"]
Reasoning: Policy topic + full yield curve + inflation protection + employment data

Example 4:
User Asset: "Tech stocks"
Primary Topics: ["ndx", "xlk", "aapl", "msft", "nvda", "googl", "meta"]
Driver Topics: ["fed_policy", "ust10y", "us_inflation", "ai_theme", "tech_regulation"]
Reasoning: Tech index + key tech stocks + rate sensitivity + thematic drivers

OUTPUT JSON (use exact topic IDs from list above):
{{
  "primary_topics": ["topic_id_1", "topic_id_2", ...],
  "driver_topics": ["topic_id_3", "topic_id_4", ...],
  "reasoning": "Brief explanation of topic selection and relevance to user's thesis"
}}

CRITICAL RULES:
1. ONLY use topic IDs from the AVAILABLE TOPICS list above
2. DO NOT invent or abbreviate topic IDs
3. DO NOT use placeholder IDs like 'x', 'topic1', etc.
4. If unsure about a topic ID, skip it - better to have fewer topics than invalid ones
5. Every topic ID must be an EXACT match from the list
"""
