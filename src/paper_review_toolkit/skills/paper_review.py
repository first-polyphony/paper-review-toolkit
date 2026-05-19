"""Paper review orchestrator skill implementation.

Runs paper-gaps and policy-review-sim in parallel, merges findings
deterministically, applies the constructive comment rubric.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from paper_review_toolkit.engines.engine import merge_findings
from paper_review_toolkit.engines.rubric import check_rubric, rewrite_needed
from paper_review_toolkit.engines.types import (
    AudienceTrust,
    Category,
    Finding,
    ReferenceRole,
    UnifiedFinding,
)
from paper_review_toolkit.llm import LLMClient, get_client
from paper_review_toolkit.skills.paper_gaps import run_paper_gaps
from paper_review_toolkit.skills.policy_review_sim import run_policy_review_sim


@dataclass
class ReviewConfig:
    """Configuration for a paper review run."""

    mode: str = "curated"
    reviewer_role: str = "external"
    audience_trust: AudienceTrust = AudienceTrust.MEDIUM
    focus: list[str] = field(default_factory=list)
    customers: list[str] = field(default_factory=list)
    context: str = ""
    reference_roles: dict[str, ReferenceRole] = field(default_factory=dict)
    output_dir: str = ""


@dataclass
class ReviewPacket:
    """Complete review output packet."""

    config: ReviewConfig
    unified_findings: list[UnifiedFinding]
    suppressed_findings: list[Finding]
    paper_gaps_result: Any
    policy_review_result: Any
    rubric_failures: list[str] = field(default_factory=list)


def _generate_output_dir() -> str:
    """Generate timestamped output directory name."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"./review-{timestamp}"


def _write_context_md(output_dir: Path, config: ReviewConfig) -> None:
    """Write context.md file."""
    content = f"""# Review Context

**Mode:** {config.mode}
**Reviewer Role:** {config.reviewer_role}
**Audience Trust:** {config.audience_trust.value}
**Focus Categories:** {', '.join(config.focus) if config.focus else 'all'}
**Customers:** {', '.join(config.customers) if config.customers else 'default reviewers only'}

## Scope
{config.context or 'A working draft for a general policy audience.'}
"""
    (output_dir / "context.md").write_text(content)


def _write_unified_findings(output_dir: Path, findings: list[UnifiedFinding]) -> None:
    """Write unified_findings.yaml file."""
    data = [f.model_dump() for f in findings]
    (output_dir / "unified_findings.yaml").write_text(yaml.dump(data, default_flow_style=False))


def _write_suppressed(output_dir: Path, findings: list[Finding]) -> None:
    """Write suppressed.yaml file."""
    data = [f.model_dump() for f in findings]
    (output_dir / "suppressed.yaml").write_text(yaml.dump(data, default_flow_style=False))


def _write_review_md(output_dir: Path, packet: ReviewPacket, title: str) -> None:
    """Write review.md for open mode."""
    lines = [
        f"# Review: {title}",
        f"\nDate: {datetime.now().strftime('%Y-%m-%d')}",
        f"\n## Configuration\n",
        f"- Mode: {packet.config.mode}",
        f"- Focus: {', '.join(packet.config.focus) if packet.config.focus else 'all'}",
        f"- Customers: {', '.join(packet.config.customers) if packet.config.customers else 'default'}",
        "\n## Executive Summary\n",
    ]

    top_findings = sorted(packet.unified_findings, key=lambda f: -f.convergence_count)[:5]
    for uf in top_findings:
        lines.append(f"- **{uf.uf_id}** (convergence {uf.convergence_count}): {uf.concern[:100]}")

    lines.append("\n## Findings by Convergence\n")

    for uf in sorted(packet.unified_findings, key=lambda f: (-f.convergence_count, f.uf_id)):
        lines.append(f"### {uf.uf_id}")
        lines.append(f"\n**Convergence:** {uf.convergence_count}")
        lines.append(f"**Severity:** {uf.severity.value}")
        lines.append(f"**Categories:** {', '.join(c.value for c in uf.categories)}")
        lines.append(f"\n**Anchor:** {uf.anchor_text[:200]}")
        lines.append(f"\n**Concern:** {uf.concern}")
        if uf.suggested_fix:
            lines.append(f"\n**Suggested Fix:** {uf.suggested_fix}")
        if uf.distinct_angles:
            lines.append("\n**Distinct Angles:**")
            for angle in uf.distinct_angles[:3]:
                lines.append(f"- {angle}")
        lines.append("\n---\n")

    lines.append(f"\n## Statistics\n")
    lines.append(f"- Total unified findings: {len(packet.unified_findings)}")
    lines.append(f"- Suppressed findings: {len(packet.suppressed_findings)}")
    lines.append(f"- Rubric failures: {len(packet.rubric_failures)}")

    (output_dir / "review.md").write_text("\n".join(lines))


