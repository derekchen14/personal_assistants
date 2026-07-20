# Round 5.2 — One Tool Surface

Maps to **Master Plan · Round 5 (Plan)** — managing the stack is workflow planning. DRAFT; builds
on [round 2.16](round_2.16_spec.md) and uses its names (`orchestrate()`, `execute()`, `call_tool`,
`call_policy`). Line refs cite post-2.16 pex.py.

Today the PEX Agent and the policy sub-agents reach the same components through differently-named
tools, and the methods behind those tools follow no single naming or routing pattern. This round
makes both loops re-use one set of methods and makes the exposed-name-to-method mapping
mechanical.

Rulings recorded 2026-07-19 (all passes):

- **One method per component action; exposed tools are shaped per audience.** The methods
  underneath are always shared. The PEX Agent may get multi-op tools; a sub-agent tool is a
  simple verb with a flat schema — either a shared tool with a narrower `op` menu
  (`manage_flows`) or its own simply-named tool over the same helper (`declare_ambiguity`,
  `view_policies`). Never two methods for one action, never an `op` param a sub-agent must
  reason about when a flat schema will do.
- **Who runs surfaced work**: the PEX Agent's `manage_flows` runs it inline via `execute()`; a
  sub-agent's `manage_flows` defers it to the PEX layer (no fourth level).
- **Scratchpad**: one tool, ops read/append, both levels get both ops; `save_findings` is
  deleted.
- **Ambiguity**: sub-agents declare via `declare_ambiguity` (name and flat schema unchanged); the
  PEX Agent never declares and no longer asks — the clarification question is authored at reply
  time, once all information is in, and arrives in the round refresh (prepare's abstention note
  is its first moment). The ask path (`ask_clarification_question`) is deleted.
- **`execution_error` gets wired** (it is exposed today but routes nowhere).
- **Amend** takes `reset:bool=False` — the amender decides whether `used_count` restarts.
- **One result shape** from `execute()`: `{_success, _error, artifact}`. Every other key the old
  results carried moves to the round refresh (live stack + unseen-entry digests + pending
  question, rendered into every PEX Agent round) or to an explicit read (5.2.5).
- **MEM naming is skipped this round** — `remember(op=x)` stays reserved; `store_preference`
  keeps its name until MEM matters.

## Toolsmith Inventory

The full surface as of 2026-07-19, exposed tool name vs the method that runs. Domain tools are
already uniform — `self.tools` (pex.py:107-143) maps each tool name to the identically-named
service method, one dict, no exceptions — so they need nothing from this round and are omitted.

**Sub-agent component tools** (`_component_tool_definitions`, pex.py:847):

| exposed tool | method | fate in this round |
|---|---|---|
| `declare_ambiguity` | `_declare_ambiguity` (517) | kept as-is — name, flat schema, method (5.2.3) |
| `coordinate_context` | `_context_tool` (482) | kept; method renamed, `action`→`op` (5.2.6) |
| `read_scratchpad` | `_read_from_scratchpad` (791) | merged into `scratchpad` (5.2.2) |
| `read_flow_stack` | `_read_flow_stack` (498) | replaced by `view_policies` (5.2.4) |
| `stackon_flow` | `_stackon_flow` (509) | deleted; `manage_flows` at both levels (5.2.1) |
| `fallback_flow` | `_fallback_flow` (513) | deleted; `manage_flows` at both levels (5.2.1) |
| `execution_error` | **none — unwired** | wired (5.2.3) |
| `save_findings` | `_save_findings_tool` (527) | deleted; `scratchpad op='append'` covers it (5.2.2) |

**PEX Agent tools** (`_orchestrator_toolset`, pex.py:163; definitions pex.py:1040):

