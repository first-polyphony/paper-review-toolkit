"""Policy review simulation skill implementation.

Simulates feedback from a panel of policy audience personas.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from paper_review_toolkit.engines.types import Category, Finding, Severity, Tone
from paper_review_toolkit.llm import LLMClient, get_client


class CustomerType(str, Enum):
    """Available policy customer personas."""

    CONGRESSIONAL_STAFFER = "Congressional Staffer"
    AGENCY_PROGRAM_MANAGER = "Agency Program Manager"
    HILL_COMMITTEE_COUNSEL = "Hill Committee Counsel"
    WHITE_HOUSE_NSC_STAFF = "White House NSC Staff"
    STATE_LOCAL_OFFICIAL = "State/Local Official"
    FOUNDATION_PROGRAM_OFFICER = "Foundation Program Officer"
    THINK_TANK_DIRECTOR = "Think Tank Director"
    FOREIGN_MINISTRY_DESK_OFFICER = "Foreign Ministry Desk Officer"
    INDUSTRY_ASSOCIATION_EXECUTIVE = "Industry Association Executive"
    ADVOCACY_ORGANIZATION_DIRECTOR = "Advocacy Organization Director"
    TECH_COMPANY_POLICY_MANAGER = "Tech Company Policy Manager"


PERSONA_PROMPTS = {
    CustomerType.CONGRESSIONAL_STAFFER: """You are a Congressional Staffer reviewing policy papers.
Your focus: Briefing utility, partisan risks, citable evidence.
Decision context: "What do I tell my boss?"
Assess whether this paper provides actionable intelligence for legislative work.""",

    CustomerType.AGENCY_PROGRAM_MANAGER: """You are a federal Agency Program Manager reviewing policy papers.
Your focus: Implementation feasibility, budget implications, authorities.
Decision context: "Can we implement this?"
Assess whether recommendations are actionable within existing authorities and resources.""",

    CustomerType.THINK_TANK_DIRECTOR: """You are a Think Tank Director reviewing policy papers.
Your focus: Intellectual contribution, methodological rigor, field positioning.
Decision context: Competitive/collaborative intelligence.
Assess whether this advances the field and would be worth amplifying.""",

    CustomerType.FOUNDATION_PROGRAM_OFFICER: """You are a Foundation Program Officer reviewing policy papers.
Your focus: Theory of change, measurable outcomes, field fit.
Decision context: Investment evaluation.
Assess whether findings support fundable initiatives.""",

    CustomerType.INDUSTRY_ASSOCIATION_EXECUTIVE: """You are an Industry Association Executive reviewing policy papers.
Your focus: Regulatory ammunition, member consensus fit.
Decision context: Comment letters, testimony preparation.
Assess whether this supports or threatens member interests.""",

    CustomerType.TECH_COMPANY_POLICY_MANAGER: """You are a Tech Company Policy Manager reviewing policy papers.
Your focus: Regulatory impact, product implications, competitive positioning.
Decision context: Policy response strategy.
Assess how this affects your company's operations and strategy.""",
}

POLICY_EDITOR_PROMPT = """You are a Policy Editor providing constructive peer review.
Focus: Evidence quality, citation standards, analytical rigor, implementation specificity.
DO NOT: Red-team framing, assess political feasibility, construct opposition case.
Evaluate whether the paper's evidence and argument are sound enough to publish."""

ADVERSARIAL_ANALYST_PROMPT = """You are an Adversarial Policy Analyst providing red team analysis.
Focus: Assumption exposure, framing challenges, political vulnerabilities, counterarguments.
DO NOT: Score evidence quality, assess citation standards, evaluate implementation specifics.
Ask: "Is the question correctly posed?" and "What would have to be true for this to be wrong?"
Steel man the opposition case."""


@dataclass
class ReviewConcern:
    """A single concern from a reviewer."""

    concern_id: str
    reviewer: str
    category: Category
    severity: str
    concern: str
    anchor_text: str
    paragraph_fallback: str
    suggested_fix: str
    tone: Tone = Tone.CONSTRUCTIVE


@dataclass
class ReviewerOutput:
    """Output from a single reviewer."""

    reviewer: str
    reviewer_type: str
    concerns: list[ReviewConcern] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    verdict: str = ""
    utility_score: int | None = None


@dataclass
class PolicyReviewResult:
    """Complete policy review result."""

    reviewers: list[ReviewerOutput] = field(default_factory=list)
    executive_summary: list[str] = field(default_factory=list)

    def all_concerns(self) -> list[ReviewConcern]:
        """Flatten all concerns from all reviewers."""
        return [c for r in self.reviewers for c in r.concerns]


