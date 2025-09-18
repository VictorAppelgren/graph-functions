llm_filter_all_interesting_topics_prompt = """
    {system_mission}
    {system_context}

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