| exposed tool | method | fate in this round |
|---|---|---|
| `manage_flows` | `_manage_flows` (566) | shared; sub-agent menu is narrower (5.2.1) |
| `understand` | `_understand_user` (773) | stays PEX-only; shares the assembly helper (5.2.4) |
| `append_to_scratchpad` | `_append_to_scratchpad` (795) | merged into `scratchpad` (5.2.2) |
| `store_preference` | `_store_preference` (804) | kept unchanged (MEM skipped) |
| `ask_clarification_question` | `_ask_clarification` (809) | deleted; question arrives in-band (5.2.3) |

The PEX Agent additionally borrows `coordinate_context` + `read_scratchpad` from the component
list and calls the six READ_ONLY_DOMAIN_TOOLS (pex.py:41).

**The surface after this round** — every method named `_` + tool name, every pair of loops
sharing the methods underneath:

| tool | params | PEX Agent menu | sub-agent menu |
|---|---|---|---|
| `manage_flows` | op: update / stackon / fallback / pop | all four ops | stackon, fallback |
| `understand` | op: read / contemplate | both ops | absent |
| `view_policies` | none (flat) | absent | present |
| `scratchpad` | op: read / append | both ops | both ops |
| `declare_ambiguity` | level, metadata, observation (flat) | absent | present |
| `execution_error` | violation, message (flat) | absent | present |
| `coordinate_context` | op: get_history / get_turn / get_checkpoint | all three | all three |

Plus `store_preference` (PEX Agent only, unchanged) and the domain tools (flow menus and the
read-only allowlist, unchanged). Note the shape: the three sub-agent-only tools are all flat —
no sub-agent tool carries an `op` param it must reason about.

## Major Themes

### 5.2.1 — One flow tool: `manage_flows` at both levels

#### Problem

The stack has two tool vocabularies. The PEX Agent manages flows through `manage_flows` (ops
update / stackon / fallback / pop). A sub-agent gets `stackon_flow` and `fallback_flow` instead —
same FlowStack actions, different names, different schemas (they take `flow` where `manage_flows`
takes `flow_name`). Skill docs and the planner prompt must describe both vocabularies, and every
reader has to learn that `stackon_flow` IS `manage_flows op='stackon'` minus the run.

There is also a latent hole: `call_tool` routes `manage_flows` for any caller (it sits in
`_orchestrator_toolset`, reached at pex.py:469-470), so a sub-agent that guessed the name today
would run a policy inline from inside a policy run — a fourth level, which the architecture
forbids (sub-agents cannot create another nesting level).

#### Root Cause

The two loops were built at different times with separate tool lists, and the run decision
(activation belongs to the runtime) was entangled with the tool name instead of with the calling
level.

#### Solution Contract

One tool, one method. `manage_flows` → `_manage_flows` at both levels, with level-scoped menus:
the PEX Agent's definition offers all four ops; the sub-agent's definition offers **stackon and
fallback only** — sub-agents have no business updating or popping flows, and the narrower enum
keeps their toolset as simple as the two tools it replaces. The level rule for surfaced work:

- called from the **PEX Agent loop** → `execute()` runs the new flow inline; the policy result is
  the tool result (2.16 behavior, unchanged);
- called from **inside a policy run** → no inline run. The flow lands on the stack and re-surfaces
  at the PEX layer; the PEX Agent runs it on a later round.

An op outside the caller's menu is rejected with a corrective error, same as any bad argument.

#### Implementation

Delete `stackon_flow` / `fallback_flow` (methods pex.py:509-515, definitions pex.py:935-956). One
definition template for `manage_flows`; each level's list renders it with its own op enum, and the
sub-agent copy adds one sentence stating the defer behavior. Wiring without a new flag:
`call_policy` (pex.py:728) already hands sub-agents their own callable (`traced_tool`); that
callable routes `manage_flows` to the defer variant and enforces the narrower menu. The level is
carried by which callable you were given, not by state.

### 5.2.2 — One scratchpad tool and one stamping site

#### Problem

Three tools write or read one component. Sub-agents read entries via `read_scratchpad`; the PEX
Agent also writes via `append_to_scratchpad`; and `save_findings` is a third, shaped write that
turned out to be dead surface — no skill doc mentions it and no policy reads its result (its only
references are its own definition, method, `call_tool` branch, and two test mentions). The pex.md
tool catalog has documented a single `scratchpad` tool with ops all along — the code never caught
up.

