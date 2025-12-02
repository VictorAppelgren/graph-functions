"""
Stage 1: Gate decision prompt for article capacity management.
Decides if new article should be accepted, downgraded to lower tier, or rejected.
Can downgrade either NEW article or EXISTING article.
"""

ARTICLE_CAPACITY_MANAGER_PROMPT = """
{system_mission}

{architecture_context}

CAPACITY MANAGEMENT - STAGE 1: GATE DECISION

You are managing article capacity for a trading/investment system. The topic has reached its capacity limit for a specific timeframe and importance tier.

TOPIC: {topic_name}
TIMEFRAME: {timeframe}
TIER: {tier}
CAPACITY: {count}/{max_allowed} (FULL - must make a decision)

NEW ARTICLE:
Source: {new_source}
Published: {new_published}
Summary: {new_summary}

EXISTING ARTICLES IN TIER {tier}:
{existing_articles}

TASK:
Decide what to do with the NEW article.

YOU HAVE 3 OPTIONS:

1. DOWNGRADE NEW ARTICLE (not good enough for tier {tier})
   → Set: downgrade="NEW", reject=false
   → We will try adding it at tier {next_tier} instead
   → Choose if: New article is decent but not tier {tier} quality

2. DOWNGRADE EXISTING ARTICLE (new article is better)
   → Set: downgrade="<existing_article_id>", reject=false
   → We will downgrade that existing article to tier {next_tier}
   → We will add new article at tier {tier}
   → Choose if: New article is better than at least one existing article

3. REJECT NEW ARTICLE (not good enough at all)
   → Set: reject=true, downgrade="NEW"
   → We will not add this article
   → Choose if: Article is low-quality, redundant, or irrelevant

TIER QUALITY GUIDELINES:
- Tier 3 (Premium): Market-moving, high-impact, actionable trading insights
- Tier 2 (Standard): Relevant, useful, good quality information
- Tier 1 (Filler): Background context, less critical information
- Tier 0 (Archive): Historical reference only

DECISION CRITERIA (PRIORITY ORDER):

1. TRADING VALUE (MOST IMPORTANT)
   - Does this help us make better trading/investment decisions?
   - Does it provide actionable insights?
   - Does it change our view of risks/opportunities?
   - Is it market-moving information?

2. TIMELINESS
   - Is this current and relevant?
   - Older articles lose value over time

3. SOURCE QUALITY
   - Is this from a reliable, authoritative source?
   - Premium sources (Bloomberg, Reuters, FT) > Generic sources

4. SPECIFICITY
   - Is this specific and detailed or vague and generic?
   - Specific insights > General commentary

5. NOVELTY
   - Is this new information or redundant?
   - Novel insights > Duplicate information

IMPORTANT GUIDELINES:
- Be GENEROUS with tier 2 (standard quality) - most good articles belong here
- Only reject if article is truly low-quality or completely redundant
- Focus on TRADING VALUE above all else
- When in doubt between downgrading NEW vs EXISTING, compare their trading value

OUTPUT JSON (strict format):
{{
  "downgrade": "NEW" or "<existing_article_id>",
  "reject": true or false,
  "reasoning": "Brief explanation focusing on trading value"
}}

ALLOWED IDs: NEW, {allowed_ids}

EXAMPLES:
{{"downgrade": "NEW", "reject": false, "reasoning": "New article is decent but existing tier 3 articles provide more actionable trading insights"}}
{{"downgrade": "abc123", "reject": false, "reasoning": "New article provides fresher market-moving data. Article abc123 is now stale and less relevant"}}
{{"downgrade": "NEW", "reject": true, "reasoning": "New article is low-quality and redundant with existing coverage"}}

YOUR RESPONSE (JSON only, no markdown):
"""
