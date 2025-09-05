from graph_utils.get_node_by_id import get_node_by_id
from graph_utils.get_all_nodes import get_all_nodes
from func_add_relationships.llm_filter_all_interesting_topics import llm_filter_all_interesting_topics
from func_add_relationships.get_existing_links import get_existing_links
from func_add_relationships.llm_select_one_new_link import llm_select_one_new_link
from func_add_relationships.add_link import add_link
from func_remove_relationship.remove_relationship import select_and_remove_link
from utils import minimal_logging
from utils.master_log import master_log_error

logger = minimal_logging.get_logger(__name__)

MAX_LINKS_PER_TYPE = 10


def find_influences_and_correlates(topic_id: str, test: bool = False) -> dict:
    """
    God-tier orchestrator: discovers and manages the strongest new relationship for the given topic node.
    Returns a dict with full trace of actions and results.
    """
    trace = {}
    logger.info(f" Called for topic_id={topic_id}")
    # 1. Fetch source node
    try:
        node = get_node_by_id(topic_id)
    except Exception as e:
        logger.warning(f" Source node missing for topic_id={topic_id}; skipping discovery")
        master_log_error(f"find_influences_and_correlates skipped: Topic missing | topic_id={topic_id}", error=e)
        trace['action'] = 'topic_missing'
        return trace
    trace['source_node'] = node
    logger.info(f" Source node fetched: {node.get('name', node.get('id'))}")
    # 2. Fetch all nodes
    all_nodes = get_all_nodes()
    trace['all_nodes_count'] = len(all_nodes)
    logger.info(f" Fetched {len(all_nodes)} total nodes for candidate selection.")
    # 3. LLM filter to plausible candidates
    shortlist = llm_filter_all_interesting_topics(node, all_nodes)
    candidate_ids = shortlist.get('candidate_ids', [])
    candidate_motivation = shortlist.get('motivation')
    trace['candidate_ids'] = candidate_ids
    trace['candidate_motivation'] = candidate_motivation
    logger.info(f" LLM shortlisted {len(candidate_ids)} candidate nodes.")
    candidate_nodes = [n for n in all_nodes if n['id'] in candidate_ids]
    # 4. Fetch existing links
    existing_links = get_existing_links(topic_id)
    trace['existing_links'] = existing_links
    logger.info(f" Node has {len(existing_links)} existing links.")
    # 5. LLM propose strongest new link
    new_link = llm_select_one_new_link(node, candidate_nodes, existing_links)
    trace['proposed_link'] = new_link
    if not new_link:
        logger.info(f" No strong new link proposed by LLM. Exiting.")
        trace['action'] = 'no_link_proposed'
        return trace
    logger.info(f" LLM proposed link: {new_link}")
    # 6. Check max-link cap for this type
    link_type = new_link['type']
    links_of_type = [l for l in existing_links if l['type'] == link_type]
    if len(links_of_type) >= MAX_LINKS_PER_TYPE:
        logger.info(f" Max links ({MAX_LINKS_PER_TYPE}) for type '{link_type}' reached. Invoking LLM removal selector.")
        status = select_and_remove_link(node, links_of_type, new_link)
        trace['removal_decision'] = status.get('removal_decision')
        if status.get('ok'):
            # Prepare context for tracker provenance (kept same keys used in add_link tracker)
            context = {
                "candidate_ids": candidate_ids,
                "candidate_motivation": candidate_motivation,
                "selection_motivation": new_link.get('motivation') if isinstance(new_link, dict) else None,
                "existing_links_before": existing_links,
                "all_nodes_count": len(all_nodes),
                "candidate_count": len(candidate_ids),
                "existing_links_count": len(existing_links),
            }
            add_link(new_link, context=context)
            logger.info(f" Added new link after removal: {new_link}")
            trace['action'] = 'removed_and_added'
            return trace
        else:
            reason = status.get('reason') or 'no_removal_recommended'
            if reason == 'removal_link_not_found':
                logger.info(f" LLM suggested removal, but link not found. No action taken.")
                trace['action'] = 'removal_link_not_found'
            else:
                logger.info(f" LLM did not recommend removing any existing link. No action taken.")
                trace['action'] = 'no_removal_recommended'
            return trace
    else:
        # Add new link directly
        # Prepare context for tracker provenance
        context = {
            "candidate_ids": candidate_ids,
            "candidate_motivation": candidate_motivation,
            "selection_motivation": new_link.get('motivation') if isinstance(new_link, dict) else None,
            "existing_links_before": existing_links,
            "all_nodes_count": len(all_nodes),
            "candidate_count": len(candidate_ids),
            "existing_links_count": len(existing_links),
        }
        add_link(new_link, context=context)
        logger.info(f" Added new link: {new_link}")
        trace['action'] = 'added_new_link'
        return trace