Separately, the entry contract fields (`version`, `used_count`) are hand-written at **eleven**
sites:

- pex.py: `_save_findings_tool` (539-546), the synthesized completion entry in `execute()`
  (672-676), the contemplate request in `_understand_user` (783-786), `_append_scratchpad`
  (799-800);
- policies/base.py: `complete_flow` (225-227);
- policies/research.py:100-103 and policies/revise.py:288-289 (propose);
- nlu.py: the validate announcement (213), the think announcement (264-265), the recovery entry
  (279-281), and the review repair (293).

Eleven copies of the same three lines is eleven places to forget a field. The round 2.16
contemplate-crash cascade was exactly this class of bug: one entry missing its consume marker.

#### Root Cause

`SessionScratchpad.append_entry` accepts whatever dict it is given; the contract lives in the
callers' heads instead of in the component that owns the Entry.

#### Solution Contract

One `scratchpad` tool, ops `read` / `append`, **both ops at both levels**. `save_findings` is
deleted — a sub-agent that wants to persist findings appends an entry carrying them; when a
sub-agent's append names no `origin`, code defaults it to the active flow's name (preserving the
auto-origin convenience `save_findings` provided).

`append_entry` stamps `version` and `used_count` itself; `turn_number` stays the caller's field
(every caller holds the context, the scratchpad does not). Amend gets an explicit ruling: the
amend path takes **`reset:bool=False`** — the amender (NLU's review repair is the one caller)
decides whether the repaired entry becomes re-consumable; by default `used_count` is untouched.

#### Implementation

Replace the two definitions (pex.py:902-917, 1102-1113) and methods (791-793, 795-802) with one
`scratchpad` tool routed by `op`. Delete `save_findings` (definition 994-1023, method 527-552,
`call_tool` branch 467-468) and update the two test references (pex_unit_tests.py:211, 1741).
Move the `version`/`used_count` stamping into `append_entry` (session_scratchpad.py:22), add
`reset` to the amend path, and delete the hand-stamping at all eleven sites — nlu.py's review
repair (293) becomes an amend with `reset` passed explicitly.

### 5.2.3 — Ambiguity declared below, relayed above; a wired violation signal

#### Problem

The architecture draws one line: user-facing uncertainty is an **Ambiguity** (Recognize [declare],
Resolve [ask]); a tool failure is a policy **Violation**, never an ambiguity. The tool surface
blurs the line twice.

First, the ambiguity path splits its verbs across two level-specific tools — `declare_ambiguity`
(sub-agents) and `ask_clarification_question` (PEX Agent) — even though the level split is real:
the PEX Agent should never declare ambiguity (it plans; uncertainty is discovered inside NLU and
inside flows), and a flow's sub-agent never needs to ask (asking is the turn boundary's job). The
declare side is fine; the ask side is a whole tool whose only job is fetching a string the
runtime could have handed over directly.

Second, the violation path is **broken**: `execution_error` is defined and offered to every
sub-agent (pex.py:959-992), and roughly twenty skill files under `backend/prompts/pex/flows/`
instruct calling it — but `call_tool` has no branch for it, so every call returns the corrective
error `Unknown tool: execution_error`. No policy reads it from the tool_log either (policies
detect failure code-side via `tool_succeeded` on their save tool). A sub-agent following its own
skill doc gets told it called a tool that does not exist, then burns rounds retrying — a direct
task-completion cost.

#### Root Cause

The ask verb was given its own PEX-side tool instead of arriving in-band, and `execution_error`
was documented as part of the design (skills, tool definition) without the routing branch ever
being written.

#### Solution Contract

