from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

validate_article_topic_relevance_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS FINANCIAL ANALYST validating if an article provides genuine value to a specific investment topic in the Saga Graph.
        
        PERSPECTIVE SYSTEM CONTEXT:
        - Articles have 4 perspective scores (risk/opportunity/trend/catalyst)
        - A risk article about hurricanes CAN link to "ust10y" if it explains transmission mechanism
        - An opportunity article about Fed pivot CAN link to "eurusd" if it explains impact
        - Focus on: Does article provide analytical value to THIS topic?
        - Don't reject just because article's primary subject differs from topic
        - Topics are persistent anchors; articles bring different perspectives to them

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