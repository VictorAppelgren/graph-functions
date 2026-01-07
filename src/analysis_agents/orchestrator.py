"""
Analysis Agent Orchestrator - GOD-TIER RISK & CHAIN REACTION FOCUSED

Composes specialized agents based on section needs.

Usage:
    python -m src.analysis_agents.orchestrator eurusd                    # Full pipeline (all 8 sections)
    python -m src.analysis_agents.orchestrator eurusd full               # Full pipeline (all 8 sections)
    python -m src.analysis_agents.orchestrator eurusd chain_reaction_map # Single section
    python -m src.analysis_agents.orchestrator all                       # Full pipeline (all 8 sections)
"""

from typing import Dict, Any, List, Tuple, Optional, Set
from src.analysis_agents.source_registry import SourceRegistry
from src.analysis_agents.synthesis_scout.agent import SynthesisScoutAgent
from src.analysis_agents.contrarian_finder.agent import ContrarianFinderAgent
from src.analysis_agents.depth_finder.agent import DepthFinderAgent
from src.analysis_agents.writer.agent import WriterAgent
from src.analysis_agents.critic.agent import CriticAgent
from src.analysis_agents.source_checker.agent import SourceCheckerAgent
from src.analysis_agents.section_config import AGENT_SECTIONS, AGENT_SECTION_CONFIGS
from src.citations import validate_citations
from src.llm.llm_router import get_llm, ModelTier
from src.llm.prompts.system_prompts import SYSTEM_MISSION, SYSTEM_CONTEXT
from src.market_data.loader import get_market_context_for_prompt
from utils import app_logging
import time

logger = app_logging.get_logger(__name__)

# =============================================================================
# SECTION CONFIGURATION (imported from section_config.py - SINGLE SOURCE OF TRUTH)
# =============================================================================

SECTION_AGENT_CONFIG = AGENT_SECTION_CONFIGS

# Execution order - CUMULATIVE BUILDING (each section uses all prior sections)
# NOTE: This MUST match AGENT_SECTIONS from section_config.py
EXECUTION_ORDER = AGENT_SECTIONS

# Validate that EXECUTION_ORDER matches the config
assert EXECUTION_ORDER == [
    "chain_reaction_map",
    "structural_threats",
    "tactical_scenarios",
    "immediate_intelligence",
    "macro_cascade",
    "trade_intelligence",
    "house_view",
    "risk_monitor"
], "EXECUTION_ORDER must match AGENT_SECTIONS in section_config.py"

# Section dependencies - defines what prior sections each section needs
SECTION_DEPENDENCIES = {
    "chain_reaction_map": [],  # Foundation - articles only
    "structural_threats": ["chain_reaction_map"],
    "tactical_scenarios": ["chain_reaction_map", "structural_threats"],
    "immediate_intelligence": ["chain_reaction_map", "structural_threats", "tactical_scenarios"],
    "macro_cascade": ["chain_reaction_map", "structural_threats", "tactical_scenarios", "immediate_intelligence"],
    "trade_intelligence": ["chain_reaction_map", "structural_threats", "tactical_scenarios", "immediate_intelligence", "macro_cascade"],
    "house_view": ["chain_reaction_map", "structural_threats", "tactical_scenarios", "immediate_intelligence", "macro_cascade", "trade_intelligence"],
    "risk_monitor": ["chain_reaction_map", "structural_threats", "tactical_scenarios", "immediate_intelligence", "macro_cascade", "trade_intelligence", "house_view"]
}

# Which sections use NEW articles vs. prior sections only
SECTIONS_USING_ARTICLES = [
    "chain_reaction_map",
    "structural_threats",
    "tactical_scenarios",
    "immediate_intelligence",
    "macro_cascade"
]

SECTIONS_USING_PRIOR_ONLY = [
    "trade_intelligence",
    "house_view",
    "risk_monitor"
]

