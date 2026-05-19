---
name: paper-review
description: "Joint paper review orchestrator — runs /paper-gaps and /policy-review-sim in parallel, merges findings deterministically, applies a constructive comment rubric, and emits a consolidated review."
triggers:
  - /paper-review
  - joint review
  - full review pass
  - reviewer panel plus gaps
---

# Paper Review — Joint Orchestrator

Run `/paper-gaps` (Toulmin argumentation analysis) and `/policy-review-sim` (multi-persona audience simulation) together, merge their findings via anchor-clustering, apply the Constructive Comment Rubric, and emit one consolidated review.

**Announce at start:** "Using `/paper-review`. I'll ask which categories of feedback you want, then run the joint review."

## Usage

```bash
/paper-review <paper-path> \
  [--customers "Customer A, Customer B"] \
  [--focus argumentation,structure,evidence] \
  [--mode curated|open] \
  [--output-dir <dir>]
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `<paper-path>` | required | `.md`, `.txt`, `.docx`, or `.pdf` |
| `--mode` | prompted | `curated` (docx-ready) or `open` (full dossier) |
| `--customers` | prompted | 1-5 audience personas |
| `--focus` | prompted | Category filter |
| `--output-dir` | `./review-<timestamp>/` | Output location |

### Modes

**`curated`** — Comments selected for docx insertion. Clean text without internal IDs or metadata.

**`open`** / **`direct`** — Full findings dossier with UF-IDs, convergence counts, and source attribution.

### Focus Categories

| Category | What You Get |
|----------|--------------|
| `argumentation` | Warrant gaps, weak links, unstated assumptions |
| `structure` | Section organization, framing ambiguity |
| `evidence` | Missing empirical support, thin sourcing |
| `grammar` | Typos, dropped words, sentence fragments |
| `citation` | Unverifiable sources |
| `precision` | Legal/technical imprecision |
| `audience` | Reception risk for named readers |
| `redteam` | Political vulnerabilities, assumption fragility |

## Workflow

### Phase 1 — Configuration

1. Read the paper. Reject if <200 words.
2. If `--mode` not supplied, prompt for curated or open.
3. If `--focus` not supplied, prompt for categories.
4. If `--customers` not supplied, prompt for audience personas.

### Phase 2 — Parallel Analysis

Dispatch concurrently:

```
/paper-gaps <paper> --focus "<categories>"
/policy-review-sim <paper> --customers "<customers>" --focus "<categories>"
```

### Phase 3 — Merge (Deterministic)

Uses union-find clustering over three signals:
- Shared paragraph + token Jaccard ≥ 0.45
- Anchor substring overlap ≥ 20 chars
- Shared named entity + same category

Output: `unified_findings.yaml` with UF-NNN IDs.

### Phase 4 — Constructive Comment Rubric

Four-axis mechanical check:

| Axis | Requirement |
|------|-------------|
| R1 | Observation named (quoted anchor or capitalized phrase) |
| R2 | Why-clause present (stake keyword) |
| R3 | Non-imperative opening |
| R4 | No forced either/or binaries |

### Phase 5 — Packet Emission

**Open mode:**
```
review.md               # Full dossier with UF-IDs
unified_findings.yaml   # Cluster records
suppressed.yaml         # Out-of-scope findings
audit/                  # Raw outputs
```

**Curated mode:**
```
curator_pool.md         # Selection table
proposed_comments.yaml  # Docx-ready payload
unified_findings.yaml
suppressed.yaml
audit/
```

## Python API

```python
from paper_review_toolkit import merge_findings, check_rubric
from paper_review_toolkit.skills import run_paper_review, ReviewConfig

config = ReviewConfig(
    mode="curated",
    focus=["argumentation", "structure"],
    customers=["Congressional Staffer", "Think Tank Director"],
)

packet = await run_paper_review(text, title="My Paper", config=config)
```

## Error Handling

| Error | Handling |
|-------|----------|
| Paper <200 words | Abort |
| Invalid category | Fail with valid set |
| Both children fail | Abort |
| Phase 3 produces 0 clusters | Abort |

## Version

Version 1.0.0 | Paper Review Toolkit
