# graph_config.py
import os
from typing import Any

# Daily limit for new topic creation (controlled graph growth)
DAILY_TOPIC_LIMIT: int = 2

# Human-readable scope with market-based granularity.
# Granularity: Nordics/US/EU/UK (high) > China/Japan/Korea/India (medium) > Africa/South America/Emerging Asia (low)
INTEREST_AREAS = [
    # HIGH GRANULARITY: NORDICS (deep coverage)
    {"id": "nordic_macro", "name": "Nordic Macro & Central Banks", "granularity": "high", "description": "Sweden, Norway, Denmark, Finland: GDP, inflation, Riksbank, Norges Bank, rates, FX", "include": ["Sweden", "Norway", "Denmark", "Finland", "Riksbank", "Norges Bank", "SEK", "NOK", "DKK"]},
    {"id": "nordic_corporates", "name": "Nordic Corporate M&A & Earnings", "granularity": "high", "description": "Nordic M&A, IPOs, corporate earnings, deal flow", "include": ["Nordic M&A", "corporate earnings", "IPO", "acquisitions", "Volvo", "H&M", "deal flow"]},
    {"id": "nordic_real_estate", "name": "Nordic Real Estate & Property", "granularity": "high", "description": "Nordic property market, real estate companies, office/residential, financing", "include": ["Nordic real estate", "property", "SBB", "Castellum", "Samhällsbyggnadsbolaget"]},
    {"id": "nordic_banks", "name": "Nordic Banks & Financial Sector", "granularity": "high", "description": "Nordic banking, financial stability, credit conditions", "include": ["SEB", "Nordea", "Handelsbanken", "Swedbank", "Nordic banks", "financial sector"]},
    {"id": "nordic_tech", "name": "Nordic Tech & Innovation", "granularity": "high", "description": "Spotify, Ericsson, gaming, software, cleantech, innovation", "include": ["Spotify", "Ericsson", "gaming", "Swedish tech", "cleantech", "Northvolt"]},
    {"id": "nordic_industrials", "name": "Nordic Industrials & Manufacturing", "granularity": "high", "description": "Volvo, ABB, SKF, manufacturing, engineering, exports", "include": ["Volvo", "ABB", "SKF", "manufacturing", "engineering", "industrials"]},

    # HIGH GRANULARITY: US (Global benchmark, expanded)
    {"id": "us_macro", "name": "US Macro & Fed Policy", "granularity": "high", "description": "US growth, inflation, Fed, employment, rates, dollar", "include": ["US", "Federal Reserve", "inflation", "GDP", "payrolls", "UST", "dollar"]},
    {"id": "us_equities", "name": "US Equities (S&P 500, Nasdaq)", "granularity": "high", "description": "S&P 500, Nasdaq, equity indices, market trends", "include": ["S&P 500", "Nasdaq", "SPX", "NDX", "equities", "stock market"]},
    {"id": "us_tech", "name": "US Tech Sector", "granularity": "high", "description": "FAANG, software, cloud, cybersecurity", "include": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "software", "cloud", "SaaS"]},
    {"id": "us_banks", "name": "US Banks & Financials", "granularity": "high", "description": "US banking sector, regional banks, financials, credit", "include": ["US banks", "JPMorgan", "Bank of America", "regional banks", "financials", "credit"]},
    {"id": "us_real_estate", "name": "US Real Estate", "granularity": "high", "description": "Commercial and residential real estate, REITs, housing market", "include": ["US real estate", "commercial property", "REITs", "housing", "mortgage"]},
    {"id": "us_consumer", "name": "US Consumer & Retail", "granularity": "high", "description": "Consumer spending, retail sales, discretionary, staples", "include": ["consumer spending", "retail", "discretionary", "staples", "Walmart", "Target"]},

    # HIGH GRANULARITY: EU (Major trading partner, expanded)
    {"id": "eu_macro", "name": "EU Macro & ECB Policy", "granularity": "high", "description": "Eurozone growth, inflation, ECB, EuroStoxx, Bund", "include": ["EU", "Eurozone", "ECB", "EuroStoxx", "HICP", "Bund", "Germany", "France"]},
    {"id": "eu_banks", "name": "EU Banking Sector", "granularity": "high", "description": "European banks, financial stability, credit", "include": ["EU banks", "European banking", "Deutsche Bank", "BNP Paribas", "financial sector"]},
    {"id": "germany_industry", "name": "German Industry & Manufacturing", "granularity": "high", "description": "German manufacturing, auto sector, industrial production, exports", "include": ["Germany", "German industry", "auto sector", "Volkswagen", "BMW", "manufacturing", "DAX"]},

    # HIGH GRANULARITY: UK
    {"id": "uk_macro", "name": "UK Macro & BoE Policy", "granularity": "high", "description": "UK economy, Bank of England, inflation, GBP, gilts", "include": ["UK", "Bank of England", "BoE", "GBP", "gilts", "FTSE", "inflation"]},

    # MEDIUM GRANULARITY: CHINA & JAPAN (Key sectors)
    {"id": "china_macro", "name": "China Macro & Policy", "granularity": "medium", "description": "China GDP, PBoC, credit impulse, yuan", "include": ["China", "PBoC", "credit impulse", "yuan", "CNY", "GDP"]},
    {"id": "china_property", "name": "China Property Sector", "granularity": "medium", "description": "China real estate, property developers, housing market", "include": ["China property", "real estate", "Evergrande", "Country Garden", "housing"]},
    {"id": "china_tech", "name": "China Tech & Exports", "granularity": "medium", "description": "China tech sector, exports, manufacturing", "include": ["China tech", "exports", "manufacturing", "Alibaba", "Tencent", "supply chain"]},
    {"id": "china_semiconductors", "name": "China Semiconductor Industry", "granularity": "medium", "description": "China chip industry, SMIC, semiconductor self-sufficiency", "include": ["China semiconductors", "SMIC", "chip industry", "semiconductor", "self-sufficiency"]},
    {"id": "japan_macro", "name": "Japan Macro & BoJ Policy", "granularity": "medium", "description": "Japan growth, BoJ, inflation, yen, Nikkei", "include": ["Japan", "BoJ", "Bank of Japan", "yen", "JPY", "Nikkei"]},

    # MEDIUM GRANULARITY: KEY ASIAN MARKETS
    {"id": "korea_macro", "name": "South Korea Macro & BoK", "granularity": "medium", "description": "Korean economy, Bank of Korea, won, KOSPI", "include": ["South Korea", "Korea", "BoK", "won", "KRW", "KOSPI", "Samsung"]},
    {"id": "india_macro", "name": "India Macro & RBI Policy", "granularity": "medium", "description": "India economy, RBI, rupee, Nifty, growth", "include": ["India", "RBI", "rupee", "INR", "Nifty", "growth"]},

    # SEMICONDUCTORS & AI HARDWARE (Critical sector - expanded)
    {"id": "taiwan_semiconductors", "name": "Taiwan Semiconductors (TSMC)", "granularity": "high", "description": "TSMC, Taiwan chip ecosystem, foundry, advanced nodes", "include": ["Taiwan", "TSMC", "foundry", "semiconductors", "advanced nodes", "chip manufacturing"]},
    {"id": "ai_semiconductors", "name": "AI Semiconductors & GPUs", "granularity": "high", "description": "NVIDIA, AMD, AI chips, GPUs, AI accelerators", "include": ["NVIDIA", "AMD", "GPUs", "AI chips", "accelerators", "HBM", "AI hardware"]},
    {"id": "semiconductor_equipment", "name": "Semiconductor Equipment", "granularity": "high", "description": "ASML, Applied Materials, Lam Research, chip equipment", "include": ["ASML", "Applied Materials", "Lam Research", "Tokyo Electron", "equipment", "lithography"]},
    {"id": "memory_semiconductors", "name": "Memory & Storage Semiconductors", "granularity": "high", "description": "Samsung, SK Hynix, Micron, DRAM, NAND, HBM", "include": ["Samsung", "SK Hynix", "Micron", "DRAM", "NAND", "HBM", "memory"]},

    # AI INFRASTRUCTURE
    {"id": "ai_infrastructure", "name": "AI Infrastructure & Data Centers", "granularity": "high", "description": "AI data centers, hyperscalers, capex, power demand", "include": ["AI", "data center", "hyperscaler", "Microsoft", "Google", "Meta", "Amazon", "capex"]},
    {"id": "ai_power_energy", "name": "AI Power & Energy Infrastructure", "granularity": "high", "description": "Power grid, nuclear (SMR), natural gas for data centers", "include": ["power grid", "nuclear", "SMR", "natural gas", "data center power", "utilities"]},

    # LOW GRANULARITY: EMERGING MARKETS (Regional only)
    {"id": "africa_markets", "name": "Africa Markets & Commodities", "granularity": "low", "description": "Africa regional trends, commodities, trade", "include": ["Africa", "South Africa", "Nigeria", "Kenya", "African commodities"]},
    {"id": "south_america_markets", "name": "South America Markets & Commodities", "granularity": "low", "description": "South America regional trends, commodities, trade", "include": ["South America", "Brazil", "Chile", "Argentina", "Latin America"]},

    # PULP & SHIPPING
    {"id": "pulp_market", "name": "Global Pulp Market", "granularity": "high", "description": "Pulp supply/demand, pricing, forestry, major producers", "include": ["pulp", "NBSK", "BHKP", "paper", "forestry", "Suzano", "CMPC", "Stora Enso"]},
    {"id": "shipping_logistics", "name": "Shipping & Logistics", "granularity": "high", "description": "Container shipping, freight rates, Baltic Dry, supply chain", "include": ["shipping", "freight", "Baltic Dry", "container", "logistics", "ports"]},

    # GEOPOLITICS
    {"id": "ukraine_war", "name": "Ukraine War & Russia", "granularity": "high", "description": "Ukraine conflict, Russia sanctions, energy impact", "include": ["Ukraine", "Russia", "war", "sanctions", "energy crisis", "gas"]},
    {"id": "middle_east_conflict", "name": "Middle East Conflict & Oil", "granularity": "high", "description": "Middle East tensions, oil supply risk, OPEC", "include": ["Middle East", "Israel", "Iran", "oil supply", "OPEC", "Red Sea"]},
    {"id": "taiwan_risk", "name": "Taiwan Geopolitical Risk", "granularity": "high", "description": "Taiwan-China tensions, semiconductor supply risk", "include": ["Taiwan", "China-Taiwan", "TSMC", "semiconductors", "geopolitical"]},

    # COMMODITIES (Expanded - separate gold/silver from industrial metals)
    {"id": "energy_markets", "name": "Energy (Oil, Gas, Power)", "granularity": "high", "description": "Crude oil, natural gas, LNG, power prices", "include": ["oil", "Brent", "WTI", "natural gas", "LNG", "power", "OPEC"]},
    {"id": "gold_silver", "name": "Gold & Silver", "granularity": "high", "description": "Precious metals, gold, silver, safe haven, bullion", "include": ["gold", "silver", "precious metals", "XAU", "XAG", "bullion", "safe haven"]},
    {"id": "industrial_metals", "name": "Industrial Metals (Copper, Iron Ore)", "granularity": "high", "description": "Copper, iron ore, aluminum, base metals as macro indicators", "include": ["copper", "iron ore", "aluminum", "base metals", "industrial metals"]},
    {"id": "agriculture_commodities", "name": "Agricultural Commodities", "granularity": "high", "description": "Grains, soft commodities, wheat, corn, soybeans, coffee", "include": ["grains", "wheat", "corn", "soybeans", "coffee", "sugar", "agriculture", "soft commodities"]},

    # FX & RATES
    {"id": "fx_major", "name": "Major FX Pairs", "granularity": "high", "description": "Major currency pairs, DXY, dollar, euro, yen", "include": ["EURUSD", "DXY", "USDJPY", "GBPUSD", "dollar", "euro", "yen"]},
    {"id": "fx_nordic", "name": "Nordic FX", "granularity": "high", "description": "SEK, NOK, DKK, Nordic currency dynamics", "include": ["SEK", "NOK", "DKK", "EURSEK", "USDSEK", "Nordic FX"]},
    {"id": "fx_emerging", "name": "Emerging Market FX", "granularity": "medium", "description": "EM currencies, TRY, ZAR, BRL, MXN, INR, other FX", "include": ["TRY", "ZAR", "BRL", "MXN", "INR", "THB", "EM FX", "emerging currencies"]},
    {"id": "rates_bonds", "name": "Interest Rates & Bonds", "granularity": "high", "description": "Treasury yields, Bunds, rate curves, fixed income", "include": ["UST", "yields", "Bund", "gilts", "rate curves", "fixed income", "bonds"]},

    # CREDIT & VOL
    {"id": "credit_spreads", "name": "Credit Markets", "granularity": "high", "description": "Credit spreads, CDX, iTraxx, high yield, investment grade", "include": ["credit", "spreads", "CDX", "iTraxx", "high yield", "IG", "corporate bonds"]},
    {"id": "volatility", "name": "Volatility & Risk Sentiment", "granularity": "high", "description": "VIX, MOVE, volatility, risk sentiment, options", "include": ["VIX", "MOVE", "volatility", "risk sentiment", "options", "implied vol"]},
]


