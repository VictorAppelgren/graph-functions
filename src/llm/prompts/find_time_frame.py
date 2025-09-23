find_time_frame_prompt = """
{system_mission}
{system_context}

YOU ARE A WORLD-CLASS MACRO/MARKETS TIME FRAME IDENTIFIER working on the Saga Graph.

TASK:
- Analyze the article text and classify its time horizon
- Output a SINGLE JSON OBJECT with exactly these fields:
    - 'motivation': 1-2 sentences explaining your classification reasoning
    - 'horizon': MUST be exactly one of: "fundamental" | "medium" | "current" | "invalid"

TIME HORIZON DEFINITIONS:
- "fundamental": Long-term structural drivers, policy frameworks, economic fundamentals (6+ months)
- "medium": Medium-term trends, analysis, outlook, forecasts (1-6 months)  
- "current": Breaking news, immediate events, real-time developments (0-4 weeks)
- "invalid": Article is corrupted, empty, spam, irrelevant, OR contains no important financial information

CLASSIFICATION RULES:
1. If article contains IMPORTANT financial/market information: Choose fundamental/medium/current based on timeframe
2. If article is corrupted, empty, spam, irrelevant, or lacks important information: Use "invalid"
3. IMPORTANT = affects markets, policy, economics, trading decisions, or financial analysis
4. NOT IMPORTANT = general news, entertainment, sports, personal stories, technical errors
5. When in doubt about importance: err on the side of "invalid" to maintain data quality
6. ALWAYS provide both fields - never return empty response

ARTICLE TEXT:
{article_text}

EXAMPLES:
{{"motivation": "Discusses Fed policy framework and long-term inflation targets - important for markets.", "horizon": "fundamental"}}
{{"motivation": "Reports today's jobs data and immediate market reaction - time-sensitive information.", "horizon": "current"}}
{{"motivation": "Article about celebrity gossip - not relevant to financial markets.", "horizon": "invalid"}}
{{"motivation": "Text is corrupted/unreadable - cannot extract meaningful information.", "horizon": "invalid"}}
{{"motivation": "General news with no market implications - lacks financial importance.", "horizon": "invalid"}}

REQUIRED OUTPUT FORMAT - JSON ONLY:
"""