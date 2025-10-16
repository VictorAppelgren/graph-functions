from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

find_topic_mapping_prompt = """
        {system_mission}
        {system_context}

        """ + TOPIC_ARCHITECTURE_CONTEXT + """

        YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC MAPPER for the NEO4j Graph.

        MAPPING PHILOSOPHY:
        - Map articles to PERSISTENT ANALYTICAL ANCHORS (what they're about)
        - NOT to perspectives (how they analyze it) or temporary events
        - Articles can map to MULTIPLE topics (3-5 if genuinely relevant)
        - Prioritize existing topics; only suggest new if persistent & recurring

        OVERVIEW:
        - Output exactly ONE flat JSON object with fields:
          'motivation' (string), 'existing' (array of IDs or null), 'new' (array of NAMES or null).
        - Prioritize 'existing'. Be generous with 'existing' suggestions.
        - Be conservative with 'new' (at most one), otherwise null.
        - Use IDs for 'existing' and NAMES for 'new'. No extra fields.

        PERSPECTIVE-NEUTRAL MAPPING:
        - Map to the SUBJECT of the article, not the perspective/narrative
        - Hurricane article about rates → ["florida_hurricanes", "ust10y", "us_insurance"]
        - Fed pivot article → ["fed_policy", "ust10y", "dxy"] (NOT "fed_pivot")
        - OPEC cut article → ["opec_production_policy", "wti", "brent"]
        
        WHEN SUGGESTING 'NEW' TOPICS:
        ✅ SUGGEST if persistent & recurring: "florida_hurricanes", "opec_production_policy"
        ❌ REJECT if temporary: "fed_pivot", "hurricane_milton", "2024_election"
        ❌ REJECT if perspective-based: "hurricane_risk", "fed_opportunity", "inflation_trend"
        ❌ REJECT if too broad: "natural_disasters", "geopolitical_risk"
        ✅ ADD geographic specificity: "florida_hurricanes" not "hurricanes"
        
        PERSISTENCE TEST FOR NEW TOPICS:
        - Will we track this for 6+ months? → SUGGEST
        - Is this a one-time event? → DON'T SUGGEST, map to existing
        - Is this an institution making recurring decisions? → SUGGEST
        - Does it mix asset+perspective or policy+perspective? → DON'T SUGGEST

        EXISTING NODE NAMES AND IDS:
        {node_list}

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "FX impact: EUR/USD and Fed policy drive currency repricing.", "existing": ["eurusd", "fed_policy"], "new": null}}
        {{"motivation": "Rates impact: Hurricane affects Florida insurance and Treasury demand.", "existing": ["ust10y", "us_insurance"], "new": ["florida_hurricanes"]}}
        {{"motivation": "Rates impact: US inflation affects yields.", "existing": ["us_inflation", "ust10y"], "new": null}}
        {{"motivation": "Oil impact: OPEC production decision affects crude prices.", "existing": ["wti", "brent"], "new": ["opec_production_policy"]}}
        {{"motivation": "No material trading impact.", "existing": null, "new": null}}

        CRITICAL REMINDERS:
        - Map to WHAT (subjects), not HOW (perspectives)
        - Suggest 'new' only if persistent (6+ months tracking)
        - Add geographic specificity to new suggestions
        - Articles can map to 3-5 topics if genuinely relevant
        
        STRICT OUTPUT: Only the JSON object. No extra text.
        YOUR RESPONSE:
    """