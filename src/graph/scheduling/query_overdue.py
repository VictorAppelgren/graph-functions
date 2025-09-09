from src.graph.policies.priority_policy import get_interval_for_importance
from datetime import datetime
from utils import app_logging
logger = app_logging.get_logger(__name__)

def query_overdue_seconds(node):
    # Use current local time; tests can monkeypatch this function if needed
    now = datetime.now().astimezone()
    importance = node.get('importance', 5)
    interval = get_interval_for_importance(importance)
    last_queried = node.get('last_queried')
    logger.debug(f"Query overdue seconds:")
    logger.debug(f"importance={importance}")
    logger.debug(f"interval={interval}")
    logger.debug(f"last_queried={last_queried} (type: {type(last_queried)})")
    
    if not last_queried:
        return float('inf')  # maximally overdue
    if isinstance(last_queried, str):
        last_dt = datetime.fromisoformat(last_queried)
    elif hasattr(last_queried, 'to_native'):
        # Accept neo4j.time.DateTime or similar
        last_dt = last_queried.to_native()
    else:
        raise ValueError(f"last_queried must be a string in ISO format or neo4j.time.DateTime, got {type(last_queried)}: {last_queried}")
    elapsed = (now - last_dt).total_seconds()
    return elapsed - interval
