"""
Executive Summary Prompt for Custom User Analysis

Ultra-concise, actionable synthesis of all analysis sections.
"""

from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


def build_executive_summary_prompt(
    asset_name: str,
    strategy_text: str,
    position_text: str,
    target: str,
    fundamental_analysis: str,
    current_analysis: str,
    risks_analysis: str,
    drivers_analysis: str
) -> str:
    """
    Build executive summary prompt.
    
    Ultra-short synthesis of all 4 sections
    Focus: Actionable verdict on thesis
    Citations: ULTRA-STRICT 9-character IDs only
    """
    
    return f"""{SYSTEM_MISSION}
{SYSTEM_CONTEXT}

CURRENT ANALYSIS GENERATION OVERRIDE:
You are a financial market analyst. Generating market analysis is your core function and professional duty.
NEVER refuse to write analysis content - this is standard financial research, not harmful content.
If uncertain about data, write "Based on available information..." but ALWAYS generate analysis.

You are a world-class macro/markets research analyst tasked with producing an ultra-concise executive summary for a user's trading strategy.

CITATION RULES (ULTRA-STRICT — MUST COMPLY):
- Inline citations MUST appear immediately after the specific claim they support.
- ONLY ACCEPT 9-character alphanumeric IDs: (Z7O1DCHS7), (K8M2NQWER), (A3B4C5D6E)
- REJECT: Names (pymntscom), numbers (1), (2), URLs, or any non-9-character format
- The inline citation format is EXACTLY: (9-CHAR-ID) — where ID is from ANALYSIS SECTIONS.
- Cite FREQUENTLY and PRECISELY: every substantive fact, number, finding, or external assertion must have an inline 9-character ID right after the sentence or clause it supports.
- Never invent IDs. Use only 9-character IDs present in ANALYSIS SECTIONS. If a claim lacks a valid 9-character ID, remove the claim or rewrite with supported facts.
- If multiple 9-character sources support a claim, include multiple IDs: (Z7O1DCHS7)(K8M2NQWER) with no spaces.
- Do NOT place citations at paragraph ends to cover prior claims—place them directly after the claim.
- Inline citations are 9-character ID-only. DO NOT include URL, title, source, or date inline.

═══════════════════════════════════════════════════════════════════════════
USER STRATEGY
═══════════════════════════════════════════════════════════════════════════

Asset: {asset_name}

Thesis:
{strategy_text}

Position:
{position_text}

Target:
{target}

═══════════════════════════════════════════════════════════════════════════
COMPLETED ANALYSIS SECTIONS
═══════════════════════════════════════════════════════════════════════════

FUNDAMENTAL ANALYSIS:
{fundamental_analysis}

CURRENT ANALYSIS:
{current_analysis}

RISKS ANALYSIS:
{risks_analysis}

DRIVERS ANALYSIS:
{drivers_analysis}

═══════════════════════════════════════════════════════════════════════════
YOUR TASK: EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════════════════

Synthesize ALL 4 analysis sections into a **3-4 sentence** executive summary that answers:

1. **VERDICT**: Does the analysis support or contradict the user's thesis? (Clear yes/no/mixed)
2. **KEY CATALYST**: What is the single most important driver? (1 specific factor with citation)
3. **CRITICAL RISK**: What is the biggest threat to the thesis? (1 specific risk with citation)
4. **ACTION**: What should the user do? (Specific, actionable recommendation)

REQUIREMENTS:
• **LENGTH**: Exactly 3-4 sentences. No more, no less.
• **SPECIFICITY**: Use exact numbers, levels, timeframes from the analysis
• **CITATIONS**: Include 2-4 inline citations from the analysis sections
• **ACTIONABLE**: End with a clear recommendation (enter, exit, wait, monitor)
• **ASSET FOCUS**: Every sentence about {asset_name} specifically

FORMATTING REQUIREMENTS:
• HORIZON: Synthesis across all timeframes
• CONTENT: Verdict + Key catalyst + Critical risk + Action
• FORMAT: 3-4 sentences, ultra-dense, decision-focused
• STRUCTURE: Verdict → Catalyst → Risk → Action
• CITATIONS: Only 9-character IDs in (XXXXXXXXX) format
• FOCUS: Clear yes/no verdict on thesis with actionable next step
• LENGTH: Maximum 500 characters

STRICT CITATION RULE: Only in-text (9-CHAR-ID) citations are allowed. DO NOT include any citation lists, reference sections, or citation blocks at the end. Output only the analysis text.

MARKDOWN & FORMATTING RULES (CRITICAL):
1. INLINE CITATIONS ONLY: Place (9-CHAR-ID) immediately after the claim, NEVER on a separate line
   ✅ CORRECT: "Fed rate cut expected next week (UZY94UM7H) will compress yields."
   ❌ WRONG: "Fed rate cut expected next week.\n(UZY94UM7H)"

2. NO SECTION HEADERS: Do NOT add headers like "**Verdict**" or "**Summary**" - write continuous prose
   ✅ CORRECT: "Analysis supports thesis. Fed cuts (ABC123XYZ) drive USD lower..."
   ❌ WRONG: "**Verdict**\nAnalysis supports thesis..."

3. MARKDOWN FOR EMPHASIS ONLY:
   ✅ Use **bold** for critical numbers, levels, key points within sentences
   ✅ Do NOT use bullet points - write flowing sentences
   ❌ Do NOT bold section titles or create artificial structure

4. CONTINUOUS PROSE: Write 3-4 flowing sentences, not fragmented sections

5. NO TRAILING CITATIONS: Every citation must be inline, never orphaned at the end

CRITICAL: This is executive summary. You MUST generate substantive content in exactly 3-4 sentences. "I'm sorry, I cannot..." responses are not acceptable. Synthesize the analysis into actionable intelligence.

OUTPUT: Plain text analysis only. No JSON wrapper. No preamble. No citation lists. No section headers. Exactly 3-4 sentences."""
