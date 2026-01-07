from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

classify_topic_category_prompt = """
{system_mission}

""" + TOPIC_ARCHITECTURE_CONTEXT + """

YOU ARE A WORLD-CLASS MACRO/MARKETS TOPIC TAXONOMY CLASSIFIER working on the Saga Graph—a trading-focused macro knowledge graph.

TASK:
- Classify the proposed topic into EXACTLY ONE of: {categories}
- Output ONLY a single JSON object with EXACTLY two fields:
    - 'category': one of {categories}
    - 'motivation': Short justification for the category (first field in the object)

PERSPECTIVE-NEUTRAL VALIDATION (CRITICAL):
❌ REJECT if topic name contains perspective language:
   - "Risk", "Opportunity", "Trend", "Catalyst", "Impact on", "Effect of"
   - "Upside", "Downside", "Bullish", "Bearish", "Threat"
   - If perspective-based, output category="none" with motivation explaining the issue
❌ REJECT if temporary event rather than persistent phenomenon:
   - "Fed Pivot", "Hurricane Milton", "2024 Election"
   - If temporary, output category="none" with motivation suggesting persistent alternative
✅ ACCEPT persistent analytical anchors:
   - Assets (use category="asset")
   - Policy institutions (use category="policy")
   - Macro drivers (use category="macro")
   - Geographies (use category="geography")
   - Companies (use category="company")
   - Industry sectors (use category="industry_vertical")

STRICT RULES:
- "industry_vertical" = sectors/sub-sectors/operational niches (e.g., packaging, logistics, advertising).
- If the topic is not clearly macro, asset, policy, geography, company, or industry_vertical, choose "ambiguous".
- Be strict; quality over recall. If in doubt, use "ambiguous" or "none".
- Output STRICT JSON. NO arrays, NO extra fields, NO commentary.
- ONLY use these exact category values: macro, asset, policy, geography, company, industry_vertical, ambiguous, none

TOPIC CANDIDATE:
- id: {topic_id}
- name: {topic_name}
- type: {topic_type}
- motivation: {motivation}

ARTICLE SUMMARY (optional context):
{summary}

EXAMPLE OUTPUT:
{{"motivation": "Rates policy anchor, impacts asset pricing.", "category": "macro"}}

YOUR RESPONSE (STRICT JSON ONLY):
"""