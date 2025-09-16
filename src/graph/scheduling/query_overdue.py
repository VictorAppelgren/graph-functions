from src.graph.policies.priority import get_interval_for_importance
from datetime import datetime
from utils import app_logging
logger = app_logging.get_logger(__name__)

def query_overdue_seconds(node: dict[str, str]) -> int:
    # Use current local time; tests can monkeypatch this function if needed
    now = datetime.now().astimezone()
    importance = node.get('importance', "5")
    interval = get_interval_for_importance(int(importance))
    last_queried = node.get('last_queried')
    logger.debug(f"Query overdue seconds:")
    logger.debug(f"importance={importance}")
    logger.debug(f"interval={interval}")
    logger.debug(f"last_queried={last_queried} (type: {type(last_queried)})")
    
    if not last_queried:
        return int(1_000_000_000)  # maximally overdue
    if isinstance(last_queried, str):
        last_dt = datetime.fromisoformat(last_queried)
        elapsed = int((now - last_dt).total_seconds())
        return elapsed - interval
