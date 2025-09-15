from src.articles.load_article import load_article
from src.observability.pipeline_logging import master_log
from src.articles.article_text_formatter import extract_text_from_json_article
from src.graph.ops.get_all_nodes import get_all_nodes
from src.analysis.policies.node_identifier import find_node_mapping
from src.analysis.policies.category_identifier import find_category
from src.analysis.policies.impact_identifier import find_impact
from src.analysis.policies.time_frame_identifier import find_time_frame
from src.graph.neo4j_client import run_cypher
from utils.app_logging import get_logger
from src.graph.ops.find_link import find_influences_and_correlates
from src.analysis.orchestration.replace_article_orchestrator import does_article_replace_old
from events.classifier import EventClassifier, EventType
logger = get_logger(__name__)

def trigger_next_steps(topic_id: str, argos_id: str) -> None:
    # Trigger relationship discovery
    logger.info(f"Starting relationship discovery for Topic {topic_id}")
    find_influences_and_correlates(topic_id)
    logger.info(f"Completed relationship discovery for Topic {topic_id}")
    
    # Trigger replacement analysis
    replacement_result = does_article_replace_old(topic_id, argos_id)
    replaces = replacement_result.get("tool") != "none"
    logger.info(f"Article replacement for topic {topic_id}: replaces={replaces}")

