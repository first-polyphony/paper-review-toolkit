"""Pydantic schemas for paper-review orchestration."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """Finding severity ordinal."""

    MAJOR = "major"
    MEDIUM = "medium"
    MINOR = "minor"
    LOW = "low"

    def rank(self) -> int:
        """Return an ordinal rank (higher = more severe)."""
        return {"major": 3, "medium": 2, "minor": 1, "low": 0}[self.value]


class Category(str, Enum):
    """Finding category — used for --focus filtering and rubric register."""

    ARGUMENTATION = "argumentation"
    EVIDENCE = "evidence"
    STRUCTURE = "structure"
    GRAMMAR = "grammar"
    CITATION = "citation"
    PRECISION = "precision"
    AUDIENCE = "audience"
    REDTEAM = "redteam"


class ReferenceRole(str, Enum):
    """Document role tags controlling whether a reference can drive findings."""

    CHARTER = "charter"
    RUBRIC = "rubric"
    SERIES_TEMPLATE = "series-template"
    CONTEXT_ONLY = "context-only"


class Tone(str, Enum):
    """Comment tone hint from the originating skill."""

    CONSTRUCTIVE = "constructive"
    DIRECT = "direct"
    SENSITIVE = "sensitive"


class AudienceTrust(str, Enum):
    """Audience trust tier selected by the caller of /paper-review.

    Controls rubric strictness:
      LOW    — student / mentee / early-draft. R3 (non-imperative opening)
               enforced strictly; suggestion frames required.
      MEDIUM — peer / co-author / professional / high-trust expert review.
               R3 waived (imperatives allowed). Default tier when the flag
               is omitted on /paper-review.
    """

    LOW = "low"
    MEDIUM = "medium"


class Finding(BaseModel):
    """Single finding from paper-gaps or policy-review-sim."""

    id: str = Field(min_length=1)
    source_skill: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    category: Category
    severity: Severity
    anchor_text: str = Field(min_length=1)
    paragraph_fallback: str = ""
    concern: str = Field(min_length=1)
    suggested_fix: str = ""
    tone_hint: Tone = Tone.CONSTRUCTIVE
    authority_ref: str = ""

    @field_validator("anchor_text")
    @classmethod
    def anchor_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("anchor_text must be non-empty after strip")
        return v


class UnifiedFinding(BaseModel):
    """Merged cluster of one or more Findings."""

    uf_id: str = Field(pattern=r"^UF-\d{3}$")
    sources: list[str]
    convergence_count: int = Field(ge=1)
    categories: list[Category]
    severity: Severity
    anchor_text: str
    paragraph_fallback: str = ""
    concern: str
    distinct_angles: list[str] = Field(default_factory=list)
    suggested_fix: str = ""
    member_ids: list[str]


class CalibrationLog(BaseModel):
    """Record of a comment rewrite."""

    uf_id: str
    original: str
    rewrite: str
    reasons: list[str]
    severe_rewrite: bool = False


class RubricResult(BaseModel):
    """Outcome of a rubric check."""

    r1_observation_present: bool
    r2_why_clause_present: bool
    r3_non_imperative_opening: bool
    r4_trusts_author: bool
    failures: list[str]

    @property
    def passes(self) -> bool:
        """True if all four axes pass."""
        return len(self.failures) == 0
