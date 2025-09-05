"""
USER ANCHOR NODES AND RELATIONSHIPS

This file is part of the Saga Graph project—a world-scale knowledge graph for understanding macro, markets, and investment research. The core of this system is a massive Neo4j graph database, designed to represent the real structure and drivers of the world economy. All nodes, relationships, and analyses are stored in Neo4j and can scale to hundreds of topics and thousands of articles per day. This file defines the permanent, user-controlled anchor nodes and explicit relationships that serve as the foundation for all automated and LLM-driven reasoning in the graph.

HOW THIS STRUCTURE WORKS:
- Each anchor node is a specific, atomic, standalone area of interest (e.g., EURUSD, S&P 500, US Inflation, Oil, Gold, Wheat).
- **General or group anchors (e.g., 'Commodities', 'Equities', 'Asia') are strictly prohibited.** Only specific, connectable entities are allowed. This is because:
    - Only specific nodes can be meaningfully linked in a knowledge graph.
    - LLMs and humans both require specificity for actionable reasoning and relationship-building.
    - General groups cannot be precisely connected or reasoned about.
- Anchor nodes are never deleted or overwritten by automated or LLM-driven processes. They are the pillars of your research universe.
- Anchor nodes store minimal fields only: 'id', 'name', 'importance' (1..5 per `graph_nodes/priority_policy.py`), and a 'query' string used for retrieval. No extra fields like status/type/notes.
- There is no parent-child hierarchy: all anchor nodes are on the same level. Relationships between them are explicit and typed: 'INFLUENCES', 'CORRELATES_WITH', and 'PEERS' (rare).
- When building or refreshing the graph, these nodes are always present. LLMs or other agents may add new nodes or relationships, but never remove or modify anchors.
- You can update this file as your interests evolve—add, remove, or modify anchor nodes and relationships at any time.
- This structure is designed for clarity, modularity, and reproducibility. It also provides a rich context for LLM prompts, ensuring that any automated reasoning or node creation is always grounded in your real priorities and mental models.

EXAMPLE USAGE:
- On graph creation, load all anchor nodes and relationships from this file and MERGE them into the graph.
- When prompting an LLM to propose new nodes or relationships, provide anchor 'name' and 'query' as context.
- Never allow any process to delete or overwrite these anchors.

"""