def add_article(article_id: str, test: bool = False, intended_topic_id: str | None = None) -> dict:
    """
    Minimal, stateless pipeline for adding an Article node and ABOUT edge.
    Loads article from cold storage, formats text, runs node identification, deduplication, LLM-driven field extraction, creates node and ABOUT edge.
    Fails fast and logs all actions.
    """

    logger.info(f"Starting article processing for {article_id}")

    # Minimal event tracking
    trk = EventClassifier(EventType.ADD_ARTICLE)
    trk.put("source_article_id", article_id)

    # 1. Load article from cold storage
    article = load_article(article_id)
    if not article or not isinstance(article, dict):
        logger.error(f"Article not found or invalid: {article_id}")
        raise ValueError(f"Article not found or invalid: {article_id}")

    logger.info(f"Article loaded successfully, name: {article.get('name')}")

    # 2. Format article text for LLMs (not strictly required for pipeline, but for LLM helpers)
    
    formatted_article_text = extract_text_from_json_article(article)
    # logger.info(f"Formatted article text for LLM input. Length: {len(formatted_article_text)}")

    # 3. Multi-topic identification (find ALL topics this article is ABOUT)
    node_list = get_all_nodes()
    node_names = [f"\"{node['name']}\" - \"{node['id']}\"" for node in node_list]
    
    # 1. Get results from LLM  
    motivation, existing_node_ids, new_node_names = find_node_mapping(formatted_article_text, node_names)

    logger.info(f"Discovery complete: {len(existing_node_ids)} existing + {len(new_node_names)} new")
    logger.info(f"Existing: {existing_node_ids}")  
    logger.info(f"New: {new_node_names}")

    if not existing_node_ids and not new_node_names and not intended_topic_id:
        logger.warning(f"ABORT: No relevant topics found for article {article_id}. Skipping article.")
        trk.put("status", "skipped_no_topic")
        trk.set_id(article_id) # This sets the ID and triggers tracker to save. 
        return {"article_id": article_id, "status": "skipped", "reason": "no_topic_found"}
    if not existing_node_ids and not new_node_names and intended_topic_id:
        logger.info(f"No topics discovered by LLM; will link to intended_topic_id={intended_topic_id}")
    
        
    # 2. Save motivation and all topic discovery results for traceability
    trk.put("multi_topic_discovery", {
        "topic_discovery_motivation": motivation,
        "existing_ids": existing_node_ids,
        "new_names": new_node_names
    })

    # 3. Article-level processing (done ONCE regardless of topic count)
    argos_id = article.get("argos_id")
    
    # Check if Article node already exists
    article_exists_query = "OPTIONAL MATCH (a:Article {id: $id}) RETURN a IS NOT NULL AS exists"
    exists_result = run_cypher(article_exists_query, {"id": argos_id})
    article_already_exists = bool(exists_result[0].get("exists")) if exists_result else False

    # 4. Article-level LLM classifications (done ONCE for all topics)    
    category_motivation, type_val = find_category(article["argos_summary"])
    logger.info(f"Category: {type_val}")
    logger.info(f"Category motivation: {category_motivation}")
    
    impact_motivation, priority_val = find_impact(article["argos_summary"])
    logger.info(f"Impact motivation: {impact_motivation}")
    logger.info(f"Impact priority: {priority_val}")
    
    time_frame_motivation, temporal_horizon_val = find_time_frame(article["argos_summary"])
    logger.info(f"Time frame motivation: {time_frame_motivation}")
    logger.info(f"Temporal horizon: {temporal_horizon_val}")
    
    # Save all LLM-driven classification outputs
    trk.put("category", {"type": type_val, "motivation": category_motivation})
    trk.put("impact", {"priority": priority_val, "motivation": impact_motivation})
    trk.put("time_frame", {"temporal_horizon": temporal_horizon_val, "motivation": time_frame_motivation})
    relevance_score_val = None

    if not article_already_exists:
        # 5. Build Article node dict (fail fast on missing required fields)
        article_node = {
            "id": argos_id,
            "title": article.get("title"),
            "summary": article.get("argos_summary") or article.get("summary"),
            "source": article.get("url"),
            "published_at": article.get("pubDate"),
            "vector_id": None,
            "type": type_val,
            "temporal_horizon": temporal_horizon_val,
            "priority": priority_val,
            "relevance_score": relevance_score_val,
        }

        # Save the final built article_node dict for traceability
        trk.put("article_node", article_node)

        # 6. Insert Article node in Neo4j (only if it doesn't already exist)
        create_query = """
        CREATE (a:Article {
            id: $id,
            title: $title,
            summary: $summary,
            source: $source,
            published_at: $published_at,
            vector_id: $vector_id,
            type: $type,
            temporal_horizon: $temporal_horizon,
            priority: $priority,
            relevance_score: $relevance_score
        })
        RETURN a
        """
        run_cypher(create_query, article_node)
        logger.info(f"Created Article node for article id={argos_id}")
    else:
        logger.info(f"Article node {argos_id} already exists; skipping creation.")

    # 7. Ensure intended topic link if explicitly provided (and not already in discovered list)
    if intended_topic_id:
        if intended_topic_id not in existing_node_ids:
            about_query = """
            MATCH (a:Article {id: $article_id}), (t:Topic {id: $topic_id})
            MERGE (a)-[:ABOUT]->(t)
            """
            run_cypher(about_query, {"article_id": argos_id, "topic_id": intended_topic_id})
            logger.info(f"Created ABOUT edge from Article {argos_id} to Intended Topic {intended_topic_id}")
            # Trigger next steps for the intended topic link
            trigger_next_steps(intended_topic_id, argos_id)
            master_log(
                f"Added article | {article.get('argos_id')} | to intended topic {intended_topic_id}",
                articles_added=1 if not article_already_exists else 0,
                about_links_added=1,
            )

    # 8. Multi-topic processing: loop over all relevant topics
    results = []
    successful_topics = 0

    # Process existing nodes
    for i, existing_id in enumerate(existing_node_ids):
        logger.info(f"Processing existing topic {i+1}/{len(existing_node_ids)}: {existing_id}")
        topic_id = existing_id
        
        # Check if ABOUT edge already exists for this topic
        edge_exists_query = """
        OPTIONAL MATCH (a:Article {id: $id})
        WITH a
        OPTIONAL MATCH (a)-[:ABOUT]->(t:Topic {id: $topic_id})
        RETURN a IS NOT NULL AS article_exists, t IS NOT NULL AS about_exists
        """
        dedup_result = run_cypher(edge_exists_query, {"id": argos_id, "topic_id": topic_id})
        
        if dedup_result:
            row = dedup_result[0]
            about_exists = bool(row.get("about_exists"))
            
            if about_exists:
                logger.info(f"Article {argos_id} already linked to topic {topic_id}. Skipping duplicate.")
                continue
        
        # Create ABOUT edge
        about_query = """
        MATCH (a:Article {id: $article_id}), (t:Topic {id: $topic_id})
        MERGE (a)-[:ABOUT]->(t)
        """
        run_cypher(about_query, {"article_id": argos_id, "topic_id": topic_id})
        logger.info(f"Created ABOUT edge from Article {argos_id} to Topic {topic_id}")
        
        # Trigger next steps, relationship discovery and replacement analysis
        trigger_next_steps(topic_id, argos_id)

        successful_topics += 1
        master_log(
            f"Added article | {article.get('argos_id')} | to existing topic {topic_id}",
            articles_added=1 if not article_already_exists else 0,
            about_links_added=1,
        )

    # If new node names are found, run this one time
    if len(new_node_names) > 0:
        
        # Create new topic
        from graph.ops.add_node import add_node
        logger.info(f"Testing to creating new topic, for article {article_id}")
        new_node_result = add_node(article_id, suggested_names=new_node_names)
        topic_id = new_node_result.get("id")
        if not topic_id:
            logger.warning(f"Failed to create new topic for article {article_id}")
            master_log(
                f"Failed to create new topic for article | {article.get('argos_id')} | to new topic {topic_id}")
        else: 
            # Create ABOUT edge
            about_query = """
            MATCH (a:Article {id: $article_id}), (t:Topic {id: $topic_id})
            MERGE (a)-[:ABOUT]->(t)
            """
            run_cypher(about_query, {"article_id": argos_id, "topic_id": topic_id})
            logger.info(f"Created ABOUT edge from Article {argos_id} to Topic {topic_id}")
            
            # Trigger next steps, relationship discovery and replacement analysis
            trigger_next_steps(topic_id, argos_id)
        
            successful_topics += 1
            master_log(
                f"Added article | {article.get('argos_id')} | to new topic {topic_id}",
                articles_added=1 if not article_already_exists else 0,
                about_links_added=1,
            )

    # Final tracking and logging, existing node len and if new nodes are more than 1, it still counts as 1
    total_topics = len(existing_node_ids) 
    if len(new_node_names) > 0:
        total_topics += 1
    # Count the intended topic if it was provided and not part of discovered/new
    if intended_topic_id and intended_topic_id not in existing_node_ids:
        # We already linked it above; include it in totals for traceability
        total_topics += 1
        successful_topics += 1
    trk.put("multi_topic_results", {
        "total_topics": total_topics,
        "successful": successful_topics
    })
    trk.put("status", "success" if successful_topics > 0 else "failed")
    trk.set_id(article.get("argos_id"))

    logger.info(f"Multi-topic processing complete: {successful_topics}/{total_topics} topics successful. Existing len: {len(existing_node_ids)} + New len: {len(new_node_names)}")
    return {
        "article_id": article.get("argos_id"), 
        "status": "success" if successful_topics > 0 else "failed",
        "topics_processed": successful_topics
    }
