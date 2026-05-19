# Paper Review Toolkit

A Claude Code skill for comprehensive paper review using multi-persona simulation and argumentation analysis.

## Overview

This toolkit provides:

1. **Paper Gap Analysis** (`/paper-gaps`) — Identifies missing arguments, weak evidence, and citation gaps using the Toulmin argumentation model
2. **Policy Review Simulation** (`/policy-review-sim`) — Simulates feedback from a panel of policy audience personas
3. **Paper Review Orchestrator** (`/paper-review`) — Runs both analyses in parallel, merges findings deterministically, applies a constructive comment rubric, and produces docx-ready output

## Installation

### Requirements

- Python 3.11+
- Claude Code CLI
- Anthropic API key

### Setup

```bash
# Clone the repository
git clone https://github.com/first-polyphony/paper-review-toolkit.git
cd paper-review-toolkit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"
```

### Claude Code Integration

Symlink the skills into your Claude Code skills directory:

```bash
ln -s $(pwd)/.claude/skills/paper-review ~/.claude/skills/
ln -s $(pwd)/.claude/skills/paper-gaps ~/.claude/skills/
ln -s $(pwd)/.claude/skills/policy-review-sim ~/.claude/skills/
```

## Usage

### Quick Start

```bash
# Full joint review
/paper-review manuscript.docx

# Just gap analysis
/paper-gaps manuscript.md

# Just audience simulation
/policy-review-sim manuscript.md --customers "Congressional Staffer, Think Tank Director"
```

### Paper Review (Joint Orchestrator)

The main entrypoint that runs both analysis passes and merges findings:

```bash
/paper-review <paper-path> \
  [--customers "Customer A, Customer B"] \
  [--focus argumentation,structure,evidence] \
  [--mode curated|open] \
  [--output-dir ./review-output/]
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `<paper-path>` | required | `.md`, `.txt`, `.docx`, or `.pdf` |
| `--mode` | prompted | `curated` (docx-ready) or `open` (full dossier) |
| `--customers` | prompted | 1-5 audience personas |
| `--focus` | prompted | Category filter (see below) |
| `--output-dir` | `./review-<timestamp>/` | Output location |

**Focus Categories:**

- `argumentation` — Warrant gaps, weak links, unstated assumptions
- `structure` — Section organization, framing ambiguity
- `evidence` — Missing empirical support, thin sourcing
- `grammar` — Typos, dropped words, sentence fragments
- `citation` — Unverifiable sources
- `precision` — Legal/technical imprecision
- `audience` — Reception risk for named readers
- `redteam` — Political vulnerabilities, assumption fragility

### Paper Gaps

Toulmin-model argumentation analysis:

```bash
/paper-gaps <file-path>
/paper-gaps --text "paste text here"
/paper-gaps <file-path> --focus "evidence gaps only"
```

**Output includes:**
- Executive summary (3 bullets)
- Gap inventory table (ID, type, severity, suggested action)
- Draft skeleton with `[CITATION NEEDED]` markers
- `/research-wave` commands for each citation gap

### Policy Review Simulation

Multi-persona audience feedback:

```bash
/policy-review-sim <file-path> --customers "Congressional Staffer, Agency Program Manager"
/policy-review-sim <file-path> --mode curated
```

**Default reviewers (always run):**
- Policy Editor — Evidence quality, analytical rigor
- Adversarial Policy Analyst — Assumption exposure, red team

**Available customer personas:**
- Congressional Staffer
- Agency Program Manager
- Hill Committee Counsel
- White House NSC Staff
- Think Tank Director
- Foundation Program Officer
- Industry Association Executive
- Tech Company Policy Manager
- Advocacy Organization Director

## Architecture

### Merge Engine

The `/paper-review` orchestrator merges findings from both child skills using a deterministic union-find algorithm (`src/paper_review_toolkit/engines/engine.py`):

**Merge signals:**
1. Shared normalized paragraph + token-set Jaccard ≥ 0.45
2. Anchor substring overlap ≥ 20 chars
3. Shared named entity + shared category

**Output invariants:**
- Every input finding appears in exactly one cluster
- Same input → identical UF-NNN IDs across runs
- Clusters with convergence ≥ 3 preserve ≥ 2 distinct angles

### Constructive Comment Rubric

Four-axis mechanical check (`src/paper_review_toolkit/engines/rubric.py`):

| Axis | Requirement |
|------|-------------|
| R1 | Observation named (quoted anchor or capitalized phrase) |
| R2 | Why-clause present (stake keyword within comment) |
| R3 | Non-imperative opening (no directive verb at start) |
| R4 | Trusts author (no forced either/or binaries) |

## Output Format

### Curated Mode

```
<output-dir>/
├── context.md              # Mode, focus, scope
├── unified_findings.yaml   # Full cluster records
├── suppressed.yaml         # Out-of-scope findings
├── curator_pool.md         # Internal view with metadata
├── proposed_comments.yaml  # Docx-ready payload
└── audit/
    ├── clusters.json       # Union-find membership
    └── raw/                # Per-skill outputs
```

### Open Mode

```
<output-dir>/
├── context.md
├── unified_findings.yaml
├── suppressed.yaml
├── review.md               # Full dossier with UF-IDs
└── audit/
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Project Structure

```
paper-review-toolkit/
├── src/paper_review_toolkit/
│   ├── engines/           # Merge, rubric, types
│   ├── skills/            # Skill implementations
│   ├── parsers/           # Output parsers
│   └── llm.py             # Anthropic SDK wrapper
├── .claude/skills/        # Skill definitions (SKILL.md)
├── tests/
└── fixtures/
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/`
4. Submit a pull request

## Acknowledgments

This toolkit implements patterns from academic writing research and argumentation theory, including:
- Toulmin's model of argumentation (1958)
- Policy analysis frameworks from public administration literature
- Multi-perspective review simulation based on stakeholder analysis methods
