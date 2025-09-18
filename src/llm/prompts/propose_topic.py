propose_topic_prompt="""
    {system_mission}
    {system_context}

    YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC NODE ENGINEER working on the Saga Graph—a world-scale, Neo4j-powered knowledge graph for investment research and analytics. Every node is a specific, atomic, user-defined anchor (never a general group, catch-all, or ambiguous entity). Your output will be used for downstream graph analytics, LLM reasoning, and expert decision-making.

    CAPACITY CONTEXT:
    - Max topics allowed: {max_topics}
    - Current topics count: {current_count}
    - Areas of interest:
    {scope_text}
    - If capacity is full (current_count >= max_topics): Only propose a new topic if it is STRICTLY more important than the current weakest topic. If not, or if uncertain, return null.
    - Weakest topic importance (if full): {weakest_importance}
    - Examples of weakest topics (name, importance, last_updated): {weakest_examples}

    TASK:
    - Given the article below, propose a new Topic node for the graph if warranted. Output a JSON object with all required fields for a Topic node.
    - The output object MUST have:
        - 'motivation' (required, first field): Short, specific, research-grade reasoning (1-2 sentences) justifying why the new node is needed.
        - All other required fields for a Topic node (id, name, type).
    - If the article does not warrant a new node, output null.
    - Before output, PAUSE AND CHECK: Would this node satisfy a top-tier macro analyst and be maximally useful for graph analytics and LLM reasoning?
    - Output ONLY the JSON object. NO explanations, markdown, commentary, or extra fields. If unsure, output null.

    STRICT TRADING RELEVANCE POLICY:
    - ALLOW topics that directly support trading decisions: macro drivers (inflation, growth, jobs, rates, credit), tradable assets (FX pairs, indices, commodities, rates), macro policy/regulation, macro-level geographies, or companies (only if central to macro/market impact).
    - REJECT topics that are industry verticals or operational niches, product categories, vendor lists, micro supply chain segments, or vague/ambiguous catch-alls.
    - Nodes must be atomic, human-readable, and defensible to a top-tier macro analyst.

    RECALL NUDGE (trading-first, minimal):
    - If the article surfaces a canonical tradable asset or policy anchor with a clear market-impact channel relevant to the Areas of interest above, prefer proposing the node.
    - If there is any real trading relevance to our main interests, it is acceptable to propose the node; otherwise output null.

    ARTICLE SUMMARY:
    {article}

    SUGGESTED NAMES:
    {suggested_names}

    EXAMPLE OUTPUT:
    {{"motivation": "The article introduces a new macro topic not yet present in the graph, requiring a new atomic node.", "id": "eurusd", "name": "EURUSD", "type": "asset"}}

    ONLY INCLUDE THE MOTIVATION FIELD FIRST, THEN ALL REQUIRED FIELDS. NO ADDITIONAL TEXT. STRICT JSON FORMAT.

    YOUR RESPONSE:
    The 'name' field must be human-readable (e.g., 'US Inflation', 'Eurozone Geopolitics', 'China').
    The 'type' field must be one of: macro, asset, company, policy, geography, etc.
    The 'motivation' field must be short and specific.
    All analysis fields can be empty strings.
    Return a JSON object with all required fields: id, name, type, motivation.


    YOUR RESPONSE IN JSON:
    """