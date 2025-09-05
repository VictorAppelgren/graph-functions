"""
Orchestrator: decides if a new article should replace an existing one for a topic node.
Fetches articles, calls does_article_replace_old_llm, handles DB replacement, and triggers should_rewrite if needed.
"""
from typing import Dict, List
from func_analysis.does_article_replace_old_llm import does_article_replace_old_llm
from func_analysis.should_rewrite import should_rewrite
from graph_db.db_driver import run_cypher
from utils.load_article import load_article
from utils import minimal_logging
from utils.master_log import master_log, problem_log
from tracker.tracker import Tracker
logger = minimal_logging.get_logger(__name__)

from graph_utils.get_article_temporal_horizon import get_article_temporal_horizon
from func_add_article.time_frame_identifier_llm import find_time_frame

# Per-timeframe policy (simple defaults, aligned with LLM helper)
MIN_PER_TIMEFRAME = 5
MAX_PER_TIMEFRAME = 10

def does_article_replace_old(topic_id: str, new_article_id: str, test: bool = False) -> Dict:
    """
    Orchestrator: fetches existing articles for topic, calls LLM to decide replacement, removes old if needed, triggers should_rewrite.
    Returns dict: {'replaces': bool, 'id_to_replace': str or None, 'motivation': str}
    """

    logger.info(f"Starting does_article_replace_old for topic_id={topic_id}")

    trk = Tracker("article_replacement_decision")
    trk.put("topic_id", topic_id)
    trk.put("new_article_id", new_article_id)
    trk.put("test", bool(test))

    logger.info(f"new_article_id that will be loaded={new_article_id}")
    new_article = load_article(new_article_id)
    if "argos_summary" not in new_article:
        problem_log("missing_summary_for_replacement_decision", topic=topic_id, details={"article_id": new_article_id})
        trk.put("status", "skipped_missing_summary")
        return {'tool': 'none', 'id': None, 'motivation': 'No argos_summary for new article'}
    summary = new_article["argos_summary"]

    # Derive timeframe; if missing, infer once and persist, then continue
    try:
        new_tf = get_article_temporal_horizon(new_article_id)
    except ValueError:
        logger.warning(f"Article {new_article_id} missing temporal_horizon. Inferring and backfilling.")
        motivation, inferred_tf = find_time_frame(summary)
        run_cypher("MATCH (a:Article {id:$id}) SET a.temporal_horizon = $tf", {"id": new_article_id, "tf": inferred_tf})
        master_log(f"Backfilled temporal_horizon | article={new_article_id} | tf={inferred_tf}")
        new_tf = inferred_tf
    logger.info(f"article: {new_article_id} temporal_horizon={new_tf}")
    event_id = f"{topic_id}__{new_article_id}__{new_tf}"
    trk.put("timeframe", new_tf)

    # Per-topic min/max caps: read from Topic if present, else fall back to module defaults.
    # This keeps the function stateless and configurable per topic without changing code.
    caps_q = """
    MATCH (t:Topic {id:$topic_id})
    RETURN t.tf_bucket_min AS tf_min, t.tf_bucket_max AS tf_max
    """
    caps_res = run_cypher(caps_q, {"topic_id": topic_id}) or []
    tf_min = caps_res[0].get("tf_min") if caps_res else None
    tf_max = caps_res[0].get("tf_max") if caps_res else None
    try:
        min_per_tf = int(tf_min) if tf_min is not None else MIN_PER_TIMEFRAME
    except Exception:
        min_per_tf = MIN_PER_TIMEFRAME
    try:
        max_per_tf = int(tf_max) if tf_max is not None else MAX_PER_TIMEFRAME
    except Exception:
        max_per_tf = MAX_PER_TIMEFRAME
    trk.put("min_per_tf", int(min_per_tf))
    trk.put("max_per_tf", int(max_per_tf))

    # Count visible articles in the same timeframe (exclude priority='hidden')
    cnt_q = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
    WHERE a.temporal_horizon = $tf
      AND (a.priority IS NULL OR a.priority <> 'hidden')
    RETURN count(a) AS cnt
    """
    same_tf_cnt = (run_cypher(cnt_q, {"topic_id": topic_id, "tf": new_tf}) or [{"cnt": 0}])[0]["cnt"]
    trk.put("same_tf_cnt", int(same_tf_cnt))
    if same_tf_cnt < min_per_tf:
        trk.put("status", "skipped_under_min")
        trk.set_id(event_id)
        master_log(f"Replacement of article skipped | {topic_id} | tf={new_tf} cnt={same_tf_cnt} < {min_per_tf}")
        return {'tool': 'none', 'id': None, 'motivation': 'Under per-timeframe minimum'}

    # Build competing candidates (same timeframe, visible, excluding the new one). Visible = not priority='hidden'
    pool_q = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
    WHERE a.temporal_horizon = $tf
      AND (a.priority IS NULL OR a.priority <> 'hidden')
    RETURN a.id AS id, a.argos_summary AS argos_summary, a.priority AS priority, a.published_at AS published_at
    """
    pool = run_cypher(pool_q, {"topic_id": topic_id, "tf": new_tf}) or []
    candidates = [a for a in pool if a["id"] != new_article_id and ("argos_summary" in a and a["argos_summary"])]
    if not candidates:
        problem_log(problem="No replacement candidates", topic=topic_id, details={"timeframe": new_tf})
        trk.put("status", "skipped_no_candidates")
        trk.set_id(event_id)
        master_log(f"Replacement of article skipped | {topic_id} | no competing candidates in timeframe {new_tf}")
        return {'tool': 'none', 'id': None, 'motivation': 'No competing candidates'}
    trk.put("candidate_ids", [a["id"] for a in candidates])

    # Build context from other timeframes (read-only). Only include not priority='hidden'
    ctx_q = """
    MATCH (a:Article)-[:ABOUT]->(t:Topic {id:$topic_id})
    WHERE a.temporal_horizon <> $tf
      AND (a.priority IS NULL OR a.priority <> 'hidden')
    RETURN a.id AS id, a.argos_summary AS argos_summary, a.temporal_horizon AS tf
    """
    others = run_cypher(ctx_q, {"topic_id": topic_id, "tf": new_tf}) or []
    others = [o for o in others if ("tf" in o and "argos_summary" in o and o["argos_summary"])]
    context_text = "\n".join([f"- ({o['tf']}) {o['id']}: {o['argos_summary']}" for o in others])

    # Decide instruction (CAN vs MUST)
    decision_instruction = (
        "MUST_REPLACE: The competing timeframe bucket is at or above capacity. You MUST choose exactly one id from the competing set and set 'tool'='remove'."
        if same_tf_cnt >= max_per_tf else
        "CAN_REPLACE: Only act if the new article clearly supersedes an existing one. Otherwise use 'tool'='none' and id=null."
    )
    mode = "MUST_REPLACE" if same_tf_cnt >= max_per_tf else "CAN_REPLACE"
    trk.put("mode", mode)

    res = does_article_replace_old_llm(
        summary,
        candidates,
        test=test,
        decision_instruction=decision_instruction,
        context_text=context_text,
    )
    motivation = res.get("motivation", "")
    tool = res.get("tool", "none")
    target_id = res.get("id")
    trk.put("llm_decision", {"tool": tool, "id": target_id, "motivation": motivation})
    logger.info(f"does_article_replace_old: tool={tool}") 
    logger.info(f"does_article_replace_old: id={target_id}")
    logger.info(f"does_article_replace_old: motivation={motivation}")
    
    # Validate LLM-selected id strictly against allowed candidate IDs. If invalid:
    # - In CAN mode: treat as no action.
    # - In MUST mode: fall back deterministically (lowest priority, then oldest).
    candidate_ids = {a["id"] for a in candidates}
    if tool != "none" and (not target_id or target_id not in candidate_ids):
        if same_tf_cnt >= max_per_tf:
            tool = "remove"
            trk.put("fallback_used", True)
            trk.put("fallback_reason", "invalid_llm_selection")
            # Deterministic fallback: choose lowest priority (1 < 2 < 3), then oldest published_at
            pmap = {"1": 1, "2": 2, "3": 3}
            def sort_key(a: Dict):
                return (pmap.get(str(a.get("priority")), 2), str(a.get("published_at") or ""))
            target_id = sorted(candidates, key=sort_key)[0]["id"]
            if not motivation:
                motivation = "Invalid LLM selection; used deterministic fallback under capacity cap."
        else:
            tool = "none"
            target_id = None
            if not motivation:
                motivation = "Invalid LLM selection; ignoring in CAN mode."
    
    # In MUST mode, if LLM chose none, pick deterministically: lowest priority, then oldest
    if same_tf_cnt >= max_per_tf and (tool == "none" or not target_id):
        trk.put("fallback_used", True)
        trk.put("fallback_reason", "capacity_cap")
        pmap = {"1": 1, "2": 2, "3": 3}
        def sort_key(a: Dict):
            return (pmap.get(str(a.get("priority")), 2), str(a.get("published_at") or ""))
        target_id = sorted(candidates, key=sort_key)[0]["id"]
        tool = "remove"
        motivation = motivation or "Capacity cap reached; removing weakest/oldest competing article."

    trk.put("target_id", target_id)
    trk.put("action_taken", tool if tool in ("remove","hide","lower_priority") else "none")
    if tool in ("remove","hide","lower_priority"):
        trk.put("status", "success")
    else:
        trk.put("status", "no_action")
    trk.set_id(event_id)

    if tool != "none" and target_id and not test:
        if tool == "remove":
            remove_query = """
            MATCH (a:Article {id: $id}) DETACH DELETE a
            """
            run_cypher(remove_query, {"id": target_id})
            logger.info(f"Removed article id={target_id} from graph.")
            master_log(f"Article replaced | {topic_id} | old={target_id} new={new_article_id}", articles_removed=1)
            # Trigger should_rewrite only when we changed graph state
            should_rewrite(topic_id, new_article_id)
        elif tool == "hide":
            from graph_utils.set_article_hidden import set_article_hidden
            set_article_hidden(target_id)
            logger.info(f"Set article id={target_id} to hidden via graph_utils.set_article_hidden.")
            should_rewrite(topic_id, new_article_id)
        elif tool == "lower_priority":
            from graph_utils.update_article_priority import update_article_priority
            update_article_priority(target_id)
            logger.info(f"Lowered priority for article id={target_id} via graph_utils.update_article_priority.")
            should_rewrite(topic_id, new_article_id)
        else:
            logger.info(f"does_article_replace_old: no action taken, action={tool}")
    else:
        logger.info(f"does_article_replace_old: no action taken")
        master_log(f"No replacement of article | {topic_id} | new_article={new_article_id}")
        # If no action and topic has no analysis, trigger analysis writing
        topic_cypher = """
        MATCH (t:Topic {id: $topic_id})
        RETURN t.fundamental_analysis as fundamental_analysis, t.medium_analysis as medium_analysis, t.current_analysis as current_analysis, t.implications as implications
        """
        topic = run_cypher(topic_cypher, {"topic_id": topic_id})
        if topic:
            analysis_fields = {k: topic[0][k] for k in ["fundamental_analysis", "medium_analysis", "current_analysis", "implications"]}
            missing_count = sum(1 for v in analysis_fields.values() if not v)
            if missing_count > 0:
                logger.info(f"Analysis incomplete for topic {topic_id} ({missing_count}/4 fields missing); triggering analysis writing.")
                should_rewrite(topic_id, new_article_id)

    return {'tool': tool, 'id': target_id, 'motivation': motivation}
