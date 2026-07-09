# Round 0.1 — SWE2 change set (self-review + diff, as submitted)

## Self-review

Round 0.1 component-interface taxonomy, built on master HEAD 070e90b (my worktree was branched
from stale a2445f6 — fast-forwarded it to master first; baseline 238 restored).

Group A (component cleanups): A1 ambiguity declare→recognize, present()→level string,
resolve(explanation); A2 FlowStack.peek removed (callers→get_flow); A3 pop_completed→pop (method +
write_state op); A4 find_turn_by_id deleted; A5 setbookmark/storecompleted_flows snake_cased; A6
revise_user_utterance+_rebuild_recent deleted; A7 serialize_session folded into read_state; A8
read_all deleted; A9 SessionScratchpad.write single-dict shape (+ flat read side in
revise._read_scratch_value and all write callers); A10 search_faqs→search_documents,
search_all/rerank privatized.

Group B (scoped tools): declare_ambiguity replaces handle_ambiguity (sub-agents); call_flow_stack
split into read_flow_stack/stackon_flow/fallback_flow; scratchpad(op) split into
read_scratchpad(borrowed)+append_to_scratchpad(hot-path); manage_memory retired + status-contract
fallback removed; new orchestrator ask_clarification_question/recover_from_ambiguity; NLU.recover
+ memory wiring.

Group C: for_orchestrator commit-rule/scratchpad/preference reword, for_pex, 15 flow .md tool
renames.

Scope: Hugo only, no new concepts beyond the spec, no defensive guards added. Out of plan scope
(flagged): stale handle_ambiguity/manage_memory/call_flow_stack mentions remain in trace docs
_traces/run_traces.py docstring + tolerance_rules.md — the plan's acceptance grep is
backend+schemas (clean).

PM test-plan satisfied: A2/A3/A7/A8/A9/A10/A1 existing-test edits; B5+B7 composition/dispatch
tests; B2+B6 _COMPONENT_TOOLS; new T-a..T-k (ambiguity present/resolve/recover ×2 in nlu;
declare/ask/recover/flow-stack/manage-memory-gone/flat-read in pex; read+append covered by the
renamed scratchpad test).

## Diff

The complete change set — all 37 files, 2089 lines, including every flow-prompt .md hunk — is
saved verbatim beside this file as `swe2_full.diff`. It is the exact `git diff` SWE2's worktree
emitted against 070e90b, and the diff the DoE applied to the repo (see doe_adjudication.md).