# Section focus prompts - GOD-TIER RISK & CHAIN REACTION FOCUSED
SECTION_FOCUS = {
    "chain_reaction_map": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: Map how events cascade through connected systems to threaten/benefit the primary asset.\n"
        "This is FOUNDATION intelligence. Everything else builds on this.\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "FOCUS: Event A → triggers B → cascades to C → D → impacts portfolio.\n"
        "Build explicit causal chains showing transmission mechanisms with surgical precision.\n\n"
        "HUNT FOR THESE CHAIN TYPES:\n"
        "→ **Cross-Asset Contagion**: How does stress in one asset class spread to others?\n"
        "→ **Feedback Loops**: Where does effect A amplify cause B which amplifies A? (reflexivity)\n"
        "→ **Non-Linear Tipping Points**: What threshold triggers regime change? (not gradual but sudden)\n"
        "→ **Hidden Dependencies**: What supply chain/funding/liquidity links are not obvious?\n"
        "→ **Second-Order Cascades**: What happens AFTER the first-order impact?\n\n"
        "STRUCTURE:\n"
        "1. TRIGGER IDENTIFICATION: What's the initial event? (policy shift, supply shock, geopolitical event)\n"
        "2. TRANSMISSION MAPPING: How does it propagate? (through what channels, intermediaries, dependencies)\n"
        "3. FEEDBACK LOOPS: Does the effect amplify itself? Where are the reflexive dynamics?\n"
        "4. TIPPING POINTS: What threshold triggers non-linear response? (not gradual but sudden regime change)\n"
        "5. CASCADE VISUALIZATION: Show the chain reaction step-by-step with timing (4+ steps)\n"
        "6. CROSS-ASSET SPILLOVER: How does this cascade affect other asset classes?\n"
        "7. ASSET IMPACT: How does it ultimately affect the primary asset? (magnitude, probability, timing)\n"
        "8. WATCH SIGNALS: What are the early warning indicators for each step?\n\n"
        "EXAMPLES OF CHAIN REACTIONS (use as structure templates, not specific values):\n"
        "• [POLICY_CHANGE] → [RESOURCE_CONSTRAINT] → [COST_IMPACT] → [MARGIN_EFFECT] → [ASSET_IMPACT]\n"
        "• [LABOR_EVENT] → [PRODUCTION_DISRUPTION] → [SUPPLY_DEFICIT] → [PRICE_SPIKE] → [DOWNSTREAM_IMPACT]\n"
        "• [CLIMATE_EVENT] → [CAPACITY_REDUCTION] → [SHORTAGE] → [PRODUCTION_CUTS] → [SECTOR_DISTRESS]\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ EXPLICIT transmission mechanisms (not 'could affect' but 'affects through X channel')\n"
        "→ FEEDBACK LOOPS identified (where does effect amplify cause?)\n"
        "→ TIPPING POINTS mapped (what threshold triggers regime change?)\n"
        "→ QUANTIFIED where possible (magnitude, timing, probability)\n"
        "→ MULTI-HOP chains (show 4+ step cascades, not just direct impacts)\n"
        "→ CROSS-ASSET CONTAGION (how does this spread to other asset classes?)\n"
        "→ CONTRARIAN ANGLES (what's the market missing? where's the hidden connection?)\n"
        "→ WATCH SIGNALS (what confirms/invalidates each step?)\n\n"
        "OUTPUT: Write COMPREHENSIVE chain reaction analysis - multiple detailed paragraphs mapping each cascade thoroughly.\n"
        "Show the full transmission path with quantified steps. Don't stop at first-order effects.\n"
        "AUTHORITY: Surgical precision. Zero hand-waving. If you can't map the transmission, don't claim the connection.\n"
        "CITATIONS: Only 9-character IDs from SOURCE MATERIAL. Cite the source for each link in the chain."
    ),
    "structural_threats": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: Multi-year structural vulnerabilities AND opportunities (6+ months).\n"
        "Secular shifts. Regime changes. Structural breaks. Where risk creates opportunity.\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have chain_reaction_map as foundation. Build on those causal chains.\n"
        "Ask: Which chain reactions are structural (not cyclical)? Which create lasting vulnerabilities? Which create asymmetric opportunities?\n\n"
        "FOCUS: First-principles thinking on structural transformation.\n"
        "Not 'what's the consensus view' but 'what's changing at the foundation?'\n\n"
        "HUNT FOR UNSEEN CONNECTIONS (HIGH PRIORITY):\n"
        "→ What 3rd/4th order effects is the market ignoring? (A→B→C→D where D is not priced)\n"
        "→ What assets move together that shouldn't? (hidden correlations breaking down)\n"
        "→ What's lagging that will catch up? (timing mismatches creating opportunity)\n"
        "→ What structural shift in one domain cascades unexpectedly to another?\n"
        "→ Where is consensus focused on 1st order while 2nd/3rd order dominates?\n\n"
        "STRUCTURE:\n"
        "1. STRUCTURAL RISKS: Multi-year vulnerabilities (deglobalization, regime shifts, technology disruption)\n"
        "2. TRANSMISSION PATHS: How do these risks cascade to the asset? Show 3-4 step chains, not just direct impacts\n"
        "3. HIDDEN CONNECTIONS: What non-obvious linkages exist? What's the market missing?\n"
        "4. OPPORTUNITY MECHANISMS: Where does structural risk create mispricing? (dislocations, forced selling, asymmetric bets)\n"
        "5. DURABILITY ASSESSMENT: Is this secular or cyclical? What's the half-life? What signals reversal?\n"
        "6. WATCH SIGNALS: What confirms the structural shift? What invalidates it?\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ MULTI-STEP CHAINS (show A→B→C→D, not just A→B)\n"
        "→ UNSEEN CONNECTIONS (what's the market missing? what correlation is breaking?)\n"
        "→ FIRST-PRINCIPLES ANCHORS (not consensus, but ground truth)\n"
        "→ RISK-OPPORTUNITY SYNTHESIS (show how structural risk creates asymmetric opportunity)\n"
        "→ DURABILITY EVIDENCE (why this is secular, not cyclical)\n"
        "→ CONTRARIAN CONVICTION (if consensus is wrong, say it with evidence)\n"
        "→ CAUSAL INTEGRATION (reference specific chains from chain_reaction_map)\n\n"
        "EXAMPLES:\n"
        "• Deglobalization → supply chain fragmentation → cost structure breaks → margin compression (RISK) → but creates nearshoring opportunity (OPPORTUNITY)\n"
        "• Energy transition → stranded assets → fossil fuel divestment (RISK) → but creates green infrastructure opportunity (OPPORTUNITY)\n"
        "• UNSEEN: AI capex surge → power demand spike → grid stress → data center REIT risk (3rd order effect market ignores)\n\n"
        "OUTPUT: Write COMPREHENSIVE analysis - multiple detailed paragraphs exploring each risk and opportunity thoroughly.\n"
        "Go deep on transmission mechanisms, quantify impacts, show the full causal chains.\n"
        "AUTHORITY: Conviction-based, zero hedging, first-principles thinking. If you see structural change, call it.\n"
        "CITATIONS: 9-character IDs. Reference chain_reaction_map insights where relevant."
    ),
    "tactical_scenarios": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: 3-6 month scenario trees (bull/bear/base) with tactical opportunities.\n"
        "Risk-weighted scenarios. Probability trees. Where does risk create mispricing?\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have chain_reaction_map + structural_threats.\n"
        "Ask: Which chain reactions could trigger in 3-6 months? How do structural risks play out tactically? Where's the asymmetric bet?\n\n"
        "FOCUS: Scenario matrix with probabilities. Not 'could happen' but 'probability-weighted paths'.\n\n"
        "DEEP RISK PATH ANALYSIS (CRITICAL):\n"
        "For each scenario, show the FULL cascade - not just 'Fed hikes → stocks down' but:\n"
        "→ Fed hikes 50bps → WACC rises 150bps → DCF valuations compress 15-20%\n"
        "→ → Passive funds forced to rebalance → selling pressure amplifies\n"
        "→ → → Liquidity withdrawal → bid-ask spreads widen → volatility spike\n"
        "→ → → → Credit spreads blow out → refinancing risk for levered names\n"
        "Show 3-4 steps in each risk path with quantified transmission at each step.\n\n"
        "STRUCTURE:\n"
        "1. SCENARIO MATRIX: Bull case (probability %), Base case (probability %), Bear case (probability %)\n"
        "2. RISK PATHS: How do risks cascade in each scenario? Show MULTI-STEP transmission with numbers\n"
        "3. SECOND-ORDER EFFECTS: What happens AFTER the obvious impact? What's the reflexive loop?\n"
        "4. OPPORTUNITY PATHS: Where does each scenario create mispricing? (tactical setups)\n"
        "5. CATALYST TIMING: What triggers each scenario? When? (specific events, dates, thresholds)\n"
        "6. PROBABILITY WEIGHTS: Why these probabilities? (market positioning, catalyst likelihood, structural context)\n"
        "7. TACTICAL SETUPS: How to position for each scenario? (entry points, hedges, asymmetric bets)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ MULTI-STEP RISK PATHS (show A→B→C→D with quantified transmission at each step)\n"
        "→ SECOND-ORDER THINKING (what happens after the obvious? what's the feedback loop?)\n"
        "→ PROBABILITY-WEIGHTED (not 'could happen' but 'X% probability based on Y evidence')\n"
        "→ CATALYST-SPECIFIC (not 'if things improve' but 'if Fed pivots at Dec meeting')\n"
        "→ CHAIN REACTION INTEGRATION (show how scenarios cascade through systems)\n"
        "→ CROSS-ASSET SPILLOVERS (how does this scenario affect related assets?)\n"
        "→ OPPORTUNITY IDENTIFICATION (where does each scenario create mispricing?)\n"
        "→ TACTICAL POSITIONING (how to play each scenario with specific setups)\n\n"
        "EXAMPLES:\n"
        "• BULL (35%): Fed pivot at Dec meeting → liquidity surge → risk-on → EM rally. Setup: Long EM at current levels.\n"
        "• BASE (45%): Fed holds → range-bound → volatility compression. Setup: Sell vol, wait for breakout.\n"
        "• BEAR (20%): Credit event → deleveraging cascade → forced selling → liquidity crisis → contagion to IG credit. Setup: Long USD, short HY.\n\n"
        "OUTPUT: Write DETAILED scenario analysis - each scenario deserves thorough exploration of the risk path,\n"
        "transmission mechanisms, second-order effects, and tactical implications. Don't rush through scenarios.\n"
        "AUTHORITY: Decisive, probability-weighted, actionable. If you see asymmetric setup, call it with conviction.\n"
        "CITATIONS: 9-character IDs. Reference chain_reaction_map and structural_threats insights."
    ),
    "immediate_intelligence": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: 0-3 week urgent threats + immediate opportunities + catalysts.\n"
        "What's hitting NOW? Where's the contrarian edge? What's the market missing?\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have chain_reaction_map + structural_threats + tactical_scenarios.\n"
        "Ask: Which chain reactions are triggering NOW? Which tactical scenarios are playing out? Where's the immediate edge?\n\n"
        "FOCUS: URGENT, trade-ready intelligence. Not 'watch this' but 'act on this NOW'.\n\n"
        "HUNT FOR WHAT'S NOT PRICED:\n"
        "→ **Catalyst Asymmetry**: Which catalyst is UNDERPRICED vs OVERPRICED by the market?\n"
        "→ **Positioning Squeeze Risk**: Where is positioning extreme enough to create squeeze regardless of fundamentals?\n"
        "→ **Ignored Second-Order**: What 2nd/3rd order effect of a known catalyst is being ignored?\n"
        "→ **Timing Mispricing**: Is the market right on direction but wrong on timing?\n"
        "→ **Hidden Catalyst**: What catalyst is coming that few are watching?\n\n"
        "STRUCTURE:\n"
        "1. IMMEDIATE CATALYSTS: What's forcing price action in next 0-3 weeks? (events, data, deadlines)\n"
        "2. CATALYST PRICING: Is each catalyst priced? Underpriced? Overpriced? (where's the edge?)\n"
        "3. FORCING MECHANISMS: How do these catalysts cascade? (reference chain_reaction_map)\n"
        "4. POSITIONING ANALYSIS: Where is positioning extreme? Squeeze risk? (percentiles, flows)\n"
        "5. CONTRARIAN ANGLES: What's the market missing? (hidden risks, ignored opportunities)\n"
        "6. NEXT 24-48H: What happens in next 24-48 hours? (specific triggers, timing)\n"
        "7. IMMEDIATE SETUPS: How to position RIGHT NOW? (entry, stop, catalyst timing)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ TIMING PRECISION (not 'soon' but 'next 24-48h' or 'by Friday close')\n"
        "→ CATALYST PRICING ANALYSIS (is it priced? underpriced? what's the asymmetry?)\n"
        "→ POSITIONING SQUEEZE AWARENESS (where are stops clustered? where's the squeeze?)\n"
        "→ CONTRARIAN CONVICTION (if everyone sees risk, where's the hidden opportunity?)\n"
        "→ FORCING FUNCTIONS (what HAS to happen? what's the deadline?)\n"
        "→ TRADE-READY SETUPS (specific entry, stop, target, timing)\n\n"
        "EXAMPLES (use as structure templates, not specific values):\n"
        "• [EVENT] + [POSITIONING_EXTREME] + [CATALYST] = [SQUEEZE_SETUP]. Setup: [DIRECTION] [ASSET], stop at [LEVEL].\n"
        "• [DISRUPTION] + [STRESS_INDICATOR] + [INVENTORY_DATA] = [CASCADE_RISK]. Setup: [TRADE_IDEA].\n"
        "• Everyone sees [OBVIOUS_RISK], but missing [HIDDEN_CATALYST]. Setup: [CONTRARIAN_TRADE].\n\n"
        "OUTPUT: Write DETAILED immediate intelligence - thoroughly explore each catalyst, its pricing, and positioning dynamics.\n"
        "AUTHORITY: Urgent, conviction-driven, timing-precise. If you see immediate edge, call it NOW.\n"
        "CITATIONS: 9-character IDs. Reference prior sections where relevant."
    ),
    "macro_cascade": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: How macro themes cascade across assets. Supply chain stress. Cross-topic drivers.\n"
        "Policy → liquidity → positioning → asset impact. Bottlenecks, dependencies, single points of failure.\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have all prior timeframe analysis (chain reactions, structural, tactical, immediate).\n"
        "Ask: How do macro themes cascade across multiple assets? Where are the supply chain vulnerabilities? What's the cross-topic transmission?\n\n"
        "FOCUS: SYSTEMATIC cross-asset synthesis. Not single-asset view but system-wide cascades.\n\n"
        "SUPPLY CHAIN DEPTH (CRITICAL):\n"
        "→ **Single Points of Failure**: What ONE disruption breaks the entire chain?\n"
        "→ **Inventory Stress Signals**: Where are inventories critically low/high?\n"
        "→ **Logistics Bottlenecks**: Ports, shipping lanes, rail, trucking - where's the constraint?\n"
        "→ **Funding/Liquidity Dependencies**: What funding channels could seize up?\n"
        "→ **Geographic Concentration Risk**: What's over-concentrated in one region?\n\n"
        "STRUCTURE:\n"
        "1. MACRO DRIVERS: Key policy/liquidity/positioning shifts (Fed, ECB, China, fiscal, flows)\n"
        "2. TRANSMISSION CHAINS: How do macro drivers cascade to this asset? (through what channels? with what lag?)\n"
        "3. SUPPLY CHAIN VULNERABILITIES: Single points of failure, inventory stress, logistics bottlenecks\n"
        "4. FUNDING/LIQUIDITY STRESS: Where could funding seize? What's the contagion path?\n"
        "5. CROSS-ASSET SPILLOVERS: How does stress in one asset spread to others?\n"
        "6. CORRELATION REGIME: Are historical correlations holding or breaking?\n"
        "7. WATCH SIGNALS: What confirms macro transmission? What breaks the chain?\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ CROSS-ASSET SYNTHESIS (show how macro cascades across multiple assets)\n"
        "→ TRANSMISSION PRECISION (not 'affects' but 'affects through X channel with Y lag')\n"
        "→ SUPPLY CHAIN DEPTH (single points of failure, inventory stress, logistics bottlenecks)\n"
        "→ FUNDING/LIQUIDITY MAPPING (where could funding seize? what's the contagion?)\n"
        "→ CORRELATION AWARENESS (are correlations holding or breaking?)\n"
        "→ SYSTEMATIC THINKING (see the system, not just the asset)\n"
        "→ CAUSAL INTEGRATION (reference specific chains from prior sections)\n\n"
        "EXAMPLES (use as structure templates, not specific values):\n"
        "• [POLICY_SHIFT] → [CURRENCY_IMPACT] → [DEBT_STRESS] → [DEMAND_DESTRUCTION] → [ASSET_IMPACT]\n"
        "• [DISRUPTION] → [LOGISTICS_BOTTLENECK] → [COST_SPIKE] → [INVENTORY_STRESS] → [MARGIN_COMPRESSION]\n"
        "• [CENTRAL_BANK_ACTION] → [CURRENCY_MOVE] → [COMPETITIVENESS_SHIFT] → [EARNINGS_IMPACT] → [EQUITY_EFFECT]\n\n"
        "OUTPUT: Write COMPREHENSIVE macro cascade analysis - thoroughly map each transmission path with supply chain depth.\n"
        "AUTHORITY: Systematic, causal clarity, cross-asset synthesis. See the system.\n"
        "CITATIONS: 9-character IDs. Reference prior sections extensively."
    ),
    "trade_intelligence": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: Executable positioning. Scenarios (2 Up, 2 Down) + trade setup with levels.\n"
        "Entry, stop, target, R/R, catalyst timing. Concrete triggers and probabilities.\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have ALL prior analysis. No new articles. Synthesize everything into actionable intelligence.\n"
        "Ask: Given everything we know (chains, structural, tactical, immediate, macro), what's the trade?\n\n"
        "FOCUS: TRADE-EXECUTABLE intelligence. Not 'watch this' but 'do this with these levels'.\n\n"
        "STRUCTURE:\n"
        "PART 1 - SCENARIOS (4 total: 2 Up, 2 Down):\n"
        "Format: Direction | Timeframe | Driver/Mechanism | What to watch | Probability %\n"
        "Example: UP | 3-6mo | Fed pivot + China stimulus | Fed dots, China PMI | 35%\n\n"
        "PART 2 - TRADE SETUP:\n"
        "Direction: Long/Short/Neutral\n"
        "Horizon: Days/Weeks/Months\n"
        "Entry: Specific level\n"
        "Stop: Specific level\n"
        "Target: Specific level\n"
        "R/R: Risk-reward ratio\n"
        "Invalidation: What kills the trade?\n"
        "Trigger: What confirms entry?\n"
        "Probability: % confidence\n"
        "Conviction: High/Medium/Low\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ SPECIFIC LEVELS (not 'around 1.10' but 'entry 1.1050, stop 1.0980, target 1.1350')\n"
        "→ CATALYST TIMING (not 'eventually' but 'on Fed pivot at Dec meeting')\n"
        "→ PROBABILITY-WEIGHTED (based on all prior analysis)\n"
        "→ INVALIDATION CLEAR (what kills the trade? at what level?)\n"
        "→ SYNTHESIS-DRIVEN (references insights from all prior sections)\n\n"
        "OUTPUT: Simple text lines, NO tables. Scenarios first, then trade setup.\n"
        "AUTHORITY: Trade-executable, conviction-driven, specific levels. If you see the trade, call it with precision.\n"
        "CITATIONS: Reference prior section insights (not article IDs)."
    ),
    "house_view": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: Integrated conviction call across all sections.\n"
        "What's the house view? Bullish/bearish/neutral? High conviction or wait?\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have ALL prior sections. Synthesize into unified view.\n"
        "Ask: Given EVERYTHING (chains, structural, tactical, immediate, macro, trade), what's the conviction call?\n\n"
        "FOCUS: MAXIMUM CONVICTION. Not 'could go either way' but 'here's the call with evidence'.\n\n"
        "STRUCTURE:\n"
        "1. CONVICTION CALL: Bullish/Bearish/Neutral with conviction level (High/Medium/Low)\n"
        "2. FUNDAMENTAL ANCHOR: What's the structural foundation? (from structural_threats)\n"
        "3. TACTICAL SCENARIOS: What's the 3-6 month path? (from tactical_scenarios)\n"
        "4. CURRENT DRIVERS: What's moving it NOW? (from immediate_intelligence)\n"
        "5. KEY RISKS: What are the top 3 risks? (from chain_reaction_map, structural_threats)\n"
        "6. TOP OPPORTUNITIES: What are the top 3 opportunities? (from structural_threats, tactical_scenarios)\n"
        "7. POSITIONING: How to position? (from trade_intelligence)\n"
        "8. WATCH ITEMS: What to monitor? (key signals, invalidation triggers)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ MAXIMUM CONVICTION (if you see it, call it with zero hedging)\n"
        "→ COMPLETE SYNTHESIS (references ALL prior sections)\n"
        "→ DECISION-READY (executive can act on this immediately)\n"
        "→ CONTRARIAN WHEN WARRANTED (if consensus is wrong, say it)\n"
        "→ WORLD-CLASS AUTHORITY (this is the definitive view)\n\n"
        "OUTPUT: Executive brief, authoritative tone, decision-ready. 2-3 paragraphs.\n"
        "AUTHORITY: Maximum conviction, zero hedging, world-class. This is THE view.\n"
        "CITATIONS: Reference prior section insights (not article IDs)."
    ),
    "risk_monitor": (
        "═══════════════════════════════════════════════════════════════════════════════\n"
        "MISSION: Key signals to monitor. Early warning indicators. What invalidates the view?\n"
        "What to watch? Trigger levels? Invalidation signals? Leading indicators?\n"
        "═══════════════════════════════════════════════════════════════════════════════\n\n"
        "CONTEXT: You have ALL prior sections including house_view. What needs monitoring?\n"
        "Ask: What confirms the house view? What invalidates it? What are the early warning signals?\n\n"
        "FOCUS: ACTIONABLE monitoring. Not 'watch this' but 'if X crosses Y, then Z happens'.\n\n"
        "STRUCTURE:\n"
        "1. CRITICAL MONITORS: Top 3-5 signals to watch (specific metrics, levels, events)\n"
        "2. TRIGGER LEVELS: At what level does each signal trigger action? (specific thresholds)\n"
        "3. INVALIDATION SIGNALS: What kills the house view? (specific events, levels, timeframes)\n"
        "4. LEADING INDICATORS: What gives early warning? (what leads the asset?)\n"
        "5. UPDATE FREQUENCY: How often to check each signal? (real-time, daily, weekly)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ SPECIFIC LEVELS (not 'watch USD' but 'if USD breaks 105, reassess')\n"
        "→ TRIGGER PRECISION (not 'if things change' but 'if Fed dots show 3 cuts, bullish')\n"
        "→ INVALIDATION CLARITY (what kills the view? at what level? by when?)\n"
        "→ LEADING INDICATORS (what gives early warning before the asset moves?)\n"
        "→ ACTIONABLE (executive knows exactly what to monitor and when to act)\n\n"
        "EXAMPLES:\n"
        "• Monitor: USD index. Trigger: Break above 105 = reassess bearish view. Check: Daily close.\n"
        "• Monitor: Fed dots. Trigger: 3+ cuts projected = bullish. Check: Dec FOMC.\n"
        "• Monitor: China PMI. Trigger: Below 48 for 2 months = structural concern. Check: Monthly.\n\n"
        "OUTPUT: 1-2 paragraphs on watch list and early warning signals with precision.\n"
        "AUTHORITY: Precise, actionable, timing-specific. Executive knows exactly what to watch.\n"
        "CITATIONS: Reference prior section insights (not article IDs)."
    )
}


