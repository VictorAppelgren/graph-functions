import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# backfill_scripts/count_topics_by_importance.py
from src.graph.neo4j_client import connect_graph_db


def count_by_importance() -> None:
    driver = connect_graph_db()
    for i in range(1, 6):
        q = f"MATCH (t:Topic) WHERE t.importance = {i} RETURN count(t) AS cnt"
        with driver.session(database="argosgraph") as s:
            res = s.run(q).data()
            cnt = res[0]["cnt"] if res else 0
        print(f"Importance {i}: {cnt} topics")
    # Count topics with unset importance
    q_unset = "MATCH (t:Topic) WHERE t.importance IS NULL RETURN count(t) AS cnt"
    with driver.session(database="argosgraph") as s:
        res = s.run(q_unset).data()
        unset_cnt = res[0]["cnt"] if res else 0
    print(f"Importance not set: {unset_cnt} topics")


if __name__ == "__main__":
    count_by_importance()
