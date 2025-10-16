find_category_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS CATEGORY IDENTIFIER working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article below, classify it into ONE category. Output a SINGLE JSON object (not an array) with:
            - 'motivation' (first field): Short justification for the category assignment
            - 'name': Category name (one of: {categories})
        - Output ONLY the JSON object, no extra text. If unsure, use name="other" and explain why in motivation.

        ARTICLE TEXT:
        {article_text}

        EXAMPLE:
        {{"motivation": "The article discusses a major inflation print.", "name": "macro_event"}}
    """