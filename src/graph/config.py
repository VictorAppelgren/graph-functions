# graph_config.py
import os
from typing import Any

# Max number of topics allowed (unified capacity limit).
# Can be overridden with env var MAX_TOPICS.
MAX_TOPICS: int = int(os.getenv("MAX_TOPICS", "200"))

# Human-readable scope with market-based granularity.
# Priority 1 = highest. Granularity: Nordics/US/EU (high) > China/Japan (medium) > Africa/South America/Asia (low)
INTEREST_AREAS = [
    # HIGH GRANULARITY: NORDICS (3 customers, deep coverage)
    {"id": "nordic_macro", "name": "Nordic Macro & Central Banks", "priority": 1, "granularity": "high", "description": "Sweden, Norway, Denmark, Finland: GDP, inflation, Riksbank, Norges Bank, rates, FX", "include": ["Sweden", "Norway", "Denmark", "Finland", "Riksbank", "Norges Bank", "SEK", "NOK", "DKK"]},
    {"id": "nordic_corporates", "name": "Nordic Corporate M&A & Earnings", "priority": 1, "granularity": "high", "description": "Nordic M&A, IPOs, corporate earnings, deal flow (exclude real estate, banks, tech)", "include": ["Nordic M&A", "corporate earnings", "IPO", "acquisitions", "Volvo", "H&M", "deal flow"]},
    {"id": "nordic_real_estate", "name": "Nordic Real Estate & Property", "priority": 1, "granularity": "high", "description": "Nordic property market, real estate companies, office/residential, financing", "include": ["Nordic real estate", "property", "SBB", "Castellum", "Samhällsbyggnadsbolaget"]},
    {"id": "nordic_banks", "name": "Nordic Banks & Financial Sector", "priority": 1, "granularity": "high", "description": "Nordic banking, financial stability, credit conditions", "include": ["SEB", "Nordea", "Handelsbanken", "Swedbank", "Nordic banks", "financial sector"]},
    {"id": "nordic_tech", "name": "Nordic Tech & Innovation", "priority": 1, "granularity": "high", "description": "Spotify, Ericsson, gaming, software, cleantech, innovation", "include": ["Spotify", "Ericsson", "gaming", "Swedish tech", "cleantech", "Northvolt"]},
    {"id": "nordic_industrials", "name": "Nordic Industrials & Manufacturing", "priority": 1, "granularity": "high", "description": "Volvo, ABB, SKF, manufacturing, engineering, exports", "include": ["Volvo", "ABB", "SKF", "manufacturing", "engineering", "industrials"]},
    
    # HIGH GRANULARITY: US (Global benchmark)
    {"id": "us_macro", "name": "US Macro & Fed Policy", "priority": 1, "granularity": "high", "description": "US growth, inflation, Fed, employment, rates, dollar", "include": ["US", "Federal Reserve", "inflation", "GDP", "payrolls", "UST", "dollar"]},
    {"id": "us_equities", "name": "US Equities (S&P 500, Nasdaq)", "priority": 1, "granularity": "high", "description": "S&P 500, Nasdaq, equity indices, market trends", "include": ["S&P 500", "Nasdaq", "SPX", "NDX", "equities", "stock market"]},
    {"id": "us_tech", "name": "US Tech Sector", "priority": 1, "granularity": "high", "description": "FAANG, software, cloud, cybersecurity (exclude AI infrastructure)", "include": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "software", "cloud", "SaaS"]},
    
    # HIGH GRANULARITY: EU (Major trading partner)
    {"id": "eu_macro", "name": "EU Macro & ECB Policy", "priority": 1, "granularity": "high", "description": "Eurozone growth, inflation, ECB, EuroStoxx, Bund", "include": ["EU", "Eurozone", "ECB", "EuroStoxx", "HICP", "Bund", "Germany", "France"]},
    {"id": "eu_banks", "name": "EU Banking Sector", "priority": 1, "granularity": "high", "description": "European banks, financial stability, credit", "include": ["EU banks", "European banking", "Deutsche Bank", "BNP Paribas", "financial sector"]},
    
    # MEDIUM GRANULARITY: CHINA & JAPAN (Key sectors only)
    {"id": "china_macro", "name": "China Macro & Policy", "priority": 1, "granularity": "medium", "description": "China GDP, PBoC, credit impulse, yuan", "include": ["China", "PBoC", "credit impulse", "yuan", "CNY", "GDP"]},
    {"id": "china_property", "name": "China Property Sector", "priority": 1, "granularity": "medium", "description": "China real estate, property developers, housing market", "include": ["China property", "real estate", "Evergrande", "Country Garden", "housing"]},
    {"id": "china_tech", "name": "China Tech & Exports", "priority": 1, "granularity": "medium", "description": "China tech sector, semiconductors, exports, manufacturing", "include": ["China tech", "exports", "manufacturing", "semiconductors", "supply chain"]},
    {"id": "japan_macro", "name": "Japan Macro & BoJ Policy", "priority": 1, "granularity": "medium", "description": "Japan growth, BoJ, inflation, yen, Nikkei", "include": ["Japan", "BoJ", "Bank of Japan", "yen", "JPY", "Nikkei"]},
    
    # LOW GRANULARITY: EMERGING MARKETS (Regional only)
    {"id": "africa_markets", "name": "Africa Markets & Commodities", "priority": 1, "granularity": "low", "description": "Africa regional trends, commodities, trade (South Africa, Nigeria, Kenya as group)", "include": ["Africa", "South Africa", "Nigeria", "Kenya", "African commodities", "emerging Africa"]},
    {"id": "south_america_markets", "name": "South America Markets & Commodities", "priority": 1, "granularity": "low", "description": "South America regional trends, commodities, trade (Brazil, Chile, Argentina as group)", "include": ["South America", "Brazil", "Chile", "Argentina", "Latin America", "commodities"]},
    {"id": "asia_emerging", "name": "Emerging Asia Markets", "priority": 1, "granularity": "low", "description": "India, South Korea, ASEAN regional overview", "include": ["India", "South Korea", "ASEAN", "Singapore", "emerging Asia"]},
    
    # AI INFRASTRUCTURE (All customers)
    {"id": "ai_infrastructure", "name": "AI Infrastructure & Data Centers", "priority": 1, "granularity": "high", "description": "AI data centers, hyperscalers, capex, power demand, land deals", "include": ["AI", "data center", "hyperscaler", "Microsoft", "Google", "Meta", "Amazon", "capex"]},
    {"id": "ai_semiconductors", "name": "AI Semiconductors & Supply Chain", "priority": 1, "granularity": "high", "description": "NVIDIA, TSMC, ASML, GPU supply, chip manufacturing", "include": ["NVIDIA", "TSMC", "ASML", "AMD", "semiconductors", "GPUs", "chips"]},
    {"id": "ai_power_energy", "name": "AI Power & Energy Infrastructure", "priority": 1, "granularity": "high", "description": "Power grid, nuclear (SMR), natural gas for data centers", "include": ["power grid", "nuclear", "SMR", "natural gas", "data center power", "utilities"]},
    
    # PULP & SHIPPING (Pulp trader)
    {"id": "pulp_market", "name": "Global Pulp Market", "priority": 1, "granularity": "high", "description": "Pulp supply/demand, pricing, forestry, major producers", "include": ["pulp", "NBSK", "BHKP", "paper", "forestry", "Suzano", "CMPC", "Stora Enso"]},
    {"id": "shipping_logistics", "name": "Shipping & Logistics", "priority": 1, "granularity": "high", "description": "Container shipping, freight rates, Baltic Dry, supply chain", "include": ["shipping", "freight", "Baltic Dry", "container", "logistics", "ports"]},
    
    # GEOPOLITICS (All customers)
    {"id": "ukraine_war", "name": "Ukraine War & Russia", "priority": 1, "granularity": "high", "description": "Ukraine conflict, Russia sanctions, energy impact", "include": ["Ukraine", "Russia", "war", "sanctions", "energy crisis", "gas"]},
    {"id": "middle_east_conflict", "name": "Middle East Conflict & Oil", "priority": 1, "granularity": "high", "description": "Middle East tensions, oil supply risk, OPEC", "include": ["Middle East", "Israel", "Iran", "oil supply", "OPEC", "Red Sea"]},
    {"id": "taiwan_risk", "name": "Taiwan Geopolitical Risk", "priority": 1, "granularity": "high", "description": "Taiwan-China tensions, semiconductor supply risk", "include": ["Taiwan", "China-Taiwan", "TSMC", "semiconductors"]},
    
    # COMMODITIES & FX (All customers)
    {"id": "energy_markets", "name": "Energy (Oil, Gas, Power)", "priority": 1, "granularity": "high", "description": "Crude oil, natural gas, LNG, power prices", "include": ["oil", "Brent", "WTI", "natural gas", "LNG", "power", "OPEC"]},
    {"id": "metals_macro", "name": "Metals (Gold, Copper, Iron Ore)", "priority": 1, "granularity": "high", "description": "Gold, copper, iron ore as macro indicators", "include": ["gold", "copper", "iron ore", "metals", "industrial metals"]},
    {"id": "fx_rates", "name": "FX & Interest Rates", "priority": 1, "granularity": "high", "description": "Major FX, Treasury yields, Bunds, rate curves", "include": ["EURUSD", "DXY", "USDJPY", "GBPUSD", "EURSEK", "UST", "yields", "Bund"]},
    
    # CREDIT & VOL (Hedge fund)
    {"id": "credit_volatility", "name": "Credit & Volatility", "priority": 2, "granularity": "high", "description": "Credit spreads, CDX, VIX, MOVE, risk sentiment", "include": ["credit", "spreads", "CDX", "iTraxx", "VIX", "MOVE", "volatility"]},
]


