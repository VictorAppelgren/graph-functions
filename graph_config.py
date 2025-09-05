# graph_config.py
import os
from datetime import datetime

# Max number of topics allowed (unified capacity limit).
# Can be overridden with env var MAX_TOPICS.
MAX_TOPICS: int = int(os.getenv("MAX_TOPICS", "100"))

# Human-readable scope for demo. Priority 1 = highest.
# Keep it compact and explicit.
INTEREST_AREAS = [
    {
        "id": "macro_us_eu",
        "name": "US/EU Macro & Markets",
        "priority": 1,
        "description": "Core macro and markets for US and EU: growth, inflation, employment, equities, credit, commodities.",
        "include": ["US", "EU", "Eurozone", "macro", "equities", "credit", "commodities", "GDP", "inflation", "employment"],
    },
    {
        "id": "policy_rates_tariffs",
        "name": "Policy, Interest Rates, Tariffs",
        "priority": 1,
        "description": "Monetary/fiscal policy, central banks, interest rates, tariffs/trade policy and their market impact.",
        "include": ["Federal Reserve", "ECB", "interest rates", "tariffs", "fiscal policy", "monetary policy", "yields"],
    },
    {
        "id": "eurusd_drivers",
        "name": "EUR/USD Drivers",
        "priority": 1,
        "description": "Anything materially influencing the EUR/USD currency cross.",
        "include": ["EURUSD", "EUR/USD", "exchange rate", "FX", "balance of payments", "trade balance"],
    },
    {
        "id": "ai_datacenters",
        "name": "AI & Data Centers",
        "priority": 1,
        "description": "AI infrastructure, data centers, energy and supply-chain implications for markets.",
        "include": ["AI", "data center", "GPUs", "semiconductors", "electricity demand", "NVIDIA", "hyperscalers"],
    },
    {
        "id": "pulp_market",
        "name": "Pulp Market",
        "priority": 2,
        "description": "Global pulp supply/demand, pricing, and market structure.",
        "include": ["pulp", "paper", "forestry", "wood pulp", "timber"],
    },
]

def describe_interest_areas() -> str:
    """Compact text description for prompts."""
    def entry(a):
        inc = ", ".join(a.get("include", [])[:8])
        return f"- {a['name']} (prio {a['priority']}): {a['description']} | include: {inc}"
    lines = "\n".join(entry(a) for a in INTEREST_AREAS)
    return f"Max topics allowed: {MAX_TOPICS}\nAreas of interest:\n{lines}"