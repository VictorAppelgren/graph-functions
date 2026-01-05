"""
Complete Graph Bootstrap Script

Sets up the graph from scratch:
1. Creates all 88 anchor topics (if they don't exist)
2. Enriches new topics with articles from storage
3. Creates all relationships between topics

Simple, focused, and fast.

Run: python -m src.start_scripts.bootstrap_graph
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.app_logging import get_logger
from src.graph.ops.topic import create_topic, check_if_topic_exists
from src.graph.ops.link import add_link, LinkModel
from src.analysis.policies.query_generator import create_wide_query
from src.analysis.policies.topic_proposal import TopicProposal

logger = get_logger(__name__)

# =============================================================================
# ANCHOR TOPICS - Master List (117 topics)
# =============================================================================

USER_ANCHOR_TOPICS = [
    # Individual currencies
    {"id": "usd", "name": "US Dollar", "query": '("USD" OR "US Dollar" OR "US$" OR "dollar" OR "DXY" OR "dollar index") AND ("Fed" OR "Federal Reserve" OR "monetary policy" OR "interest rates" OR "forex" OR "FX" OR "currency")'},
    {"id": "eur", "name": "Euro", "query": '("EUR" OR "Euro" OR "€" OR "euro currency") AND ("ECB" OR "European Central Bank" OR "monetary policy" OR "forex" OR "FX" OR "currency" OR "Eurozone")'},
    {"id": "jpy", "name": "Japanese Yen", "query": '("JPY" OR "Japanese Yen" OR "yen" OR "¥") AND ("BOJ" OR "Bank of Japan" OR "forex" OR "FX" OR "currency" OR "monetary policy")'},
    {"id": "gbp", "name": "British Pound", "query": '("GBP" OR "British Pound" OR "pound sterling" OR "£") AND ("BOE" OR "Bank of England" OR "forex" OR "FX" OR "currency" OR "monetary policy")'},
    {"id": "chf", "name": "Swiss Franc", "query": '("CHF" OR "Swiss Franc" OR "franc") AND ("SNB" OR "Swiss National Bank" OR "forex" OR "FX" OR "currency" OR "safe haven")'},
    {"id": "sek", "name": "Swedish Krona", "query": '("SEK" OR "Swedish Krona" OR "krona") AND ("Riksbank" OR "forex" OR "FX" OR "currency" OR "Sweden" OR "monetary policy")'},
    {"id": "nok", "name": "Norwegian Krone", "query": '("NOK" OR "Norwegian Krone" OR "krone") AND ("Norges Bank" OR "forex" OR "FX" OR "currency" OR "Norway" OR "oil")'},

    # Currency pairs
    {"id": "eurusd", "name": "EURUSD", "query": '("EURUSD" OR "EUR/USD" OR "euro dollar") AND ("forex" OR "FX" OR "currency pair" OR "exchange rate")'},
    {"id": "dxy", "name": "US Dollar Index (DXY)", "query": '("DXY" OR "dollar index" OR "US Dollar Index") AND ("forex" OR "FX" OR "currency" OR "trade-weighted")'},
    {"id": "usdjpy", "name": "USD/JPY", "query": '("USDJPY" OR "USD/JPY" OR "dollar yen") AND ("forex" OR "FX" OR "currency pair" OR "exchange rate")'},
    {"id": "gbpusd", "name": "GBP/USD", "query": '("GBPUSD" OR "GBP/USD" OR "cable" OR "pound dollar") AND ("forex" OR "FX" OR "currency pair" OR "exchange rate")'},
    {"id": "usdcny", "name": "USD/CNY", "query": '("USDCNY" OR "USD/CNY" OR "yuan" OR "renminbi") AND ("forex" OR "FX" OR "China" OR "PBOC" OR "currency")'},

    # Indices
    {"id": "spx", "name": "S&P 500", "query": '("S&P 500" OR "SPX" OR "SP500" OR "S&P") AND ("stocks" OR "equities" OR "market" OR "rally" OR "selloff" OR "earnings")'},
    {"id": "sx5e", "name": "Euro Stoxx 50", "query": '("Euro Stoxx 50" OR "SX5E" OR "Stoxx 50") AND ("stocks" OR "equities" OR "European market" OR "index")'},
    {"id": "ndx", "name": "NASDAQ-100", "query": '("NASDAQ-100" OR "NDX" OR "NASDAQ 100" OR "Nasdaq") AND ("tech stocks" OR "technology" OR "equities" OR "market")'},

    # Policy
    {"id": "fed_policy", "name": "Fed Policy", "query": '("Fed" OR "Federal Reserve" OR "FOMC" OR "Powell" OR "Fed policy") AND ("interest rates" OR "monetary policy" OR "rate hike" OR "rate cut" OR "QE" OR "Fed funds")'},
    {"id": "ecb_policy", "name": "ECB Policy", "query": '("ECB" OR "European Central Bank" OR "Lagarde") AND ("monetary policy" OR "interest rates" OR "rate decision" OR "PEPP" OR "deposit rate")'},
    {"id": "riksbank_policy", "name": "Riksbank Policy Rate", "query": '("Riksbank" OR "Swedish central bank") AND ("policy rate" OR "interest rate" OR "monetary policy" OR "Sweden")'},

    # US Rates
    {"id": "ust10y", "name": "US 10Y Treasury Yield", "query": '("10-year" OR "10Y" OR "Treasury yield" OR "UST10Y") AND ("bonds" OR "fixed income" OR "rates" OR "yield curve")'},
    {"id": "ust2y", "name": "US 2Y Treasury Yield", "query": '("2-year" OR "2Y" OR "Treasury yield" OR "UST2Y") AND ("bonds" OR "fixed income" OR "rates" OR "Fed policy")'},
    {"id": "ust5y", "name": "US 5Y Treasury Yield", "query": '("5-year" OR "5Y" OR "Treasury yield" OR "UST5Y") AND ("bonds" OR "fixed income" OR "rates")'},
    {"id": "ust30y", "name": "US 30Y Treasury Yield", "query": '("30-year" OR "30Y" OR "Treasury yield" OR "UST30Y" OR "long bond") AND ("bonds" OR "fixed income" OR "rates")'},
    {"id": "sofr", "name": "SOFR", "query": '("SOFR" OR "Secured Overnight Financing Rate") AND ("interest rate" OR "benchmark" OR "repo" OR "Fed")'},

    # European Rates
    {"id": "euribor", "name": "Euribor", "query": '("Euribor" OR "Euro Interbank Offered Rate") AND ("interest rate" OR "benchmark" OR "Eurozone" OR "ECB")'},
    {"id": "bund10y", "name": "German 10Y Bund Yield", "query": '("Bund" OR "German 10-year" OR "10Y Bund") AND ("bonds" OR "yield" OR "Germany" OR "fixed income")'},
    {"id": "bund2y", "name": "German 2Y Bund Yield", "query": '("2Y Bund" OR "German 2-year") AND ("bonds" OR "yield" OR "Germany" OR "fixed income")'},
    {"id": "oat10y", "name": "French 10Y OAT Yield", "query": '("OAT" OR "French 10-year" OR "10Y OAT") AND ("bonds" OR "yield" OR "France" OR "fixed income")'},
    {"id": "btp10y", "name": "Italian 10Y BTP Yield", "query": '("BTP" OR "Italian 10-year" OR "10Y BTP") AND ("bonds" OR "yield" OR "Italy" OR "fixed income" OR "spread")'},
    {"id": "estr", "name": "Euro Short-Term Rate (€STR)", "query": '("ESTR" OR "€STR" OR "Euro Short-Term Rate") AND ("interest rate" OR "benchmark" OR "ECB" OR "Eurozone")'},
    {"id": "gilt10y", "name": "UK 10Y Gilt Yield", "query": '("Gilt" OR "UK 10-year" OR "10Y Gilt") AND ("bonds" OR "yield" OR "UK" OR "Britain" OR "fixed income")'},

    # Nordic Rates
    {"id": "swe10y", "name": "Swedish 10Y Government Bond Yield", "query": '("Swedish 10-year" OR "Sweden 10Y" OR "Swedish bond") AND ("yield" OR "bonds" OR "fixed income" OR "Riksbank")'},
    {"id": "stibor", "name": "STIBOR (Swedish Interbank Rate)", "query": '("STIBOR" OR "Swedish Interbank Rate") AND ("interest rate" OR "benchmark" OR "Sweden" OR "Riksbank")'},
    {"id": "nor10y", "name": "Norwegian 10Y Government Bond Yield", "query": '("Norwegian 10-year" OR "Norway 10Y" OR "Norwegian bond") AND ("yield" OR "bonds" OR "fixed income" OR "Norges Bank")'},

    # Asian Rates
    {"id": "jgb10y", "name": "Japan 10Y JGB Yield", "query": '("JGB" OR "Japanese Government Bond" OR "Japan 10-year") AND ("yield" OR "bonds" OR "BOJ" OR "fixed income")'},
    {"id": "china_rates", "name": "China Government Bond Yields & Policy Rates", "query": '("China" OR "Chinese") AND ("government bond" OR "yield" OR "policy rate" OR "PBOC" OR "interest rate")'},
    {"id": "japan_rates", "name": "Japan Government Bond Yields & BOJ Policy", "query": '("Japan" OR "Japanese") AND ("government bond" OR "yield" OR "BOJ" OR "Bank of Japan" OR "policy rate")'},

    # Credit & Spreads
    {"id": "cdx_ig", "name": "CDX IG", "query": '("CDX IG" OR "CDX Investment Grade") AND ("credit" OR "spread" OR "CDS" OR "corporate bonds")'},
    {"id": "cdx_hy", "name": "CDX HY", "query": '("CDX HY" OR "CDX High Yield") AND ("credit" OR "spread" OR "CDS" OR "junk bonds")'},
    {"id": "itrx_main", "name": "iTraxx Main", "query": '("iTraxx" OR "iTraxx Main") AND ("credit" OR "spread" OR "CDS" OR "Europe" OR "corporate bonds")'},
    {"id": "us_ig_spread", "name": "US IG Credit Spread", "query": '("investment grade" OR "IG spread" OR "IG credit") AND ("US" OR "United States") AND ("spread" OR "corporate bonds" OR "credit")'},
    {"id": "us_hy_spread", "name": "US HY Credit Spread", "query": '("high yield" OR "HY spread" OR "junk bonds") AND ("US" OR "United States") AND ("spread" OR "corporate bonds" OR "credit")'},

    # Inflation
    {"id": "us_inflation", "name": "US Inflation", "query": '("inflation" OR "CPI" OR "consumer prices") AND ("United States" OR "US" OR "USA" OR "Fed") AND NOT ("Europe" OR "China")'},
    {"id": "us_core_cpi", "name": "US Core CPI", "query": '("core CPI" OR "core inflation") AND ("United States" OR "US" OR "USA") AND ("consumer prices" OR "Fed")'},
    {"id": "us_pce", "name": "US PCE Inflation", "query": '("PCE" OR "personal consumption expenditures" OR "PCE inflation") AND ("United States" OR "US" OR "Fed")'},
    {"id": "euro_inflation", "name": "Euro Area Inflation", "query": '("inflation" OR "HICP" OR "consumer prices") AND ("Eurozone" OR "Euro Area" OR "ECB") AND NOT ("US" OR "China")'},
    {"id": "euro_core_hicp", "name": "Euro Area Core HICP", "query": '("core HICP" OR "core inflation") AND ("Eurozone" OR "Euro Area" OR "ECB")'},

    # US Labor
    {"id": "us_payrolls", "name": "US Nonfarm Payrolls", "query": '("nonfarm payrolls" OR "NFP" OR "payrolls" OR "jobs report") AND ("United States" OR "US" OR "employment" OR "BLS")'},
    {"id": "us_unemployment_rate", "name": "US Unemployment Rate", "query": '("unemployment" OR "jobless rate" OR "unemployment rate") AND ("United States" OR "US" OR "USA" OR "BLS" OR "labor market")'},
    {"id": "us_job_openings", "name": "US Job Openings (JOLTS)", "query": '("JOLTS" OR "job openings" OR "Job Openings and Labor Turnover") AND ("United States" OR "US" OR "labor market")'},
    {"id": "us_unemployment_claims", "name": "US Unemployment Claims", "query": '("unemployment claims" OR "jobless claims" OR "initial claims") AND ("United States" OR "US" OR "weekly" OR "labor market")'},

    # European Labor
    {"id": "euro_unemployment", "name": "Euro Area Unemployment Rate", "query": '("unemployment" OR "jobless rate") AND ("Eurozone" OR "Euro Area" OR "ECB") AND ("labor market" OR "employment")'},
    {"id": "germany_unemployment", "name": "Germany Unemployment Rate", "query": '("unemployment" OR "jobless rate") AND ("Germany" OR "German") AND ("labor market" OR "employment")'},
    {"id": "uk_unemployment", "name": "UK Unemployment Rate", "query": '("unemployment" OR "jobless rate") AND ("UK" OR "United Kingdom" OR "Britain") AND ("labor market" OR "employment")'},
    {"id": "sweden_unemployment", "name": "Sweden Unemployment Rate", "query": '("unemployment" OR "jobless rate") AND ("Sweden" OR "Swedish") AND ("labor market" OR "employment")'},

    # Energy
    {"id": "brent", "name": "Brent Crude Oil", "query": '("Brent" OR "Brent crude" OR "oil") AND ("energy" OR "OPEC" OR "supply" OR "demand" OR "barrel" OR "commodities")'},
    {"id": "wti", "name": "WTI Crude Oil", "query": '("WTI" OR "West Texas Intermediate" OR "crude oil") AND ("energy" OR "oil" OR "supply" OR "demand" OR "barrel" OR "commodities")'},
    {"id": "natgas_hh", "name": "US Natural Gas (Henry Hub)", "query": '("natural gas" OR "Henry Hub" OR "natgas") AND ("US" OR "United States" OR "energy" OR "commodities")'},
    {"id": "ttf_gas", "name": "Dutch TTF Natural Gas", "query": '("TTF" OR "Dutch TTF" OR "natural gas") AND ("Europe" OR "Netherlands" OR "energy" OR "commodities")'},
    {"id": "diesel", "name": "US Diesel Price", "query": '("diesel" OR "diesel price" OR "diesel fuel") AND ("US" OR "United States" OR "energy" OR "fuel")'},
    {"id": "ercot_load", "name": "ERCOT Electricity Load", "query": '("ERCOT" OR "Electric Reliability Council of Texas") AND ("electricity" OR "power" OR "load" OR "demand" OR "Texas")'},
    {"id": "pjm_power_price", "name": "PJM Power Price", "query": '("PJM" OR "PJM Interconnection") AND ("power price" OR "electricity" OR "energy" OR "wholesale")'},
    {"id": "eu_ets", "name": "EU ETS Carbon Price", "query": '("EU ETS" OR "carbon price" OR "emissions trading") AND ("Europe" OR "carbon" OR "CO2" OR "climate")'},

    # Metals
    {"id": "gold", "name": "Gold", "query": '("gold" OR "XAU" OR "bullion") AND ("precious metals" OR "safe haven" OR "inflation hedge" OR "commodities" OR "central banks")'},
    {"id": "silver", "name": "Silver", "query": '("silver" OR "XAG") AND ("precious metals" OR "commodities" OR "industrial demand")'},
    {"id": "copper", "name": "Copper", "query": '("copper" OR "copper price") AND ("commodities" OR "industrial metals" OR "China" OR "demand" OR "supply")'},
    {"id": "iron_ore", "name": "Iron Ore", "query": '("iron ore" OR "iron ore price") AND ("commodities" OR "steel" OR "China" OR "mining")'},
    {"id": "aluminum", "name": "Aluminum", "query": '("aluminum" OR "aluminium") AND ("commodities" OR "industrial metals" OR "supply" OR "demand")'},

    # Agriculture
    {"id": "wheat", "name": "Wheat", "query": '("wheat" OR "wheat price") AND ("commodities" OR "agriculture" OR "grain" OR "food prices")'},
    {"id": "corn", "name": "Corn", "query": '("corn" OR "maize" OR "corn price") AND ("commodities" OR "agriculture" OR "grain" OR "food prices")'},
    {"id": "soybeans", "name": "Soybeans", "query": '("soybeans" OR "soybean" OR "soy") AND ("commodities" OR "agriculture" OR "grain" OR "food prices")'},

    # Shipping
    {"id": "baltic_dry", "name": "Baltic Dry Index", "query": '("Baltic Dry" OR "BDI" OR "Baltic Dry Index") AND ("shipping" OR "freight" OR "commodities" OR "trade")'},
    {"id": "scfi", "name": "Shanghai Containerized Freight Index", "query": '("SCFI" OR "Shanghai Containerized Freight") AND ("shipping" OR "freight" OR "container" OR "China" OR "trade")'},

    # US Housing
    {"id": "us_housing_starts", "name": "US Housing Starts", "query": '("housing starts" OR "new home construction") AND ("United States" OR "US" OR "real estate" OR "housing market")'},
    {"id": "us_mortgage30y", "name": "US 30Y Mortgage Rate", "query": '("mortgage rate" OR "30-year mortgage" OR "30Y mortgage") AND ("United States" OR "US" OR "housing" OR "real estate")'},
    {"id": "us_case_shiller_20", "name": "US Case-Shiller 20-City Home Price Index", "query": '("Case-Shiller" OR "home price index" OR "house prices") AND ("United States" OR "US" OR "20-city" OR "real estate")'},

    # European Housing
    {"id": "germany_house_prices", "name": "Germany House Price Index", "query": '("house prices" OR "home prices" OR "property prices") AND ("Germany" OR "German") AND ("real estate" OR "housing market")'},
    {"id": "uk_house_prices", "name": "UK House Price Index", "query": '("house prices" OR "home prices" OR "property prices") AND ("UK" OR "United Kingdom" OR "Britain") AND ("real estate" OR "housing market")'},
    {"id": "sweden_house_prices", "name": "Sweden House Price Index", "query": '("house prices" OR "home prices" OR "property prices") AND ("Sweden" OR "Swedish") AND ("real estate" OR "housing market")'},

    # Fed Plumbing
    {"id": "rrp", "name": "Fed Reverse Repo (RRP) Balance", "query": '("reverse repo" OR "RRP" OR "ON RRP") AND ("Fed" OR "Federal Reserve" OR "liquidity")'},
    {"id": "tga", "name": "US Treasury General Account (TGA)", "query": '("TGA" OR "Treasury General Account") AND ("Fed" OR "Federal Reserve" OR "Treasury" OR "liquidity")'},
    {"id": "fed_reserves", "name": "Fed Reserve Balances", "query": '("reserve balances" OR "bank reserves" OR "Fed reserves") AND ("Federal Reserve" OR "Fed" OR "liquidity")'},
    {"id": "ust_net_issuance", "name": "US Treasury Net Issuance", "query": '("Treasury issuance" OR "net issuance" OR "T-bill" OR "Treasury auction") AND ("US" OR "United States" OR "debt" OR "supply")'},

    # China
    {"id": "china_credit_impulse", "name": "China Credit Impulse", "query": '("credit impulse" OR "credit growth") AND ("China" OR "Chinese" OR "PBOC") AND ("lending" OR "TSF" OR "total social financing")'},
    {"id": "china_exports", "name": "China Exports", "query": '("China" OR "Chinese") AND ("exports" OR "trade" OR "shipments" OR "trade balance" OR "customs data")'},
    {"id": "china_property_sales", "name": "China Property Sales", "query": '("property sales" OR "home sales" OR "real estate") AND ("China" OR "Chinese") AND ("housing" OR "developers")'},
    {"id": "china_manufacturing_pmi", "name": "China Manufacturing PMI", "query": '("PMI" OR "Purchasing Managers Index" OR "manufacturing PMI") AND ("China" OR "Chinese") AND ("manufacturing" OR "factory activity")'},

    # Sector Indices
    {"id": "xlk", "name": "Technology Select Sector SPDR (XLK)", "query": '("XLK" OR "Technology Select Sector" OR "tech ETF") AND ("stocks" OR "equities" OR "technology" OR "sector")'},
    {"id": "soxx", "name": "iShares Semiconductor ETF (SOXX)", "query": '("SOXX" OR "semiconductor ETF" OR "chip stocks") AND ("semiconductors" OR "chips" OR "technology" OR "equities")'},
]

# =============================================================================
# ANCHOR RELATIONSHIPS
# =============================================================================

USER_ANCHOR_RELATIONSHIPS = [
    # Policy to currencies
    {"from": "fed_policy", "to": "usd", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "eur", "type": "INFLUENCES"},
    {"from": "riksbank_policy", "to": "sek", "type": "INFLUENCES"},
    
    # Currencies to pairs
    {"from": "usd", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "eur", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "usd", "to": "dxy", "type": "INFLUENCES"},
    {"from": "jpy", "to": "usdjpy", "type": "INFLUENCES"},
    {"from": "gbp", "to": "gbpusd", "type": "INFLUENCES"},
    
    # Policy to Rates/Indices
    {"from": "fed_policy", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "ust2y", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "spx", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "dxy", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "bund10y", "type": "INFLUENCES"},
    {"from": "riksbank_policy", "to": "swe10y", "type": "INFLUENCES"},
    
    # Inflation to Rates/Indices
    {"from": "us_inflation", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "us_inflation", "to": "spx", "type": "INFLUENCES"},
    {"from": "euro_inflation", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "euro_inflation", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "ust2y", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "spx", "type": "INFLUENCES"},
    
    # Commodities to Inflation
    {"from": "brent", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "wti", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "natgas_hh", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "ttf_gas", "to": "euro_inflation", "type": "INFLUENCES"},
    
    # China
    {"from": "china_credit_impulse", "to": "copper", "type": "INFLUENCES"},
    {"from": "china_exports", "to": "copper", "type": "INFLUENCES"},
    
    # Housing
    {"from": "us_mortgage30y", "to": "us_housing_starts", "type": "INFLUENCES"},
    
    # Key correlations
    {"from": "spx", "to": "sx5e", "type": "CORRELATES_WITH"},
    {"from": "dxy", "to": "eurusd", "type": "CORRELATES_WITH"},
    {"from": "ust2y", "to": "ust10y", "type": "CORRELATES_WITH"},
    {"from": "gold", "to": "silver", "type": "CORRELATES_WITH"},
    {"from": "brent", "to": "wti", "type": "PEERS"},
]

# =============================================================================
# STEP 1: CREATE ANCHOR TOPICS
# =============================================================================

def create_anchor_topics():
    """Create all anchor topics if they don't exist."""
    logger.info(f"Creating {len(USER_ANCHOR_TOPICS)} anchor topics...")
    created = 0
    existed = 0
    
    for topic in USER_ANCHOR_TOPICS:
        topic_id = topic["id"]
        
        if check_if_topic_exists(topic_id):
            existed += 1
            logger.debug(f"Topic exists: {topic_id}")
            continue
        
        # Create topic
        t = TopicProposal(
            id=topic["id"],
            name=topic["name"],
        )
        
        # Use hardcoded query if available, otherwise skip (no LLM generation)
        if "query" in topic and topic["query"]:
            t.query = topic["query"]
            logger.info(f"✅ Using hardcoded query for {topic_id}")
        else:
            logger.error(f"❌ No query provided for {topic_id} - SKIPPING")
            continue
        
        result = create_topic(t)
        logger.info(f"✅ Created topic: {result['name']} (id={result['id']})")
                
        created += 1
    
    logger.info(f"Topics: {created} created, {existed} existed")
    return created, existed

