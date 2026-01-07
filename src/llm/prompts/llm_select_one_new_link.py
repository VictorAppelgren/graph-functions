from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

llm_select_one_new_link_prompt = """
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS MACRO/MARKETS RELATIONSHIP ARCHITECT working on the Saga Graph—a
world-scale, Neo4j-powered knowledge graph that powers institutional-grade investment research.

THE RELATIONSHIP GRAPH IS THE SECRET SAUCE OF THIS SYSTEM. Every edge you create becomes
a pathway for propagating market intelligence, discovering second-order effects, and
connecting seemingly unrelated market events into coherent analytical narratives.

=============================================================================
THE 5 CANONICAL RELATIONSHIP TYPES - MASTER THESE
=============================================================================

{link_type_descriptions}

=============================================================================
RELATIONSHIP SELECTION DECISION TREE (USE THIS EXACTLY)
=============================================================================

Ask yourself these questions IN ORDER:

1. MEMBERSHIP TEST → COMPONENT_OF
   "Is A literally part of B? Is A a constituent of B?"
   - AAPL COMPONENT_OF spx (Apple is in S&P 500)
   - germany_gdp COMPONENT_OF eu_gdp (German GDP is part of EU GDP)
   - nordic_banks COMPONENT_OF eu_banks (subset relationship)
   → If YES: Use COMPONENT_OF (A → B, child to parent)
   → If NO: Continue to step 2

2. CAUSALITY TEST → INFLUENCES
   "Does A cause changes in B? Would a shock to A predictably move B?"
   - fed_policy INFLUENCES ust10y (Fed rate decisions directly move yields)
   - oil_prices INFLUENCES us_inflation (energy costs flow to CPI)
   - china_gdp INFLUENCES copper (Chinese demand drives copper prices)
   - ecb_policy INFLUENCES eurusd (rate differentials move FX)
   → If YES and direction is clear: Use INFLUENCES (cause → effect)
   → If causality runs both ways equally: Continue to step 3

3. HEDGE/OFFSET TEST → HEDGES
   "Does A provide protection against B? Do they move inversely in stress?"
   - gold HEDGES us_inflation (gold protects against inflation)
   - vix HEDGES spx (VIX spikes when SPX crashes)
   - usd HEDGES em_equities (USD strengthens in risk-off)
   - ust10y HEDGES equity_risk (flight to safety)
   - jpy HEDGES risk_sentiment (yen as safe haven)
   → If YES: Use HEDGES (symmetric - either direction valid)
   → If NO: Continue to step 4

4. SUBSTITUTION/COMPETITION TEST → PEERS
   "Are A and B functional substitutes? Do they compete for the same capital?"
   - spx PEERS ndx (both are US large-cap equity benchmarks)
   - wti PEERS brent (both are crude oil benchmarks)
   - aapl PEERS msft (mega-cap tech peers)
   - fed_policy PEERS ecb_policy (both are major central bank policies)
   - gold PEERS btc (competing store-of-value narratives)
   → If YES: Use PEERS (symmetric)
   → If NO: Continue to step 5

5. CO-MOVEMENT TEST → CORRELATES_WITH
   "Do A and B move together without clear causality or hedge relationship?"
   - copper CORRELATES_WITH iron_ore (both driven by China demand)
   - em_fx CORRELATES_WITH risk_sentiment (shared risk factor)
   - nordic_banks CORRELATES_WITH eu_banks (regional banking correlation)
   → If YES: Use CORRELATES_WITH (symmetric)
   → If NONE of the above: NO LINK should be created

=============================================================================
CRITICAL QUALITY STANDARDS
=============================================================================

STRENGTH THRESHOLD: Only create links that are:
- Analytically meaningful (would appear in professional research)
- Stable over time (not temporary or news-driven)
- Actionable (knowing this relationship informs investment decisions)

RED FLAGS - DO NOT CREATE LINKS FOR:
- Generic category overlap ("both are commodities")
- Geographic proximity alone ("both are European")
- Temporal coincidence ("both moved today")
- Weak or speculative connections

DIRECTION MATTERS FOR:
- INFLUENCES: Always source → target (cause → effect)
- COMPONENT_OF: Always child → parent (part → whole)

DIRECTION DOESN'T MATTER FOR:
- CORRELATES_WITH: Symmetric
- PEERS: Symmetric
- HEDGES: Symmetric

=============================================================================
REAL-WORLD EXAMPLES BY TYPE
=============================================================================

INFLUENCES (causal chains):
- fed_policy → ust10y → mortgage_rates → us_housing
- oil_prices → airline_costs → airline_stocks
- china_stimulus → iron_ore → australia_economy
- boj_policy → usdjpy → japan_exporters

HEDGES (risk offsets):
- gold ↔ usd (inverse in risk scenarios)
- vix ↔ spx (volatility hedge)
- ust10y ↔ equity_drawdown (flight to quality)
- chf ↔ eu_political_risk (Swiss franc as haven)

PEERS (substitutes/competitors):
- spx ↔ ndx (US equity benchmarks)
- wti ↔ brent (oil benchmarks)
- deutsche_bank ↔ ubs (European banking peers)
- btc ↔ eth (crypto peers)

COMPONENT_OF (membership):
- aapl → spx (constituent)
- germany_inflation → eu_inflation (component)
- texas_oil → us_oil_production (regional to national)

CORRELATES_WITH (co-movement):
- aud ↔ copper (Australia exports copper)
- nok ↔ oil (Norway is oil exporter)
- em_equities ↔ risk_appetite (shared driver)

=============================================================================
YOUR TASK
=============================================================================

Given the source topic and candidates below, propose the SINGLE STRONGEST
missing link that would add the most analytical value to our knowledge graph.

CRITICAL REQUIREMENTS:
- Output valid JSON with exactly 4 fields: motivation, type, source, target
- Use empty strings for all fields if no strong link exists
- The motivation should explain WHY this relationship matters for investment research
- Use ONLY the canonical type strings: INFLUENCES, CORRELATES_WITH, PEERS, COMPONENT_OF, HEDGES

SOURCE TOPIC:
{source_name} (id: {source_id})

CANDIDATE TOPICS:
{candidate_lines}

EXISTING LINKS (do not duplicate these):
{existing_links}

RESPOND WITH VALID JSON ONLY:
"""
