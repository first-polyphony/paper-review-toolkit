"""Deterministic union-find merge for paper-review orchestration.

Given findings from /paper-gaps and /policy-review-sim, cluster them into
UnifiedFindings by three merge signals:

  (a) shared normalized paragraph + token-set Jaccard >= 0.45
  (b) contiguous anchor overlap >= 20 chars (after normalization)
  (c) shared named entity + shared category

No LLM is invoked in this module. Output is byte-identical across runs
given identical input.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from paper_review_toolkit.engines.types import (
    Finding,
    ReferenceRole,
    Severity,
    UnifiedFinding,
)

_STOP_TOKENS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "into", "is", "it", "its", "of", "on", "or",
        "that", "the", "these", "this", "to", "was", "were", "with", "which",
        "but", "not", "no", "do", "does", "did", "will", "would", "can", "could",
        "if", "when", "what", "how", "one", "two", "three", "been", "also",
    }
)

_KNOWN_ENTITIES: frozenset[str] = frozenset(
    {
        "DSP", "PADFAA", "EHDS", "HIPAA", "GDPR", "CLOUD", "CBPR", "ADPPA",
        "APRA", "CPRA", "MHMDA", "GCP", "GLP", "CFR", "USC", "FDA", "EMA",
        "SCC", "BAA", "FTC", "HHS", "DOJ", "DPF", "Schrems", "Snowden",
        "Chatham House", "NATO", "EU", "UN", "OECD", "WTO", "IMF",
        "World Bank", "Congress", "Parliament", "Senate", "House",
    }
)

_CAPPHRASE_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\b"
)


def _normalize_whitespace(s: str) -> str:
    """Collapse all whitespace runs to single space; strip."""
    return " ".join(s.split())


def _normalize_quotes(s: str) -> str:
    """Replace smart quotes with straight ASCII equivalents."""
    return (
        s.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )


def _strip_punct(s: str) -> str:
    """Remove punctuation except hyphens internal to words."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[^\w\s\-]", " ", s)


def normalize_anchor(text: str) -> str:
    """Canonicalize anchor text for comparison. Lowercase + strip + collapse."""
    return _normalize_whitespace(_strip_punct(_normalize_quotes(text))).lower()


def token_set(text: str, concern: str = "") -> frozenset[str]:
    """Return the token set for matching: normalized tokens + named entities."""
    norm = normalize_anchor(text + " " + concern)
    tokens = {t for t in norm.split() if t not in _STOP_TOKENS and len(t) >= 2}
    return frozenset(tokens)


def extract_named_entities(text: str) -> frozenset[str]:
    """Extract known acronyms and capitalized multi-word phrases."""
    hits: set[str] = set()
    for ent in _KNOWN_ENTITIES:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(ent) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text):
            hits.add(ent)
    for m in _CAPPHRASE_RE.finditer(text):
        phrase = m.group(0).strip()
        if len(phrase) >= 4 and phrase not in {"The", "This"}:
            hits.add(phrase)
    return frozenset(hits)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _anchor_contiguous_overlap(a: str, b: str, min_chars: int = 20) -> bool:
    """True if a and b share a contiguous substring of length >= min_chars."""
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) < min_chars:
        return False
    return any(
        short[i : i + min_chars] in long
        for i in range(len(short) - min_chars + 1)
    )


def _shares_entity_category(f_i: Finding, f_j: Finding) -> bool:
    if f_i.category != f_j.category:
        return False
    e_i = extract_named_entities(f_i.anchor_text + " " + f_i.concern)
    e_j = extract_named_entities(f_j.anchor_text + " " + f_j.concern)
    return bool(e_i & e_j)


def _should_merge(f_i: Finding, f_j: Finding) -> bool:
    norm_a_i = normalize_anchor(f_i.anchor_text)
    norm_a_j = normalize_anchor(f_j.anchor_text)
    norm_p_i = normalize_anchor(f_i.paragraph_fallback)
    norm_p_j = normalize_anchor(f_j.paragraph_fallback)

    if norm_p_i and norm_p_j and norm_p_i == norm_p_j:
        ts_i = token_set(f_i.anchor_text, f_i.concern)
        ts_j = token_set(f_j.anchor_text, f_j.concern)
        if _jaccard(ts_i, ts_j) >= 0.45:
            return True
    if _anchor_contiguous_overlap(norm_a_i, norm_a_j, min_chars=20):
        return True
    return _shares_entity_category(f_i, f_j)