USER_ANCHOR_NODES = [
    # Existing core
    {"id": "eurusd", "name": "EURUSD", "importance": 1},
    {"id": "us_inflation", "name": "US Inflation", "importance": 2},
    {"id": "euro_inflation", "name": "Euro Area Inflation", "importance": 2},
    {"id": "spx", "name": "S&P 500", "importance": 2},
    {"id": "sx5e", "name": "Euro Stoxx 50", "importance": 2},
    {"id": "fed_policy", "name": "Fed Policy", "importance": 4},
    {"id": "ecb_policy", "name": "ECB Policy", "importance": 4},
    {"id": "ust10y", "name": "US 10Y Treasury Yield", "importance": 1},
    {"id": "euribor", "name": "Euribor", "importance": 2},
    {"id": "brent", "name": "Brent Crude Oil", "importance": 1},
    {"id": "wti", "name": "WTI Crude Oil", "importance": 1},
    {"id": "gold", "name": "Gold", "importance": 2},
    {"id": "copper", "name": "Copper", "importance": 2},
    {"id": "wheat", "name": "Wheat", "importance": 2},
    {"id": "china_credit_impulse", "name": "China Credit Impulse", "importance": 2},
    {"id": "china_exports", "name": "China Exports", "importance": 2},

    # FX & Dollar
    {"id": "dxy", "name": "US Dollar Index (DXY)", "importance": 1},
    {"id": "usdjpy", "name": "USD/JPY", "importance": 1},
    {"id": "gbpusd", "name": "GBP/USD", "importance": 1},
    {"id": "usdcny", "name": "USD/CNY", "importance": 2},

    # Global rates & curves
    {"id": "ust2y", "name": "US 2Y Treasury Yield", "importance": 1},
    {"id": "ust5y", "name": "US 5Y Treasury Yield", "importance": 2},
    {"id": "ust30y", "name": "US 30Y Treasury Yield", "importance": 2},
    {"id": "bund10y", "name": "German 10Y Bund Yield", "importance": 2},
    {"id": "gilt10y", "name": "UK 10Y Gilt Yield", "importance": 2},
    {"id": "jgb10y", "name": "Japan 10Y JGB Yield", "importance": 2},
    {"id": "sofr", "name": "SOFR", "importance": 2},

    # Credit & spreads
    {"id": "cdx_ig", "name": "CDX IG", "importance": 2},
    {"id": "cdx_hy", "name": "CDX HY", "importance": 2},
    {"id": "itrx_main", "name": "iTraxx Main", "importance": 2},
    {"id": "us_ig_spread", "name": "US IG Credit Spread", "importance": 2},
    {"id": "us_hy_spread", "name": "US HY Credit Spread", "importance": 2},

    # Inflation details
    {"id": "us_core_cpi", "name": "US Core CPI", "importance": 2},
    {"id": "us_pce", "name": "US PCE Inflation", "importance": 2},
    {"id": "euro_core_hicp", "name": "Euro Area Core HICP", "importance": 2},

    # Labor markets
    {"id": "us_payrolls", "name": "US Nonfarm Payrolls", "importance": 2},
    {"id": "us_unemployment_rate", "name": "US Unemployment Rate", "importance": 3},
    {"id": "us_job_openings", "name": "US Job Openings (JOLTS)", "importance": 3},

    # Energy & power
    {"id": "natgas_hh", "name": "US Natural Gas (Henry Hub)", "importance": 2},
    {"id": "ttf_gas", "name": "Dutch TTF Natural Gas", "importance": 2},
    {"id": "diesel", "name": "US Diesel Price", "importance": 3},
    {"id": "ercot_load", "name": "ERCOT Electricity Load", "importance": 3},
    {"id": "pjm_power_price", "name": "PJM Power Price", "importance": 3},
    {"id": "eu_ets", "name": "EU ETS Carbon Price", "importance": 3},

    # Metals & agri
    {"id": "silver", "name": "Silver", "importance": 2},
    {"id": "iron_ore", "name": "Iron Ore", "importance": 2},
    {"id": "aluminum", "name": "Aluminum", "importance": 3},
    {"id": "corn", "name": "Corn", "importance": 2},
    {"id": "soybeans", "name": "Soybeans", "importance": 2},

    # Shipping & logistics
    {"id": "baltic_dry", "name": "Baltic Dry Index", "importance": 2},
    {"id": "scfi", "name": "Shanghai Containerized Freight Index", "importance": 2},

    # Housing
    {"id": "housing_starts", "name": "US Housing Starts", "importance": 3},
    {"id": "mortgage30y", "name": "US 30Y Mortgage Rate", "importance": 2},
    {"id": "case_shiller_20", "name": "Case-Shiller 20-City Home Price Index", "importance": 3},

    # Banking system & issuance
    {"id": "rrp", "name": "Fed Reverse Repo (RRP) Balance", "importance": 2},
    {"id": "tga", "name": "US Treasury General Account (TGA)", "importance": 2},
    {"id": "fed_reserves", "name": "Fed Reserve Balances", "importance": 2},
    {"id": "ust_net_issuance", "name": "US Treasury Net Issuance", "importance": 2},

    # China specifics
    {"id": "china_property_sales", "name": "China Property Sales", "importance": 3},
    {"id": "china_manufacturing_pmi", "name": "China Manufacturing PMI", "importance": 2},

    # Select companies (tickers uppercase)
    {"id": "NVDA", "name": "NVIDIA", "importance": 3},
    {"id": "TSM", "name": "TSMC", "importance": 3},
    {"id": "ASML", "name": "ASML", "importance": 3},
    {"id": "MSFT", "name": "Microsoft", "importance": 3},
    {"id": "AMZN", "name": "Amazon", "importance": 3},
    {"id": "GOOGL", "name": "Alphabet", "importance": 3},
    {"id": "META", "name": "Meta Platforms", "importance": 3},
]

