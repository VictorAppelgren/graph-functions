from src.graph.policies.priority import get_interval_for_importance
from datetime import datetime
from utils import app_logging
from neo4j.time import DateTime as Neo4jDateTime

logger = app_logging.get_logger(__name__)


def query_overdue_seconds(topic: dict[str, str]) -> int:
    """Return seconds overdue (positive), due in (negative), or zero. Never None.

    Policy:
    - If last_queried missing/empty -> treat as very overdue (run now).
    - Else expect Neo4j DateTime, convert to native datetime and compute.
    - For any unexpected type, fail-open to very overdue to avoid crashes.
    """
    # Use current local time; tests can monkeypatch this function if needed
    now = datetime.now().astimezone()
    importance = topic.get("importance", "5")
    interval = get_interval_for_importance(int(importance))
    last_queried = topic.get("last_queried")
    logger.debug("[query_overdue_seconds] Start")
    logger.debug(f"[query_overdue_seconds] topic.id={topic.get('id')}")
    logger.debug(f"[query_overdue_seconds] importance={importance}")
    logger.debug(f"[query_overdue_seconds] interval(s)={interval}")
    logger.debug(
        f"[query_overdue_seconds] last_queried={last_queried!r} | type={type(last_queried)}"
    )

    if not last_queried:
        logger.debug("[query_overdue_seconds] last_queried missing/empty -> VERY_OVERDUE")
        return int(1_000_000_000)

    if isinstance(last_queried, Neo4jDateTime):
        try:
            last_dt = last_queried.to_native()  # tz-aware datetime
        except Exception as e:
            logger.warning(
                f"[query_overdue_seconds] to_native() failed: {e}; treating as VERY_OVERDUE"
            )
            return int(1_000_000_000)
        elapsed = int((now - last_dt).total_seconds())
        overdue = elapsed - interval
        logger.debug(
            f"[query_overdue_seconds] neo4j_dt={last_dt.isoformat()} | elapsed={elapsed}s | overdue={overdue}s"
        )
        return overdue

    # Any other unexpected type -> fail-open to very overdue
    logger.warning(
        "[query_overdue_seconds] Unexpected last_queried type; treating as VERY_OVERDUE | "
        f"topic.id={topic.get('id')} type={type(last_queried)} value={last_queried!r}"
    )
    return int(1_000_000_000)
