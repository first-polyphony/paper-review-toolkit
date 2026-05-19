---
name: policy-review-sim
description: "Simulate feedback from a panel of policy audience personas"
triggers:
  - /policy-review-sim
  - policy review
  - audience feedback
---

# Policy Review Simulation

Simulate feedback from a policy review panel: two default analyst reviewers plus 1-5 user-selected policy customers (audience personas).

**Announce at start:** "Using the /policy-review-sim skill to simulate policy audience feedback."

## Ethical Notice

> **Simulated Policy Review — Not real stakeholder feedback**
>
> This simulation uses constructed reviewer personas for author self-improvement only. These are not real policymakers.

## Reviewer Architecture

### Default Reviewers (always run)

| Reviewer | Focus |
|----------|-------|
| **Policy Editor** | Evidence quality, citation standards, analytical rigor |
| **Adversarial Policy Analyst** | Assumption exposure, framing challenges, red team |

### Policy Customer Personas (1-5 selectable)

| Customer | Decision Context |
|----------|-----------------|
| Congressional Staffer | "What do I tell my boss?" |
| Agency Program Manager | "Can we implement this?" |
| Think Tank Director | Competitive intelligence |
| Foundation Program Officer | Investment evaluation |
| Industry Association Executive | Member interests |
| Tech Company Policy Manager | Regulatory impact |
| Advocacy Organization Director | Campaign materials |

## Usage

```bash
/policy-review-sim <file-path>
/policy-review-sim <file-path> --customers "Congressional Staffer, Think Tank Director"
/policy-review-sim <file-path> --mode curated
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `<file-path>` | required | Document to review |
| `--customers` | prompted | 1-5 customer personas |
| `--mode` | open | `open` or `curated` |
| `--focus` | all | Category filter |
| `--context` | "" | Scope preamble |

### Modes

**`open`** — Direct feedback with full analysis report.

**`curated`** — Separates editor report from author-facing comments. User selects which comments to include.

## Output Structure

Each reviewer produces:
- Concerns with category, severity, anchor text
- Strengths list
- Verdict
- Utility score (customers only)

## Python API

```python
from paper_review_toolkit.skills import run_policy_review_sim

result, findings = await run_policy_review_sim(
    text,
    customers=["Congressional Staffer", "Think Tank Director"],
    focus=["argumentation", "audience"],
)

for reviewer in result.reviewers:
    print(f"{reviewer.reviewer}: {reviewer.verdict}")
```

## Error Handling

| Error | Handling |
|-------|----------|
| Document <200 words | Reject |
| Unknown customer | List available types |
| 4+ customers | Warn about latency |

## Version

Version 1.0.0 | Paper Review Toolkit