def build_findings_context(topic_id: str) -> str:
    """
    Get formatted risks/opportunities from exploration agent for analysis context.

    These findings were discovered by the exploration agent BEFORE analysis runs.
    They provide pre-identified risks and opportunities that the writer should incorporate.
    """
    from src.graph.ops.topic_findings import get_topic_findings

    output = []
    risks = get_topic_findings(topic_id, "risk")
    opps = get_topic_findings(topic_id, "opportunity")

    if risks:
        output.append("\n═══ IDENTIFIED RISKS (from Exploration Agent) ═══")
        for i, r in enumerate(risks, 1):
            output.append(f"\n【Risk {i}】 {r.get('headline', 'Untitled')}")
            if r.get('rationale'):
                output.append(f"Rationale: {r.get('rationale')}")
            if r.get('flow_path'):
                output.append(f"Causal Chain: {r.get('flow_path')}")
            if r.get('confidence'):
                output.append(f"Confidence: {r.get('confidence')}")

    if opps:
        output.append("\n═══ IDENTIFIED OPPORTUNITIES (from Exploration Agent) ═══")
        for i, o in enumerate(opps, 1):
            output.append(f"\n【Opportunity {i}】 {o.get('headline', 'Untitled')}")
            if o.get('rationale'):
                output.append(f"Rationale: {o.get('rationale')}")
            if o.get('flow_path'):
                output.append(f"Causal Chain: {o.get('flow_path')}")
            if o.get('confidence'):
                output.append(f"Confidence: {o.get('confidence')}")

    if output:
        logger.info(f"Found {len(risks)} risks and {len(opps)} opportunities for {topic_id}")

    return "\n".join(output) if output else ""


