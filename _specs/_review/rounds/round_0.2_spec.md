# Round 0.2 — World wiring: modules own components, calls dot through the World

Status: **shipped 2026-07-08** (commit `9c124bb`), built directly with Derek iterating live — no
agent swarm. Deterministic tests are parked by decision (the suites were coverage theatre against a
turn loop that could not run E2E); they come back once the sequential turn loop lands.

Follows [[round_0.1_spec.md]] (the component taxonomy). This round makes the ownership real in code.

## The design (as decided)

1. **Modules construct and own their components.** NLU builds `ambiguity_handler` +
   `dialogue_state`; PEX builds `flow_stack` + `session_scratchpad`; MEM builds
   `context_coordinator` + `user_preferences` + `business_knowledge`. Module classes spell their
   names out (`NaturalLanguageUnderstanding`, `PolicyExecutor`, `MemoryExtensionModule`) with short
   aliases (`NLU` / `PEX` / `MEM`); the Assistant class is `Assistant` (`backend/assistant.py`,
   renamed from `agent.py`) — Assistant / Module / agent / sub-agent is the terminology ladder.
2. **The World holds the shared component references only** — one canonical name each: `state`,
   `ambiguity`, `flows`, `scratchpad`, `context`, `prefs`, `knowledge` — plus the artifacts list and
   the session-dir lifecycle. The World holds NO module handles, and modules never hold each other.
   A cross-module call dots THROUGH the world into the component directly:
   `self.world.state.read_state()`, `self.world.knowledge.search_documents()`.
3. **Never rebind — mutate in place.** ONE `DialogueState` and ONE `FlowStack` persist for the
   Assistant's lifetime; a new session calls `reset()` on every component (`world.reset()` fans
   out). Python references make sharing free; rebinding is the only way to break it, so rebinding
   is banned. The World's list of states is gone (`current_state()` / `insert_state` deleted);
   the history of past predictions is MEM's record on disk, not objects in memory.
   `DialogueState.load` remains only as MEM's throwaway read of a past session's file.
4. **PEX never invokes the NLU module.** `think` / `react` / `contemplate` are module behavior and
   only the Assistant calls modules. When PEX "wants NLU to do something," it invokes the
   component: belief reads via `world.state`, clarification questions via `world.ambiguity.ask`,
   internal recovery via `world.ambiguity.recover(world.prefs, world.scratchpad)`.
5. **Code-only NLU and MEM (direction, partially landed).** Both modules run as deterministic code
   plus plain LLM predictions — no agent loop, no tool-calling. Only PEX has an agent. The
   remaining piece (removing the NLU thread from `take_turn`) is the next round's work.

## Construction order (Assistant.__init__)

```python
self.engineer = PromptEngineer(self.config)
self.nlu = NaturalLanguageUnderstanding(self.config, self.engineer)
self.pex = PolicyExecutor(self.config, self.engineer)
self.mem = MemoryExtensionModule(self.config, self.engineer)
self.world = World(self.config, self.nlu, self.pex, self.mem)   # pulls the component refs
self.nlu.world = self.world
self.pex.world = self.world   # property setter also wires search_documents + the policies
self.mem.world = self.world
```

PEX's `world` is a property: assigning it finishes the wiring (the `search_documents` tool binds to
`world.knowledge`, and the policies are built with their scoped components dict — sub-agents get the
narrow dict, never the whole world). No module touches a foreign component during construction.

## What changed (by file)

- `backend/components/world.py` — component registry + session lifecycle only; `reset()` resets
  every component in place; `open_session` binds dirs (no reload — reading past sessions is MEM's).
- `backend/components/dialogue_state.py` — `DialogueState(config)`; `reset()` clears every field
  in place; duplicate partial `reset` removed; `load` re-documented as MEM's read.
- `backend/components/flow_stack/stack.py` — `reset()` added (clear in place); depth cap from
  `config['session']['max_flow_depth']` (Derek).
- `backend/components/memory_manager.py` — `MemoryExtensionModule` constructs its three components.
- `backend/components/business_knowledge.py` — renamed from business_context/business_documents;
  class `BusinessKnowledge`; the L3 read stays `search_documents`.
- `backend/modules/nlu.py` — owns ambiguity_handler + dialogue_state; foreign access via world
  (`world.flows`, `world.scratchpad`, `world.prefs`, `world.context`); `attempt_recovery` calls the
  ambiguity component with world-bound references.
- `backend/modules/pex.py` — owns flow_stack + session_scratchpad; `understand` tool is READ-ONLY
  (`op='read'`); the post-failure hook re-arms the belief note instead of calling contemplate; the
  recover tool is direct component calls and returns `recovery: None` on a miss (fixing the
  missing-name-as-value confusion); dead `components['memory']` dropped from policies.
- `backend/assistant.py` — the construction order above; ambiguity pre-hook via `world.ambiguity`.
- `backend/manager.py` + `backend/routers/chat_service.py` — Assistant naming; chat_service's
  state REBIND (fresh `DialogueState` + `insert_state`) replaced with in-place mutation.

## Consequences to know

- **Mid-turn re-detection is gone.** PEX can no longer trigger `contemplate`; a stalled flow
  surfaces its clarification (or recovers internally from memory), and re-detection is the
  Assistant's move on the next turn. This is deliberate under code-only NLU; the sequential turn
  loop decides where re-detection lives.
- The `understand` tool schema shrank to `op='read'`; `ask_clarification_question` and
  `recover_from_ambiguity` are the ambiguity channels.
- Smoke verification (in place of the parked suites): Assistant constructs; `world.state is
  nlu.dialogue_state`; `world.flows is pex.flow_stack`; `world.reset()` preserves object identity;
  all backend imports (webserver included) load.

## Deferred (the next rounds)

1. **Sequential turn loop** — remove `Thread` from `take_turn` and `_nlu_thread`/`_check_nlu` from
   PEX; implement the PEX-first turn order (System-1 intent, NLU think with the stack-top hint,
   Plan/Clarify await the belief); one scripted 3-turn E2E conversation as the smoke test.
2. **MEM store step** — the end-of-turn record (turn, state snapshot, deterministic promotion
   check); preferences persistence (L2 must survive the session).
3. **Tests** — rebuild the suites against the wired architecture once the turn loop runs E2E.