def describe_interest_areas_compact() -> str:
    """Compact list for LLM prompts - just id, name, granularity."""
    lines = [f"- {a['id']} ({a.get('granularity', 'medium')}): {a['name']}" for a in INTEREST_AREAS]
    return "\n".join(lines)

def describe_granularity_policy() -> str:
    """Granularity rules for topic creation."""
    return """MARKET-BASED GRANULARITY:
- HIGH (Nordics/US/EU/UK/Semiconductors/Commodities): Allow sector-level topics
- MEDIUM (China/Japan/Korea/India): Key sectors only (2-4 per country)
- LOW (Africa/South America): Regional grouping ONLY

CONSOLIDATION TEST:
1. Check market granularity level
2. HIGH: Allow if distinct analytical value (real estate ≠ banks ≠ tech)
3. MEDIUM: Only key sectors (property, tech, macro)
4. LOW: REJECT country-level, map to regional topic"""

def describe_interest_areas() -> str:
    """Full description with all details."""
    def entry(a: dict[str, Any]) -> str:
        inc = ", ".join(a.get("include", [])[:8])
        return f"- {a['name']}: {a['description']} | include: {inc}"
    lines = "\n".join(entry(a) for a in INTEREST_AREAS)
    return f"Areas of interest:\n{lines}"


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