class AnalysisAgentOrchestrator:
    """
    Orchestrates analysis agents based on section needs.
    
    Simple, composable, no over-engineering.
    """
    
    def __init__(self):
        # Initialize all agents once
        self.agents = {
            "synthesis": SynthesisScoutAgent(),
            "contrarian": ContrarianFinderAgent(),
            "depth": DepthFinderAgent()
        }
    
    def _get_agent(self, agent_name: str):
        return self.agents.get(agent_name)
    
    def run_agents_for_section(self, topic_id: str, section: str) -> Tuple[Dict[str, Any], SourceRegistry]:
        """
        Run all agents configured for a section.
        
        Args:
            topic_id: Topic to analyze
            section: Analysis section (chain_reaction_map, structural_threats, etc.)
            
        Returns:
            Tuple of (agent results dict, source registry)
        """
        config = SECTION_AGENT_CONFIG.get(section, SECTION_AGENT_CONFIG["chain_reaction_map"])
        agent_names = config["agents"]
        description = config["description"]
        priority = config.get("priority", "MEDIUM")
        
        # Get section focus for context-aware analysis
        section_focus = SECTION_FOCUS.get(section, "")
        
        print(f"\n{'='*70}")
        print(f"RUNNING AGENTS FOR: {topic_id} / {section}")
        print(f"Description: {description}")
        print(f"Agents: {', '.join(agent_names)}")
        print(f"{'='*70}\n")
        
        results = {}
        source_registry = SourceRegistry()
        
        for agent_name in agent_names:
            print(f"\n{'='*80}")
            print(f"🔍 {agent_name.upper()} AGENT")
            print(f"{'='*80}")
            agent = self._get_agent(agent_name)
            
            try:
                result = agent.run(topic_id, section, section_focus=section_focus)
                results[agent_name] = result
                
                # Display results immediately
                if hasattr(result, '__dict__'):
                    result_dict = result.__dict__
                    # Log what this agent found and will pass forward
                    print(f"\n📋 Output Summary:")
                    for key, value in result_dict.items():
                        if key == 'article_ids_used' and value:
                            print(f"   • {key}: {len(value)} IDs ({', '.join(value[:3])}{'...' if len(value) > 3 else ''})")
                        elif isinstance(value, list):
                            print(f"   • {key}: {len(value)} items")
                        elif value:
                            print(f"   • {key}: present")
                    
                    # Show detailed results
                    print(f"\n📊 Detailed Results:")
                    for key, value in result_dict.items():
                        if isinstance(value, list) and value:
                            print(f"\n   {key.replace('_', ' ').title()}:")
                            for i, item in enumerate(value[:5], 1):
                                if isinstance(item, str):
                                    # Truncate long strings
                                    display = item[:200] + "..." if len(item) > 200 else item
                                    print(f"      {i}. {display}")
                                else:
                                    print(f"      {i}. {item}")
                            if len(value) > 5:
                                print(f"      ... and {len(value) - 5} more")
                
                print(f"\n✅ {agent_name.upper()} complete")
            except Exception as e:
                print(f"❌ {agent_name.upper()} failed: {e}")
                results[agent_name] = None
        
        return results, source_registry
    
    def format_results_for_display(self, results: Dict[str, Any]) -> str:
        """Format agent results for human-readable display"""
        output = []
        
        for agent_name, result in results.items():
            if not result:
                continue
            
            output.append("\n" + "="*80)
            output.append(f"📊 {agent_name.upper()} AGENT RESULTS")
            output.append("="*80)
            
            # Format based on result type
            if isinstance(result, dict):
                for key, value in result.items():
                    if isinstance(value, list) and value:
                        output.append(f"\n✅ {key.replace('_', ' ').title()}: {len(value)} items")
                        for i, item in enumerate(value[:5], 1):  # Show first 5
                            if isinstance(item, dict):
                                # Format dict items nicely
                                item_str = " | ".join(f"{k}: {v}" for k, v in list(item.items())[:3])
                                output.append(f"   {i}. {item_str}")
                            else:
                                output.append(f"   {i}. {item}")
                        if len(value) > 5:
                            output.append(f"   ... and {len(value) - 5} more")
                    elif value:
                        output.append(f"\n✅ {key.replace('_', ' ').title()}: {value}")
            else:
                output.append(str(result))
        
        return "\n".join(output)