REVIEW_SYSTEM_PROMPT = """You are reviewing a policy paper from a specific perspective.

For each concern you identify, provide:
1. category: One of argumentation, evidence, structure, grammar, citation, precision, audience, redteam
2. severity: major or minor
3. concern: Description of the issue
4. anchor_text: 5-15 word verbatim quote from the text
5. paragraph_fallback: 3-5 keyword backup
6. suggested_fix: Concrete improvement suggestion

Also provide:
- strengths: What works well (list of strings)
- verdict: Your overall assessment
- utility_score: 1-5 rating of usefulness (for customer personas only)

Respond in JSON format."""


async def run_single_reviewer(
    text: str,
    reviewer_name: str,
    system_prompt: str,
    client: LLMClient,
    focus: list[str] | None = None,
    context: str | None = None,
) -> ReviewerOutput:
    """Run a single reviewer's analysis.

    Args:
        text: Document text.
        reviewer_name: Name of the reviewer persona.
        system_prompt: System prompt for this reviewer.
        client: LLM client.
        focus: Categories to focus on.
        context: Additional context.

    Returns:
        ReviewerOutput with concerns and assessment.
    """
    prompt = f"""Review this policy paper:

{text}

{f"Additional context: {context}" if context else ""}
{f"Focus on these categories: {', '.join(focus)}" if focus else ""}

Provide your review in JSON format with:
- concerns: array of concern objects
- strengths: array of strings
- verdict: string
- utility_score: integer 1-5 (if applicable)"""

    full_system = f"{system_prompt}\n\n{REVIEW_SYSTEM_PROMPT}"

    try:
        response = await client.complete_json(
            prompt=prompt,
            system=full_system,
            max_tokens=4096,
            temperature=0.4,
        )
    except Exception:
        return ReviewerOutput(
            reviewer=reviewer_name,
            reviewer_type="error",
            concerns=[],
            strengths=[],
            verdict="Review failed",
        )

    concerns = []
    concern_id_counter = 1

    for c in response.get("concerns", []):
        try:
            cat = Category(c.get("category", "argumentation"))
        except ValueError:
            cat = Category.ARGUMENTATION

        try:
            tone = Tone(c.get("tone", "constructive"))
        except ValueError:
            tone = Tone.CONSTRUCTIVE

        concerns.append(ReviewConcern(
            concern_id=f"C{concern_id_counter:03d}",
            reviewer=reviewer_name,
            category=cat,
            severity=c.get("severity", "minor"),
            concern=c.get("concern", ""),
            anchor_text=c.get("anchor_text", ""),
            paragraph_fallback=c.get("paragraph_fallback", ""),
            suggested_fix=c.get("suggested_fix", ""),
            tone=tone,
        ))
        concern_id_counter += 1

    return ReviewerOutput(
        reviewer=reviewer_name,
        reviewer_type="policy_customer" if reviewer_name in [ct.value for ct in CustomerType] else "analyst",
        concerns=concerns,
        strengths=response.get("strengths", []),
        verdict=response.get("verdict", ""),
        utility_score=response.get("utility_score"),
    )


async def run_policy_review_sim(
    text: str,
    customers: list[str] | None = None,
    focus: list[str] | None = None,
    context: str | None = None,
    client: LLMClient | None = None,
) -> tuple[PolicyReviewResult, list[Finding]]:
    """Run policy review simulation.

    Args:
        text: Document text.
        customers: List of customer persona names.
        focus: Categories to focus on.
        context: Additional context.
        client: LLM client.

    Returns:
        Tuple of (PolicyReviewResult, list of Findings for merge).
    """
    if len(text.split()) < 200:
        raise ValueError("Document too short for review (minimum 200 words)")

    client = client or get_client()

    tasks = [
        run_single_reviewer(text, "Policy Editor", POLICY_EDITOR_PROMPT, client, focus, context),
        run_single_reviewer(text, "Adversarial Policy Analyst", ADVERSARIAL_ANALYST_PROMPT, client, focus, context),
    ]

    if customers:
        for customer_name in customers[:5]:
            try:
                customer_type = CustomerType(customer_name)
                prompt = PERSONA_PROMPTS.get(customer_type, PERSONA_PROMPTS[CustomerType.THINK_TANK_DIRECTOR])
                tasks.append(run_single_reviewer(text, customer_name, prompt, client, focus, context))
            except ValueError:
                pass

    results = await asyncio.gather(*tasks)

    policy_result = PolicyReviewResult(reviewers=list(results))

    findings = []
    for reviewer_output in results:
        for concern in reviewer_output.concerns:
            severity_map = {"major": Severity.MAJOR, "minor": Severity.MINOR}
            findings.append(Finding(
                id=concern.concern_id,
                source_skill="policy-review-sim",
                reviewer=concern.reviewer,
                category=concern.category,
                severity=severity_map.get(concern.severity, Severity.MINOR),
                anchor_text=concern.anchor_text or concern.concern[:50],
                paragraph_fallback=concern.paragraph_fallback,
                concern=concern.concern,
                suggested_fix=concern.suggested_fix,
                tone_hint=concern.tone,
            ))

    return policy_result, findings
