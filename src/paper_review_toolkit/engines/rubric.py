"""Mechanical four-axis constructive comment rubric.

This module provides PURE Python checks (no LLM) so the rubric can be
regression-tested deterministically.

Rubric axes:
  R1 — observation named (quoted anchor OR capitalized noun phrase present)
  R2 — why-clause present (stake keyword within window of observation)
  R3 — non-imperative opening (first token not in directive-verb list,
       unless tone_hint=direct)
  R4 — trusts author (no forced either/or without third option)
"""

from __future__ import annotations

import re

from paper_review_toolkit.engines.types import (
    AudienceTrust,
    Category,
    RubricResult,
    Tone,
)

_IMPERATIVE_VERBS: frozenset[str] = frozenset(
    {
        "add", "pull", "cut", "tighten", "move", "drop", "fix", "restructure",
        "swap", "tie", "make", "remove", "delete", "insert", "change",
        "rewrite", "revise", "reword", "replace", "reorder", "rework",
        "include", "exclude", "expand", "shorten", "elaborate", "clarify",
        "explain", "justify", "source", "cite", "soften", "verify", "retitle",
        "convert", "restate", "separate", "distinguish", "resolve",
    }
)

_SUGGESTION_FRAMES: frozenset[str] = frozenset(
    {"consider", "perhaps", "maybe", "worth", "might", "one"}
)

_STAKE_KEYWORDS: frozenset[str] = frozenset(
    {
        "because", "since", "so", "reception", "precision", "warrant",
        "readers", "reader", "audience", "compliance", "stake", "signal",
        "distinction", "framing", "risk", "cite", "cited", "citable",
        "misread", "misreads", "credibility", "authority", "push back",
        "pushback", "skimmer", "opponent", "hostile", "reviewer",
        "exposure", "expected", "cost", "clean pass", "worth",
    }
)

_TOKEN_RE = re.compile(r"^[\"'`\(]*([A-Za-z][A-Za-z\-]*)")
_CAP_PHRASE_RE = re.compile(r"[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*")
_QUOTED_RE = re.compile(r"[\"“‘][^\"”’]{3,}[\"”’]"
                        r"|'[^']{3,}'")
_FORCED_BINARY_RE = re.compile(
    r"\beither\b[^.]{3,}\bor\b", re.IGNORECASE
)


def _first_token(text: str) -> str | None:
    """Return first alphabetic token, lowercased."""
    stripped = text.strip()
    if not stripped:
        return None
    m = _TOKEN_RE.match(stripped)
    return m.group(1).lower() if m else None


def _has_observation(text: str) -> bool:
    """R1: observation named.

    Pass if the comment contains a quoted phrase (anchor) or a capitalized
    noun phrase of at least one token.
    """
    if _QUOTED_RE.search(text):
        return True
    return bool(_CAP_PHRASE_RE.search(text))


def _has_why_clause(text: str) -> bool:
    """R2: at least one stake keyword present in the comment."""
    lower = text.lower()
    return any(kw in lower for kw in _STAKE_KEYWORDS)


def _is_imperative_start(
    text: str,
    tone_hint: Tone,
    audience_trust: AudienceTrust | None = None,
) -> bool:
    """R3 fail condition: first token is a directive verb, no exemption.

    Waiver matrix:
      - tone_hint == DIRECT            -> R3 waived
      - audience_trust == MEDIUM       -> R3 waived
      - audience_trust == LOW / None   -> R3 enforced
    """
    if tone_hint == Tone.DIRECT:
        return False
    if audience_trust == AudienceTrust.MEDIUM:
        return False
    first = _first_token(text)
    if first is None:
        return False
    if first in _SUGGESTION_FRAMES:
        return False
    return first in _IMPERATIVE_VERBS


def _violates_trust(text: str) -> bool:
    """R4 fail: forced either/or with no third-option hedge."""
    if not _FORCED_BINARY_RE.search(text):
        return False
    lower = text.lower()
    hedge_markers = (
        "a third", "or a brief", "or perhaps", ", or",
        " or both", "one option",
    )
    return not any(h in lower for h in hedge_markers)


def check_rubric(
    text: str,
    category: Category,
    tone_hint: Tone = Tone.CONSTRUCTIVE,
    audience_trust: AudienceTrust | None = None,
) -> RubricResult:
    """Run the 4-axis rubric on a comment. Pure function, no side effects.

    audience_trust controls R3 enforcement:
      - None or AudienceTrust.LOW -> R3 enforced
      - AudienceTrust.MEDIUM -> R3 waived

    Medium tier also relaxes R2 for comments shorter than six words.
    """
    failures: list[str] = []

    r1 = _has_observation(text)
    if not r1:
        failures.append("R1_observation")

    r2 = _has_why_clause(text)
    if not r2:
        word_count = len(text.split())
        medium_short_waiver = (
            audience_trust == AudienceTrust.MEDIUM and word_count <= 5
        )
        if not medium_short_waiver:
            failures.append("R2_why_clause")
        else:
            r2 = True

    r3_fail = _is_imperative_start(text, tone_hint, audience_trust)
    if r3_fail:
        failures.append("R3_imperative_opening")

    r4_fail = _violates_trust(text)
    if r4_fail:
        failures.append("R4_forced_binary")

    if (
        category == Category.GRAMMAR
        and not r1
        and r2
        and "R1_observation" in failures
    ):
        failures.remove("R1_observation")
        r1 = True

    return RubricResult(
        r1_observation_present=r1,
        r2_why_clause_present=r2,
        r3_non_imperative_opening=not r3_fail,
        r4_trusts_author=not r4_fail,
        failures=failures,
    )


def rewrite_needed(result: RubricResult) -> bool:
    """True if rubric check failed on at least one axis."""
    return not result.passes


def severe_rewrite(result: RubricResult) -> bool:
    """True if >= 3 axes failed."""
    return len(result.failures) >= 3