# =============================================================================
# STEP 2: CREATE RELATIONSHIPS
# =============================================================================

def create_anchor_relationships():
    """Create all anchor relationships."""
    logger.info(f"Creating {len(USER_ANCHOR_RELATIONSHIPS)} relationships...")
    success = 0
    errors = 0
    
    for rel in USER_ANCHOR_RELATIONSHIPS:
        link = LinkModel(
            type=rel["type"].upper(),
            source=rel["from"],
            target=rel["to"]
        )
        try:
            add_link(link)
            success += 1
            logger.debug(f"Added: {rel['from']} -> {rel['to']}")
        except Exception as e:
            errors += 1
            logger.warning(f"Failed: {rel['from']} -> {rel['to']}: {e}")
    
    logger.info(f"Relationships: {success} created, {errors} errors")
    return success, errors


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Bootstrap the entire graph."""
    logger.info("="*80)
    logger.info("GRAPH BOOTSTRAP STARTED")
    logger.info("="*80)
    
    # Step 1: Create topics (with enrichment)
    logger.info("\n[STEP 1] Creating anchor topics...")
    topics_created, topics_existed = create_anchor_topics()
    
    # Step 2: Create relationships
    logger.info("\n[STEP 2] Creating relationships...")
    rels_created, rels_errors = create_anchor_relationships()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("GRAPH BOOTSTRAP COMPLETE")
    logger.info("="*80)
    logger.info(f"Topics:        {topics_created} created, {topics_existed} existed")
    logger.info(f"Relationships: {rels_created} created, {rels_errors} errors")
    logger.info("="*80)
    logger.info("Next: Run 'python main.py' to start the pipeline")
    logger.info("="*80)

if __name__ == "__main__":
    main()