# =============================================================================
# MAIN PIPELINE - GOD-TIER ENTRY POINT
# =============================================================================

def analysis_rewriter_with_agents(
    topic_id: str,
    analysis_type: Optional[str] = None,
    new_article_ids: Optional[List[str]] = None
) -> None:
    """
    🚀 NEW AGENT-BASED ANALYSIS PIPELINE - RISK & CHAIN REACTION FOCUSED

    This is the GOD-TIER entry point that REPLACES the old analysis_rewriter.

    CUMULATIVE BUILDING FLOW:
    1. chain_reaction_map (articles only) → Foundation
    2. structural_threats (articles + chain_reaction_map) → Long-term
    3. tactical_scenarios (articles + chain + structural) → Medium-term
    4. immediate_intelligence (articles + all 3 prior) → Short-term
    5. macro_cascade (articles + all 4 prior) → Cross-topic
    6. trade_intelligence (NO articles, uses all 5 prior) → Actionable
    7. house_view (NO articles, uses all 6 prior) → Executive synthesis
    8. risk_monitor (NO articles, uses all 7 prior) → Watch list

    Each section gets progressively MORE context. By house_view, we have 6 prior analyses!

    Args:
        topic_id: Topic to analyze
        analysis_type: Specific section to run (or None for all 8 sections)
        new_article_ids: Optional list of NEW article IDs to highlight in prompts
    """
    from src.analysis.material.article_material import build_material_for_synthesis_section
    from src.graph.ops.topic import get_topic_analysis_field
    from src.graph.neo4j_client import run_cypher
    from utils import app_logging
    
    logger = app_logging.get_logger(__name__)
    
    def save_analysis(topic_id: str, section: str, analysis_text: str):
        """Save analysis section to Neo4j Topic node"""
        query = f"""
        MATCH (t:Topic {{id: $topic_id}})
        SET t.{section} = $analysis_text,
            t.last_updated = datetime()
        RETURN t.id
        """
        result = run_cypher(query, {
            "topic_id": topic_id,
            "analysis_text": analysis_text
        })
        if not result:
            raise Exception(f"Failed to save {section} for topic {topic_id}")
    
    print("\n" + "="*100)
    print("🚀 AGENT-BASED ANALYSIS PIPELINE - RISK & CHAIN REACTION FOCUSED")
    print("="*100)
    logger.info(f"Starting analysis_rewriter_with_agents | topic={topic_id}")
    
    # Determine which sections to run
    sections_to_run = [analysis_type] if analysis_type else EXECUTION_ORDER
    
    # Track completed sections for cumulative building
    completed_sections = {}
    
    orchestrator = AnalysisAgentOrchestrator()
    writer = WriterAgent()
    
    for i, section in enumerate(sections_to_run, 1):
        print(f"\n{'='*100}")
        print(f"📊 SECTION {i}/{len(sections_to_run)}: {section.upper()}")
        print(f"{'='*100}")
        
        try:
            # STEP 1: Load prior sections (cumulative building)
            deps = SECTION_DEPENDENCIES.get(section, [])
            prior_context = ""
            
            if deps:
                print(f"📦 Loading {len(deps)} prior sections...")
                for dep in deps:
                    if dep not in completed_sections:
                        dep_content = get_topic_analysis_field(topic_id, dep)
                        if dep_content:
                            completed_sections[dep] = dep_content
                
                prior_context = "\n\n".join([
                    f"═══ {dep.upper()} ═══\n{completed_sections[dep]}"
                    for dep in deps if dep in completed_sections
                ])
            
            # STEP 2: Run agents
            print(f"🤖 Running agents...")
            agent_results, _ = orchestrator.run_agents_for_section(topic_id, section)
            
            # STEP 3: Build material
            if section in SECTIONS_USING_PRIOR_ONLY:
                print(f"📚 Using prior sections only (no new articles)")
                material = prior_context
                article_ids = []  # No new articles for these sections by design
            else:
                print(f"📦 Building material from articles...")
                material, article_ids = build_material_for_synthesis_section(
                    topic_id, section, new_article_ids=new_article_ids
                )
                if prior_context:
                    material = f"{material}\n\n{'='*80}\nPRIOR ANALYSIS:\n{'='*80}\n\n{prior_context}"

            # STEP 3b: Add exploration findings (risks/opportunities) to material
            findings_context = build_findings_context(topic_id)
            if findings_context:
                print(f"🔍 Adding exploration findings to context...")
                material = f"{findings_context}\n\n{'='*80}\n\n{material}"
            
            # Log material composition
            logger.info(f"   prior sections: {len(prior_context):,} chars (~{len(prior_context)//4:,} tokens)")
            articles_size = len(material) - len(prior_context) if prior_context else len(material)
            logger.info(f"   articles: {articles_size:,} chars (~{articles_size//4:,} tokens)")

            # HARD GUARD: If this section is supposed to use articles but none were
            # successfully loaded from the Backend API, skip the section entirely.
            if section not in SECTIONS_USING_PRIOR_ONLY and not article_ids:
                logger.error(
                    f"   ❌ No source articles successfully loaded | topic={topic_id} section={section} | "
                    f"material_chars={len(material):,}"
                )
                print(
                    f"   ❌ Skipping section {section} for topic {topic_id}: "
                    f"no source articles loaded from backend."
                )
                from src.observability.stats_client import track
                track("agent_section_skipped_no_articles", f"Topic {topic_id}: {section}")
                continue
            
            # STEP 4: Load existing analysis (if any) for incremental updates
            existing_analysis = get_topic_analysis_field(topic_id, section)
            if existing_analysis:
                logger.info(f"   📄 Found existing analysis: {len(existing_analysis):,} chars")
            else:
                logger.info(f"   🆕 No existing analysis - fresh write")
            
            # Get article IDs for validation (only for sections using articles)
            allowed_article_ids: Set[str] = set()
            if section not in SECTIONS_USING_PRIOR_ONLY and 'article_ids' in locals():
                allowed_article_ids = set(article_ids)
                logger.info(f"   📋 Allowed article IDs: {len(allowed_article_ids)}")
            
            # STEP 5: Writer synthesis (using unified WriterAgent)
            print(f"🧠 LLM synthesis via WriterAgent...")
            section_focus = SECTION_FOCUS.get(section, "")

            writer_output = writer.write(
                topic_id=topic_id,
                section=section,
                material=material,
                section_focus=section_focus,
                pre_writing_results=agent_results,
                previous_analysis=existing_analysis,  # Pass existing for incremental update
            )
            analysis_text = writer_output.analysis_text
            logger.info(f"   initial analysis length: {len(analysis_text):,} chars")

            # STEP 5b: ID Validation Loop (only for sections with articles)
            if allowed_article_ids:
                analysis_text = run_id_validation_loop(
                    writer=writer,
                    draft=analysis_text,
                    topic_id=topic_id,
                    section=section,
                    material=material,
                    section_focus=section_focus,
                    allowed_article_ids=allowed_article_ids,
                    pre_writing_results=agent_results,
                )

            # STEP 5c: Quality loop (Critic + SourceChecker + Writer rewrite)
            try:
                analysis_text = run_topic_quality_loop(
                    writer=writer,
                    section_name=section,
                    draft_text=analysis_text,
                    section_material=material,
                    section_focus=section_focus,
                    topic_id=topic_id,
                    pre_writing_results=agent_results,
                )
                logger.info(f"   final analysis length after quality loop: {len(analysis_text):,} chars")
            except Exception as e:
                logger.warning(f"   ⚠️  Quality loop failed for {section}: {e}")

            print(f"✅ Generated: {len(analysis_text):,} chars")

            # Show full generated analysis with clear section title and separators
            print(f"\n{'='*80}")
            print(f"📄 GENERATED ANALYSIS - {section.upper()}:")
            print(f"{'='*80}")
            print(analysis_text)
            print(f"{'='*80}\n")
            
            # STEP 5: Save to Neo4j and memory
            save_analysis(topic_id, section, analysis_text)
            print(f"💾 Saved to Neo4j")
            
            # Track section written
            from src.observability.stats_client import track
            track("agent_section_written", f"Topic {topic_id}: {section}")
            
            completed_sections[section] = analysis_text
            print(f"✅ COMPLETE\n")
            
        except Exception as e:
            logger.error(f"Failed {section}: {e}", exc_info=True)
            print(f"❌ FAILED: {e}")
            raise
    
    # After all sections: print a consolidated view of all generated sections
    if completed_sections:
        print("\n" + "=" * 80)
        print("=" * 80)
        print("=" * 80)
        print("ALL SECTIONS (FINAL CONSOLIDATED OUTPUT):")
        
        # Respect execution order but only show sections that were actually run
        for idx, section in enumerate(sections_to_run, 1):
            if section not in completed_sections:
                continue
            print(f"\nSection {idx}: {section.upper()}")
            print("-" * 80)
            print(completed_sections[section])
        
        print("=" * 80)
        print("=" * 80)
        print("=" * 80)
    
    print(f"\n{'='*100}")
    print(f"✅ PIPELINE COMPLETE | {len(completed_sections)}/{len(sections_to_run)} sections")
    print(f"{'='*100}\n")
    logger.info(f"Pipeline complete: {len(completed_sections)}/{len(sections_to_run)} sections")

    # Update last_analyzed timestamp after successful completion
    if completed_sections:
        try:
            update_query = """
            MATCH (t:Topic {id: $topic_id})
            SET t.last_analyzed = datetime()
            RETURN t.id
            """
            run_cypher(update_query, {"topic_id": topic_id})
            logger.info(f"Updated last_analyzed timestamp for {topic_id}")
        except Exception as e:
            logger.warning(f"Failed to update last_analyzed for {topic_id}: {e}")


