"""
Worker Mode Configuration

Controls what this worker instance does:
- "ingest": Only fetch/ingest articles, NO writing (Servers 1 & 2)
- "write": Only write analyses and strategies (Server 3)  
- "" or unset: Do everything (local dev)

Set via environment variable: WORKER_MODE=ingest|write
"""

import os

# Get mode from environment (default: empty = do everything)
WORKER_MODE = os.environ.get("WORKER_MODE", "").lower().strip()

# Validate
if WORKER_MODE and WORKER_MODE not in ("ingest", "write"):
    raise ValueError(f"Invalid WORKER_MODE='{WORKER_MODE}'. Must be 'ingest', 'write', or unset.")


def can_write() -> bool:
    """Returns True if this worker is allowed to write analyses/strategies."""
    return WORKER_MODE != "ingest"


def can_ingest() -> bool:
    """Returns True if this worker is allowed to ingest articles."""
    return WORKER_MODE != "write"


def is_write_only() -> bool:
    """Returns True if this worker ONLY writes (no ingestion)."""
    return WORKER_MODE == "write"


def is_ingest_only() -> bool:
    """Returns True if this worker ONLY ingests (no writing)."""
    return WORKER_MODE == "ingest"


def get_mode_description() -> str:
    """Human-readable description of current mode."""
    if WORKER_MODE == "ingest":
        return "INGEST ONLY (no writing)"
    elif WORKER_MODE == "write":
        return "WRITE ONLY (no ingestion)"
    else:
        return "FULL (ingest + write)"
