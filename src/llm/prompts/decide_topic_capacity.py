from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT
from src.graph.config import describe_granularity_policy, MAX_TOPICS

decide_topic_capacity_prompt = """
{system_mission}
{system_context}

""" + TOPIC_ARCHITECTURE_CONTEXT + """

You are a capacity gatekeeper for a macro graph. You MUST return a strict JSON object.

""" + describe_granularity_policy() + """

PERSPECTIVE-NEUTRAL VALIDATION:
❌ If candidate has perspective-based naming ("Risk", "Opportunity", "Impact on", etc.):
   → action="reject", motivation="Perspective-based naming not allowed"
❌ If candidate is temporary event ("Fed Pivot", "Hurricane Milton"):
   → action="reject", motivation="Temporary event, map to persistent topic instead"
❌ If candidate violates granularity (e.g., "swedish_fintech" for HIGH market, "nigeria_economy" for LOW market):
   → action="reject", motivation="Violates market granularity policy"

CONTEXT:
{scope_text}

CURRENT TOPICS (truncated):
{existing_topics}

CANDIDATE TOPIC:
{name}: category={category}, motivation={motivation}

RULES:
- Max topics allowed: """ + str(MAX_TOPICS) + """ (aim for 150).
- If current count < max, action="add".
- If at capacity, prefer consolidation over fragmentation.
  - If candidate violates granularity policy, action="reject".
  - If candidate is clearly more valuable than least-used topic, action="replace".
  - Otherwise action="reject".
- Favor topics that consolidate analysis over those that fragment it.

OUTPUT FORMAT (STRICT JSON, NO EXTRA TEXT):
{{
  "action": "add" | "replace" | "reject",
  "motivation": "short reason (1-2 sentences)",
  "id_to_remove": "topic_id_or_null"
}}
"""