**Declare**: `declare_ambiguity` stays exactly as it is — name, flat schema (`level`, `metadata`,
`observation`, no `op` param), method, and the per-level metadata validation
(`_validate_ambig_metadata`, pex.py:66) all unchanged, sub-agent menu only. The simple verb is
easiest for the sub-agent to use; nothing here needed fixing. `is_present` and `resolve` stay
code-side — a property read and NLU's move on the answer turn are not tools.

**Ask**: the path is deleted. The clarification question always reaches the PEX Agent in-band, so
a fetch tool is redundant — and the question is authored at the END of the turn, never mid-run by
one flow's myopic view:

- when a policy run ends incomplete on a pending ambiguity, the next round refresh (5.2.5)
  renders `ambiguity.ask(...)`'s text — generated at render time, after all information has been
  collected;
- on an NLU-abstention turn (no flow detected, no policy ran), `prepare()`'s note — the first
  refresh of the turn — carries the question the same way, instead of today's "relay it with
  ask_clarification_question".

The PEX Agent relays the question it was handed; the Ambiguity Handler remains the author in both
paths. One fewer tool in the PEX menu, one fewer round per clarification turn.

**Violation**: `execution_error` stays a separate tool (the ambiguity/violation line is doctrinal)
and gets wired: a call acknowledges (`{'_success': True}`), and one code-side site turns it into
the error artifact.

#### Implementation

Delete `ask_clarification_question` (definition pex.py:1132-1140, method 809-815) and rewrite
`prepare()`'s abstention note to embed `ambiguity.ask(...)`'s text. For `execution_error`: add
the `call_tool` branch; then in `call_policy`, after the policy returns, scan the traced `calls`
for a successful `execution_error` — if the artifact carries no `violation` yet, stamp
`artifact.data['violation']` (and thoughts) from the call. One site, no per-policy edits;
`verify` (pex.py:242-244) already routes artifacts with a violation to the error path.

One eval-suite note: the corpus labels ambiguous turns with `expected_tools:
["handle_ambiguity"]` (see the generating-evals table). Since the tool keeps the name
`declare_ambiguity`, the scorer's mapping or the labels need a one-time alias so ambiguity turns
still score — a T9 item, not a reason to rename the tool.

### 5.2.4 — Two belief reads, one assembly

#### Problem

There are two tools for reading belief, and neither serves its audience well. The PEX Agent calls
`understand op='read'`: PEX assembles the view by combining `state.read_state()` with its own
live FlowStack at read time — the Dialogue State and the FlowStack are sibling components (the
stack belongs to PEX, not to NLU, and is never stored inside the state; state.json only carries a
serialized copy at save time). Sub-agents call `read_flow_stack`, which makes them pick a
`details` view (`flows` / `slots` / `flow_meta`) — an op-style choice a sub-agent should not have
to reason about, for data that is one small scoped view anyway.

Under the hood the assembly itself is copy-pasted: `document = state.read_state();
document['flow_stack'] = self.flow_stack.to_list()` appears at pex.py:562-563, 602-603, and
723-724. And `read_state` (pex.py:559) is no longer a tool at all — `understand` wraps it — yet it
still takes a `params` argument nothing uses.

#### Root Cause

`read_flow_stack` predates `understand`; when the belief read landed for the PEX Agent, the
sub-agent side was never revisited.

#### Solution Contract

Two tools shaped per audience, one assembly underneath:

- **PEX Agent**: `understand`, ops `read` / `contemplate`, behavior unchanged — `read` returns
  the full assembled view (state + live stack); `contemplate` queues the re-route request. Stays
  absent from the sub-agent menu (a sub-agent asking to re-route itself has no meaning, and the
  full state would break sub-agent context isolation).
