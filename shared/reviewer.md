Read the CLAUDE.md, README.md and the main AGENTS.md file for the assistant in question to get a feel for the codebase — its architecture, conventions, and how the frontend and backend fit together. These files are your map, but treat them as potentially stale; the code is the source of truth.

Several other agents have done deep, focused searches for bugs in this codebase prior to public release. Their findings are in `Hugo/utils/tasklist_claude.md`, `Hugo/utils/tasklist_gemini.md`, and `Hugo/utils/tasklist_codex.md`. Your job is to critically evaluate, validate, and consolidate these findings into a single authoritative hitlist.

How to evaluate each finding:
  * Don't just verify that the cited code supports the conclusion — of course it does; that's how it was found. Instead, do a 360-degree investigation
  * Check for mitigation elsewhere: Is the issue handled by a caller, a wrapper, middleware, or a fallback path the original agent didn't trace into? Follow the full call chain, not just the flagged function.
  * Check for real-world impact: Could a user or operator actually trigger this? Under what conditions? If it requires a scenario that's statistically implausible or would require multiple simultaneous failures, say so — but still include it with an honest severity assessment rather than discarding it. Unlikely is not the same as impossible, and pre-release is the time to be thorough.
  * Check for agreement across agents: If multiple agents independently flagged the same issue (possibly described differently), that's strong signal. If only one agent flagged it and the others passed over the same code, that's worth noting either way — it could mean the finding is subtle, or it could mean it's a false positive.
  * Check the "good enough" findings carefully: Some findings may describe code that technically works but masks errors, silently degrades, or uses a suboptimal pattern. Do not dismiss these just because the code doesn't crash. Evaluate whether the behavior is truly acceptable for a public release, or whether "it works" is hiding "it works until it doesn't." These are the findings most likely to be prematurely dismissed.

What to preserve, what to cut:
  * Keep any finding where you cannot concretely demonstrate it is mitigated. "I don't think this matters" is not sufficient; show the code that makes it safe, or it stays on the list.
  * Cut findings where you can point to specific code that handles the case, or where the finding is based on a misunderstanding of the codebase's actual behavior.
  * Downgrade but keep findings that are real but low-impact or low-probability. Mark them clearly as low priority rather than removing them.

You may wish to reference _specs/components, _specs/modules, or _specs/utilities (our specifications that hold true across all assistants) to validate assumptions about protocol behavior, expected data formats, and conversation lifecycle.

_Output_ 

Combine the surviving findings into a single prioritized tasklist. For each item, include:
  * the original finding
  * your evaluation
  * the impact to end users
  * any additional context you discovered
  * a clear severity/priority level
  * the relevant file(s) and line(s)
  * what the general shape/impact of a fix would be
  
Write the consolidated tasklist to `Hugo/utils/unified_tasks.md`.