def _write_curator_pool(output_dir: Path, packet: ReviewPacket) -> None:
    """Write curator_pool.md for curated mode."""
    lines = [
        "# Curator Comment Pool",
        "\nSelect comments by ID to include in the document.\n",
        "| ID | Category | Severity | Anchor | Concern |",
        "|-----|----------|----------|--------|---------|",
    ]

    for uf in packet.unified_findings:
        anchor_short = uf.anchor_text[:40].replace("|", "\\|")
        concern_short = uf.concern[:60].replace("|", "\\|")
        cats = ",".join(c.value[:4] for c in uf.categories)
        lines.append(f"| {uf.uf_id} | {cats} | {uf.severity.value} | {anchor_short}... | {concern_short}... |")

    (output_dir / "curator_pool.md").write_text("\n".join(lines))


def _write_proposed_comments(output_dir: Path, findings: list[UnifiedFinding], author: str) -> None:
    """Write proposed_comments.yaml for docx insertion."""
    comments = []
    for uf in findings:
        comments.append({
            "comment_id": uf.uf_id,
            "anchor_text": uf.anchor_text,
            "comment_text": uf.concern + (f" {uf.suggested_fix}" if uf.suggested_fix else ""),
            "w_author": author,
        })
    (output_dir / "proposed_comments.yaml").write_text(yaml.dump(comments, default_flow_style=False))


async def run_paper_review(
    text: str,
    title: str | None = None,
    config: ReviewConfig | None = None,
    client: LLMClient | None = None,
) -> ReviewPacket:
    """Run the full paper review orchestration.

    Args:
        text: Document text.
        title: Document title.
        config: Review configuration.
        client: LLM client.

    Returns:
        ReviewPacket with all results.
    """
    if len(text.split()) < 200:
        raise ValueError("Document too short for review (minimum 200 words)")

    config = config or ReviewConfig()
    client = client or get_client()

    if not config.output_dir:
        config.output_dir = _generate_output_dir()

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit" / "raw").mkdir(parents=True, exist_ok=True)

    if title is None:
        lines = text.strip().split("\n")
        for line in lines[:5]:
            if line.strip():
                title = line.strip().lstrip("#").strip()
                break
        title = title or "Untitled"

    focus = config.focus if config.focus else None

    gaps_task = run_paper_gaps(text, title, focus, client)
    policy_task = run_policy_review_sim(
        text,
        customers=config.customers,
        focus=focus,
        context=config.context,
        client=client,
    )

    results = await asyncio.gather(gaps_task, policy_task, return_exceptions=True)

    all_findings: list[Finding] = []
    gaps_result = None
    policy_result = None

    if not isinstance(results[0], Exception):
        gaps_result, gaps_findings = results[0]
        all_findings.extend(gaps_findings)
        with open(output_dir / "audit" / "raw" / "paper-gaps.yaml", "w") as f:
            yaml.dump([f.model_dump() for f in gaps_findings], f)

    if not isinstance(results[1], Exception):
        policy_result, policy_findings = results[1]
        all_findings.extend(policy_findings)
        with open(output_dir / "audit" / "raw" / "policy.yaml", "w") as f:
            yaml.dump([f.model_dump() for f in policy_findings], f)

    if not all_findings:
        raise RuntimeError("Both analysis passes failed")

    reference_roles = {k: ReferenceRole(v) for k, v in config.reference_roles.items()} if config.reference_roles else {}
    unified, suppressed = merge_findings(all_findings, reference_roles)

    with open(output_dir / "audit" / "clusters.json", "w") as f:
        json.dump({
            "unified_count": len(unified),
            "suppressed_count": len(suppressed),
            "input_count": len(all_findings),
        }, f, indent=2)

    rubric_failures = []
    for uf in unified:
        for cat in uf.categories:
            result = check_rubric(
                uf.concern,
                cat,
                audience_trust=config.audience_trust,
            )
            if rewrite_needed(result):
                rubric_failures.append(f"{uf.uf_id}: {', '.join(result.failures)}")
                break

    packet = ReviewPacket(
        config=config,
        unified_findings=unified,
        suppressed_findings=suppressed,
        paper_gaps_result=gaps_result,
        policy_review_result=policy_result,
        rubric_failures=rubric_failures,
    )

    _write_context_md(output_dir, config)
    _write_unified_findings(output_dir, unified)
    _write_suppressed(output_dir, suppressed)

    if config.mode == "open" or config.mode == "direct":
        _write_review_md(output_dir, packet, title)
    else:
        _write_curator_pool(output_dir, packet)
        author = "Reviewer" if config.reviewer_role == "external" else "Self"
        _write_proposed_comments(output_dir, unified, author)

    return packet
