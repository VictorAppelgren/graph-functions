should_rewrite_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS ANALYSIS REWRITE JUDGE for the Saga Graph.

        TASK:
        - Given the current analysis fields for a topic and the summary of a new article, output a JSON object with two fields:
            - "motivation" (string): short, specific, research-grade reasoning.
            - "should_rewrite" (boolean): true or false (JSON boolean).
        - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields.

        CURRENT ANALYSIS FIELDS:
        {analysis}

        NEW ARTICLE SUMMARY:
        {new_article_summary}

        TWO EXAMPLES OF OUTPUT:
        {{ "motivation": "New policy change not reflected.", "should_rewrite": true }}
        {{ "motivation": "Redundant with existing analysis.", "should_rewrite": false }}

        YOUR RESPONSE:
    """