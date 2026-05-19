"""Tests for type definitions."""

import pytest
from pydantic import ValidationError

from paper_review_toolkit.engines.types import (
    AudienceTrust,
    Category,
    Finding,
    RubricResult,
    Severity,
    Tone,
    UnifiedFinding,
)


class TestSeverity:
    """Test Severity enum."""

    def test_severity_values(self):
        assert Severity.MAJOR.value == "major"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.MINOR.value == "minor"
        assert Severity.LOW.value == "low"

    def test_severity_ranking(self):
        assert Severity.MAJOR.rank() > Severity.MEDIUM.rank()
        assert Severity.MEDIUM.rank() > Severity.MINOR.rank()
        assert Severity.MINOR.rank() > Severity.LOW.rank()


class TestCategory:
    """Test Category enum."""

    def test_all_categories_exist(self):
        expected = [
            "argumentation", "evidence", "structure", "grammar",
            "citation", "precision", "audience", "redteam"
        ]
        actual = [c.value for c in Category]
        assert sorted(actual) == sorted(expected)


class TestFinding:
    """Test Finding model."""

    def test_valid_finding(self):
        f = Finding(
            id="F001",
            source_skill="paper-gaps",
            reviewer="engine",
            category=Category.ARGUMENTATION,
            severity=Severity.MAJOR,
            anchor_text="some anchor text",
            concern="description of concern",
        )
        assert f.id == "F001"
        assert f.tone_hint == Tone.CONSTRUCTIVE

    def test_finding_requires_anchor(self):
        with pytest.raises(ValidationError):
            Finding(
                id="F001",
                source_skill="paper-gaps",
                reviewer="engine",
                category=Category.ARGUMENTATION,
                severity=Severity.MAJOR,
                anchor_text="",
                concern="description",
            )

    def test_finding_anchor_whitespace_only_fails(self):
        with pytest.raises(ValidationError):
            Finding(
                id="F001",
                source_skill="paper-gaps",
                reviewer="engine",
                category=Category.ARGUMENTATION,
                severity=Severity.MAJOR,
                anchor_text="   ",
                concern="description",
            )


class TestUnifiedFinding:
    """Test UnifiedFinding model."""

    def test_valid_unified_finding(self):
        uf = UnifiedFinding(
            uf_id="UF-001",
            sources=["paper-gaps:engine:F001"],
            convergence_count=1,
            categories=[Category.ARGUMENTATION],
            severity=Severity.MAJOR,
            anchor_text="anchor",
            concern="concern text",
            member_ids=["F001"],
        )
        assert uf.uf_id == "UF-001"

    def test_uf_id_pattern(self):
        with pytest.raises(ValidationError):
            UnifiedFinding(
                uf_id="INVALID",
                sources=[],
                convergence_count=1,
                categories=[],
                severity=Severity.LOW,
                anchor_text="a",
                concern="c",
                member_ids=[],
            )

    def test_convergence_minimum(self):
        with pytest.raises(ValidationError):
            UnifiedFinding(
                uf_id="UF-001",
                sources=[],
                convergence_count=0,
                categories=[],
                severity=Severity.LOW,
                anchor_text="a",
                concern="c",
                member_ids=[],
            )


class TestRubricResult:
    """Test RubricResult model."""

    def test_passes_all_true(self):
        result = RubricResult(
            r1_observation_present=True,
            r2_why_clause_present=True,
            r3_non_imperative_opening=True,
            r4_trusts_author=True,
            failures=[],
        )
        assert result.passes

    def test_fails_with_failures(self):
        result = RubricResult(
            r1_observation_present=False,
            r2_why_clause_present=True,
            r3_non_imperative_opening=True,
            r4_trusts_author=True,
            failures=["R1_observation"],
        )
        assert not result.passes


class TestAudienceTrust:
    """Test AudienceTrust enum."""

    def test_trust_levels(self):
        assert AudienceTrust.LOW.value == "low"
        assert AudienceTrust.MEDIUM.value == "medium"
