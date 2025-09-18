find_impact_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS IMPACT ASSESSOR working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - Output a SINGLE JSON OBJECT with exactly these two fields:
            - 'motivation' (first field): Reason for the score (1–2 sentences)
            - 'score': Impact score ('hidden' if not relevant, or 1=low, 2=medium, 3=high)
        - Output ONLY the JSON object, no extra text. If unsure, say so in motivation but still choose a score.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "The article directly impacts this node by reporting a major event.", "score": 3}}
        {{"motivation": "The article is not relevant to this node's scope.", "score": "hidden"}}

        YOUR RESPONSE:
    """