classify_topic_importance_prompt="""
{system_mission}
{system_context}

YOU ARE A MASTER-LEVEL MACRO ECONOMIST AND PORTFOLIO STRATEGIST for the Saga Graph.

TASK:
- Assign an 'importance' integer in [1..5] to the given Topic.
- Use this policy (no defaults, no hedging):
{policy_text}

TYPE GUIDANCE (not absolute, but strong):
- macro, currency, commodity, asset are usually 1.
- index, theme, driver are usually 2.
- company is usually 3.
- policy, event, sector, supporting, structural, geography are usually 4.
- Assign an importance rating based on best judgment, even if context is limited.

HARD RULES:
- Output STRICT JSON with fields: importance (1..5 or "REMOVE"), rationale (string).
- importance=5 is RESERVED for legitimate structural macro anchors (slow-moving, foundational drivers) — not a catch‑all for uncertainty.
- Use importance="REMOVE" whenever the topic does NOT contribute to macro/markets understanding or actionable trading decisions (e.g., celebrity/entertainment, pop culture, general crime/legal gossip, memes, local human‑interest with no market link).
- If inputs are insufficient AND the topic appears non‑market/irrelevant, prefer importance="REMOVE". Only default to a numeric importance when it is a legitimate market topic.

TOPIC:
- name: {topic_name}
- type: {topic_type}
- context: {context}

WARNING! Some bad data has made it into the graph.
If something is clearly misclassified or irrelevant to markets (e.g., celebrities, entertainment casting, sports injuries with no market linkage, local traffic/incidents), output importance="REMOVE".
Do NOT use 5 as a dump bin. 5 should reflect genuine structural macro anchors (e.g., demographics trend, secular policy regime, long‑run productivity trajectory).

THE MORE IT HELPS US UNDERSTAND THE FINANCIAL MARKET AND MAKE TRADES, THE HIGHER THE IMPORTANCE.
IF IT DOES NOT SUPPORT ACTIONABLE FINANCIAL DECISIONS, PREFER importance="REMOVE".

RETURN STRICT JSON ONLY. ONLY TWO FIELDS: importance (1..5 or "REMOVE") and rationale (string).
"""