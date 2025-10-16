# topic_architecture_context.py
# Shared context explaining the Saga Graph topic + perspective architecture
# Include this in ALL prompts dealing with topic creation, mapping, or classification

TOPIC_ARCHITECTURE_CONTEXT = """
═══════════════════════════════════════════════════════════════════════════════
SAGA GRAPH ARCHITECTURE: TOPICS AS PERSISTENT ANALYTICAL ANCHORS
═══════════════════════════════════════════════════════════════════════════════

CORE PRINCIPLE: Topics = WHAT to Track | Perspectives = HOW to Analyze

TOPICS ARE PERSISTENT ANALYTICAL ANCHORS:
- Represent entities/phenomena worth tracking for 6+ months
- Must be recurring, tradable, or structurally important
- Can be mapped to multiple times (articles can link to multiple topics)
- Geographic specificity adds value when it's recurring/persistent

PERSPECTIVES ARE ATTRIBUTES, NOT TOPICS:
- 4 independent dimensions: Risk, Opportunity, Trend, Catalyst
- Each article scored 0-3 on each perspective (independent scores)
- Each topic has 4 perspective analysis sections synthesizing articles
- Perspectives are HOW we analyze topics, not separate nodes

═══════════════════════════════════════════════════════════════════════════════
TOPIC CREATION DECISION FRAMEWORK
═══════════════════════════════════════════════════════════════════════════════

✅ CREATE TOPIC FOR:

1. TRADABLE ASSETS (Always)
   - FX: eurusd, usdjpy, dxy, gbpusd
   - Rates: ust2y, ust10y, bund10y, gilt10y
   - Equities: spx, ndx, eurostoxx50
   - Commodities: wti, brent, gold, copper, natgas

2. POLICY INSTITUTIONS (Recurring Decision-Makers)
   - Central banks: fed_policy, ecb_policy, boj_policy, pboc_policy
   - Coordinated bodies: opec_production_policy
   - Regulatory: sec_policy, eu_regulation

3. MACRO DRIVERS (Fundamental Metrics)
   - Inflation: us_inflation, us_core_cpi, us_pce, eu_cpi
   - Growth: us_gdp, eu_gdp, cn_gdp
   - Labor: us_nonfarm_payrolls, us_unemployment
   - Credit: cn_credit_growth, us_credit_conditions

4. RECURRING GEOGRAPHIC EVENTS (Persistent Phenomena)
   ✅ florida_hurricanes - Seasonal, recurring, specific geography
   ✅ california_wildfires - Seasonal, recurring, specific geography
   ✅ us_natural_disasters - Broader structural/climate theme
   ✅ middle_east_geopolitical_risk - Persistent regional dynamic
   ⚠️ natural_disasters - TOO BROAD, links to everything globally

5. TRADABLE SECTORS (With Geographic Specificity)
   ✅ us_insurance, eu_banks, swedish_banks, northern_european_banks
   ✅ us_homebuilders, us_tech_sector, eu_auto_sector
   ✅ cn_property_sector - Structural issue, ongoing
   - Can be broad (us_insurance) or specific (swedish_banks) based on analytical need
   - Geographic breakdown when it adds precision

6. STRUCTURAL THEMES (If Persistent & Tradable)
   ✅ us_natural_disasters - Long-term climate impact analysis
   ✅ global_supply_chain - Persistent structural issue
   ✅ energy_transition - Multi-year structural shift
   ❌ market_volatility - Too vague/general

═══════════════════════════════════════════════════════════════════════════════

❌ DO NOT CREATE TOPIC FOR:

1. TEMPORARY EVENTS/MOMENTS (Map to Persistent Topics Instead)
   ❌ fed_pivot → Map to: fed_policy
   ❌ hurricane_milton → Map to: florida_hurricanes
   ❌ 2024_us_election → Map to: us_politics or relevant assets
   ❌ opec_november_meeting → Map to: opec_production_policy
   
2. PERSPECTIVE + ENTITY COMBINATIONS (FORBIDDEN)
   ❌ hurricane_risk_on_ust10y - Mixes event + asset + perspective
   ❌ fed_dovish_opportunity - Mixes policy + perspective
   ❌ inflation_upside_trend - Mixes driver + perspective
   ❌ eurusd_downside_risk - Mixes asset + perspective
   ❌ ust10y_risk - Mixes asset + perspective
   
3. OVERLY BROAD CATCH-ALLS (Link to Everything)
   ❌ natural_disasters - Global, no geographic specificity
   ❌ geopolitical_risk - Too vague
   ❌ market_risk - Too general
   ❌ economic_uncertainty - Too broad

═══════════════════════════════════════════════════════════════════════════════
ARTICLE CLASSIFICATION & MAPPING
═══════════════════════════════════════════════════════════════════════════════

ARTICLE CLASSIFICATION (3 Dimensions):
1. Temporal Horizon: fundamental (6+ months) | medium (3-6 months) | current (0-3 weeks)
2. Perspective Scores (0-3 each, INDEPENDENT):
   - importance_risk: Downside scenarios, threats, vulnerabilities
   - importance_opportunity: Upside scenarios, catalysts, bullish drivers
   - importance_trend: Structural shifts, regime changes, secular trends
   - importance_catalyst: Immediate triggers (0-7 days), forcing functions
3. Overall Importance: 0-3 (general relevance to trading decisions)

MAPPING LOGIC (Articles Can Map to Multiple Topics):
- Map to ALL relevant persistent topics
- Prioritize existing topics over creating new ones
- Geographic specificity when it adds analytical value
- One article can link to 3-5 topics if genuinely relevant to each

═══════════════════════════════════════════════════════════════════════════════
ANALYSIS GENERATION
═══════════════════════════════════════════════════════════════════════════════

EACH TOPIC GETS 7 ANALYSIS SECTIONS:

Timeframe Sections (3):
- fundamental_analysis: Query articles WHERE temporal_horizon='fundamental'
  → Synthesize across ALL 4 perspectives (risk+opportunity+trend+catalyst)
- medium_analysis: Query articles WHERE temporal_horizon='medium'
  → Synthesize across ALL 4 perspectives
- current_analysis: Query articles WHERE temporal_horizon='current'
  → Synthesize across ALL 4 perspectives

Perspective Sections (4):
- risk_analysis: Query articles WHERE importance_risk >= 2
  → Synthesize across ALL 3 timeframes (fundamental+medium+current)
- opportunity_analysis: Query articles WHERE importance_opportunity >= 2
  → Synthesize across ALL 3 timeframes
- trend_analysis: Query articles WHERE importance_trend >= 2
  → Synthesize across ALL 3 timeframes
- catalyst_analysis: Query articles WHERE importance_catalyst >= 2
  → Synthesize across ALL 3 timeframes

═══════════════════════════════════════════════════════════════════════════════
CONCRETE EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

EXAMPLE 1: Hurricane Article
Article: "Hurricane Milton threatens Florida insurance sector, impacts Treasury yields"

TOPIC CREATION:
✅ Create "florida_hurricanes" (if doesn't exist) - Recurring seasonal phenomenon
✅ "us_insurance" already exists - Tradable sector
✅ "ust10y" already exists - Tradable asset

ARTICLE MAPPING:
✅ Map to: ["florida_hurricanes", "ust10y", "us_insurance"]

ARTICLE CLASSIFICATION:
✅ importance_risk=3, importance_catalyst=2, temporal_horizon="current"

ANALYSIS RESULT:
- florida_hurricanes.risk_analysis: "Insurance sector exposure, Treasury transmission"
- florida_hurricanes.current_analysis: "Hurricane Milton immediate impact"
- ust10y.risk_analysis: "Florida hurricane → insurance losses → flight to quality"
- us_insurance.risk_analysis: "Direct hurricane exposure, claims spike"

WHY THIS WORKS:
✅ "florida_hurricanes" is persistent (happens every year), not "hurricane_milton"
✅ Geographic specificity (Florida) adds analytical precision
✅ Multiple topics benefit from different analytical angles
✅ NO "hurricane_risk_on_ust10y" topic (forbidden combination)

---

EXAMPLE 2: OPEC Production Cut
Article: "OPEC announces surprise production cut, oil prices surge"

TOPIC CREATION:
✅ "opec_production_policy" exists - Institutional policy anchor (like fed_policy)
✅ "wti" exists - Tradable asset
✅ "brent" exists - Tradable asset

ARTICLE MAPPING:
✅ Map to: ["opec_production_policy", "wti", "brent"]

ARTICLE CLASSIFICATION:
✅ importance_catalyst=3, importance_opportunity=2, temporal_horizon="current"

ANALYSIS RESULT:
- opec_production_policy.catalyst_analysis: "Production cut mechanics, timing, impact"
- wti.catalyst_analysis: "OPEC cut → supply shock → price surge"
- wti.opportunity_analysis: "Long oil on supply tightness"

WHY THIS WORKS:
✅ OPEC is an institution (like Fed), not a temporary event
✅ Policy decisions are recurring and persistent
✅ Multiple topics get relevant perspectives

---

EXAMPLE 3: Fed Pivot Speculation
Article: "Markets price in Fed pivot, dovish shift expected"

TOPIC CREATION:
❌ DO NOT create "fed_pivot" - Temporary speculation, not persistent

ARTICLE MAPPING:
✅ Map to: ["fed_policy", "ust10y", "dxy", "eurusd"]

ARTICLE CLASSIFICATION:
✅ importance_opportunity=3, importance_trend=2, temporal_horizon="medium"

ANALYSIS RESULT:
- fed_policy.opportunity_analysis: "Dovish pivot creates duration opportunity"
- fed_policy.trend_analysis: "Potential regime shift from hawkish to dovish"
- ust10y.opportunity_analysis: "Fed pivot → lower yields → bond rally"
- dxy.risk_analysis: "Fed pivot → USD weakness"

WHY THIS WORKS:
✅ "fed_policy" is the persistent anchor
✅ "Fed pivot" captured in opportunity/trend analysis, not separate topic
✅ No temporary topic that would go stale

═══════════════════════════════════════════════════════════════════════════════
TOPIC CREATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

Before creating a new topic, verify:

1. ✅ PERSISTENT? Will we track this for 6+ months?
2. ✅ RECURRING? Does it happen repeatedly or continuously?
3. ✅ TRADABLE? Can we make investment decisions based on it?
4. ✅ SPECIFIC ENOUGH? Not too broad to link to everything?
5. ✅ BROAD ENOUGH? Not so specific it's a one-off event?
6. ❌ FORBIDDEN MIX? Does it combine Asset+Risk, Policy+Perspective, Event+Asset?

IF YES to 1-5 AND NO to 6 → CREATE TOPIC
OTHERWISE → MAP TO EXISTING TOPICS

═══════════════════════════════════════════════════════════════════════════════
GEOGRAPHIC SPECIFICITY GUIDELINES
═══════════════════════════════════════════════════════════════════════════════

GOOD SPECIFICITY (Adds Analytical Value):
✅ florida_hurricanes (specific, recurring, valuable)
✅ swedish_banks (specific sector + geography)
✅ northern_european_banks (regional grouping with analytical coherence)
✅ middle_east_geopolitical_risk (persistent regional dynamic)

ACCEPTABLE BREADTH (For Structural Analysis):
⚠️ us_natural_disasters (broader, acceptable for climate/structural analysis)
⚠️ eu_banks (broad but coherent regional grouping)

TOO BROAD (Links to Everything):
❌ natural_disasters (global, no geographic bound)
❌ geopolitical_risk (too vague, no regional focus)
❌ banks (no geographic specificity at all)

PRINCIPLE: Geographic specificity should match the analytical need and recurrence pattern.

═══════════════════════════════════════════════════════════════════════════════
FINAL ENFORCEMENT RULES
═══════════════════════════════════════════════════════════════════════════════

REJECT IMMEDIATELY:
❌ Any topic name containing: "risk", "opportunity", "trend", "catalyst", "upside", "downside"
❌ Any topic name with "X impact on Y" or "effect of X on Y" structure
❌ Any topic name combining asset + perspective or policy + perspective
❌ Any topic that is a one-time event rather than recurring phenomenon
❌ Any topic too broad to provide analytical specificity (natural_disasters, geopolitical_risk)

ACCEPT WITH CONFIDENCE:
✅ Tradable assets with clear market handles
✅ Policy institutions making recurring decisions
✅ Macro drivers with persistent relevance
✅ Recurring geographic events with analytical value
✅ Tradable sectors with appropriate geographic specificity
✅ Structural themes with 6+ month persistence and tradable implications

WHEN IN DOUBT:
- Prefer mapping to existing topics over creating new ones
- Add geographic specificity if it adds analytical precision
- Test: "Will we track this for 6+ months?" If no → don't create topic
- Test: "Is this a temporary event/narrative?" If yes → map to persistent topic

═══════════════════════════════════════════════════════════════════════════════
END OF ARCHITECTURE CONTEXT
═══════════════════════════════════════════════════════════════════════════════
"""
