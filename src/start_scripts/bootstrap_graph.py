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
    {"id": "usd", "name": "US Dollar", "importance": 2},
    {"id": "eur", "name": "Euro", "importance": 2},
    {"id": "jpy", "name": "Japanese Yen", "importance": 2},
    {"id": "gbp", "name": "British Pound", "importance": 2},
    {"id": "chf", "name": "Swiss Franc", "importance": 3},
    {"id": "sek", "name": "Swedish Krona", "importance": 2},
    {"id": "nok", "name": "Norwegian Krone", "importance": 3},
    
    # Currency pairs
    {"id": "eurusd", "name": "EURUSD", "importance": 1},
    {"id": "dxy", "name": "US Dollar Index (DXY)", "importance": 1},
    {"id": "usdjpy", "name": "USD/JPY", "importance": 1},
    {"id": "gbpusd", "name": "GBP/USD", "importance": 1},
    {"id": "usdcny", "name": "USD/CNY", "importance": 2},
    
    # Indices
    {"id": "spx", "name": "S&P 500", "importance": 2},
    {"id": "sx5e", "name": "Euro Stoxx 50", "importance": 2},
    {"id": "ndx", "name": "NASDAQ-100", "importance": 2},
    
    # Policy
    {"id": "fed_policy", "name": "Fed Policy", "importance": 4},
    {"id": "ecb_policy", "name": "ECB Policy", "importance": 4},
    {"id": "riksbank_policy", "name": "Riksbank Policy Rate", "importance": 2},
    
    # US Rates
    {"id": "ust10y", "name": "US 10Y Treasury Yield", "importance": 1},
    {"id": "ust2y", "name": "US 2Y Treasury Yield", "importance": 1},
    {"id": "ust5y", "name": "US 5Y Treasury Yield", "importance": 2},
    {"id": "ust30y", "name": "US 30Y Treasury Yield", "importance": 2},
    {"id": "sofr", "name": "SOFR", "importance": 2},
    
    # European Rates
    {"id": "euribor", "name": "Euribor", "importance": 2},
    {"id": "bund10y", "name": "German 10Y Bund Yield", "importance": 2},
    {"id": "bund2y", "name": "German 2Y Bund Yield", "importance": 2},
    {"id": "oat10y", "name": "French 10Y OAT Yield", "importance": 2},
    {"id": "btp10y", "name": "Italian 10Y BTP Yield", "importance": 2},
    {"id": "estr", "name": "Euro Short-Term Rate (€STR)", "importance": 2},
    {"id": "gilt10y", "name": "UK 10Y Gilt Yield", "importance": 2},
    
    # Nordic Rates
    {"id": "swe10y", "name": "Swedish 10Y Government Bond Yield", "importance": 2},
    {"id": "stibor", "name": "STIBOR (Swedish Interbank Rate)", "importance": 2},
    {"id": "nor10y", "name": "Norwegian 10Y Government Bond Yield", "importance": 3},
    
    # Asian Rates
    {"id": "jgb10y", "name": "Japan 10Y JGB Yield", "importance": 2},
    {"id": "china_rates", "name": "China Government Bond Yields & Policy Rates", "importance": 2},
    {"id": "japan_rates", "name": "Japan Government Bond Yields & BOJ Policy", "importance": 2},
    
    # Credit & Spreads
    {"id": "cdx_ig", "name": "CDX IG", "importance": 2},
    {"id": "cdx_hy", "name": "CDX HY", "importance": 2},
    {"id": "itrx_main", "name": "iTraxx Main", "importance": 2},
    {"id": "us_ig_spread", "name": "US IG Credit Spread", "importance": 2},
    {"id": "us_hy_spread", "name": "US HY Credit Spread", "importance": 2},
    
    # Inflation
    {"id": "us_inflation", "name": "US Inflation", "importance": 2},
    {"id": "us_core_cpi", "name": "US Core CPI", "importance": 2},
    {"id": "us_pce", "name": "US PCE Inflation", "importance": 2},
    {"id": "euro_inflation", "name": "Euro Area Inflation", "importance": 2},
    {"id": "euro_core_hicp", "name": "Euro Area Core HICP", "importance": 2},
    
    # US Labor
    {"id": "us_payrolls", "name": "US Nonfarm Payrolls", "importance": 2},
    {"id": "us_unemployment_rate", "name": "US Unemployment Rate", "importance": 3},
    {"id": "us_job_openings", "name": "US Job Openings (JOLTS)", "importance": 3},
    {"id": "us_unemployment_claims", "name": "US Unemployment Claims", "importance": 3},
    
    # European Labor
    {"id": "euro_unemployment", "name": "Euro Area Unemployment Rate", "importance": 2},
    {"id": "germany_unemployment", "name": "Germany Unemployment Rate", "importance": 3},
    {"id": "uk_unemployment", "name": "UK Unemployment Rate", "importance": 3},
    {"id": "sweden_unemployment", "name": "Sweden Unemployment Rate", "importance": 3},
    
    # Energy
    {"id": "brent", "name": "Brent Crude Oil", "importance": 1},
    {"id": "wti", "name": "WTI Crude Oil", "importance": 1},
    {"id": "natgas_hh", "name": "US Natural Gas (Henry Hub)", "importance": 2},
    {"id": "ttf_gas", "name": "Dutch TTF Natural Gas", "importance": 2},
    {"id": "diesel", "name": "US Diesel Price", "importance": 3},
    {"id": "ercot_load", "name": "ERCOT Electricity Load", "importance": 3},
    {"id": "pjm_power_price", "name": "PJM Power Price", "importance": 3},
    {"id": "eu_ets", "name": "EU ETS Carbon Price", "importance": 3},
    
    # Metals
    {"id": "gold", "name": "Gold", "importance": 2},
    {"id": "silver", "name": "Silver", "importance": 2},
    {"id": "copper", "name": "Copper", "importance": 2},
    {"id": "iron_ore", "name": "Iron Ore", "importance": 2},
    {"id": "aluminum", "name": "Aluminum", "importance": 3},
    
    # Agriculture
    {"id": "wheat", "name": "Wheat", "importance": 2},
    {"id": "corn", "name": "Corn", "importance": 2},
    {"id": "soybeans", "name": "Soybeans", "importance": 2},
    
    # Shipping
    {"id": "baltic_dry", "name": "Baltic Dry Index", "importance": 2},
    {"id": "scfi", "name": "Shanghai Containerized Freight Index", "importance": 2},
    
    # US Housing
    {"id": "us_housing_starts", "name": "US Housing Starts", "importance": 3},
    {"id": "us_mortgage30y", "name": "US 30Y Mortgage Rate", "importance": 2},
    {"id": "us_case_shiller_20", "name": "US Case-Shiller 20-City Home Price Index", "importance": 3},
    
    # European Housing
    {"id": "germany_house_prices", "name": "Germany House Price Index", "importance": 3},
    {"id": "uk_house_prices", "name": "UK House Price Index", "importance": 3},
    {"id": "sweden_house_prices", "name": "Sweden House Price Index", "importance": 3},
    
    # Fed Plumbing
    {"id": "rrp", "name": "Fed Reverse Repo (RRP) Balance", "importance": 2},
    {"id": "tga", "name": "US Treasury General Account (TGA)", "importance": 2},
    {"id": "fed_reserves", "name": "Fed Reserve Balances", "importance": 2},
    {"id": "ust_net_issuance", "name": "US Treasury Net Issuance", "importance": 2},
    
    # China
    {"id": "china_credit_impulse", "name": "China Credit Impulse", "importance": 2},
    {"id": "china_exports", "name": "China Exports", "importance": 2},
    {"id": "china_property_sales", "name": "China Property Sales", "importance": 3},
    {"id": "china_manufacturing_pmi", "name": "China Manufacturing PMI", "importance": 2},
    
    # Sector Indices
    {"id": "xlk", "name": "Technology Select Sector SPDR (XLK)", "importance": 3},
    {"id": "soxx", "name": "iShares Semiconductor ETF (SOXX)", "importance": 3},
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
            importance=topic["importance"]
        )
        
        # Generate query - NO FALLBACK, skip if fails
        anchor_text = f"Name: {topic['name']}"
        try:
            qres = create_wide_query(anchor_text)
            if isinstance(qres, dict) and qres.get("query"):
                t.query = qres["query"]
            else:
                logger.error(f"❌ Query generation returned empty for {topic_id} - SKIPPING")
                continue
        except Exception as e:
            logger.error(f"❌ Query generation failed for {topic_id}: {e} - SKIPPING")
            continue
        
        result = create_topic(t)
        logger.info(f"✅ Created topic: {result['name']} (id={result['id']})")
        
        # Enrich new topic
        try:
            from worker.workflows.topic_enrichment import backfill_topic_from_storage
            logger.info(f"Enriching: {result['id']}")
            backfill_topic_from_storage(
                topic_id=result['id'],
                threshold=2,
                max_articles_per_section=20
            )
            logger.info(f"✅ Enriched: {result['id']}")
        except Exception as e:
            logger.warning(f"⚠️ Enrichment failed for {result['id']}: {e}")
        
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
