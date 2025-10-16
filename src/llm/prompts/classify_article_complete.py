"""
Unified article classifier - replaces find_time_frame, find_category, find_impact
Single LLM call returns: temporal_horizon + category + 4x perspective scores
"""

CLASSIFY_ARTICLE_COMPLETE_PROMPT = """
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS MACRO/MARKETS ARTICLE CLASSIFIER working on the Saga Graph.

TASK: Analyze article and provide COMPLETE classification in ONE JSON object.

🚨 CRITICAL OUTPUT REQUIREMENTS 🚨
- Output ONLY the JSON object, NOTHING ELSE
- NO explanations before or after the JSON
- NO markdown code blocks (no ```json or ```)
- NO commentary like "Here's the classification:" or "Hope this helps!"
- JUST the raw JSON object starting with {{ and ending with }}
- All field names MUST be lowercase with underscores
- All string values MUST use double quotes, not single quotes
- All integer values MUST be numbers (0, 1, 2, 3), not strings ("0", "1")

OUTPUT FIELDS (all required, exact names):
1. 'motivation': Your reasoning (1-2 sentences, string)
2. 'temporal_horizon': EXACTLY ONE OF: "fundamental" | "medium" | "current" | "invalid"
3. 'category': Article category type (string from list below)
4. 'importance_risk': Risk score (integer 0-3, NOT string)
5. 'importance_opportunity': Opportunity score (integer 0-3, NOT string)
6. 'importance_trend': Trend score (integer 0-3, NOT string)
7. 'importance_catalyst': Catalyst score (integer 0-3, NOT string)

═══ TEMPORAL HORIZON ═══
- "fundamental": Long-term structural (6+ months) - regime shifts, secular trends
- "medium": Medium-term trends (1-6 months) - cyclical moves, policy shifts
- "current": Breaking news (0-4 weeks) - immediate catalysts, real-time data
- "invalid": Corrupted/spam/irrelevant/no financial importance

═══ CATEGORY TYPES ═══
{categories}

═══ PERSPECTIVE SCORING (0-3, INDEPENDENT) ═══

**CRITICAL: Each perspective scored INDEPENDENTLY**
- Article can score high on multiple perspectives (rare but valid)
- Most articles: 1 dominant perspective (score 2-3), others 0-1
- Typical: ONE perspective scores ≥2, rest are 0-1
- Rare: TWO perspectives score ≥2 (dual-edged stories)
- Very rare: THREE+ perspectives score ≥2 (exceptional articles only)
- Be STRICT - score 3 only for exceptional, unambiguous cases

**RISK (Downside/Threat):**
0 = No risk content
1 = Risk mentioned in passing, minor concern
2 = Significant risk with clear mechanism and magnitude
3 = EXCEPTIONAL: Critical existential threat, immediate systemic danger

**OPPORTUNITY (Upside/Catalyst):**
0 = No opportunity content
1 = Opportunity mentioned in passing, speculative
2 = Significant opportunity with clear mechanism and conviction
3 = EXCEPTIONAL: Major game-changing opportunity, high-conviction upside

**TREND (Structural Shift):**
0 = No trend content
1 = Trend mentioned, minor observation
2 = Clear structural shift with multi-year implications
3 = EXCEPTIONAL: Major regime change, secular transformation

**CATALYST (Immediate Trigger):**
0 = No catalyst content
1 = Potential catalyst mentioned, timing unclear
2 = Clear catalyst with specific timing (days/weeks)
3 = EXCEPTIONAL: Immediate catalyst forcing action RIGHT NOW (hours/days)

═══ SCORING EXAMPLES ═══

Example 1 - Typical (ONE dominant perspective):
"Fed cuts boost growth expectations"
→ importance_risk: 0
→ importance_opportunity: 2 (growth boost, clear mechanism)
→ importance_trend: 0
→ importance_catalyst: 1 (mentioned but not immediate)

Example 2 - Dual-edged (TWO perspectives, RARE):
"Fed cuts boost growth but risk inflation reacceleration"
→ importance_risk: 2 (inflation threat, clear mechanism)
→ importance_opportunity: 2 (growth boost, clear mechanism)
→ importance_trend: 0
→ importance_catalyst: 0

Example 3 - Pure Risk:
"Market crash risk as Fed signals emergency hikes"
→ importance_risk: 3 (EXCEPTIONAL: systemic threat)
→ importance_opportunity: 0
→ importance_trend: 0
→ importance_catalyst: 2 (clear timing)

Example 4 - Exceptional Multi-Perspective (VERY RARE):
"BREAKING: Fed emergency cuts NOW amid systemic crisis, reshaping monetary regime"
→ importance_risk: 3 (systemic crisis)
→ importance_opportunity: 0
→ importance_trend: 3 (regime change)
→ importance_catalyst: 3 (immediate action)
(THREE 3s only for truly exceptional events!)

Example 5 - Invalid:
"Celebrity gossip, no financial content"
→ temporal_horizon: "invalid"
→ All scores: 0

═══ ARTICLE TEXT ═══
{article_text}

═══ REQUIRED OUTPUT FORMAT (STRICT!) ═══

🚨 ULTRA-CRITICAL: Your ENTIRE response must be ONLY this JSON object 🚨

CORRECT OUTPUT (copy this structure EXACTLY):
{{
  "motivation": "Brief reasoning here",
  "temporal_horizon": "fundamental",
  "category": "policy",
  "importance_risk": 0,
  "importance_opportunity": 2,
  "importance_trend": 0,
  "importance_catalyst": 1
}}

❌ WRONG - DO NOT DO THIS:
"Here's my classification: {{...}}"
"Based on the article, I believe: {{...}}"
"```json {{...}} ```"
"{{...}} Hope this helps!"

✅ RIGHT - DO THIS:
{{...}}

VALIDATION CHECKLIST (before you respond):
✅ Does response start with {{ ?
✅ Does response end with }} ?
✅ Are all 7 fields present?
✅ Is temporal_horizon one of: "fundamental", "medium", "current", "invalid"?
✅ Are all importance scores integers (0, 1, 2, or 3)?
✅ Are field names lowercase with underscores?
✅ Is there NO text before or after the JSON?

YOUR RESPONSE (JSON ONLY):
"""
