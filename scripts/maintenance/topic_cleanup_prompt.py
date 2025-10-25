"""
Prompt for LLM-driven topic cleanup analysis (batch mode).
"""

from src.graph.config import describe_granularity_policy, describe_interest_areas_compact

TOPIC_CLEANUP_BATCH_PROMPT = """
You are a graph topology expert analyzing topic nodes for correctness.

""" + describe_granularity_policy() + """

CURRENT INTEREST AREAS:
""" + describe_interest_areas_compact() + """

ANCHOR TOPICS (canonical IDs):
{anchor_list}

YOUR TASK:
Analyze the following topics and determine which need:
1. RENAME: Wrong ID/name (e.g., "usdollar" should be "dxy")
2. REMOVE: Violates policy (perspective-based, too granular, temporary event, junk)
3. KEEP: Valid topic (omit from response)

TOPICS TO ANALYZE:
{topics_list}

RENAME RULES:
- If topic refers to an anchor but uses wrong ID → RENAME to anchor ID
- Examples: "usdollar" → "dxy", "sp500" → "spx", "nasdaq" → "ndx"

REMOVE RULES:
- Perspective-based naming: "_risk_", "_opportunity_", "_impact_", "_trend_"
- Temporary events: "fed_pivot", "hurricane_milton", "election_2024"
- Too granular for market: "swedish_fintech", "nigeria_economy"
- Junk topics: "gccsoftcontactlensesmarket", unclear/nonsense names
- Violates granularity policy

OUTPUT FORMAT (JSON array, only include topics that need action):
[
  {{"id": "usdollar", "action": "rename", "reason": "US Dollar should use canonical anchor dxy", "new_id": "dxy", "new_name": "US Dollar Index (DXY)"}},
  {{"id": "financialmarkets", "action": "remove", "reason": "Generic topic with no distinct analytical value", "new_id": null, "new_name": null}}
]

IMPORTANT:
- Only include topics that need RENAME or REMOVE
- Omit topics that should be kept
- Return empty array [] if all topics are valid

YOUR RESPONSE (JSON array only):
"""