def describe_interest_areas_compact() -> str:
    """Compact list for LLM prompts - just id, name, granularity."""
    lines = [f"- {a['id']} ({a.get('granularity', 'medium')}): {a['name']}" for a in INTEREST_AREAS]
    return f"Max topics: {MAX_TOPICS} (aim for 150)\n" + "\n".join(lines)

def describe_granularity_policy() -> str:
    """Granularity rules for topic creation."""
    return """MARKET-BASED GRANULARITY:
- HIGH (Nordics/US/EU/AI/Geopolitics): Allow sector-level topics (5-8 per region)
- MEDIUM (China/Japan): Key sectors only (2-4 per country)
- LOW (Africa/South America/Emerging Asia): Regional grouping ONLY

CONSOLIDATION TEST:
1. Check market granularity level
2. HIGH: Allow if distinct analytical value (real estate ≠ banks ≠ tech)
3. MEDIUM: Only key sectors (property, tech, exports)
4. LOW: REJECT country-level, map to regional topic"""

def describe_interest_areas() -> str:
    """Full description with all details."""
    def entry(a: dict[str, Any]) -> str:
        inc = ", ".join(a.get("include", [])[:8])
        return f"- {a['name']} (prio {a['priority']}): {a['description']} | include: {inc}"
    lines = "\n".join(entry(a) for a in INTEREST_AREAS)
    return f"Max topics allowed: {MAX_TOPICS}\nAreas of interest:\n{lines}"


# ============================================================================
# ARTICLE CAPACITY MANAGEMENT
# ============================================================================

# Total hard limit per topic
MAX_ARTICLES_PER_TOPIC = 120

# Per-timeframe, per-perspective limits
# Each timeframe (fundamental/medium/current) × each perspective (risk/opp/trend/cat)
# gets: 4 premium + 3 standard + 3 filler = 10 articles
MAX_ARTICLES_PER_TIMEFRAME_PERSPECTIVE = 10

# Per-importance tier within each timeframe-perspective bucket
TIER_LIMITS_PER_TIMEFRAME_PERSPECTIVE = {
    3: 4,  # Premium: max 4 importance=3 articles per timeframe-perspective
    2: 3,  # Standard: max 3 importance=2 articles per timeframe-perspective
    1: 3,  # Filler: max 3 importance=1 articles per timeframe-perspective
}

# Math: 
# - Per timeframe-perspective: 4 + 3 + 3 = 10 articles
# - Per timeframe: 4 perspectives × 10 = 40 articles
# - Total per topic: 3 timeframes × 40 = 120 articles
