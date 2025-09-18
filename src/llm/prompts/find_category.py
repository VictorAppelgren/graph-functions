find_category_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS CATEGORY IDENTIFIER working on the Saga Graph—a knowledge graph for the global economy.

        TASK:
        - For the article below, output a JSON array of category objects. Each object MUST have:
            - 'motivation' (first field): Short justification for the category assignment
            - 'name': Category name (one of: {categories})
        - Output ONLY the JSON array, no extra text. If unsure, use name="other" and explain why in motivation.

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        [{{"motivation": "The article discusses a major inflation print.", "name": "macro_event"}}]
    """