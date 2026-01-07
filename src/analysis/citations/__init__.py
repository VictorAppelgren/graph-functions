"""
Citation validation utilities.

DEPRECATED: Use src.citations instead. This re-exports for backward compatibility.
"""

# Re-export from new canonical location
from src.citations import (
    CitationReport,
    validate_citations,
)

__all__ = ["CitationReport", "validate_citations"]
