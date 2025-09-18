find_topic_mapping_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC MAPPER for the NEO4j Graph.

        OVERVIEW:
        - Output exactly ONE flat JSON object with fields:
          'motivation' (string), 'existing' (array of IDs or null), 'new' (array of NAMES or null).
        - Prioritize 'existing'. Be generous with 'existing' suggestions.
        - Be conservative with 'new' (at most one), otherwise null.
        - Use IDs for 'existing' and NAMES for 'new'. No extra fields.

        EXISTING NODE NAMES AND IDS:
        {node_list}

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "Impact: FX; EUR/USD and Fed policy drive currency repricing.", "existing": ["eurusd", "fed_policy"], "new": null}}
        {{"motivation": "Impact: credit; Structured finance gap affects credit pricing.", "existing": null, "new": ["structured_finance"]}}
        {{"motivation": "Impact: rates; US inflation affects yields.", "existing": ["us_inflation"], "new": null}}
        {{"motivation": "Impact: none; No material mapping.", "existing": null, "new": null}}

        STRICT OUTPUT: Only the JSON object. No extra text.
        YOUR RESPONSE:
    """