class _UnionFind:
    """Deterministic union-find with path compression."""

    def __init__(self, n: int) -> None:
        self.parent: list[int] = list(range(n))
        self.rank: list[int] = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def _scope_suppressed(
    f: Finding, reference_roles: dict[str, ReferenceRole]
) -> bool:
    """True if this finding cites a context-only or series-template doc."""
    if not f.authority_ref:
        return False
    role = reference_roles.get(f.authority_ref)
    return role in (ReferenceRole.CONTEXT_ONLY, ReferenceRole.SERIES_TEMPLATE)


def _cluster_severity(findings: list[Finding]) -> Severity:
    """Maximum severity across cluster members."""
    return max(findings, key=lambda f: f.severity.rank()).severity


def _cluster_anchor(findings: list[Finding]) -> str:
    """Longest anchor_text wins (carries most context)."""
    return max(findings, key=lambda f: len(f.anchor_text)).anchor_text


def _cluster_fallback(findings: list[Finding]) -> str:
    """Most common paragraph_fallback across members."""
    fallbacks = [f.paragraph_fallback for f in findings if f.paragraph_fallback]
    if not fallbacks:
        return ""
    counter = Counter(fallbacks)
    most_common = counter.most_common(1)
    return most_common[0][0] if most_common else ""


def _cluster_distinct_angles(findings: list[Finding]) -> list[str]:
    """Preserve each distinct concern as an angle (dedup exact duplicates)."""
    seen: set[str] = set()
    angles: list[str] = []
    for f in findings:
        key = f.concern.strip().lower()
        if key and key not in seen:
            seen.add(key)
            angles.append(f.concern.strip())
    return angles


def merge_findings(
    findings: list[Finding],
    reference_roles: dict[str, ReferenceRole] | None = None,
) -> tuple[list[UnifiedFinding], list[Finding]]:
    """Cluster findings deterministically.

    Returns:
        (unified_findings, suppressed_findings)

    Invariants:
        - Every input Finding appears in exactly one of:
          a cluster in unified_findings, or the suppressed list.
        - Running twice with the same input produces identical UF- IDs in
          first-appearance order.
        - Clusters with convergence_count >= 3 have len(distinct_angles) >= 2.
    """
    reference_roles = reference_roles or {}

    in_scope: list[Finding] = []
    suppressed: list[Finding] = []
    for f in findings:
        if _scope_suppressed(f, reference_roles):
            suppressed.append(f)
        else:
            in_scope.append(f)

    n = len(in_scope)
    if n == 0:
        return ([], suppressed)

    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if _should_merge(in_scope[i], in_scope[j]):
                uf.union(i, j)

    clusters: dict[int, list[int]] = {}
    cluster_order: list[int] = []
    for idx in range(n):
        root = uf.find(idx)
        if root not in clusters:
            clusters[root] = []
            cluster_order.append(root)
        clusters[root].append(idx)

    unified: list[UnifiedFinding] = []
    for cluster_idx, root in enumerate(cluster_order, start=1):
        members_idx = clusters[root]
        members = [in_scope[i] for i in members_idx]

        sources = sorted(
            f"{m.source_skill}:{m.reviewer}:{m.id}" for m in members
        )
        categories = sorted({m.category for m in members}, key=lambda c: c.value)
        distinct_angles = _cluster_distinct_angles(members)

        if len(members) >= 3 and len(distinct_angles) < 2:
            extras = [
                m.suggested_fix for m in members if m.suggested_fix
            ]
            for extra in extras:
                if extra not in distinct_angles:
                    distinct_angles.append(extra)
                if len(distinct_angles) >= 2:
                    break

        primary = max(members, key=lambda m: len(m.concern))
        uf_record = UnifiedFinding(
            uf_id=f"UF-{cluster_idx:03d}",
            sources=sources,
            convergence_count=len(members),
            categories=categories,
            severity=_cluster_severity(members),
            anchor_text=_cluster_anchor(members),
            paragraph_fallback=_cluster_fallback(members),
            concern=primary.concern.strip(),
            distinct_angles=distinct_angles,
            suggested_fix=primary.suggested_fix.strip(),
            member_ids=sorted(m.id for m in members),
        )
        unified.append(uf_record)

    return (unified, suppressed)
