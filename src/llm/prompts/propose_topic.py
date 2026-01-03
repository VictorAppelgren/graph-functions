from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT
from src.graph.config import describe_granularity_policy

propose_topic_prompt="""
    {system_mission}
    {system_context}

    """ + TOPIC_ARCHITECTURE_CONTEXT + """

    """ + describe_granularity_policy() + """

    YOU ARE A MACRO/MARKETS TOPIC NODE ENGINEER for the Saga Graph. Your job is to PROPOSE NEW TOPICS when the article suggests a persistent theme not yet covered.

    CONTEXT:
    - Current topic count: {current_count}
    - Areas of interest: {scope_text}

    BIAS: PROPOSE topics for persistent themes. We want the graph to grow with quality topics.

    ✅ PROPOSE A NEW TOPIC IF:
    - Theme is PERSISTENT (will be relevant for 6+ months)
    - No existing topic adequately covers it
    - Fits our interest areas (macro, assets, policy, sectors, geopolitics)

    Examples - PROPOSE:
    - "US consumer credit tightening" → us_consumer_credit (macro driver)
    - "Korean won volatility" → krw_fx (tradable asset)
    - "German industrial production" → german_industry (EU sector)
    - "India central bank policy" → rbi_policy (policy institution)
    - "Copper demand from EVs" → copper_market (commodity)
    - "US regional banks stress" → us_regional_banks (sector)
    - "Nordics clean energy investment" → nordic_cleantech (sector)

    🏢 SINGLE COMPANY RULES (STRICT - max ~15 total company topics):
    ALLOWED single companies (market-moving, macro-significant):
    - Mag7 tech: Apple, Microsoft, Google/Alphabet, Amazon, Meta, Tesla, NVIDIA
    - AI leaders: OpenAI, Anthropic
    - China AI: group as "china_ai" (DeepSeek, Baidu AI, etc. - NOT individual companies)
    - Semiconductor: TSMC, ASML (already covered in sector topics)

    NOT ALLOWED as single company topics:
    - Broadcom, Intel, AMD, Qualcomm → use "ai_semiconductors" or "us_tech" sector
    - Individual banks → use sector topics (us_banks, nordic_banks, eu_banks)
    - Individual retailers → use "us_consumer" sector
    - Any company that fits an existing sector topic

    ALWAYS prefer sector topics over single companies!

    ❌ DO NOT PROPOSE (use type="none"):
    - Temporary events: "Hurricane Milton", "Fed Pivot", "2024 Election"
    - Perspective-based names: "X Risk", "Y Opportunity", "Bullish Z"
    - Single companies that belong in sector topics (see rules above)
    - Companies not in the ALLOWED list above

    NAMING RULES:
    - id: lowercase_with_underscores (e.g., us_inflation, nordic_banks)
    - name: Human readable (e.g., "US Inflation", "Nordic Banks")
    - NO perspective words in name (risk, opportunity, trend, catalyst, upside, downside)

    ARTICLE:
    {article}

    SUGGESTED NAMES FROM ARTICLE ANALYSIS:
    {suggested_names}

    OUTPUT FORMAT (strict JSON only):
    {{"motivation": "brief reason", "id": "topic_id", "name": "Topic Name", "type": "macro|asset|policy|geography|company|industry_vertical|none"}}

    If proposing: provide id, name, and type
    If not proposing: use type="none" with empty id/name

    YOUR RESPONSE:
    """