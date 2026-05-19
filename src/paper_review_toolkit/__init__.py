"""Paper Review Toolkit — Multi-persona academic paper review with argumentation analysis."""

__version__ = "1.0.0"

from paper_review_toolkit.engines.engine import merge_findings
from paper_review_toolkit.engines.rubric import check_rubric
from paper_review_toolkit.engines.types import (
    AudienceTrust,
    Category,
    Finding,
    RubricResult,
    Severity,
    UnifiedFinding,
)

__all__ = [
    "merge_findings",
    "check_rubric",
    "Finding",
    "UnifiedFinding",
    "Category",
    "Severity",
    "AudienceTrust",
    "RubricResult",
]
