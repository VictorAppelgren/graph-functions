should_rewrite_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS ANALYSIS REWRITE JUDGE for the Saga Graph.

        TASK:
        - Given the current analysis fields for a topic and the summary of a new article, decide if we should UPDATE the analysis.
        - Output a JSON object with two fields:
            - "motivation" (string): short, specific, research-grade reasoning.
            - "should_rewrite" (boolean): true or false (JSON boolean).
        - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields.

        REWRITE CRITERIA (Be AGGRESSIVE - favor updating):
        ✓ NEW DATA: Article contains new data points, metrics, or developments
        ✓ FRESH PERSPECTIVE: Article offers new angle or interpretation
        ✓ MARKET MOVING: Article discusses events that could impact markets
        ✓ POLICY CHANGES: New policy decisions, guidance, or shifts
        ✓ CATALYST: New catalyst or trigger not in current analysis
        ✓ OUTDATED: Current analysis feels stale or missing recent context
        
        DON'T REWRITE ONLY IF:
        ✗ Article is COMPLETELY redundant (exact same info already covered)
        ✗ Article is off-topic or irrelevant
        
        BIAS TOWARD REWRITING: When in doubt, say TRUE. Fresh analysis is better than stale analysis.

        CURRENT ANALYSIS FIELDS:
        {analysis}

        NEW ARTICLE SUMMARY:
        {new_article_summary}

        EXAMPLES:
        {{ "motivation": "New Fed rate decision not in current analysis.", "should_rewrite": true }}
        {{ "motivation": "Fresh GDP data provides updated growth outlook.", "should_rewrite": true }}
        {{ "motivation": "Article repeats exact same info already covered.", "should_rewrite": false }}

        YOUR RESPONSE:
    """