USER_ANCHOR_RELATIONSHIPS = [
    # Policy to Rates/FX/Index
    {"from": "fed_policy", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "ust2y", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "spx", "type": "INFLUENCES"},
    {"from": "fed_policy", "to": "dxy", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "ecb_policy", "to": "bund10y", "type": "INFLUENCES"},

    # Inflation to Rates/FX/Index
    {"from": "us_inflation", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "us_inflation", "to": "spx", "type": "INFLUENCES"},
    {"from": "euro_inflation", "to": "eurusd", "type": "INFLUENCES"},
    {"from": "euro_inflation", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "ust2y", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "ust10y", "type": "INFLUENCES"},
    {"from": "us_core_cpi", "to": "spx", "type": "INFLUENCES"},
    {"from": "euro_core_hicp", "to": "bund10y", "type": "INFLUENCES"},
    {"from": "euro_core_hicp", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "euro_core_hicp", "to": "eurusd", "type": "INFLUENCES"},

    # Rates to Index & FX
    {"from": "ust10y", "to": "spx", "type": "INFLUENCES"},
    {"from": "euribor", "to": "sx5e", "type": "INFLUENCES"},
    {"from": "ust2y", "to": "dxy", "type": "INFLUENCES"},

    # Commodities to Inflation
    {"from": "brent", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "wti", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "wheat", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "natgas_hh", "to": "us_inflation", "type": "INFLUENCES"},
    {"from": "ttf_gas", "to": "euro_inflation", "type": "INFLUENCES"},
    {"from": "diesel", "to": "us_inflation", "type": "INFLUENCES"},

    # China growth proxies
    {"from": "china_credit_impulse", "to": "copper", "type": "INFLUENCES"},
    {"from": "china_exports", "to": "copper", "type": "INFLUENCES"},
    {"from": "china_credit_impulse", "to": "china_property_sales", "type": "INFLUENCES"},
    {"from": "china_manufacturing_pmi", "to": "china_exports", "type": "CORRELATES_WITH"},

    # Banking & liquidity
    {"from": "rrp", "to": "sofr", "type": "INFLUENCES"},
    {"from": "ust_net_issuance", "to": "ust10y", "type": "INFLUENCES"},

    # Housing
    {"from": "mortgage30y", "to": "housing_starts", "type": "INFLUENCES"},

    # Power & fuels
    {"from": "ercot_load", "to": "natgas_hh", "type": "INFLUENCES"},
    {"from": "pjm_power_price", "to": "natgas_hh", "type": "CORRELATES_WITH"},

    # Credit spreads
    {"from": "cdx_ig", "to": "us_ig_spread", "type": "CORRELATES_WITH"},
    {"from": "cdx_hy", "to": "us_hy_spread", "type": "CORRELATES_WITH"},

    # Cross-market correlations
    {"from": "spx", "to": "sx5e", "type": "CORRELATES_WITH"},
    {"from": "sx5e", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "gold", "to": "us_inflation", "type": "CORRELATES_WITH"},
    {"from": "dxy", "to": "eurusd", "type": "CORRELATES_WITH"},
    {"from": "eurusd", "to": "dxy", "type": "CORRELATES_WITH"},
    {"from": "ust2y", "to": "ust10y", "type": "CORRELATES_WITH"},
    {"from": "ust10y", "to": "ust2y", "type": "CORRELATES_WITH"},
    {"from": "ust10y", "to": "ust30y", "type": "CORRELATES_WITH"},
    {"from": "bund10y", "to": "gilt10y", "type": "CORRELATES_WITH"},
    {"from": "silver", "to": "gold", "type": "CORRELATES_WITH"},
    {"from": "gold", "to": "silver", "type": "CORRELATES_WITH"},
    {"from": "baltic_dry", "to": "iron_ore", "type": "CORRELATES_WITH"},
    {"from": "iron_ore", "to": "baltic_dry", "type": "CORRELATES_WITH"},
    {"from": "baltic_dry", "to": "scfi", "type": "CORRELATES_WITH"},
    {"from": "eu_ets", "to": "ttf_gas", "type": "CORRELATES_WITH"},
    {"from": "us_pce", "to": "us_core_cpi", "type": "CORRELATES_WITH"},
    {"from": "usdjpy", "to": "dxy", "type": "CORRELATES_WITH"},
    {"from": "gbpusd", "to": "dxy", "type": "CORRELATES_WITH"},
    {"from": "usdcny", "to": "dxy", "type": "CORRELATES_WITH"},

    # Benchmarks that are true peers
    {"from": "brent", "to": "wti", "type": "PEERS"},
    {"from": "wti", "to": "brent", "type": "PEERS"},

    # Company correlations (market beta / supply chain)
    {"from": "NVDA", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "MSFT", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "AMZN", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "GOOGL", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "META", "to": "spx", "type": "CORRELATES_WITH"},
    {"from": "TSM", "to": "NVDA", "type": "CORRELATES_WITH"},
    {"from": "ASML", "to": "TSM", "type": "CORRELATES_WITH"},
]

