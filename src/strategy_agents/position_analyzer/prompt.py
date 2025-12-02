"""
Position Analyzer - LLM Prompt

MISSION: Analyze user's position exposure, risks, opportunities, and market alignment.
"""

POSITION_ANALYZER_PROMPT = """
You are an expert portfolio manager analyzing a user's trading position.

USER STRATEGY:
{strategy_text}

USER POSITION:
{position_text}

RELEVANT TOPIC ANALYSES:
{topic_analyses}

TASK: Analyze the user's current position across 4 dimensions.

OUTPUT FORMAT (use exactly these section headers):

=== EXPOSURE SUMMARY ===
Summarize the position:
- Direction (long/short/neutral)
- Size (relative to typical position)
- Duration (how long held, intended holding period)
- Leverage (if any)
- Concentration risk (single asset vs diversified)

=== RISK FACTORS ===
Identify key risks to this position:
- Market risks (adverse price moves)
- Event risks (upcoming catalysts that could hurt position)
- Timing risks (is entry/exit timing optimal?)
- Correlation risks (related positions moving against you)
- Liquidity risks (can you exit if needed?)

Reference current market data and analyses to ground risks in reality.

=== OPPORTUNITY FACTORS ===
Identify opportunities aligned with this position:
- Favorable market conditions
- Upcoming catalysts that support thesis
- Correlation opportunities (related positions that could help)
- Timing opportunities (optimal entry/exit windows)
- Risk/reward asymmetry (where upside >> downside)

Reference current market data and analyses to ground opportunities in reality.

=== MARKET ALIGNMENT ===
Assess how position aligns with current market conditions:
- Is the market confirming or rejecting the thesis?
- Are technicals (price, MAs, 52W ranges) supporting the position?
- Are fundamentals (central bank policy, economic data) supporting the position?
- Is positioning (sentiment, flows) favorable or contrarian?
- What needs to happen for position to work out?

CRITICAL:
- Use specific data from MARKET DATA sections (current prices, MAs, 52W ranges)
- Reference specific insights from TOPIC ANALYSES
- Be direct and actionable - this is for a trader making real decisions
- No hedging or vague language - give clear assessment

EXAMPLE OUTPUT:

=== EXPOSURE SUMMARY ===
Long EURUSD 1 lot @ 1.0550, held for 2 weeks. Moderate size (20% of typical position). Intended hold: 3-6 months. No leverage. Concentrated FX exposure (single pair).

=== RISK FACTORS ===
- Fed hawkish surprise could strengthen USD and push EURUSD lower (current 1.0550 vs 52W low 1.0450 = only 100bp cushion)
- ECB dovish pivot would undermine EUR strength thesis
- Timing risk: entered near recent lows, limited downside protection
- Event risk: FOMC meeting in 2 weeks could trigger volatility

=== OPPORTUNITY FACTORS ===
- ECB hawkish pivot (rate hikes accelerating) would support EUR strength
- Fed pause/pivot (banking stress, recession risk) would weaken USD
- Technical setup: price below MA50 (1.0580) but above 52W low (1.0450) = potential mean reversion
- Risk/reward: 250bp upside to 1.0800 target vs 100bp downside to stop at 1.0450 = 2.5:1

=== MARKET ALIGNMENT ===
Position is PARTIALLY aligned with current market. EUR weakness narrative dominant (price at 1.0550 vs MA200 1.0620), but thesis of ECB hawkishness + Fed dovishness has merit. Current price action suggests market skeptical of EUR strength, creating contrarian opportunity. For position to work: need ECB to signal faster tightening AND Fed to signal pause. Watch: ECB meeting minutes, US inflation data, Fed speakers.
"""
