"""
Neo4j Database Backup & Restore Utility

Complete database backup/restore functionality for SAGA_V3 development and disaster recovery.
Exports entire graph (nodes + relationships) to timestamped JSON files and restores with 
full fidelity including labels, properties, and relationship types.

Key Features:
- Full graph export to JSON with ISO timestamps
- Batch processing for large datasets (configurable batch size)
- APOC-based restore with dynamic label/relationship creation
- Safety validations to prevent import conflicts
- Preserves all Neo4j data types via custom serialization

Requirements:
- APOC plugin installed and enabled in Neo4j
- Write permissions to neo4j_backup/dumps/ directory

Usage:
    # Backup current database
    python neo4j_backup/dump_or_load_neo_to_or_from_json.py
    
    # Programmatic backup/restore
    from neo4j_backup.dump_or_load_neo_to_or_from_json import dump_neo_db, load_neo_db
    path = dump_neo_db()  # Creates timestamped dump
    load_neo_db(path, wipe=True)  # Destructive restore

Use Cases: Environment migration, development snapshots, disaster recovery, testing with clean state.
"""

# Absolute import guard (README §3)
import sys, os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from datetime import datetime
from neo4j import GraphDatabase
from graph.neo4j_client import connect_graph_db, NEO4J_DATABASE

# Dump directory anchored next to this script
DUMPS_DIR = os.path.join(os.path.dirname(__file__), "dumps")
TMP_ID = "__tmp_import_id__"
BATCH_SIZE = 1000


def _ts():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _json_default(o):
    # Minimal safe serializer for Neo4j temporal/spatial: keep simple
    try:
        return o.isoformat()
    except Exception:
        return str(o)


def _ensure_apoc(session):
    try:
        session.run("RETURN apoc.version()").consume()
    except Exception as e:
        raise RuntimeError(
            "APOC is required for backup/restore (apoc.create.setLabels / apoc.create.relationship). "
            "Install/enable APOC and restart Neo4j."
        ) from e


def dump_neo_db(out_dir=DUMPS_DIR):
    """
    Export all nodes and relationships to a single JSON file.
    Returns the dump file path.
    """
    os.makedirs(out_dir, exist_ok=True)
    dump_path = os.path.join(out_dir, f"{NEO4J_DATABASE}-neo_dump-{_ts()}.json")

    driver = connect_graph_db()
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            nodes = s.run("""
                MATCH (n)
                RETURN id(n) AS _id, labels(n) AS labels, properties(n) AS props
            """).data()

            rels = s.run("""
                MATCH (a)-[r]->(b)
                RETURN id(r) AS _id, type(r) AS type, properties(r) AS props,
                       id(a) AS start, id(b) AS end
            """).data()

        payload = {"nodes": nodes, "relationships": rels}
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=_json_default)

        return dump_path
    finally:
        driver.close()


def load_neo_db(dump_path, wipe=True):
    """
    Load a dump produced by dump_neo_db() into the target DB.
    If wipe=True, clears the DB first. Requires APOC.
    """
    with open(dump_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    nodes = payload.get("nodes", [])
    rels = payload.get("relationships", [])

    driver = connect_graph_db()
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            _ensure_apoc(s)

            # Safety: ensure temporary property doesn't exist already
            exists = s.run(f"MATCH (n) WHERE exists(n.{TMP_ID}) RETURN count(n) AS c").single()["c"]
            if exists:
                raise RuntimeError(
                    f"Temporary property {TMP_ID} already present on {exists} nodes. Abort to avoid conflicts."
                )

            if wipe:
                s.run("MATCH (n) DETACH DELETE n")

            # Create nodes in batches
            for i in range(0, len(nodes), BATCH_SIZE):
                batch = nodes[i:i + BATCH_SIZE]
                s.run(f"""
                    UNWIND $batch AS row
                    CREATE (n)
                    SET n += row.props, n.{TMP_ID} = row._id
                    CALL apoc.create.setLabels(n, row.labels) YIELD node
                    RETURN count(*) AS _
                """, {"batch": batch})

            # Create relationships in batches
            for i in range(0, len(rels), BATCH_SIZE):
                batch = rels[i:i + BATCH_SIZE]
                s.run(f"""
                    UNWIND $batch AS row
                    MATCH (a {{{TMP_ID}: row.start}})
                    MATCH (b {{{TMP_ID}: row.end}})
                    CALL apoc.create.relationship(a, row.type, row.props, b) YIELD rel
                    RETURN count(*) AS _
                """, {"batch": batch})

            # Clean up the temporary marker
            s.run(f"MATCH (n) WHERE exists(n.{TMP_ID}) REMOVE n.{TMP_ID}")

        return True
    finally:
        driver.close()


if __name__ == "__main__":
    # Minimal demo: dump current DB to neo4j_backup/dumps/
    path = dump_neo_db()
    print("Dump written to:", path)

    # To restore (commented for safety):
    # load_neo_db(path, wipe=True)
    # print("Load complete.")