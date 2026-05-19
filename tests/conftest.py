"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_text() -> str:
    """Sample academic paper text for testing."""
    return """
    # The Impact of Data Privacy Regulations on Healthcare AI

    ## Introduction

    This paper argues that data privacy regulations like HIPAA and GDPR
    significantly impact the development and deployment of AI systems in
    healthcare. Several studies support this connection, though the evidence
    suggests a complex relationship between regulatory compliance and innovation.

    ## Background

    Healthcare AI systems process sensitive patient data, making them subject
    to strict regulatory frameworks. The Health Insurance Portability and
    Accountability Act (HIPAA) in the United States and the General Data
    Protection Regulation (GDPR) in the European Union establish baseline
    requirements for data handling.

    ## Analysis

    Our analysis reveals three key findings. First, compliance costs represent
    a significant barrier to entry for smaller AI developers. Second, regulatory
    uncertainty creates hesitation among healthcare institutions considering
    AI adoption. Third, the fragmented regulatory landscape across jurisdictions
    complicates international research collaborations.

    ## Recommendations

    We recommend policymakers consider harmonizing AI-specific provisions across
    existing privacy frameworks. This would reduce compliance burden while
    maintaining patient protections.

    ## Conclusion

    Data privacy regulations shape the healthcare AI landscape in complex ways.
    Further research is needed to quantify these effects and identify optimal
    regulatory approaches.
    """


@pytest.fixture
def sample_findings():
    """Sample findings for merge testing."""
    from paper_review_toolkit.engines.types import Category, Finding, Severity, Tone

    return [
        Finding(
            id="GAP-001",
            source_skill="paper-gaps",
            reviewer="engine",
            category=Category.EVIDENCE,
            severity=Severity.MAJOR,
            anchor_text="Several studies support this connection",
            paragraph_fallback="studies support connection",
            concern="'Several studies' is vague — no specific citations provided",
            suggested_fix="Cite 2-3 specific studies",
            tone_hint=Tone.CONSTRUCTIVE,
        ),
        Finding(
            id="C001",
            source_skill="policy-review-sim",
            reviewer="Congressional Staffer",
            category=Category.EVIDENCE,
            severity=Severity.MAJOR,
            anchor_text="Several studies support this connection",
            paragraph_fallback="studies support",
            concern="Need specific citations for Hill briefings",
            suggested_fix="Add peer-reviewed sources",
            tone_hint=Tone.CONSTRUCTIVE,
        ),
        Finding(
            id="GAP-002",
            source_skill="paper-gaps",
            reviewer="engine",
            category=Category.PRECISION,
            severity=Severity.MEDIUM,
            anchor_text="significantly impact the development",
            paragraph_fallback="significantly impact",
            concern="'Significantly' needs quantification",
            suggested_fix="Add metrics or threshold",
            tone_hint=Tone.CONSTRUCTIVE,
        ),
    ]
