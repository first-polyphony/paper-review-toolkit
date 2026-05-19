"""Paper gap analysis skill implementation.

Analyzes academic papers for missing arguments, weak evidence, and citation gaps
using the Toulmin argumentation model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from paper_review_toolkit.engines.types import Category, Finding, Severity, Tone
from paper_review_toolkit.llm import LLMClient, get_client

logger = logging.getLogger(__name__)


class GapType(str, Enum):
    """Types of gaps that can be identified in academic papers."""

    MISSING_EVIDENCE = "missing_evidence"
    WEAK_WARRANT = "weak_warrant"
    MISSING_CITATION = "missing_citation"
    UNSTATED_ASSUMPTION = "unstated_assumption"
    COUNTERARGUMENT_IGNORED = "counterargument_ignored"
    SCOPE_UNCLEAR = "scope_unclear"


class EvidenceStrength(str, Enum):
    """Evidence strength assessment levels."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    MISSING = "missing"
    CONTESTED = "contested"


@dataclass
class Gap:
    """A single identified gap in the paper."""

    gap_id: str
    gap_type: GapType
    severity: str
    related_claim: str
    anchor_text: str
    paragraph_fallback: str
    suggested_action: str
    citation_needed: bool = False


@dataclass
class GapAnalysisResult:
    """Result of gap analysis on a document."""

    title: str
    gaps: list[Gap] = field(default_factory=list)
    overall_evidence_strength: EvidenceStrength = EvidenceStrength.MODERATE
    executive_summary: list[str] = field(default_factory=list)

    def get_citation_needed_gaps(self) -> list[Gap]:
        """Return gaps that need citations."""
        return [g for g in self.gaps if g.citation_needed]


EXTRACTION_SYSTEM_PROMPT = """You are an expert academic reviewer analyzing papers for argumentation gaps using the Toulmin model.

Toulmin components:
- CLAIM: The main assertion being made
- GROUND: Evidence or data supporting the claim
- WARRANT: The reasoning connecting ground to claim
- BACKING: Support for the warrant itself
- QUALIFIER: Conditions or limitations on the claim
- REBUTTAL: Acknowledgment of counter-arguments

Your task is to identify gaps in the argumentation structure.

Gap types to identify:
- missing_evidence: Claim with no supporting data
- weak_warrant: Poor logic chain between evidence and claim
- missing_citation: Needs a published reference
- unstated_assumption: Hidden premise not made explicit
- counterargument_ignored: Known rebuttals not addressed
- scope_unclear: Claim boundaries are vague

For each gap, provide:
1. gap_type: One of the types above
2. severity: high, medium, or low
3. related_claim: The claim this gap affects
4. anchor_text: 5-15 word verbatim quote from the text
5. paragraph_fallback: 3-5 keyword backup
6. suggested_action: Concrete improvement suggestion
7. citation_needed: true/false

Respond in JSON format with a "gaps" array."""


async def analyze_document(
    text: str,
    title: str | None = None,
    focus: list[str] | None = None,
    client: LLMClient | None = None,
) -> GapAnalysisResult:
    """Analyze a document for argumentation gaps.

    Args:
        text: Document text to analyze.
        title: Document title (extracted from text if not provided).
        focus: Optional list of gap types to focus on.
        client: LLM client to use.

    Returns:
        GapAnalysisResult with identified gaps.
    """
    word_count = len(text.split())
    if word_count < 50:
        raise ValueError("Document too short for gap analysis (minimum 50 words)")

    if len(text) > 50000:
        logger.warning("Document truncated from %d to 50000 chars", len(text))
        text = text[:50000]

    if title is None:
        lines = text.strip().split("\n")
        for line in lines[:5]:
            if line.strip():
                title = line.strip().lstrip("#").strip()
                break
        if not title:
            title = "Untitled Document"

    client = client or get_client()
    logger.info("Starting gap analysis: %s (%d words)", title, word_count)

    prompt = f"""Analyze this document for argumentation gaps:

TITLE: {title}

TEXT:
{text}

{f"Focus on these gap types: {', '.join(focus)}" if focus else ""}

Identify all gaps and respond with JSON containing:
- gaps: array of gap objects
- overall_evidence_strength: strong/moderate/weak/missing/contested
- executive_summary: 3 bullet points summarizing key issues"""

    response = await client.complete_json(
        prompt=prompt,
        system=EXTRACTION_SYSTEM_PROMPT,
        max_tokens=4096,
        temperature=0.3,
    )

    gaps = []
    for i, g in enumerate(response.get("gaps", []), start=1):
        try:
            gap_type = GapType(g.get("gap_type", "missing_evidence"))
        except ValueError:
            gap_type = GapType.MISSING_EVIDENCE

        gaps.append(Gap(
            gap_id=f"GAP-{i:03d}",
            gap_type=gap_type,
            severity=g.get("severity", "medium"),
            related_claim=g.get("related_claim", ""),
            anchor_text=g.get("anchor_text", ""),
            paragraph_fallback=g.get("paragraph_fallback", ""),
            suggested_action=g.get("suggested_action", ""),
            citation_needed=g.get("citation_needed", False),
        ))

    try:
        strength = EvidenceStrength(response.get("overall_evidence_strength", "moderate"))
    except ValueError:
        strength = EvidenceStrength.MODERATE

    logger.info("Gap analysis complete: %d gaps found", len(gaps))

    return GapAnalysisResult(
        title=title,
        gaps=gaps,
        overall_evidence_strength=strength,
        executive_summary=response.get("executive_summary", []),
    )


def gap_to_finding(gap: Gap, skill_name: str = "paper-gaps") -> Finding:
    """Convert a Gap to a Finding for merge compatibility."""
    severity_map = {
        "high": Severity.MAJOR,
        "medium": Severity.MEDIUM,
        "low": Severity.MINOR,
    }
    category_map = {
        GapType.MISSING_EVIDENCE: Category.EVIDENCE,
        GapType.WEAK_WARRANT: Category.ARGUMENTATION,
        GapType.MISSING_CITATION: Category.CITATION,
        GapType.UNSTATED_ASSUMPTION: Category.ARGUMENTATION,
        GapType.COUNTERARGUMENT_IGNORED: Category.REDTEAM,
        GapType.SCOPE_UNCLEAR: Category.PRECISION,
    }

    return Finding(
        id=gap.gap_id,
        source_skill=skill_name,
        reviewer="paper-gaps-engine",
        category=category_map.get(gap.gap_type, Category.ARGUMENTATION),
        severity=severity_map.get(gap.severity, Severity.MEDIUM),
        anchor_text=gap.anchor_text or gap.related_claim[:50],
        paragraph_fallback=gap.paragraph_fallback,
        concern=f"{gap.gap_type.value}: {gap.related_claim}",
        suggested_fix=gap.suggested_action,
        tone_hint=Tone.CONSTRUCTIVE,
    )


async def run_paper_gaps(
    text: str,
    title: str | None = None,
    focus: list[str] | None = None,
    client: LLMClient | None = None,
) -> tuple[GapAnalysisResult, list[Finding]]:
    """Run paper gaps analysis and return both result and findings.

    Args:
        text: Document text.
        title: Document title.
        focus: Gap types to focus on.
        client: LLM client.

    Returns:
        Tuple of (GapAnalysisResult, list of Findings for merge).
    """
    result = await analyze_document(text, title, focus, client)
    findings = [gap_to_finding(g) for g in result.gaps]
    return result, findings