def run_id_validation_loop(
    writer: WriterAgent,
    draft: str,
    topic_id: str,
    section: str,
    material: str,
    section_focus: str,
    allowed_article_ids: Set[str],
    pre_writing_results: Dict[str, Any] | None = None,
    max_attempts: int = 2,
) -> str:
    """
    Validate article IDs in draft. If invalid IDs found, re-prompt Writer to fix.
    
    This runs BEFORE the quality loop to catch hallucinated IDs early.
    
    Returns validated draft.
    """
    current = draft
    
    for attempt in range(max_attempts):
        report = validate_citations(current, allowed_article_ids)
        
        if report.is_valid:
            logger.info(f"   ✅ ID validation passed (attempt {attempt + 1}) | {len(report.article_ids_in_text)} IDs found")
            return current
        
        logger.warning(
            f"   ⚠️ Invalid IDs found (attempt {attempt + 1}/{max_attempts}): "
            f"{sorted(report.unknown_article_ids)}"
        )
        print(f"   ⚠️ Invalid IDs: {sorted(report.unknown_article_ids)} - triggering rewrite...")
        
        # Re-prompt Writer with error feedback
        output = writer.write(
            topic_id=topic_id,
            section=section,
            material=material,
            section_focus=section_focus,
            pre_writing_results=pre_writing_results,
            previous_analysis=current,  # The bad draft
            invalid_ids_feedback=report.format_error_message(),
        )
        current = output.analysis_text
    
    # Final check after all attempts
    final_report = validate_citations(current, allowed_article_ids)
    if final_report.unknown_article_ids:
        logger.error(
            f"   ❌ ID validation failed after {max_attempts} attempts | "
            f"still invalid: {sorted(final_report.unknown_article_ids)}"
        )
        logger.warning(
            f"   ❌ WARNING: Could not fix all invalid IDs: {sorted(final_report.unknown_article_ids)}"
        )
    else:
        logger.info(f"   ✅ ID validation passed after {max_attempts} attempts")
    
    return current


