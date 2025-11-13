"""
Prompt for article capacity management LLM decision.
Decides whether to remove, downgrade, or reject when adding new article at capacity.
"""

ARTICLE_CAPACITY_MANAGER_PROMPT = """
{system_mission}

{architecture_context}

CAPACITY MANAGEMENT TASK:
You are managing article capacity for a topic's portfolio. The topic has reached its capacity limit for a specific timeframe and importance tier.

TOPIC: {topic_name}
TIMEFRAME: {timeframe} (fundamental=6+ months, medium=3-6 months, current=0-3 weeks)
IMPORTANCE TIER: {importance_tier} (1=filler, 2=standard, 3=premium)
CAPACITY STATUS: {current_count} / {max_allowed} articles in this tier

NEW ARTICLE TO ADD:
ID: {new_article_id}
Source: {new_article_source}
Published: {new_article_published}
Summary: {new_article_summary}
Dominant Perspective: {dominant_perspective} (risk/opportunity/trend/catalyst)
Importance Scores: Risk={risk}, Opportunity={opp}, Trend={trend}, Catalyst={cat}

EXISTING ARTICLES (same timeframe + tier):
{existing_articles_formatted}

DECISION REQUIRED:
Should we add this new article? If yes, what should we do to make room?

OPTIONS:
1. "remove": Remove an existing article completely
   - Choose the LEAST valuable article to remove
   - Consider: redundancy, staleness, lower quality source, less relevant perspective
   - Only if new article is clearly better
   
2. "downgrade": Downgrade an existing article's importance
   - Choose an article that's good but overrated for this tier
   - Suggest new importance (must be < {importance_tier})
   - Preserves article but reduces its weight in analysis
   
3. "reject": Do NOT add the new article
   - New article doesn't justify replacing any existing ones
   - Existing portfolio is already optimal
   - Prefer this if uncertain

RESPONSE FORMAT (strict JSON only):
{{
  "motivation": "Brief explanation (1-2 sentences)",
  "action": "remove" | "downgrade" | "reject",
  "target_article_id": "article_id" | null,
  "new_importance": 1 | 2 | null
}}

PRIORITIZATION RULES:
1. DIVERSITY: Prefer removing redundant perspectives
2. FRESHNESS: Prefer removing stale articles (old published_at)
3. SOURCE QUALITY: Prefer removing lower-quality sources
4. IMPORTANCE ACCURACY: Downgrade overrated articles
5. UNCERTAINTY: If unsure → choose "reject"

ALLOWED TARGET IDS:
{allowed_ids_str}

EXAMPLES:
{{"motivation": "New article provides fresher data on same topic. Removing older redundant article.", "action": "remove", "target_article_id": "a123", "new_importance": null}}
{{"motivation": "Article a124 is good but overrated for tier 3. Downgrading to tier 2.", "action": "downgrade", "target_article_id": "a124", "new_importance": 2}}
{{"motivation": "New article doesn't add value beyond existing portfolio.", "action": "reject", "target_article_id": null, "new_importance": null}}

YOUR RESPONSE (JSON only, no markdown):
"""