if __name__ == "__main__":
    from graph_utils.create_topic_node import create_topic_node
    from graph_utils.check_if_node_exists import check_if_node_exists, get_node_if_exists
    from func_add_topic.create_query_llm import create_wide_query
    from func_add_relationships.add_link import add_link
    from graph_db.db_driver import run_cypher
    from utils import minimal_logging
    logger = minimal_logging.get_logger(__name__)

    # First, seed all anchor nodes
    logger.info(f"Seeding {len(USER_ANCHOR_NODES)} anchor nodes...")
    nodes_created = 0
    nodes_existed = 0
    
    for node in USER_ANCHOR_NODES:
        node_id = node['id']
        logger.info(f"Processing anchor node: {node['name']} (id={node_id})")
        
        # Check if node already exists
        if check_if_node_exists(node_id):
            existing_node = get_node_if_exists(node_id)
            logger.info(f"Anchor node already exists: {existing_node['name']} (id={node_id})")
            # Ensure importance is set to the configured value
            desired_imp = node.get("importance")
            existing_imp = existing_node.get("importance")
            if desired_imp is not None and existing_imp != desired_imp:
                run_cypher(
                    "MATCH (n:Topic {id: $id}) SET n.importance = $importance RETURN n.importance AS importance",
                    {"id": node_id, "importance": int(desired_imp)}
                )
                logger.info(f"Updated importance for anchor {node_id}: {existing_imp} -> {desired_imp}")
            nodes_existed += 1
            continue
            
        # Node doesn't exist, create it
        topic_dict = {"id": node["id"], "name": node["name"]}
        if "importance" in node and node["importance"] is not None:
            topic_dict["importance"] = node["importance"]

        # If the node already contains a query, respect it; otherwise generate via LLM
        if "query" in node and node["query"]:
            topic_dict["query"] = node["query"]
        else:
            anchor_text = f"Name: {node['name']}"
            qres = create_wide_query(anchor_text)
            if not isinstance(qres, dict) or not qres.get("query"):
                raise RuntimeError(f"Query generation failed for anchor '{node_id}'")
            topic_dict["query"] = qres["query"]

        result = create_topic_node(topic_dict)
        logger.info(f"Created new anchor node: {result['name']} (id={result['id']})")
        nodes_created += 1
        
    logger.info(f"Anchor node seeding complete: {nodes_created} nodes created, {nodes_existed} already existed.")

    # Validate that all anchors have a valid importance (1..5). Fail fast if any are missing/invalid.
    anchor_ids = [n["id"] for n in USER_ANCHOR_NODES]
    bad_rows = run_cypher(
        """
        MATCH (n:Topic)
        WHERE n.id IN $ids AND (n.importance IS NULL OR NOT n.importance IN [1,2,3,4,5])
        RETURN n.id AS id, n.importance AS importance
        """,
        {"ids": anchor_ids}
    )
    if bad_rows:
        details = ", ".join(f"{r['id']} (importance={r.get('importance')})" for r in bad_rows)
        raise RuntimeError(f"Anchor importance validation failed for: {details}")


    # Then, create all anchor relationships
    logger.info(f"Creating {len(USER_ANCHOR_RELATIONSHIPS)} anchor relationships...")
    success_count = 0
    error_count = 0

    for rel in USER_ANCHOR_RELATIONSHIPS:
        source_id = rel["from"]
        target_id = rel["to"]
        rel_type = rel["type"].upper()  # Normalize to uppercase for add_link
        link = {
            "type": rel_type,
            "source": source_id,
            "target": target_id,
            "motivation": rel.get("motivation", "Anchor relationship seeding")
        }
        try:
            add_link(link)
            logger.info(f"Added {rel_type}: {source_id} -> {target_id}")
            success_count += 1
        except Exception as e:
            logger.error(f"Error creating relationship {rel_type} from {source_id} to {target_id}: {str(e)}")
            error_count += 1

    logger.info(f"Anchor relationships created: {success_count} successful, {error_count} errors")