def run_topic_quality_loop(
    writer: WriterAgent,
    section_name: str,
    draft_text: str,
    section_material: str,
    section_focus: str,
    topic_id: str,
    pre_writing_results: Dict[str, Any] | None = None,
    max_rounds: int = 1,
) -> str:
    """
    Run Critic + SourceChecker + Writer rewrite loop for a single topic section.
    
    Uses the unified Writer for rewrites instead of a separate rewrite prompt.
    
    Returns the refined analysis text.
    """
    critic_agent = CriticAgent()
    source_agent = SourceCheckerAgent()
    current = draft_text

    for round_idx in range(max_rounds):
        round_num = round_idx + 1
        logger.info(f"   🧪 Quality loop round {round_num}/{max_rounds} | section={section_name}")

        # Critic reviews
        critic_fb = critic_agent.run(
            draft=current,
            material=section_material,
            section_focus=section_focus,
            asset_name=topic_id,
            asset_id=topic_id,
        )

        # SourceChecker reviews
        source_fb = source_agent.run(
            draft=current,
            material=section_material,
            section_focus=section_focus,
            critic_feedback=critic_fb.feedback,
            asset_name=topic_id,
            asset_id=topic_id,
        )

        logger.info(
            f"      critic: {len(critic_fb.feedback):,} chars | "
            f"source: {len(source_fb.feedback):,} chars"
        )

        # Track the rewrite
        from src.observability.stats_client import track
        track("analysis_section_rewrite", f"topic={topic_id} section={section_name}")

        # Rewrite using unified Writer
        output = writer.write(
            topic_id=topic_id,
            section=section_name,
            material=section_material,
            section_focus=section_focus,
            pre_writing_results=pre_writing_results,
            previous_analysis=current,
            critic_feedback=critic_fb.feedback,
            source_feedback=source_fb.feedback,
        )

        revised = output.analysis_text
        logger.info(f"      revised: {len(revised):,} chars")
        current = revised

    return current


