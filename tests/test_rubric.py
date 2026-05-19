"""Tests for the constructive comment rubric."""

import pytest

from paper_review_toolkit.engines.rubric import (
    check_rubric,
    rewrite_needed,
    severe_rewrite,
)
from paper_review_toolkit.engines.types import AudienceTrust, Category, Tone


class TestR1Observation:
    """Test R1: observation named."""

    def test_quoted_phrase_passes(self):
        result = check_rubric(
            '"The evidence suggests" is vague  --  readers need specifics.',
            Category.ARGUMENTATION,
        )
        assert result.r1_observation_present

    def test_capitalized_phrase_passes(self):
        result = check_rubric(
            "The HIPAA regulations require more context here.",
            Category.EVIDENCE,
        )
        assert result.r1_observation_present

    def test_bare_assertion_fails(self):
        result = check_rubric(
            "this argument is thin",
            Category.ARGUMENTATION,
        )
        assert not result.r1_observation_present
        assert "R1_observation" in result.failures


class TestR2WhyClause:
    """Test R2: why-clause present."""

    def test_stake_keyword_passes(self):
        result = check_rubric(
            "The claim about HIPAA needs more evidence because readers will question it.",
            Category.EVIDENCE,
        )
        assert result.r2_why_clause_present

    def test_no_stake_fails(self):
        result = check_rubric(
            "The HIPAA section needs work.",
            Category.EVIDENCE,
        )
        assert not result.r2_why_clause_present
        assert "R2_why_clause" in result.failures

    def test_medium_trust_short_waiver(self):
        result = check_rubric(
            "HIPAA cites.",
            Category.CITATION,
            audience_trust=AudienceTrust.MEDIUM,
        )
        assert result.r2_why_clause_present

    def test_low_trust_no_waiver(self):
        result = check_rubric(
            "HIPAA needs work.",
            Category.CITATION,
            audience_trust=AudienceTrust.LOW,
        )
        assert not result.r2_why_clause_present


class TestR3ImperativeOpening:
    """Test R3: non-imperative opening."""

    def test_imperative_fails_low_trust(self):
        result = check_rubric(
            "Add more evidence to support the HIPAA claim.",
            Category.EVIDENCE,
            audience_trust=AudienceTrust.LOW,
        )
        assert not result.r3_non_imperative_opening
        assert "R3_imperative_opening" in result.failures

    def test_imperative_passes_medium_trust(self):
        result = check_rubric(
            "Add more evidence to support the HIPAA claim.",
            Category.EVIDENCE,
            audience_trust=AudienceTrust.MEDIUM,
        )
        assert result.r3_non_imperative_opening

    def test_imperative_passes_direct_tone(self):
        result = check_rubric(
            "Fix the HIPAA section.",
            Category.EVIDENCE,
            tone_hint=Tone.DIRECT,
            audience_trust=AudienceTrust.LOW,
        )
        assert result.r3_non_imperative_opening

    def test_suggestion_frame_passes(self):
        result = check_rubric(
            "Consider adding more evidence to the HIPAA claim because readers expect it.",
            Category.EVIDENCE,
            audience_trust=AudienceTrust.LOW,
        )
        assert result.r3_non_imperative_opening


class TestR4TrustsAuthor:
    """Test R4: trusts author."""

    def test_forced_binary_fails(self):
        result = check_rubric(
            "The HIPAA section: either add citations or remove it entirely.",
            Category.CITATION,
        )
        assert not result.r4_trusts_author
        assert "R4_forced_binary" in result.failures

    def test_third_option_passes(self):
        result = check_rubric(
            "The HIPAA section: either add citations, or perhaps a brief mention.",
            Category.CITATION,
        )
        assert result.r4_trusts_author

    def test_bare_imperative_passes(self):
        result = check_rubric(
            "Tighten the HIPAA section because readers expect precision.",
            Category.PRECISION,
        )
        assert result.r4_trusts_author


class TestRubricHelpers:
    """Test helper functions."""

    def test_rewrite_needed_on_failure(self):
        result = check_rubric(
            "thin argument",
            Category.ARGUMENTATION,
        )
        assert rewrite_needed(result)

    def test_no_rewrite_needed_on_pass(self):
        result = check_rubric(
            '"The evidence suggests" is vague because readers need specifics.',
            Category.ARGUMENTATION,
        )
        assert not rewrite_needed(result)

    def test_severe_rewrite_threshold(self):
        result = check_rubric(
            "fix it",
            Category.GRAMMAR,
            audience_trust=AudienceTrust.LOW,
        )
        assert len(result.failures) >= 2 or severe_rewrite(result) == (len(result.failures) >= 3)


class TestCategorySpecificBehavior:
    """Test category-specific rubric behavior."""

    def test_grammar_r1_relaxed_with_r2(self):
        result = check_rubric(
            "Missing verb because this is the key sentence readers will cite.",
            Category.GRAMMAR,
        )
        assert result.r1_observation_present

    def test_grammar_r1_not_relaxed_without_r2(self):
        result = check_rubric(
            "missing verb here",
            Category.GRAMMAR,
        )
        assert not result.r1_observation_present


class TestFullComments:
    """Test realistic comment examples."""

    def test_good_low_trust_comment(self):
        comment = (
            "Good challenge and well-motivated. The claim about 'HIPAA coverage gaps' "
            "could be useful to sharpen because readers will expect specifics."
        )
        result = check_rubric(comment, Category.EVIDENCE, audience_trust=AudienceTrust.LOW)
        assert result.passes

    def test_good_medium_trust_comment(self):
        comment = "HIPAA cite needed. Readers will push back without it."
        result = check_rubric(comment, Category.CITATION, audience_trust=AudienceTrust.MEDIUM)
        assert result.passes
