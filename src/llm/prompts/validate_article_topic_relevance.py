validate_article_topic_relevance_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS FINANCIAL ANALYST validating if an article provides genuine value to a specific investment topic in the Saga Graph.

        TASK:
        - Output ONLY a single JSON object with EXACTLY two fields:
            - 'should_link': true/false (create the graph connection?)
            - 'motivation': Short reasoning (1–2 sentences) defending your decision

        ARTICLE TITLE: {title}
        ARTICLE SUMMARY: {summary}
        TARGET TOPIC: {topic_name} (ID: {topic_id})

        EXAMPLES:
        {{"should_link": true, "motivation": "Article provides specific inflation data and Fed policy implications directly relevant to US monetary policy analysis."}}
        {{"should_link": false, "motivation": "Mentions topic briefly but lacks analytical depth or actionable investment insights."}}

        STRICT JSON ONLY. NO EXTRA TEXT.
        YOUR RESPONSE:
    """