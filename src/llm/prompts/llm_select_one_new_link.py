llm_select_one_new_link_prompt = """
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics.

    TASK:
    - Given the source topic, candidate topics, and existing links, propose the single strongest missing link.
    - Output a JSON object with:
        - 'motivation' (required, first field): Short, research-grade, actionable reasoning (1-2 sentences max) justifying why this link should be created. Motivation must be defensible to a top-tier financial analyst and maximally useful for graph analytics and LLM reasoning.
        - All other required fields (type, source, target, etc.).
    - ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN ALL REQUIRED FIELDS. NO ADDITIONAL TEXT. STRICT JSON FORMAT. Output null if no link should be created.

    EXAMPLE OUTPUT:
    {{"motivation": "This link connects two highly correlated macro drivers not yet linked in the graph.", "type": "INFLUENCES", "source": "eurusd", "target": "ecb_policy"}}

    LINK TYPES:
    - INFLUENCES: A → B means A is a major driver or cause of B. Directional.
    - PEERS: A ↔ B means A and B are direct competitors, alternatives, or fulfill the same role in a market or system. Bi-directional, “true peer” only.
    - COMPONENT_OF: A is a component of B. Directional.
    - CORRELATES_WITH: A and B are correlated. Bi-directional. Moves together to some large degree.  

    SOURCE TOPIC:
    {source_name} (id: {source_id})

    CANDIDATE TOPICS:
    {candidate_lines}

    CURRENT LINKS:
    {existing_links}

    STRICT OUTPUT FORMAT:
    - Output exactly ONE JSON object with these REQUIRED keys only: "motivation", "type", "source", "target".
    - All four fields are REQUIRED and MUST be non-empty strings.
    - Do NOT include any other keys. Do NOT include any text before or after the JSON.

    YOUR RESPONSE IN JSON:
    """