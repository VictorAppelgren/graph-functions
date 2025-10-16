is_relevant_to_eurusd_swing_prompt = """
    {system_mission}
    {system_context}

    You are an expert FX macro analyst. Determine if the article below is directly relevant to EURUSD swing trading (multi-day to multi-week).
    Criteria: Macro/ECB/Fed policy, rate differentials, Eurozone/US growth/inflation, risk sentiment, flows affecting EURUSD.
    Respond ONLY with a single line of strict JSON: {{"relevant": "yes"}} or {{"relevant": "no"}}. No explanation, no extra text.

    Article:
    {article}
    """