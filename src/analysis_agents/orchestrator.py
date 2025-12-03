"""
Analysis Agent Orchestrator - GOD-TIER RISK & CHAIN REACTION FOCUSED

Composes specialized agents based on section needs.

Usage:
    python -m src.analysis_agents.orchestrator eurusd                    # Full pipeline (all 8 sections)
    python -m src.analysis_agents.orchestrator eurusd full               # Full pipeline (all 8 sections)
    python -m src.analysis_agents.orchestrator eurusd chain_reaction_map # Single section
"""

from typing import Dict, Any, List, Tuple, Optional
from src.analysis_agents.source_registry import SourceRegistry
from src.analysis_agents.synthesis_scout.agent import SynthesisScoutAgent
from src.analysis_agents.contrarian_finder.agent import ContrarianFinderAgent
from src.analysis_agents.depth_finder.agent import DepthFinderAgent
import time


# =============================================================================
# NEW: RISK-FOCUSED CHAIN REACTION ANALYSIS SECTIONS
# =============================================================================

# Section-specific agent configuration - RISK & CHAIN REACTION FOCUSED
SECTION_AGENT_CONFIG = {
    # TIER 1: FOUNDATION
    "chain_reaction_map": {
        "agents": ["synthesis", "depth", "contrarian"],
        "description": "Map event cascades through connected systems",
        "priority": "CRITICAL"
    },
    
    # TIER 2: TIMEFRAME RISK ANALYSIS
    "structural_threats": {
        "agents": ["synthesis", "depth", "contrarian"],
        "description": "Multi-year vulnerabilities + structural opportunities (6+ months)",
        "priority": "HIGH"
    },
    "tactical_scenarios": {
        "agents": ["synthesis", "contrarian", "depth"],
        "description": "Scenario trees (bull/bear/base) + tactical opportunities (3-6 months)",
        "priority": "HIGH"
    },
    "immediate_intelligence": {
        "agents": ["depth", "contrarian"],
        "description": "Urgent threats + immediate opportunities + catalysts (0-3 weeks)",
        "priority": "URGENT"
    },
    
    # TIER 3: CROSS-TOPIC SYNTHESIS
    "macro_cascade": {
        "agents": ["synthesis", "depth"],
        "description": "How macro themes cascade across assets + supply chain stress",
        "priority": "MEDIUM"
    },
    
    # TIER 4: ACTIONABLE INTELLIGENCE
    "trade_intelligence": {
        "agents": ["synthesis", "depth", "contrarian"],
        "description": "Scenarios (2 Up, 2 Down) + trade setup with levels",
        "priority": "HIGH"
    },
    
    # TIER 5: EXECUTIVE SYNTHESIS
    "house_view": {
        "agents": ["synthesis", "contrarian"],
        "description": "Integrated conviction call across all sections",
        "priority": "CRITICAL"
    },
    "risk_monitor": {
        "agents": ["depth", "contrarian"],
        "description": "Key signals to monitor, early warning indicators",
        "priority": "HIGH"
    }
}

