# scheduling/priority_policy.py
PRIORITY_POLICY = {
    1: {
        "interval_seconds": 900,  # 15 min
        "label": "traded/core",
        "characteristics": (
            "Highest centrality, intraday impact, broad cross-asset transmission; directly traded and monitored continuously. "
            "Examples: major FX pairs, front-month energy, policy shocks or central-bank decisions with immediate market impact. "
            "Emphasis: macro core with clear, actionable intraday implications. "
            "Type guidance: macro, currency, commodity, asset are usually 1. "
        ),
        "number_of_articles": 10
    },
    2: {
        "interval_seconds": 3600,  # 1 hours
        "label": "high",
        "characteristics": (
            "High centrality with short time-to-impact; multi-asset relevance; monitored intra-day to daily. "
            "Examples: major central-bank guidance/setup outside meetings, key index/theme/driver signals, liquidity/funding impulses. "
            "Type guidance: index, theme, driver are usually 2. "
        ),
        "number_of_articles": 10
    },
    3: {
        "interval_seconds": 7200,  # 2 hours
        "label": "medium",
        "characteristics": (
            "Meaningful drivers with sector/thematic scope; medium horizon (days–months); indirect cross-asset spillovers. "
            "Type guidance: company is usually 3. "
        ),
        "number_of_articles": 8
    },
    4: {
        "interval_seconds": 14400,  # 4 hours
        "label": "low",
        "characteristics": (
            "Supporting signals with limited centrality and slow impact; monitor periodically for regime shifts or structural evidence. "
            "Type guidance: policy, event, sector, supporting, structural, geography are usually 4. "
            ""
        ),
        "number_of_articles": 8
    },
    5: {
        "interval_seconds": 86400,  # 24 hours
        "label": "structural",
        "characteristics": (
            "Foundational, slow-moving macro anchors with long-run impact; strategic cadence suffices. "
            "Examples: demographics, secular policy regimes, long-run productivity. "
            ""
        ),
        "number_of_articles": 6
    },
}

def get_interval_for_importance(importance: int) -> int:
    if importance not in PRIORITY_POLICY:
        raise ValueError(f"Invalid importance: {importance}")
    return PRIORITY_POLICY[importance]["interval_seconds"]