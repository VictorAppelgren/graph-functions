find_time_frame_prompt = """
        {system_mission}
        {system_context}

        YOU ARE A WORLD-CLASS MACRO/MARKETS TIME FRAME IDENTIFIER working on the Saga Graph.

        TASK:
        - Output a SINGLE JSON OBJECT with exactly:
            - 'motivation' (first field): 1–2 sentences explaining the choice
            - 'horizon': one of: fundamental | medium | current
        - Only the JSON object. If unsure, say so in motivation but still pick one (default to "fundamental").

        ARTICLE TEXT:
        {article_text}

        EXAMPLES:
        {{"motivation": "Discusses long-term structural drivers.", "horizon": "fundamental"}}
        {{"motivation": "Focuses on immediate market events.", "horizon": "current"}}

        YOUR RESPONSE:
    """