# Execution order - CUMULATIVE BUILDING (each section uses all prior sections)
EXECUTION_ORDER = [
    "chain_reaction_map",      # Foundation: articles only
    "structural_threats",       # + chain_reaction_map
    "tactical_scenarios",       # + chain_reaction_map + structural_threats
    "immediate_intelligence",   # + all prior
    "macro_cascade",           # + all prior
    "trade_intelligence",      # + all prior (no new articles)
    "house_view",              # + all prior (no new articles)
    "risk_monitor"             # + all prior (no new articles)
]

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
        "FOCUS: Event A → triggers B → cascades to C → impacts portfolio.\n"
        "Build explicit causal chains showing transmission mechanisms with surgical precision.\n\n"
        "STRUCTURE:\n"
        "1. TRIGGER IDENTIFICATION: What's the initial event? (policy shift, supply shock, geopolitical event)\n"
        "2. TRANSMISSION MAPPING: How does it propagate? (through what channels, intermediaries, dependencies)\n"
        "3. CASCADE VISUALIZATION: Show the chain reaction step-by-step with timing\n"
        "4. ASSET IMPACT: How does it ultimately affect the primary asset? (magnitude, probability, timing)\n"
        "5. WATCH SIGNALS: What are the early warning indicators for each step?\n\n"
        "EXAMPLES OF CHAIN REACTIONS:\n"
        "• Chile water policy → lithium mine capacity → battery costs → EV margins → auto supplier revenue\n"
        "• Finnish labor strike → paper mill shutdown → European supply deficit → commodity price spike → packaging costs\n"
        "• Taiwan drought → chip fab capacity → semiconductor shortage → auto production cuts → supplier distress\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ EXPLICIT transmission mechanisms (not 'could affect' but 'affects through X channel')\n"
        "→ QUANTIFIED where possible (magnitude, timing, probability)\n"
        "→ MULTI-HOP chains (show 3-4 step cascades, not just direct impacts)\n"
        "→ CONTRARIAN ANGLES (what's the market missing? where's the hidden connection?)\n"
        "→ WATCH SIGNALS (what confirms/invalidates each step?)\n\n"
        "OUTPUT: 2-3 authoritative paragraphs showing explicit causal chains.\n"
        "AUTHORITY: Surgical precision. Zero hand-waving. If you can't map the transmission, don't claim the connection.\n"
        "CITATIONS: Only 9-character IDs (ABC123DEF). Cite the source for each link in the chain."
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
        "STRUCTURE:\n"
        "1. STRUCTURAL RISKS: Multi-year vulnerabilities (deglobalization, regime shifts, technology disruption)\n"
        "2. TRANSMISSION PATHS: How do these risks cascade to the asset? (use chain_reaction_map insights)\n"
        "3. OPPORTUNITY MECHANISMS: Where does structural risk create mispricing? (dislocations, forced selling, asymmetric bets)\n"
        "4. DURABILITY ASSESSMENT: Is this secular or cyclical? What's the half-life? What signals reversal?\n"
        "5. WATCH SIGNALS: What confirms the structural shift? What invalidates it?\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ FIRST-PRINCIPLES ANCHORS (not consensus, but ground truth)\n"
        "→ RISK-OPPORTUNITY SYNTHESIS (show how structural risk creates asymmetric opportunity)\n"
        "→ DURABILITY EVIDENCE (why this is secular, not cyclical)\n"
        "→ CONTRARIAN CONVICTION (if consensus is wrong, say it with evidence)\n"
        "→ CAUSAL INTEGRATION (reference specific chains from chain_reaction_map)\n\n"
        "EXAMPLES:\n"
        "• Deglobalization → supply chain fragmentation → cost structure breaks → margin compression (RISK) → but creates nearshoring opportunity (OPPORTUNITY)\n"
        "• Energy transition → stranded assets → fossil fuel divestment (RISK) → but creates green infrastructure opportunity (OPPORTUNITY)\n\n"
        "OUTPUT: 2-3 paragraphs balancing structural risks AND opportunities with conviction.\n"
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
        "STRUCTURE:\n"
        "1. SCENARIO MATRIX: Bull case (probability %), Base case (probability %), Bear case (probability %)\n"
        "2. RISK PATHS: How do risks cascade in each scenario? (reference chain_reaction_map)\n"
        "3. OPPORTUNITY PATHS: Where does each scenario create mispricing? (tactical setups)\n"
        "4. CATALYST TIMING: What triggers each scenario? When? (specific events, dates, thresholds)\n"
        "5. PROBABILITY WEIGHTS: Why these probabilities? (market positioning, catalyst likelihood, structural context)\n"
        "6. TACTICAL SETUPS: How to position for each scenario? (entry points, hedges, asymmetric bets)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ PROBABILITY-WEIGHTED (not 'could happen' but 'X% probability based on Y evidence')\n"
        "→ CATALYST-SPECIFIC (not 'if things improve' but 'if Fed pivots at Dec meeting')\n"
        "→ CHAIN REACTION INTEGRATION (show how scenarios cascade through systems)\n"
        "→ OPPORTUNITY IDENTIFICATION (where does each scenario create mispricing?)\n"
        "→ TACTICAL POSITIONING (how to play each scenario with specific setups)\n\n"
        "EXAMPLES:\n"
        "• BULL (35%): Fed pivot at Dec meeting → liquidity surge → risk-on → EM rally. Setup: Long EM at current levels.\n"
        "• BASE (45%): Fed holds → range-bound → volatility compression. Setup: Sell vol, wait for breakout.\n"
        "• BEAR (20%): Credit event → deleveraging cascade → flight to quality. Setup: Long USD, short credit.\n\n"
        "OUTPUT: 2-3 paragraphs with scenario probabilities, catalyst timing, and tactical setups.\n"
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
        "STRUCTURE:\n"
        "1. IMMEDIATE CATALYSTS: What's forcing price action in next 0-3 weeks? (events, data, deadlines)\n"
        "2. FORCING MECHANISMS: How do these catalysts cascade? (reference chain_reaction_map)\n"
        "3. MARKET POSITIONING: Is catalyst priced? Ignored? Misunderstood? (where's the edge?)\n"
        "4. CONTRARIAN ANGLES: What's the market missing? (hidden risks, ignored opportunities)\n"
        "5. NEXT 24-48H: What happens in next 24-48 hours? (specific triggers, timing)\n"
        "6. IMMEDIATE SETUPS: How to position RIGHT NOW? (entry, stop, catalyst timing)\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ TIMING PRECISION (not 'soon' but 'next 24-48h' or 'by Friday close')\n"
        "→ CONTRARIAN CONVICTION (if everyone sees risk, where's the hidden opportunity? if consensus bullish, what's the tail risk?)\n"
        "→ MARKET POSITIONING ANALYSIS (is it priced? what's the positioning? where's the squeeze?)\n"
        "→ FORCING FUNCTIONS (what HAS to happen? what's the deadline? what's the forcing mechanism?)\n"
        "→ TRADE-READY SETUPS (specific entry, stop, target, timing)\n\n"
        "EXAMPLES:\n"
        "• OPEC meeting Friday + positioning stretched short + inventory surprise = oil squeeze in 48h. Setup: Long oil NOW, stop below $75.\n"
        "• Shipping lane closure + insurance spike + inventory stress = logistics cascade by next week. Setup: Long freight, hedge with puts.\n"
        "• Everyone sees Fed risk, but missing China stimulus catalyst this week. Setup: Long EM on stimulus announcement.\n\n"
        "OUTPUT: 1-2 URGENT paragraphs. Trade-ready intelligence with timing precision.\n"
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
        "STRUCTURE:\n"
        "1. MACRO DRIVERS: Key policy/liquidity/positioning shifts (Fed, ECB, China, fiscal, flows)\n"
        "2. TRANSMISSION CHAINS: How do macro drivers cascade to this asset? (through what channels?)\n"
        "3. SUPPLY CHAIN STRESS: Bottlenecks, dependencies, single points of failure (where's the vulnerability?)\n"
        "4. CROSS-ASSET IMPACTS: How does this affect other assets? (correlations, spillovers, contagion)\n"
        "5. WATCH SIGNALS: What confirms macro transmission? What breaks the chain?\n\n"
        "WHAT MAKES THIS GOD-TIER:\n"
        "→ CROSS-ASSET SYNTHESIS (show how macro cascades across multiple assets)\n"
        "→ TRANSMISSION PRECISION (not 'affects' but 'affects through X channel with Y lag')\n"
        "→ SUPPLY CHAIN MAPPING (identify bottlenecks, dependencies, single points of failure)\n"
        "→ SYSTEMATIC THINKING (see the system, not just the asset)\n"
        "→ CAUSAL INTEGRATION (reference specific chains from prior sections)\n\n"
        "EXAMPLES:\n"
        "• Fed tightening → USD strength → EM debt stress → commodity demand destruction → asset impact (show full chain)\n"
        "• China lockdown → port congestion → shipping costs → inventory stress → margin compression (supply chain cascade)\n"
        "• ECB pivot → EUR strength → European export competitiveness → corporate earnings → equity impact (macro transmission)\n\n"
        "OUTPUT: 2 paragraphs on macro transmission and supply chain vulnerabilities with systematic clarity.\n"
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
    analysis_type: Optional[str] = None
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
    """
    from src.analysis.material.article_material import build_material_for_synthesis_section
    from src.analysis.persistance.analysis_saver import save_analysis
    from src.graph.ops.topic import get_topic_analysis_field
    from utils import app_logging
    
    logger = app_logging.get_logger(__name__)
    
    print("\n" + "="*100)
    print("🚀 AGENT-BASED ANALYSIS PIPELINE - RISK & CHAIN REACTION FOCUSED")
    print("="*100)
    logger.info(f"Starting analysis_rewriter_with_agents | topic={topic_id}")
    
    # Determine which sections to run
    sections_to_run = [analysis_type] if analysis_type else EXECUTION_ORDER
    
    # Track completed sections for cumulative building
    completed_sections = {}
    
    orchestrator = AnalysisAgentOrchestrator()
    
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
            else:
                print(f"📦 Building material from articles...")
                material, article_ids = build_material_for_synthesis_section(topic_id, section)
                if prior_context:
                    material = f"{material}\n\n{'='*80}\nPRIOR ANALYSIS:\n{'='*80}\n\n{prior_context}"
            
            # Log material composition
            logger.info(f"   prior sections: {len(prior_context):,} chars (~{len(prior_context)//4:,} tokens)")
            articles_size = len(material) - len(prior_context) if prior_context else len(material)
            logger.info(f"   articles: {articles_size:,} chars (~{articles_size//4:,} tokens)")
            
            # STEP 4: LLM synthesis
            print(f"🧠 LLM synthesis...")
            agent_context = format_agent_outputs_for_llm(agent_results)
            logger.info(f"   agent insights: {len(agent_context):,} chars (~{len(agent_context)//4:,} tokens)")
            section_focus = SECTION_FOCUS.get(section, "")
            
            prompt = f"""You are a world-class financial analyst writing risk-focused intelligence.

