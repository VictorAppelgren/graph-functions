from datetime import datetime
from utils import app_logging
from neo4j.time import DateTime as Neo4jDateTime

logger = app_logging.get_logger(__name__)


def query_overdue_seconds(topic: dict[str, str]) -> int:
    """Return seconds since last_queried. Higher = more overdue. Never None.

    Simple policy: Topics that haven't been queried longest get priority.
    No importance-based intervals - just sort by staleness.

    - If last_queried missing/empty -> treat as very overdue (run now).
    - Else return seconds elapsed since last query.
    - For any unexpected type, fail-open to very overdue to avoid crashes.
    """
    now = datetime.now().astimezone()
    last_queried = topic.get("last_queried")

    logger.debug(f"[query_overdue_seconds] topic.id={topic.get('id')}")
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
        logger.debug(
            f"[query_overdue_seconds] neo4j_dt={last_dt.isoformat()} | elapsed={elapsed}s"
        )
        return elapsed

    # Any other unexpected type -> fail-open to very overdue
    logger.warning(
        "[query_overdue_seconds] Unexpected last_queried type; treating as VERY_OVERDUE | "
        f"topic.id={topic.get('id')} type={type(last_queried)} value={last_queried!r}"
    )
    return int(1_000_000_000)