- **Sub-agent**: `view_policies()` — flat, **no parameters**, one call returns the whole scoped
  view: the flow stack plus the active flow's slot values. Replaces `read_flow_stack` and its
  three-way `details` choice; the `flow_meta` view is dropped (the skill doc and the
  resolved-entities block already carry the flow's own metadata).

Both tool methods call one private assembly helper that replaces the three copies; `read_state`
loses the dead `params` argument or folds into `_understand`.

#### Implementation

Delete `read_flow_stack` (definition pex.py:919-933, method 498-507); add the `view_policies`
definition to `_component_tool_definitions` and `_view_policies` over the assembly helper. Add
the helper and call it from `_understand`, `_view_policies`, `_manage_flows`, and `execute()`.

### 5.2.5 — One result shape from `execute()`: (success, error, artifact)

#### Problem

`execute()` builds its results inline at each exit, producing five shapes: approval_required /
validation failure / execution_error (the corrective pair), non-completed (status + question),
completed (completion + popped + next_flow, sometimes + nlu_update), and the no-run exit (state
document only). The `manage_flows` description and the planner prompt must hedge about which
fields arrive when, and the PEX Agent reads results defensively.

#### Root Cause

Each exit path builds its own dict inline — and the result became a side channel for facts the
agent should get from the components themselves. `status`, `next_flow`, and `state` are stack
facts; `completion` and the nlu note are scratchpad entries; each was copied into the payload
because nothing else delivered them at the right moment.

#### Solution Contract

Ruled: three keys, nothing else.

```python
{'_success': bool,   # did the run produce a deliverable artifact
 '_error': str,      # failure class ('' on success): a Violation code, or
                     # 'validation' / 'approval_required' / 'server_error'
 'artifact': dict}   # compact projection of the run's TaskArtifact
```

Every policy has always produced a TaskArtifact — `call_policy` returns it and the World stores
it for display. The result just never carried it: `execute()` cherry-picked fields out of it
(`thoughts`, `blocks`) to keep the tool-result payload small. The projection replaces the
cherry-picking: `origin`, `thoughts`, block summaries (type + title), and, when present, the
`violation` and the approval prompt. The full artifact still goes to the World for display; the
agent sees the compact view.

Where every old key's job moves:

| old key | where the job moves |
|---|---|
| `_message` | Into the artifact. Error artifacts already carry the description in `thoughts`; a static code→text map would lose the specifics (which section, which tool), so the specifics ride the artifact and `_error` alone drives the agent's branch. `corrective()` keeps `_message` for plain tool failures inside skill loops — different surface, unchanged. |
| `status` | The round refresh — the live stack summary shows every flow's status each round. |
| `thoughts` | Inside `artifact`. |
| `blocks` | Inside `artifact`. |
| `question` | The round refresh renders `ambiguity.ask(...)`'s text whenever an ambiguity is pending — authored at reply time with the full view (5.2.3), never mid-run by one flow. |
| `nlu_update` | The unseen-entry digest in the round refresh. The name dies with the key; the rendering speaks in existing terms (`pred_flows` — the flows NLU predicted and stacked). |
| `completion` | The unseen-entry digest — completion entries are already scratchpad entries. |
| `popped` | Gone. `recently_finished` records it code-side; nothing read the key. |
| `next_flow` | The round refresh — a surfaced Pending top is visible in the stack summary. The turn-end invariant (never a Pending top at the boundary) stays a code-side check. |
| `state` | Gone. PEX holds the components; the no-run `manage_flows` result is a bare success ack. |

Two mechanisms make the cuts safe; they land with this theme:

1. **The round refresh.** `prepare()` already writes a turn-opening note; the same mechanism
   extends to every PEX Agent round. One code-rendered block carrying: (a) the live stack, top
   first, with statuses; (b) one-line digests of every scratchpad entry with `used_count == 0` —
   origin + summary; the render consumes them, so each appears exactly once; (c) the pending
   clarification question, when the Ambiguity Handler holds one. This answers "query everything
   unseen since the last update" without spending a tool round on it every turn: the digest is
   pushed, and the agent pulls full entries with `scratchpad op='read'` only when a digest line
   is not enough. The hook-3/5 nlu-note rendering (`_read_nlu_entry`, pex.py:750-771) and
   prepare's note become two moments of this one renderer.
2. **`used_count` is the seen-cursor** — already built (2.16): unseen means `used_count == 0`,
   and the read that renders a digest bumps it.

Edge paths covered without extra keys:

- **approval_required**: the security check already builds an approval artifact (its blocks carry
  the prompt) — that artifact IS the result's artifact.
- **invalid_stack**: dies as a corrective. The run itself succeeded; the non-Active surfaced top
  is the agent's to see in the next refresh and fix with `manage_flows`.

Net effect on rounds per turn: down, not up — no ask fetch (5.2.3), no post-completion
scratchpad pull (the digest is pushed), and smaller tool results.

#### Implementation

One result builder inside `execute()` (pex.py:619-726) that every exit path calls, plus the one
refresh renderer replacing `_read_nlu_entry` and extending `prepare()`'s note. `understand
op='read'` stays for on-demand full reads. Document the result shape and the refresh contents in
the `manage_flows` description and for_orchestrator.py.

### 5.2.6 — One wiring convention: routing, method names, op parameter

#### Problem

Three smaller inconsistencies make the surface harder to audit than it needs to be:

1. **Three routing mechanisms in `call_tool`** (pex.py:445-480): the `self.tools` dict for domain
   tools, a seven-branch elif chain for component tools, and the `_orchestrator_toolset` dict.
   Adding a tool means knowing which of the three to touch.
2. **Method names drift from tool names.** The convention is method = `_` + exposed name
   (`_manage_flows`, `_declare_ambiguity`), but several deviate: `_context_tool`,
   `_read_from_scratchpad`, `_understand_user`, `_ask_clarification`, `_save_findings_tool`.
3. **The op parameter has three names.** `manage_flows` and `understand` route on `op`;
   `coordinate_context` routes on `action`; `read_flow_stack` routed on `details`.

#### Root Cause

Tools were added one at a time and each brought its own wiring; no rule was ever written down.

#### Solution Contract

- One registry: component tool methods live in a single name→method dict, looked up the same way
  as `self.tools`; `call_tool` becomes lookup plus the existing error handling. The level menus
  (which tools and ops a caller sees) live in the definitions, not in the routing.
- One naming rule, stated in pex.py: **method = `_` + exposed tool name**, no exceptions. After
  this round: `_manage_flows`, `_understand`, `_view_policies`, `_scratchpad`,
  `_declare_ambiguity`, `_execution_error`, `_coordinate_context`, `_store_preference`.
- One op key on multi-op tools: `op` (`coordinate_context`'s `action` renames; `scratchpad` and
  `manage_flows` already use it). Sub-agent-only tools stay flat — `declare_ambiguity`,
  `execution_error`, and `view_policies` carry no op key at all.

#### Implementation

Fold the elif chain into the registry dict built in `__init__`; rename the deviating methods;
rename `action`→`op` in `coordinate_context`'s schema, method, and any skill docs that show the
call.

## Unresolved Issues

1. **Round refresh contents and cost.** The working choice pushes the full stack summary, the
   unseen-entry digests, and the pending question into every round. Worth one measurement pass
   before it becomes the baseline: tokens per round on a long turn, and whether digests need a
   cap (e.g. older lines collapse to a count).
2. **The sub-agent read tool's name.** `view_policies` is your proposal. One vocabulary check
   before it lands: the architecture map says the stack holds **flows** and a **policy** is the
   code that executes one — what the tool returns is the flow stack plus the active flow's
   slots, so `view_flows` may fit the vocabulary contract better. Either name works mechanically;
   flagging it only because the vocabulary doc is binding.

## Todo List

- [ ] **T1 — manage_flows at both levels** (5.2.1): delete `stackon_flow` / `fallback_flow`; one
  definition template, sub-agent menu limited to ops stackon/fallback with the defer sentence;
  defer rule + menu enforcement via the callable handed to sub-agents.
- [ ] **T2 — scratchpad tool** (5.2.2): one definition, ops read/append, both levels; sub-agent
  append defaults `origin` to the active flow; delete `save_findings` (definition, method,
  `call_tool` branch, two test refs); `append_entry` stamps `version`/`used_count`; amend takes
  `reset:bool=False`; delete the hand-stamping at all eleven sites (pex ×4, base ×1, research ×1,
  revise ×1, nlu ×4 — the review repair becomes an amend with explicit `reset`).
- [ ] **T3 — in-band ask** (5.2.3): `declare_ambiguity` untouched; delete
  `ask_clarification_question`; `prepare()`'s abstention note embeds NLU's question text; add the
  scorer alias so `expected_tools: ["handle_ambiguity"]` labels still match `declare_ambiguity`
  calls.
- [ ] **T4 — wire execution_error** (5.2.3): `call_tool` branch acknowledges; `call_policy` scans
  the traced calls and stamps `artifact.data['violation']` when the artifact has none.
- [ ] **T5 — two belief reads, one assembly** (5.2.4): delete `read_flow_stack`; add
  `view_policies` (flat, no params, scoped view; name pending Unresolved #2); `understand` stays
  PEX-only; one assembly helper replacing the three copies; drop `read_state`'s dead `params`.
- [ ] **T6 — three-key result + round refresh** (5.2.5): one builder returning
  `{_success, _error, artifact}` (artifact = compact projection incl. violation / approval
  prompt); delete the side-channel keys; extend `prepare()`'s note into the every-round refresh
  (live stack + unseen-entry digests + pending question), replacing `_read_nlu_entry`;
  `corrective()` keeps `_message` for plain tool calls only; document the shape and refresh in
  the `manage_flows` description and for_orchestrator.py.
- [ ] **T7 — wiring convention** (5.2.6): single tool registry in `call_tool`; rename methods to
  `_` + tool name; `action`→`op` on `coordinate_context`.
- [ ] **T8 — prompt/skill sync**: sweep `backend/prompts/pex/flows/*.md`, starters, support
  prompts, for_pex.py, and for_orchestrator.py for the deleted names (`stackon_flow`,
  `fallback_flow`, `ask_clarification_question`, `read_scratchpad`, `append_to_scratchpad`,
  `read_flow_stack`, `save_findings`) and the `action` op key; rewrite to the merged names and
  the in-band ask; grep to zero. (`declare_ambiguity` references stay — the tool keeps its name.)
- [ ] **T9 — tests**: update `pex_unit_tests.py` / `nlu_unit_tests.py` call sites and fixtures
  naming the old tools (moratorium: update or delete only); wire the `handle_ambiguity` label
  alias into the eval scorer. Run the three test files from the Hugo dir.

## Other

### Out of Scope

- `understand` op='think' (documented in pex.md's catalog, still unwired) — separate decision.
- `call_mcp` implementation (carried from 2.16's out-of-scope).
- Any change to which ops exist on `manage_flows` — this round moves surfaces, it does not
  redesign them.
- MEM's tool surface: `remember(op=x)` stays reserved; `store_preference` and `search_documents`
  keep their names. Skipped per ruling — MEM does not need to work perfectly yet.

### Verification

- Commit first. Live probes: (1) a sub-agent stacks a prerequisite through `manage_flows` and the
  flow re-surfaces at the PEX layer (the defer rule); (2) a skill calls `execution_error` and the
  turn ends with the error artifact, not a retry loop; (3) an NLU-abstention opener — the reply
  relays the question embedded in the prepare note; (4) a completed flow — the reply quotes the
  completion summary delivered by the refresh digest, with no extra scratchpad read.
- Replay canaries B03.C14 and B01.C13 — completion no worse than baseline.
- Grep sweeps: zero hits under `backend/` for `stackon_flow`, `fallback_flow`,
  `ask_clarification_question`, `read_scratchpad`, `append_to_scratchpad`, `read_flow_stack`,
  `save_findings`; zero hand-written `'used_count': 0` outside `session_scratchpad.py`.
- 229 deterministic tests green; restore `database/content` after the live probes.