{section_focus}

{'═'*80}
AGENT INSIGHTS:
{'═'*80}

{agent_context}

{'═'*80}
MATERIAL & CONTEXT:
{'═'*80}

{material}

TASK: Synthesize into authoritative analysis following the structure above.
"""
            
            # Log total prompt size
            total_prompt_size = len(prompt)
            logger.info(f"   📊 TOTAL PROMPT: {total_prompt_size:,} chars (~{total_prompt_size//4:,} tokens)")
            if total_prompt_size > 100000:
                logger.warning(f"   ⚠️  Large prompt! May hit token limits")
            
            from src.llm.llm_router import get_llm, ModelTier
            llm = get_llm(ModelTier.COMPLEX)
            analysis_text = llm.invoke(prompt).content
            
            print(f"✅ Generated: {len(analysis_text):,} chars")
            
            # Show analysis preview (capped at 2000 chars)
            preview_length = 2000
            if len(analysis_text) > preview_length:
                preview = analysis_text[:preview_length] + f"\n\n... [truncated, total: {len(analysis_text):,} chars] ..."
            else:
                preview = analysis_text
            
            print(f"\n{'='*80}")
            print(f"📄 GENERATED ANALYSIS:")
            print(f"{'='*80}")
            print(preview)
            print(f"{'='*80}\n")
            
            # STEP 5: Save to Neo4j and memory
            save_analysis(topic_id, section, analysis_text)
            print(f"💾 Saved to Neo4j")
            
            completed_sections[section] = analysis_text
            print(f"✅ COMPLETE\n")
            
        except Exception as e:
            logger.error(f"Failed {section}: {e}", exc_info=True)
            print(f"❌ FAILED: {e}")
            raise
    
    print(f"\n{'='*100}")
    print(f"✅ PIPELINE COMPLETE | {len(completed_sections)}/{len(sections_to_run)} sections")
    print(f"{'='*100}\n")
    logger.info(f"Pipeline complete: {len(completed_sections)}/{len(sections_to_run)} sections")


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
