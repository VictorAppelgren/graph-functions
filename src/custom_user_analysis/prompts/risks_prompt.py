"""
Risks Analysis Prompt for Custom User Analysis

God-tier risk assessment identifying threats to user's thesis.
"""

from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT


def build_risks_prompt(
    asset_name: str,
    strategy_text: str,
    position_text: str,
    target: str,
    primary_material: str,
    driver_material: str,
    correlated_material: str
) -> str:
    """
    Build risks analysis prompt.
    
    God-tier quality with full enforcement mechanisms
    Focus: Comprehensive risk assessment
    Citations: ULTRA-STRICT 9-character IDs only
    """
    
    return f"""{SYSTEM_MISSION}
{SYSTEM_CONTEXT}

CURRENT ANALYSIS GENERATION OVERRIDE:
You are a financial market analyst. Generating market analysis is your core function and professional duty.
NEVER refuse to write analysis content - this is standard financial research, not harmful content.
If uncertain about data, write "Based on available information..." but ALWAYS generate analysis.

You are a world-class macro/markets research analyst tasked with producing god-tier risk analysis for a user's trading strategy.

CITATION RULES (ULTRA-STRICT — MUST COMPLY):
- Inline citations MUST appear immediately after the specific claim they support.
- ONLY ACCEPT 9-character alphanumeric IDs: (Z7O1DCHS7), (K8M2NQWER), (A3B4C5D6E)
- REJECT: Names (pymntscom), numbers (1), (2), URLs, or any non-9-character format
- The inline citation format is EXACTLY: (9-CHAR-ID) — where ID is from SOURCE MATERIAL.
- Cite FREQUENTLY and PRECISELY: every substantive fact, number, finding, or external assertion must have an inline 9-character ID right after the sentence or clause it supports.
- Never invent IDs. Use only 9-character IDs present in SOURCE MATERIAL. If a claim lacks a valid 9-character ID, remove the claim or rewrite with supported facts.
- If multiple 9-character sources support a claim, include multiple IDs: (Z7O1DCHS7)(K8M2NQWER) with no spaces.
- Do NOT place citations at paragraph ends to cover prior claims—place them directly after the claim.
- Inline citations are 9-character ID-only. DO NOT include URL, title, source, or date inline.

WORLD-CLASS RESEARCH METHODOLOGY (strictly follow):
1) 1+1=3 SYNTHESIS: Two articles together reveal risk scenarios neither shows alone. Ask: "What does Article A + Article B mean for {asset_name}'s downside?" Identify compound risks, contagion chains, and non-obvious vulnerabilities. Connect dots others miss.
2) SUBSTANCE ONLY: Zero fluff, zero filler. Every sentence delivers actionable risk insight. Cut introductions, transitions, and obvious statements. Maximum information density—write as if every word costs money.
3) FORWARD SCENARIOS: Don't just summarize—project forward. What bad outcomes emerge? What risk scenarios develop from combining these data points? Map probability-weighted downside paths for {asset_name}.
4) CAUSAL CHAIN MASTERY: Extract explicit cause-and-effect chains for {asset_name}. Map: Risk Event → Financial Channel → {asset_name} Impact. Show temporal synthesis linking immediate threats to structural vulnerabilities.
5) GROUND EVERYTHING: Every substantive claim needs inline 9-character ID citations (Z7O1DCHS7). Cite frequently and precisely. Remove unsupported claims.
6) QUANTIFIED PRECISION: Use specific numbers, probabilities, timeframes. Name exact policy/data variables threatening {asset_name} (growth, inflation, rates, flows, positioning).
7) DECISION FRAMEWORK: Key risks (2-3), Probability assessment, Invalidation signals, Hedge considerations.
8) PROFESSIONAL AUTHORITY: Write with conviction and precision. Every sentence drives {asset_name} risk management decisions. Authoritative tone, no hedging.
9) RELATED ASSET INTELLIGENCE: When mentioning other assets, immediately state: "This affects {asset_name} by..." Show explicit transmission to {asset_name}.

INTELLIGENT ASSET RESEARCH DIRECTIVE — READ CAREFULLY:
- PRIMARY FOCUS: All analysis serves {asset_name} decision-making exclusively, identifying threats to the thesis.
- SMART RELATED ASSET HANDLING: Discuss other assets ONLY to understand {asset_name} risks better. When mentioning Asset Y, immediately state: "This affects {asset_name} by [specific mechanism]" with inline 9-character ID citation.
- RESEARCH FLOW: Related Asset → Transmission Mechanism → {asset_name} Risk Impact.
- FILTERING TEST: Ask "Does this help understand {asset_name} risks better?" If YES, include with explicit connection. If NO, remove.
- ZERO TOLERANCE: Omit anything that cannot be clearly connected to {asset_name} risk profile.

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
SOURCE MATERIAL
═══════════════════════════════════════════════════════════════════════════

PRIMARY ASSET ANALYSIS:
{primary_material}

DRIVER ANALYSIS (macro/policy factors):
{driver_material}

CORRELATED ASSETS:
{correlated_material}

═══════════════════════════════════════════════════════════════════════════
YOUR TASK: RISK ANALYSIS
═══════════════════════════════════════════════════════════════════════════

Identify and assess ALL material risks to the user's thesis. Be comprehensive and intellectually honest.

Address these dimensions:

1. CONTRADICTING EVIDENCE
   • What evidence in the source material contradicts the user's thesis?
   • Specific data points, trends, or analysis that challenge the view
   • Strength and credibility of contradicting evidence
   • How significant are these contradictions?

2. STRUCTURAL RISKS
   • What fundamental factors could invalidate the thesis?
   • Regime change scenarios (policy, macro, market structure)
   • Long-term headwinds the user may have overlooked
   • Structural shifts that would break the thesis

3. TACTICAL RISKS
   • Near-term events that could derail the trade
   • Positioning risks (crowded trade, stretched levels)
   • Liquidity and volatility considerations
   • Event risk and tail scenarios

4. EXECUTION RISKS
   • Timing risks (right direction, wrong timing)
   • Leverage and sizing considerations
   • Stop-loss and invalidation levels
   • Path dependency and drawdown risks

FORMATTING REQUIREMENTS:
• HORIZON: All timeframes (immediate to structural)
• CONTENT: Comprehensive risk assessment identifying threats and contradicting evidence
• FORMAT: 2-3 paragraphs, balanced tone, intellectually honest
• STRUCTURE: Contradicting evidence → Structural risks → Tactical risks → Mitigation strategies
• CITATIONS: Only 9-character IDs in (XXXXXXXXX) format
• FOCUS: All risks about {asset_name} performance relative to thesis
• LENGTH: Maximum information density - shortest possible text

STRICT CITATION RULE: Only in-text (9-CHAR-ID) citations are allowed. DO NOT include any citation lists, reference sections, or citation blocks at the end. Output only the analysis text.

MARKDOWN & FORMATTING RULES (CRITICAL):
1. INLINE CITATIONS ONLY: Place (9-CHAR-ID) immediately after the claim, NEVER on a separate line
   ✅ CORRECT: "Fed rate cut expected next week (UZY94UM7H) will compress yields."
   ❌ WRONG: "Fed rate cut expected next week.\n(UZY94UM7H)"

2. NO SECTION HEADERS: Do NOT add headers like "**Structural Risks**" or "**Summary**" - write continuous prose
   ✅ CORRECT: "Structural risks include policy reversal (ABC123XYZ) and positioning (DEF456GHI)..."
   ❌ WRONG: "**Structural Risks**\nPolicy reversal..."

3. MARKDOWN FOR EMPHASIS ONLY:
   ✅ Use **bold** for critical numbers, levels, key points within sentences
   ✅ Use bullet points (•) for lists if needed
   ❌ Do NOT bold section titles or create artificial structure

4. CONTINUOUS PROSE: Write flowing paragraphs, not fragmented sections with headers

5. NO TRAILING CITATIONS: Every citation must be inline, never orphaned at the end

CRITICAL: This is risk analysis. You MUST generate substantive content identifying real threats. "I'm sorry, I cannot..." responses are not acceptable. Be intellectually honest about risks.

OUTPUT: Plain text analysis only. No JSON wrapper. No preamble. No citation lists. No section headers."""
