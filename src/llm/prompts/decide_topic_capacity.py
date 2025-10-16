from src.llm.prompts.topic_architecture_context import TOPIC_ARCHITECTURE_CONTEXT

decide_topic_capacity_prompt = """
{system_mission}
{system_context}

""" + TOPIC_ARCHITECTURE_CONTEXT + """

You are a capacity gatekeeper for a demo-mode macro graph. You MUST return a strict JSON object.

PERSPECTIVE-NEUTRAL VALIDATION:
❌ If candidate has perspective-based naming ("Risk", "Opportunity", "Impact on", etc.):
   → action="reject", motivation="Perspective-based naming not allowed"
❌ If candidate is temporary event ("Fed Pivot", "Hurricane Milton"):
   → action="reject", motivation="Temporary event, map to persistent topic instead"
❌ If candidate is too broad ("Natural Disasters", "Geopolitical Risk"):
   → action="reject", motivation="Too broad, needs geographic specificity"

CONTEXT:
{scope_text}

CURRENT TOPICS (truncated):
{existing_topics}

CANDIDATE TOPIC:
{name}: importance={importance}, category={category}, motivation={motivation}

RULES:
- Max topics allowed: {max_topics}.
- If current count < max, action="add".
- If at capacity, compare candidate vs the least important existing topic.
  - If candidate is clearly more important/relevant to the scope than the weakest topic, action="replace" and set id_to_remove=that topic's id.
  - Otherwise action="reject".
- Priority weights: Priority 1 areas outrank Priority 2 if comparable importance.
- Be conservative on replace: only replace when confident the candidate is stronger for this demo scope.

OUTPUT FORMAT (STRICT JSON, NO EXTRA TEXT):
{{
  "action": "add" | "replace" | "reject",
  "motivation": "short reason (1-2 sentences)",
  "id_to_remove": "topic_id_or_null"
}}
"""