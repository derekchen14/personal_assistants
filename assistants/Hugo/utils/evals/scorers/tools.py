"""Traces-tier tool scorer (step_1_evals.md — Observability Traces).

Scores the DOMAIN tools the live orchestrator actually dispatched on a user turn against the
following agent turn's `actions` label, by token-level Levenshtein similarity — NOT a strict
pass/fail. A turn that lands 2 of 3 expected tools in order still earns partial credit; the
aggregate metric is the mean per-turn similarity, and the gate passes once it crosses a threshold.

`actual_tools` is the ordered list of domain tool names the agent dispatched, with orchestration
plumbing already filtered out by the runner (a domain tool = a key in `schemas/tools.yaml`). Ambiguity
is never scored here: it does not appear in `actions` (it rides the user turn's `ambiguity` level
field, checked by the completion scorer). Tool-name drift between a flow's live menu and its labeled tool
surfaces here as a sub-1.0 similarity — that red is the signal to fix, by design."""


def _levenshtein(a:list, b:list) -> int:
    """Token-level edit distance between two tool-name sequences (each tool is one token)."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for idx, tool_a in enumerate(a, 1):
        cur = [idx]
        for jdx, tool_b in enumerate(b, 1):
            cur.append(min(prev[jdx] + 1, cur[jdx - 1] + 1, prev[jdx - 1] + (tool_a != tool_b)))
        prev = cur
    return prev[-1]


def tool_similarity(actual_tools:list, expected_tools:list) -> float:
    """Per-turn similarity in [0, 1]: 1 - normalized Levenshtein distance over the two tool sequences.
    Both empty -> 1.0 (the agent correctly ran no domain tool — e.g. an ambiguous turn where it asked,
    or an approval-gated plan turn). One empty and the other not -> 0.0."""
    denom = max(len(actual_tools), len(expected_tools))
    if denom == 0:
        return 1.0
    return 1.0 - _levenshtein(actual_tools, expected_tools) / denom
