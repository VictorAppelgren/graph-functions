generate_keyword_prompt = """
    {system_mission}
    {system_context}

    You are a lead macro/markets editor. Write a professional, research‑grade keyword checklist.

    PURPOSE (downstream matcher)
    - We scan concatenated text: title + summary/description + argos_summary, lowercased.
    - Matching is tolerant: spaces, hyphens, or slashes between tokens are treated as optional (e.g., eurusd ~= eur/usd ~= eur-usd ~= eur usd).
    - Each keyword counts at most once per article; duplicates don't add score.
    - An article becomes a candidate when it contains ≥ 3–4 DISTINCT keyword hits.
    - Your list should maximize recall of truly on‑topic articles while avoiding generic noise.

    TASK
    Return a single flat list of short newsroom‑surface keywords to find articles about "{topic_name}" in the "{section}" timeframe.
    These must be terms that realistically appear in headlines or summaries, pointing clearly toward the intended topic—neither generic nor overly narrow.

    QUALITY BAR
    - Prefer canonical market tokens, entities, policy names, indicators, and tradable instruments.
    - Avoid generic words with weak signal (e.g., "price", "market", "stocks", "update").
    - Heavily prefer single‑word action tokens and two‑word anchors; do NOT output three‑word event composites like "oil price slump".
    - Include common inflections as separate items when natural (e.g., decline/declined/declining; slump/slumps/slumped; drop/drops/dropped; fall/falls/fell).
    - Use standard 1–2 word forms; allow 3 words only if truly standardized (rare) and never for [anchor + action] blends.
    - Avoid long composites and joined variants (no "globalgdpgrowthslowdown"; no tailing "-structural").

    PATTERN EXAMPLES (illustrative, adapt to the actual topic)
    - If you would have written 3‑word phrases like "oil price decline" or "crude oil slump", instead produce:
      • two‑word anchors: "oil price", "crude oil", "brent", "wti"
      • single‑word actions: "decline", "drop", "fall", "slump", "dip", "slide", "selloff", "sell-off", "plunge", "tumble"
      • keep them as separate items in the list so any combination can trigger ≥3–4 distinct hits

    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    CRITICAL JSON FORMAT REQUIREMENTS - FAILURE TO FOLLOW EXACTLY WILL BREAK THE SYSTEM:
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    1. RETURN ONLY JSON - NO TEXT BEFORE OR AFTER
    2. NO MARKDOWN CODE FENCES (```) - JUST RAW JSON
    3. NO EXPLANATIONS, NO COMMENTS, NO ROLE LABELS
    4. EXACTLY ONE JSON OBJECT WITH EXACTLY ONE KEY CALLED "list"
    5. THE "list" KEY MUST CONTAIN AN ARRAY OF STRINGS
    6. USE DOUBLE QUOTES ONLY - NO SINGLE QUOTES
    7. NO TRAILING COMMAS ANYWHERE
    8. 15-40 ITEMS IN THE ARRAY
    9. ALL LOWERCASE STRINGS
    10. NO EMPTY STRINGS IN THE ARRAY

    CORRECT EXAMPLES:
    {{"list":["fed", "rate", "cut", "powell", "jackson hole", "september", "inflation", "unemployment", "policy", "dovish", "hawkish", "basis points", "federal reserve", "fomc", "meeting"]}}

    {{"list":["oil", "crude", "brent", "wti", "opec", "production", "inventory", "barrel", "energy", "petroleum", "refinery", "gasoline", "diesel", "pipeline", "drilling", "rig count", "shale", "fracking"]}}

    {{"list":["eurusd", "eur/usd", "euro", "dollar", "ecb", "fed", "draghi", "powell", "rate", "policy", "divergence", "parity", "forex", "currency", "exchange", "monetary", "stimulus", "tightening"]}}

    WRONG EXAMPLES (DO NOT DO THIS):
    ```json
    {{"list":["fed", "rate"]}}
    ```

    Here are some keywords for your topic: ["fed", "rate"]

    {{"list":["fed", "rate",]}}

    {{"list":['fed', 'rate']}}

    {{"list":[]}}

    topic: "{topic_name}"
    timeframe: "{section}"
    section focus: {focus}

    BUILD A PERFECT LIST FOR THIS TOPIC SO THAT 3-4 HITS STRONGLY IMPLY RELEVANCE.

    RESPOND WITH ONLY THE JSON OBJECT - NOTHING ELSE:
    """