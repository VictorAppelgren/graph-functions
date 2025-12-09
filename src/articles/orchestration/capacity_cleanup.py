from typing import List, Optional

from utils.app_logging import get_logger

from src.graph.ops.topic import get_all_topics
from src.articles.orchestration.article_capacity_orchestrator import (
    check_capacity,
    check_capacity_per_perspective,
)
from src.graph.neo4j_client import run_cypher


logger = get_logger(__name__)


DEFAULT_TIMEFRAMES: List[str] = ["fundamental", "medium", "current"]
DEFAULT_TIERS: List[int] = [3, 2, 1]
MAX_CLEANUP_PASSES: int = 5
PERSPECTIVES: List[str] = ["risk", "opportunity", "trend", "catalyst"]


def _log_topic_distribution(topic_id: str, label: str) -> None:
    """Log high-level distribution of ABOUT links for a topic.

    Shows, for each timeframe:
    - Counts per overall tier (1/2/3)
    - Counts per perspective (risk/opportunity/trend/catalyst) and tier
    """
    logger.info("-" * 80)
    logger.info(f"[{label}] DISTRIBUTION | topic_id={topic_id}")

    # Overall per timeframe/tier (using max importance across perspectives)
    tier_query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WITH r,
         coalesce(r.importance_risk, 0) AS ir,
         coalesce(r.importance_opportunity, 0) AS io,
         coalesce(r.importance_trend, 0) AS it,
         coalesce(r.importance_catalyst, 0) AS ic
    WITH r.timeframe AS timeframe,
         CASE
             WHEN ir = 0 AND io = 0 AND it = 0 AND ic = 0 THEN 0
             WHEN ir >= io AND ir >= it AND ir >= ic THEN ir
             WHEN io >= ir AND io >= it AND io >= ic THEN io
             WHEN it >= ir AND it >= io AND it >= ic THEN it
             ELSE ic
         END AS tier
    WHERE tier > 0
    RETURN timeframe, tier, count(*) AS count
    ORDER BY timeframe, tier DESC
    """

    tier_rows = run_cypher(tier_query, {"topic_id": topic_id}) or []
    by_tf: dict[str, dict[int, int]] = {}
    for row in tier_rows:
        tf = row["timeframe"]
        tr = row["tier"]
        ct = row["count"]
        by_tf.setdefault(tf, {})[tr] = ct

    for tf in DEFAULT_TIMEFRAMES:
        tiers = by_tf.get(tf, {})
        if not tiers:
            continue
        t3 = int(tiers.get(3, 0))
        t2 = int(tiers.get(2, 0))
        t1 = int(tiers.get(1, 0))
        total = t1 + t2 + t3
        logger.info(
            f"  {tf.upper():<11}: tier3={t3:3d}, tier2={t2:3d}, tier1={t1:3d} | total={total:3d}"
        )

    # Per perspective per timeframe/tier
    persp_query = """
    MATCH (a:Article)-[r:ABOUT]->(t:Topic {id: $topic_id})
    WITH r,
         [
           ['risk',        coalesce(r.importance_risk, 0)],
           ['opportunity', coalesce(r.importance_opportunity, 0)],
           ['trend',       coalesce(r.importance_trend, 0)],
           ['catalyst',    coalesce(r.importance_catalyst, 0)]
         ] AS pairs
    UNWIND pairs AS p
    WITH r.timeframe AS timeframe, p[0] AS perspective, p[1] AS tier
    WHERE tier > 0
    RETURN timeframe, perspective, tier, count(*) AS count
    ORDER BY timeframe, perspective, tier DESC
    """

    persp_rows = run_cypher(persp_query, {"topic_id": topic_id}) or []
    by_tf_p: dict[str, dict[str, dict[int, int]]] = {}
    for row in persp_rows:
        tf = row["timeframe"]
        p = row["perspective"]
        tr = row["tier"]
        ct = row["count"]
        by_tf_p.setdefault(tf, {}).setdefault(p, {})[tr] = ct

    for tf in DEFAULT_TIMEFRAMES:
        perspectives = by_tf_p.get(tf, {})
        if not perspectives:
            continue
        logger.info(f"  {tf.upper():<11} by perspective:")
        for p in ["risk", "opportunity", "trend", "catalyst"]:
            tiers = perspectives.get(p, {})
            if not tiers:
                continue
            t3 = int(tiers.get(3, 0))
            t2 = int(tiers.get(2, 0))
            t1 = int(tiers.get(1, 0))
            total = t1 + t2 + t3
            logger.info(
                f"    {p:<11}: tier3={t3:3d}, tier2={t2:3d}, tier1={t1:3d} | total={total:3d}"
            )


def run_capacity_cleanup_for_topic(
    topic_id: str,
    timeframes: Optional[List[str]] = None,
    tiers: Optional[List[int]] = None,
) -> None:
    """Run capacity auto-cleanup for a single topic across timeframes and tiers."""
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES
    if tiers is None:
        tiers = DEFAULT_TIERS

    logger.info("=" * 80)
    logger.info(f"CAPACITY CLEANUP | topic_id={topic_id}")
    logger.info("=" * 80)

    _log_topic_distribution(topic_id, label="BEFORE")

    for cleanup_pass in range(1, MAX_CLEANUP_PASSES + 1):
        any_over_capacity = False
        logger.info("-" * 80)
        logger.info(
            f"CAPACITY PASS {cleanup_pass} | topic_id={topic_id} "
            f"timeframes={timeframes} tiers={tiers}"
        )

        for timeframe in timeframes:
            for tier in tiers:
                try:
                    result = check_capacity(
                        topic_id=topic_id,
                        timeframe=timeframe,
                        tier=tier,
                    )
                    over = result["count"] > result["max"]
                    if over:
                        any_over_capacity = True
                    logger.info(
                        f"topic={topic_id} | timeframe={timeframe} | tier={tier}: "
                        f"{result['count']}/{result['max']} articles "
                        f"(has_room={result['has_room']}, over_capacity={over})"
                    )
                except Exception as e:
                    logger.warning(
                        f"Capacity check failed for topic={topic_id}, "
                        f"timeframe={timeframe}, tier={tier}: {e}"
                    )

        # Second layer: enforce caps per (timeframe, perspective, tier)
        for timeframe in timeframes:
            for perspective in PERSPECTIVES:
                for tier in tiers:
                    try:
                        result = check_capacity_per_perspective(
                            topic_id=topic_id,
                            timeframe=timeframe,
                            perspective=perspective,
                            tier=tier,
                        )
                        over = result["count"] > result["max"]
                        if over:
                            any_over_capacity = True
                        logger.info(
                            f"topic={topic_id} | timeframe={timeframe} | perspective={perspective} | tier={tier}: "
                            f"{result['count']}/{result['max']} articles (over_capacity={over})"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Perspective capacity check failed for topic={topic_id}, "
                            f"timeframe={timeframe}, perspective={perspective}, tier={tier}: {e}"
                        )

        if not any_over_capacity:
            logger.info(
                f"All buckets within limits after pass {cleanup_pass} for topic_id={topic_id}"
            )
            break

    _log_topic_distribution(topic_id, label="AFTER")


def run_capacity_cleanup_for_all_topics(
    timeframes: Optional[List[str]] = None,
    tiers: Optional[List[int]] = None,
) -> None:
    """Run capacity auto-cleanup for all topics in the graph."""
    topics = get_all_topics()

    logger.info("=" * 80)
    logger.info(f"BULK CAPACITY CLEANUP | topics={len(topics)}")
    logger.info("=" * 80)

    for topic in topics:
        topic_id = topic.get("id") or topic.get("topic_id")
        if not topic_id:
            continue
        run_capacity_cleanup_for_topic(topic_id, timeframes=timeframes, tiers=tiers)


if __name__ == "__main__":
    # Load environment first
    from utils.env_loader import load_env

    load_env()

    import sys

    # Usage:
    #   python -m src.articles.orchestration.capacity_cleanup           # all topics
    #   python -m src.articles.orchestration.capacity_cleanup all       # all topics
    #   python -m src.articles.orchestration.capacity_cleanup EURUSD    # single topic
    if len(sys.argv) >= 2 and sys.argv[1] not in ("all", "ALL"):
        topic_id_arg = sys.argv[1]
        logger.info(f"Running capacity cleanup for single topic: {topic_id_arg}")
        run_capacity_cleanup_for_topic(topic_id_arg)
    else:
        logger.info("Running capacity cleanup for ALL topics")
        run_capacity_cleanup_for_all_topics()