def format_agent_outputs_for_llm(agent_results: Dict[str, Any]) -> str:
    """Format agent outputs into context for LLM"""
    output = []
    
    if "synthesis" in agent_results and agent_results["synthesis"]:
        output.append("═══════════════════════════════════════════════════════════════")
        output.append("SYNTHESIS AGENT INSIGHTS")
        output.append("═══════════════════════════════════════════════════════════════")
        output.append(str(agent_results["synthesis"]))
    
    if "depth" in agent_results and agent_results["depth"]:
        output.append("\n═══════════════════════════════════════════════════════════════")
        output.append("DEPTH AGENT FINDINGS")
        output.append("═══════════════════════════════════════════════════════════════")
        output.append(str(agent_results["depth"]))
    
    if "contrarian" in agent_results and agent_results["contrarian"]:
        output.append("\n═══════════════════════════════════════════════════════════════")
        output.append("CONTRARIAN AGENT TAKES")
        output.append("═══════════════════════════════════════════════════════════════")
        output.append(str(agent_results["contrarian"]))
    
    return "\n".join(output)


# Convenience function
def run_analysis_agents(topic_id: str, section: str) -> Dict[str, Any]:
    """
    Run all agents for a section.
    
    Args:
        topic_id: Topic to analyze
        section: Analysis section
    
    Returns:
        Dict with results from each agent
    """
    orchestrator = AnalysisAgentOrchestrator()
    results = orchestrator.run_agents_for_section(topic_id, section)
    
    # Print formatted results
    print(orchestrator.format_results_for_display(results))
    
    return results


if __name__ == "__main__":
    # Load .env FIRST
    from utils.env_loader import load_env
    load_env()
    
    # Test the GOD-TIER pipeline
    import sys
    import random
    
    if len(sys.argv) > 1:
        topic_id = sys.argv[1]
        
        # Check for "all" mode - analyze ALL topics randomly
        if topic_id == "all":
            from src.graph.ops.topic import get_all_topics
            
            print(f"\n🌍 RUNNING ALL TOPICS MODE")
            print("="*80)
            
            # Get all topics
            all_topics = get_all_topics(fields=["id", "name"])
            topic_ids = [t["id"] for t in all_topics]
            
            print(f"📊 Found {len(topic_ids)} topics")
            
            # Shuffle for randomness
            random.shuffle(topic_ids)
            
            print(f"🎲 Shuffled order, starting analysis...\n")
            
            # Run full analysis for each topic
            for i, tid in enumerate(topic_ids, 1):
                print(f"\n{'='*80}")
                print(f"🎯 TOPIC {i}/{len(topic_ids)}: {tid}")
                print(f"{'='*80}")
                
                try:
                    analysis_rewriter_with_agents(tid)
                    print(f"✅ Completed {tid}")
                except Exception as e:
                    print(f"❌ Failed {tid}: {e}")
                    continue
            
            print(f"\n{'='*80}")
            print(f"🎉 ALL TOPICS COMPLETE!")
            print(f"{'='*80}")
        
        # Check if specific section or full analysis
        elif len(sys.argv) > 2 and sys.argv[2] != "full":
            # Run single section
            section = sys.argv[2]
            print(f"\n🎯 Running SINGLE SECTION: {section}")
            analysis_rewriter_with_agents(topic_id, analysis_type=section)
        else:
            # Run FULL analysis (all 8 sections)
            print(f"\n🚀 Running FULL ANALYSIS (all 8 sections)")
            analysis_rewriter_with_agents(topic_id)
    else:
        print("="*80)
        print("GOD-TIER AGENT-BASED ANALYSIS PIPELINE")
        print("="*80)
        print("\nUsage:")
        print("  python -m src.analysis_agents.orchestrator <topic_id> [section|full|all]")
        print("\nExamples:")
        print("  python -m src.analysis_agents.orchestrator all                      # Run ALL topics (random order)")
        print("  python -m src.analysis_agents.orchestrator eurusd full              # Run all 8 sections")
        print("  python -m src.analysis_agents.orchestrator eurusd                   # Run all 8 sections")
        print("  python -m src.analysis_agents.orchestrator eurusd chain_reaction_map  # Run single section")
        print("\nAvailable sections:")
        for i, section in enumerate(EXECUTION_ORDER, 1):
            config = SECTION_AGENT_CONFIG[section]
            print(f"  {i}. {section:25s} - {config['description']}")
        print("="*80)
