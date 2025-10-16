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
   - If perspective-based, output category="INVALID" with motivation explaining the issue
❌ REJECT if temporary event rather than persistent phenomenon:
   - "Fed Pivot", "Hurricane Milton", "2024 Election"
   - If temporary, output category="INVALID" with motivation suggesting persistent alternative
✅ ACCEPT persistent analytical anchors:
   - Tradable assets, policy institutions, macro drivers
   - Recurring geographic events (florida_hurricanes, california_wildfires)
   - Tradable sectors with geographic specificity

STRICT RULES:
- "industry_vertical" = sectors/sub-sectors/operational niches (e.g., packaging, logistics, advertising, sterilized packaging).
- If the topic is not clearly a macro driver, asset, policy, geography, or company, choose "ambiguous".
- Be strict; quality over recall. If in doubt, do NOT place in macro/asset/policy/geography/company.
- Output STRICT JSON. NO arrays, NO extra fields, NO commentary.

TOPIC CANDIDATE:
- id: {topic_id}
- name: {topic_name}
- type: {topic_type}
- motivation: {motivation}

ARTICLE SUMMARY (optional context):
{summary}

EXAMPLE OUTPUT:
{{"motivation": "Rates policy anchor, impacts asset pricing.", "category": "macro_driver"}}

YOUR RESPONSE (STRICT JSON ONLY):
"""