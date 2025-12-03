"""
SINGLE SOURCE OF TRUTH for all analysis section names.
Import this wherever you need section names to avoid mismatches.
"""

# =============================================================================
# AGENT-BASED ANALYSIS SECTIONS (New Risk-Focused Pipeline)
# =============================================================================

AGENT_SECTION_CONFIGS = {
    "chain_reaction_map": {
        "description": "Map event cascades through connected systems",
        "agents": ["synthesis", "depth", "contrarian"],
        "priority": "CRITICAL"
    },
    "structural_threats": {
        "description": "Multi-year vulnerabilities + structural opportunities (6+ months)",
        "agents": ["synthesis", "depth", "contrarian"],
        "priority": "HIGH"
    },
    "tactical_scenarios": {
        "description": "Scenario trees (bull/bear/base) + tactical opportunities (3-6 months)",
        "agents": ["synthesis", "contrarian", "depth"],
        "priority": "HIGH"
    },
    "immediate_intelligence": {
        "description": "Urgent threats + immediate opportunities + catalysts (0-3 weeks)",
        "agents": ["depth", "contrarian"],
        "priority": "URGENT"
    },
    "macro_cascade": {
        "description": "How macro themes cascade across assets + supply chain stress",
        "agents": ["synthesis", "depth"],
        "priority": "MEDIUM"
    },
    "trade_intelligence": {
        "description": "Scenarios (2 Up, 2 Down) + trade setup with levels",
        "agents": ["synthesis", "depth", "contrarian"],
        "priority": "HIGH"
    },
    "house_view": {
        "description": "Integrated conviction call across all sections",
        "agents": ["synthesis", "contrarian"],
        "priority": "CRITICAL"
    },
    "risk_monitor": {
        "description": "Key signals to monitor, early warning indicators",
        "agents": ["depth", "contrarian"],
        "priority": "HIGH"
    }
}

# Execution order (list of keys from AGENT_SECTION_CONFIGS)
AGENT_SECTIONS = list(AGENT_SECTION_CONFIGS.keys())

# =============================================================================
# LEGACY ANALYSIS SECTIONS (Old Pipeline)
# =============================================================================

LEGACY_SECTIONS = [
    "fundamental_analysis",
    "medium_analysis",
    "current_analysis",
    "drivers",
    "movers_scenarios",
    "swing_trade_or_outlook",
    "executive_summary",
    "risk_analysis",
    "opportunity_analysis",
    "trend_analysis",
    "catalyst_analysis"
]

# =============================================================================
# ALL SECTIONS (Combined)
# =============================================================================

ALL_ANALYSIS_SECTIONS = AGENT_SECTIONS + LEGACY_SECTIONS
