---
name: paper-gaps
description: "Analyze academic papers for missing arguments, weak evidence, and citation gaps using Toulmin argumentation model"
triggers:
  - /paper-gaps
  - analyze paper gaps
  - find argument gaps
  - missing evidence
---

# Paper Gap Analysis

Analyze an academic document for missing arguments, weak evidence, and citation gaps using the Toulmin argumentation model.

**Announce at start:** "Using the /paper-gaps skill for argumentation gap analysis."

## Overview

Academic papers often contain claims without adequate evidence, missing warrants between data and conclusions, and blind spots where counterarguments go unaddressed. This skill systematically surfaces those gaps using the Toulmin model (claim, ground, warrant, backing, qualifier, rebuttal).

## Usage

```bash
/paper-gaps <file-path>
/paper-gaps --text "paste text here"
/paper-gaps <file-path> --focus "evidence gaps only"
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `<file-path>` | required | `.md`, `.txt`, `.pdf`, or `.docx` |
| `--text` | alternative | Pasted text to analyze |
| `--focus` | all | Narrow to specific gap types |

## Gap Types

| Type | Description |
|------|-------------|
| `missing_evidence` | Claim with no supporting data |
| `weak_warrant` | Poor logic chain between evidence and claim |
| `missing_citation` | Needs a published reference |
| `unstated_assumption` | Hidden premise not made explicit |
| `counterargument_ignored` | Known rebuttals not addressed |
| `scope_unclear` | Claim boundaries are vague |

## Output Format

### Section 1: Executive Summary (3 bullets max)

Summarizes overall argument strength, gap count, and critical issues.

### Section 2: Gap Inventory Table

```markdown
| Gap ID | Type | Severity | Related Claim | Suggested Action | Citation Needed? |
|--------|------|----------|---------------|------------------|------------------|
| GAP-001 | missing_evidence | high | "..." | Add empirical data | Yes |
```

### Section 3: Draft Skeleton with Citation Markers

```markdown
## Introduction

This paper argues that X drives Y.
Several studies support this. [CITATION NEEDED: "cross-country studies X Y"]
```

### Section 4: Research Commands

```bash
/research-wave "cross-country studies X Y causal evidence"
```

## Python API

```python
from paper_review_toolkit.skills import run_paper_gaps

result, findings = await run_paper_gaps(text, title="My Paper")
for gap in result.gaps:
    print(f"{gap.gap_id}: {gap.gap_type.value} - {gap.related_claim}")
```

## Error Handling

| Error | Handling |
|-------|----------|
| File not found | Report error |
| Document <50 words | Reject |
| Document >50k chars | Auto-truncate |

## Version

Version 1.0.0 | Paper Review Toolkit
