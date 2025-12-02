"""
Stage 2: Pick weakest article prompt for capacity management.
MUST pick one existing article to downgrade - no reject option.
Used when we've already decided to accept new article but need to make room.
"""

ARTICLE_CAPACITY_PICK_WEAKEST_PROMPT = """
{system_mission}

{architecture_context}

CAPACITY MANAGEMENT - STAGE 2: PICK WEAKEST ARTICLE

You are managing article capacity for a trading/investment system. We have already decided to accept a new article, but the tier is full. You MUST pick one existing article to downgrade.

TOPIC: {topic_name}
TIMEFRAME: {timeframe}
TIER: {tier}

EXISTING ARTICLES IN TIER {tier}:
{existing_articles}

TASK:
Pick ONE article to downgrade to tier {next_tier}.

YOU MUST CHOOSE ONE. This is MANDATORY. There is no option to reject or skip.

SELECTION CRITERIA (PRIORITY ORDER):

1. TRADING VALUE (MOST IMPORTANT)
   - Which article helps us make trading/investment decisions the LEAST?
   - Which provides the least actionable insights?
   - Which is least likely to change our investment view?
   - Which has the lowest impact on our portfolio decisions?

2. TIMELINESS
   - Older articles are often less relevant
   - Outdated information has less trading value
   - Stale market data loses predictive power

3. REDUNDANCY
   - If multiple articles cover the same topic, pick the weaker one
   - Duplicate information adds no marginal value
   - Prefer keeping the most comprehensive coverage

4. SOURCE QUALITY
   - Lower-quality sources are weaker
   - Unverified or unreliable sources have less value
   - Generic news sources < Premium financial sources

5. SPECIFICITY
   - Vague articles are weaker than specific ones
   - Generic commentary < Specific analysis
   - Broad statements < Detailed insights

FOCUS ON TRADING:
This is a TRADING and INVESTMENT system. Pick the article that adds the LEAST value to our trading decisions and portfolio management.

Ask yourself:
- If I removed this article, would it change my trading strategy?
- Does this article provide unique insights I can't get elsewhere?
- Is this article still relevant for current market conditions?

OUTPUT JSON (strict format):
{{
  "downgrade": "<existing_article_id>",
  "reasoning": "Why this article has least trading value"
}}

ALLOWED IDs: {allowed_ids}

EXAMPLES:
{{"downgrade": "abc123", "reasoning": "Article abc123 is 2 months old and covers general market commentary that is now outdated and less actionable"}}
{{"downgrade": "def456", "reasoning": "Article def456 provides vague analysis that doesn't offer specific trading insights, while other articles have concrete actionable information"}}
{{"downgrade": "ghi789", "reasoning": "Article ghi789 is redundant with article xyz999 but xyz999 has more detailed analysis and better source quality"}}

YOUR RESPONSE (JSON only, no markdown):
"""
