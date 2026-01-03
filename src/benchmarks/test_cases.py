"""
Frozen Test Cases for Model Benchmarking

These are fixed scenarios that never change - allowing fair comparison across models and time.
Each test probes a specific capability needed for financial reasoning.
"""

# =============================================================================
# TEST SCENARIOS - Frozen articles and prompts
# =============================================================================

TEST_CASES = {
    # -------------------------------------------------------------------------
    # TEST 1: Article Classification - Can it assess relevance?
    # -------------------------------------------------------------------------
    "classify_relevance": {
        "name": "Article Relevance Classification",
        "description": "Can the model correctly classify article relevance to a topic?",
        "article": {
            "id": "BENCH001A",
            "title": "Fed Raises Rates 25bps, Signals More Hikes Possible",
            "content": """The Federal Reserve raised its benchmark interest rate by 25 basis
points today, bringing the target range to 5.25-5.50%. Chair Powell stated that inflation
remains "too high" and the committee is prepared to raise rates further if needed. Markets
now price 60% probability of another hike by December. The 2-year Treasury yield jumped
12bps to 4.92% following the announcement. The dollar index (DXY) rose 0.4% as rate
differentials widened against major currencies.""",
        },
        "topic": "EUR/USD",
        "prompt": """You are classifying article relevance for a financial research system.

ARTICLE:
Title: {title}
Content: {content}

TOPIC: {topic}

TASK: Classify how relevant this article is to the topic.

Output JSON:
{{
    "relevance": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "One sentence explaining why"
}}""",
        "expected": {
            "relevance": "HIGH",
            "good_reasoning_contains": ["rate", "dollar", "EUR", "differential"],
        },
    },

    # -------------------------------------------------------------------------
    # TEST 2: Conviction Test - Does it take a stance or hedge?
    # -------------------------------------------------------------------------
    "conviction_test": {
        "name": "Conviction Test",
        "description": "Does the model take a clear stance or hedge with 'on one hand' language?",
        "article": {
            "id": "BENCH002A",
            "title": "Gold Caught Between Inflation Fears and Rising Yields",
            "content": """Gold prices held steady at $1,950 as markets weigh conflicting signals.
Persistent inflation above 4% supports gold's traditional hedge role. However, rising real
yields (10Y TIPS at 2.1%) increase the opportunity cost of holding non-yielding gold.
ETF outflows continued for the 8th straight week (-12 tonnes), while central bank buying
remains strong (China added 23 tonnes in August). Technical support sits at $1,920 with
resistance at $1,980.""",
        },
        "topic": "Gold",
        "prompt": """You are a financial analyst making a directional call.

ARTICLE:
Title: {title}
Content: {content}

TASK: Based on this article, what is the most likely direction for {topic} over the next month?

You MUST take a clear stance. Do not hedge. Pick a direction and defend it.

Output JSON:
{{
    "direction": "BULLISH" | "BEARISH" | "NEUTRAL",
    "conviction": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "2-3 sentences defending your stance"
}}""",
        "expected": {
            "has_clear_stance": True,
            "fail_phrases": ["could go either way", "on one hand", "on the other hand", "uncertain", "hard to say", "depends on"],
        },
    },

    # -------------------------------------------------------------------------
    # TEST 3: Simple Causal Chain - Can it do A→B→C?
    # -------------------------------------------------------------------------
    "simple_causal_chain": {
        "name": "Simple Causal Chain (3 steps)",
        "description": "Can the model build a coherent 3-step causal chain?",
        "article": {
            "id": "BENCH003A",
            "title": "ECB Signals End to Rate Hikes as Inflation Cools",
            "content": """The European Central Bank held rates steady at 4.0% and signaled
that the hiking cycle is likely over. President Lagarde noted that headline inflation
has fallen to 2.9% and the eurozone economy is showing signs of weakness. German PMI
came in at 42.3, deep in contraction territory. Markets now price rate cuts beginning
in Q2 2024. The euro fell 0.6% against the dollar following the announcement.""",
        },
        "topic": "EUR/USD",
        "prompt": """You are building causal chains for financial analysis.

ARTICLE:
Title: {title}
Content: {content}

TASK: Build a 3-step causal chain showing how this ECB decision impacts {topic}.

Format: Step 1 → Step 2 → Step 3 → Final Impact on {topic}

Each step must be specific and show the MECHANISM of transmission.

Output JSON:
{{
    "chain": [
        "Step 1: [First cause]",
        "Step 2: [Mechanism/transmission]",
        "Step 3: [Second-order effect]",
        "Impact: [Specific impact on EUR/USD with direction]"
    ],
    "summary": "One sentence summary of the full chain"
}}""",
        "expected": {
            "min_steps": 3,
            "should_mention": ["rate", "ECB", "differential", "EUR/USD"],
            "should_have_direction": True,
        },
    },

    # -------------------------------------------------------------------------
    # TEST 4: Source Citation - Does it use provided IDs?
    # -------------------------------------------------------------------------
    "source_citation": {
        "name": "Source Citation Accuracy",
        "description": "Does the model use provided article IDs without hallucinating?",
        "articles": [
            {
                "id": "BENCH004A",
                "title": "US Jobs Report Beats Expectations",
                "content": "Non-farm payrolls rose 275,000 in February, above consensus of 200,000.",
            },
            {
                "id": "BENCH004B",
                "title": "China PMI Contracts for Third Month",
                "content": "Manufacturing PMI fell to 49.1, signaling continued economic weakness.",
            },
            {
                "id": "BENCH004C",
                "title": "Oil Prices Surge on OPEC+ Cuts",
                "content": "Brent crude jumped 4% to $85/barrel after surprise production cut announcement.",
            },
        ],
        "prompt": """You are writing analysis with source citations.

ARTICLES:
{articles_formatted}

TASK: Write a 2-3 sentence market summary that references at least 2 of these articles.

CITATION RULES:
- Use ONLY the article IDs provided above
- Format: (ARTICLE_ID) - e.g., (BENCH004A)
- Do NOT invent or modify article IDs

Output JSON:
{{
    "summary": "Your 2-3 sentence summary with (ARTICLE_ID) citations",
    "articles_cited": ["BENCH004A", "BENCH004B"]
}}""",
        "expected": {
            "valid_ids": ["BENCH004A", "BENCH004B", "BENCH004C"],
            "must_cite_at_least": 2,
            "no_hallucinated_ids": True,
        },
    },

    # -------------------------------------------------------------------------
    # TEST 5: JSON Compliance - Can it follow output format?
    # -------------------------------------------------------------------------
    "json_compliance": {
        "name": "JSON Format Compliance",
        "description": "Does the model output valid JSON in the exact schema requested?",
        "prompt": """You are testing JSON output compliance.

TASK: Analyze the current market environment for EUR/USD.

Output ONLY valid JSON matching this EXACT schema:
{{
    "trend": "BULLISH" | "BEARISH" | "NEUTRAL",
    "confidence": 0.0 to 1.0,
    "key_factors": ["factor1", "factor2", "factor3"],
    "price_target": "X.XXXX",
    "timeframe": "short-term" | "medium-term" | "long-term"
}}

Do NOT add any text before or after the JSON.
Do NOT wrap in markdown code blocks.""",
        "expected": {
            "valid_json": True,
            "required_fields": ["trend", "confidence", "key_factors", "price_target", "timeframe"],
            "trend_values": ["BULLISH", "BEARISH", "NEUTRAL"],
            "timeframe_values": ["short-term", "medium-term", "long-term"],
        },
    },

    # -------------------------------------------------------------------------
    # TEST 6: Quantification - Can it turn vague into specific?
    # -------------------------------------------------------------------------
    "quantification": {
        "name": "Quantification Ability",
        "description": "Can the model turn vague claims into specific numbers?",
        "article": {
            "id": "BENCH006A",
            "title": "Dollar Strength Weighs on Emerging Markets",
            "content": """The dollar's significant rally this quarter has put substantial
pressure on emerging market currencies. Capital outflows have been considerable, with
foreign investors pulling meaningful amounts from EM bond funds. The impact on local
currency debt has been notable, with spreads widening materially. Several central banks
have intervened heavily to support their currencies.""",
        },
        "prompt": """You are improving vague financial writing with specific numbers.

ARTICLE (contains vague language):
Title: {title}
Content: {content}

TASK: Identify the vague terms and suggest specific replacements.

For each vague term, provide:
1. The vague phrase
2. A reasonable specific number/range based on typical market moves
3. Why this quantification matters

Output JSON:
{{
    "vague_terms_found": [
        {{
            "vague_phrase": "significant rally",
            "suggested_replacement": "X.X% rally",
            "reasoning": "Why this number makes sense"
        }}
    ],
    "improved_summary": "Rewritten first sentence with specific numbers"
}}""",
        "expected": {
            "identifies_vague_terms": True,
            "provides_numbers": True,
            "min_terms_found": 3,
        },
    },

    # -------------------------------------------------------------------------
    # TEST 7: Multi-Step Chain (4+ steps) - Deeper reasoning
    # -------------------------------------------------------------------------
    "multi_step_chain": {
        "name": "Multi-Step Causal Chain (4+ steps)",
        "description": "Can the model build deeper causal chains with second-order effects?",
        "article": {
            "id": "BENCH007A",
            "title": "China Announces Major Stimulus Package",
            "content": """China unveiled a 2 trillion yuan ($280 billion) stimulus package
aimed at boosting domestic consumption and stabilizing the property sector. The package
includes tax cuts for consumers, subsidies for EV purchases, and support for distressed
property developers. The PBOC also cut the reserve requirement ratio by 50bps, releasing
an estimated 1 trillion yuan in liquidity. Copper prices jumped 3% on the news.""",
        },
        "topic": "EUR/USD",
        "prompt": """You are building deep causal chains for macro analysis.

ARTICLE:
Title: {title}
Content: {content}

TASK: Build a 4+ step causal chain showing how China stimulus impacts {topic}.

This requires SECOND-ORDER thinking:
- Not just China stimulus → risk-on → EUR up (too simple)
- Think about: trade flows, commodity demand, inflation transmission, policy divergence

Output JSON:
{{
    "chain": [
        "Step 1: [Initial cause]",
        "Step 2: [First transmission]",
        "Step 3: [Second-order effect]",
        "Step 4: [Third-order effect or feedback]",
        "Impact: [Specific impact on EUR/USD]"
    ],
    "non_obvious_insight": "What does this chain reveal that isn't immediately obvious?"
}}""",
        "expected": {
            "min_steps": 4,
            "has_non_obvious_insight": True,
            "mentions_mechanism": True,
        },
    },

    # -------------------------------------------------------------------------
    # TEST 8: Cross-Domain Synthesis - A + B = C
    # -------------------------------------------------------------------------
    "cross_domain_synthesis": {
        "name": "Cross-Domain Synthesis",
        "description": "Can the model combine multiple sources into non-obvious insights?",
        "articles": [
            {
                "id": "BENCH008A",
                "title": "Fed Signals Higher for Longer",
                "content": "Federal Reserve officials indicated rates will stay elevated through 2024, with no cuts expected before Q3. The hawkish stance reflects persistent services inflation.",
            },
            {
                "id": "BENCH008B",
                "title": "China Stimulus Boosts European Exporters",
                "content": "German auto and luxury goods makers rally on China stimulus news. BMW, Mercedes, and LVMH see significant gains as China accounts for 30-40% of their sales.",
            },
            {
                "id": "BENCH008C",
                "title": "EUR Shorts at Extreme Levels",
                "content": "CFTC data shows EUR net shorts at -$28 billion, the largest position since 2020. Hedge funds are heavily positioned for EUR weakness.",
            },
        ],
        "topic": "EUR/USD",
        "prompt": """You are finding non-obvious synthesis opportunities.

ARTICLES:
{articles_formatted}

TASK: Combine these articles to find a NON-OBVIOUS insight about {topic}.

The insight must be:
- Something that NONE of the articles states directly
- Created by COMBINING information from multiple articles
- Specific and actionable (not vague)

Format: Article A + Article B + Article C = Non-obvious insight

Output JSON:
{{
    "synthesis": "Article (ID_A) [key point] + Article (ID_B) [key point] + Article (ID_C) [key point] = [Your non-obvious insight]",
    "why_non_obvious": "Why this insight isn't stated in any single article",
    "actionable_implication": "What this means for trading/positioning"
}}""",
        "expected": {
            "combines_multiple_sources": True,
            "has_specific_insight": True,
            "not_just_summary": True,
        },
    },
}


# =============================================================================
# TEST SUITES - Which tests to run
# =============================================================================

TEST_SUITES = {
    "quick": [
        "classify_relevance",
        "json_compliance",
        "conviction_test",
    ],
    "standard": [
        "classify_relevance",
        "json_compliance",
        "conviction_test",
        "simple_causal_chain",
        "source_citation",
        "quantification",
    ],
    "deep": [
        "classify_relevance",
        "json_compliance",
        "conviction_test",
        "simple_causal_chain",
        "source_citation",
        "quantification",
        "multi_step_chain",
        "cross_domain_synthesis",
    ],
}
