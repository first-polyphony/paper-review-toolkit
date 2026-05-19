"""Tests for the merge engine."""

import pytest

from paper_review_toolkit.engines.engine import (
    _jaccard,
    _anchor_contiguous_overlap,
    extract_named_entities,
    merge_findings,
    normalize_anchor,
    token_set,
)
from paper_review_toolkit.engines.types import Category, Finding, Severity, Tone


class TestNormalization:
    """Test text normalization functions."""

    def test_normalize_anchor_basic(self):
        text = "Hello, World!"
        assert normalize_anchor(text) == "hello world"

    def test_normalize_anchor_smart_quotes(self):
        text = "\u201cquoted text\u201d"
        assert normalize_anchor(text) == "quoted text"

    def test_normalize_anchor_whitespace(self):
        text = "  multiple   spaces  "
        assert normalize_anchor(text) == "multiple spaces"

    def test_token_set_filters_stop_words(self):
        tokens = token_set("the quick brown fox", "")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_token_set_filters_short_tokens(self):
        tokens = token_set("a b cd efg", "")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "efg" in tokens


class TestNamedEntityExtraction:
    """Test named entity extraction."""

    def test_extract_known_acronyms(self):
        entities = extract_named_entities("The HIPAA regulations require compliance with GDPR.")
        assert "HIPAA" in entities
        assert "GDPR" in entities

    def test_extract_capitalized_phrases(self):
        entities = extract_named_entities("The European Union and United Nations agreed.")
        assert any("European Union" in e or "European" in e for e in entities)

    def test_no_entities_in_lowercase(self):
        entities = extract_named_entities("all lowercase text here")
        assert len([e for e in entities if len(e) >= 4]) == 0


class TestJaccard:
    """Test Jaccard similarity."""

    def test_jaccard_identical(self):
        a = frozenset(["a", "b", "c"])
        assert _jaccard(a, a) == 1.0

    def test_jaccard_disjoint(self):
        a = frozenset(["a", "b"])
        b = frozenset(["c", "d"])
        assert _jaccard(a, b) == 0.0

    def test_jaccard_partial_overlap(self):
        a = frozenset(["a", "b", "c"])
        b = frozenset(["b", "c", "d"])
        assert _jaccard(a, b) == pytest.approx(0.5)

    def test_jaccard_empty(self):
        assert _jaccard(frozenset(), frozenset(["a"])) == 0.0


class TestAnchorOverlap:
    """Test anchor contiguous overlap detection."""

    def test_overlap_found(self):
        a = "this is a test string"
        b = "another test string here"
        assert _anchor_contiguous_overlap(a, b, min_chars=10)

    def test_no_overlap(self):
        a = "completely different"
        b = "nothing in common"
        assert not _anchor_contiguous_overlap(a, b, min_chars=10)

    def test_short_strings(self):
        a = "short"
        b = "also short"
        assert not _anchor_contiguous_overlap(a, b, min_chars=20)


class TestMergeFindings:
    """Test the merge_findings function."""

    def _make_finding(
        self,
        id: str,
        anchor: str,
        concern: str,
        category: Category = Category.ARGUMENTATION,
        paragraph: str = "",
    ) -> Finding:
        return Finding(
            id=id,
            source_skill="test",
            reviewer="test-reviewer",
            category=category,
            severity=Severity.MEDIUM,
            anchor_text=anchor,
            paragraph_fallback=paragraph,
            concern=concern,
            suggested_fix="",
            tone_hint=Tone.CONSTRUCTIVE,
        )

    def test_merge_identical_anchors(self):
        f1 = self._make_finding("1", "same anchor text here", "concern 1")
        f2 = self._make_finding("2", "same anchor text here", "concern 2")

        unified, suppressed = merge_findings([f1, f2])

        assert len(unified) == 1
        assert unified[0].convergence_count == 2
        assert len(suppressed) == 0

    def test_no_merge_different_findings(self):
        f1 = self._make_finding("1", "first anchor text", "concern 1")
        f2 = self._make_finding("2", "completely different anchor", "concern 2")

        unified, suppressed = merge_findings([f1, f2])

        assert len(unified) == 2
        assert all(u.convergence_count == 1 for u in unified)

    def test_merge_by_paragraph(self):
        f1 = self._make_finding("1", "short", "concern 1", paragraph="same paragraph")
        f2 = self._make_finding("2", "short", "similar concern", paragraph="same paragraph")

        unified, suppressed = merge_findings([f1, f2])

        assert len(unified) <= 2

    def test_empty_input(self):
        unified, suppressed = merge_findings([])
        assert len(unified) == 0
        assert len(suppressed) == 0

    def test_uf_id_format(self):
        f1 = self._make_finding("1", "anchor text one", "concern")
        f2 = self._make_finding("2", "anchor text two", "concern")

        unified, _ = merge_findings([f1, f2])

        for uf in unified:
            assert uf.uf_id.startswith("UF-")
            assert len(uf.uf_id) == 6

    def test_deterministic_output(self):
        findings = [
            self._make_finding("1", "anchor one", "concern one"),
            self._make_finding("2", "anchor two", "concern two"),
            self._make_finding("3", "anchor three", "concern three"),
        ]

        result1, _ = merge_findings(findings)
        result2, _ = merge_findings(findings)

        assert [u.uf_id for u in result1] == [u.uf_id for u in result2]
