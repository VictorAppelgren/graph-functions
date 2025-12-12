"""
Shared Citation Rules & Research Methodology

MISSION: Ensure ALL agents (analysis + strategy) use consistent citation standards.
Import this into every agent prompt that produces analysis text.

Usage:
    from src.llm.prompts.citation_rules import SHARED_CITATION_AND_METHODOLOGY
    
    PROMPT = '''
    {system_mission}
    {system_context}
    
    {citation_rules}
    
    ... rest of prompt ...
    '''
    
    prompt = PROMPT.format(
        citation_rules=SHARED_CITATION_AND_METHODOLOGY,
        ...
    )
"""

CITATION_RULES = """
=== CITATION RULES (ULTRA-STRICT - APPLIES TO ALL OUTPUT) ===

ARTICLES:
- Use ONLY 9-character alphanumeric IDs in parentheses from SOURCE MATERIAL
- Inline citations MUST appear immediately after the specific claim they support
- REJECT: Names, numbers (1), (2), URLs, or any non-9-character format
- Cite FREQUENTLY: every substantive fact, number, finding must have an inline citation
- NEVER INVENT IDs. Use ONLY IDs present in SOURCE MATERIAL. This is validated automatically.
- Multiple sources: (Z7O1DCHS7)(K8M2NQWER) with no spaces
- Place citations directly after the claim, NOT at paragraph ends
- NEVER create citation-only sentences or dump multiple citations at end of paragraphs

TOPICS:
- Use format: (Topic:topic_id.field_name) for cross-topic references
- Valid fields: executive_summary, house_view, drivers, analysis
- Use when referencing analysis from related topics

MARKET DATA:
- Market data from Yahoo Finance can be cited as (Topic:topic_id.market_data)
- Current prices, 52-week ranges, MA levels are valid without article citation
- BUT predictions/forecasts about price movements MUST cite articles

STRICT RULES:
- If you cannot cite a prediction, DO NOT MAKE IT
- If you cannot cite a probability, DO NOT STATE IT
- If you cannot cite a future date/event, DO NOT REFERENCE IT
- ZERO tolerance for uncited claims about future price movements
"""

RESEARCH_METHODOLOGY = """
=== WORLD-CLASS RESEARCH METHODOLOGY ===

1) **CAUSAL CHAIN MASTERY** (Non-Negotiable)
   Never say "X affects Y"—always show: "X → mechanism A → mechanism B → Y at level Z"
   Every claim must show EXPLICIT transmission path with QUANTIFIED steps.
   
   WRONG: "Fed rate cuts would benefit tech stocks"
   RIGHT: "Fed cut probability 70.5% (08HD556V4) → UST10Y yield falls 25bp (GNJV2Y9P7) 
          → tech discount rate drops → NDX fair value rises 3-5% (K8M2NQWER)"

2) **CROSS-DOMAIN SYNTHESIS** (Elite Thinking)
   Connect macro (policy) → meso (flows/positioning) → micro (price action)
   Show how different domains interact and compound.

3) **SECOND-ORDER THINKING** (What Others Miss)
   Don't stop at first-order effects. Ask: "Then what?"
   Identify reflexive loops, compounding effects, non-linear outcomes.

4) **1+1=3 SYNTHESIS** (Superior Intelligence)
   Two articles together reveal scenarios neither shows alone.
   Generate insights that CANNOT be derived from single sources.

5) **QUANTIFIED PRECISION** (Zero Vagueness)
   Ban words like "significant", "substantial", "considerable"
   Use: Exact levels, probabilities, timeframes, magnitudes.
   Every number needs citation (article ID or topic reference).

6) **CITATION DENSITY** (Bulletproof Accuracy)
   Every substantive claim needs inline 9-character ID citation.
   Cite immediately after claim, not at paragraph end.
   Remove ANY unsupported claim—if you can't cite it, cut it.

7) **ANTI-HALLUCINATION** (Critical)
   BANNED without citation:
   - Future price levels (e.g., "target 100.5")
   - Future dates (e.g., "Fed meeting May 15")  
   - Probabilities (e.g., "30% chance")
   - Trading recommendations (e.g., "short at X, stop at Y")
   
   ALLOWED without citation:
   - Current market prices (from market data)
   - Logical conclusions explicitly derived from cited premises
   - Standard financial definitions

8) **MAXIMUM INFORMATION DENSITY** (Every Word Earns Its Place)
   Zero fluff, zero filler, zero obvious statements.
   Write as if every word costs $100.

9) **PROFESSIONAL AUTHORITY** (Conviction, Not Hedging)
   Write with precision and conviction. Ban: "might", "could", "possibly", "perhaps"
   Every sentence drives investment decisions.
"""

# Combined for easy import
SHARED_CITATION_AND_METHODOLOGY = CITATION_RULES + "\n" + RESEARCH_METHODOLOGY
