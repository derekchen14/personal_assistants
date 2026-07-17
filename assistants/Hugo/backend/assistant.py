from __future__ import annotations

import json
import logging
import threading
from datetime import datetime

from schemas.config import load_config
from backend.modules.nlu import NaturalLanguageUnderstanding
from backend.modules.pex import PolicyExecutor, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE
from backend.modules.mem import MemoryExtensionModule
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
from backend.prompts.for_orchestrator import build_orchestrator_prompt

log = logging.getLogger(__name__)

# _FALLBACK_MESSAGE / _NUDGE_MESSAGE / _WRAP_UP_MESSAGE are re-exported from PEX (the acting loop
# moved there) so callers importing them from backend.assistant keep working.


class Assistant:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None
        self.system_prompt: str | None = None

        self.engineer = PromptEngineer(self.config)
        self.nlu = NaturalLanguageUnderstanding(self.config, self.engineer)
        self.pex = PolicyExecutor(self.config, self.engineer)
        self.mem = MemoryExtensionModule(self.config, self.engineer, username)

        self.world = World(self.config, self.nlu, self.pex, self.mem)
        self.nlu.world = self.world
        self.pex.world = self.world
        self.mem.world = self.world

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        """The threaded turn (round 3.4). Two lanes: NLU's thinking (check → detect_flows →
        fill_slots → validate) runs on a worker thread; PEX's acting loop runs on main. No
        stack lock — whichever lane stacks first, the other converges (same-type dedupe, or
        the hook 3/5 scratchpad read). The click path stays synchronous: `_execute_click`
        activates the flow react stacked, so react must finish first. An NLU crash is stored
        and re-raised at the join, landing in this method's safety net; MEM stores the turn
        at the end."""
        try:
            self._ensure_session()
            turn_type = 'action' if dax else 'utterance'
            self.world.context.add_turn('User', text, turn_type=turn_type)
            log.info('USER (%s): %s', turn_type, text)

            # Round 3.3: an open ambiguity persists across turns until NLU's check() clears it.
            # Only the per-turn ask counts reset on a new user turn.
            self.world.ambiguity.counts = dict.fromkeys(self.world.ambiguity.counts, 0)

            nlu_thread, nlu_error = None, []
            if dax:      # click: react is synchronous, belief lands before PEX
                self.nlu.react(dax, payload or {})
                self.world.nlu_done.set()
            else:
                # NLU 1: the fast synchronous System-1 intent both lanes read (T16). A failed
                # call stores '' so the Plan/Clarify gate and Continue narrowing stay quiet.
                self.nlu.dialogue_state.classify_intent(self.engineer, self.world.context, text)
                self.world.nlu_done.clear()
                def run_nlu():
                    try:
                        self.nlu.think(text, payload or {})
                    except Exception as ecp:  # noqa: BLE001 — stored, re-raised at the join
                        nlu_error.append(ecp)
                    finally:
                        self.world.nlu_done.set()  # PEX's waits always wake, even on a crash
                nlu_thread = threading.Thread(target=run_nlu, daemon=True)
                nlu_thread.start()

            # The utterances enter the Context Coordinator here — the Assistant is a thin
            # wrapper handing the raw turn over; the coordinator builds the message (the
            # [click]/[action] decoration is MEM's job, Unresolved 3). PEX appends only its
            # working transcript (tool blocks, results, notes).
            self.world.context.append_user_message(text, dax or '', payload)

            # turn_start scopes the contemplate read below (>= — tool-log turns advance
            # turn_id mid-loop, so equality would never match).
            turn_start = self.world.context.turn_id
            utterance = self.pex.execute(self.system_prompt, dax=dax, payload=payload, text=text)

            if nlu_thread:
                nlu_thread.join()          # a turn never ends with NLU mid-write
                if nlu_error:
                    raise nlu_error[0]

            # 3.4.7: PEX queued a re-route request — the Assistant calls NLU (modules never
            # reach each other), then re-enters PEX once. The re-detected flow is on the stack.
            requests = self.world.scratchpad.read(origin='orchestrator', keys=['request'])
            if any(entry['request'] == 'contemplate' and entry['turn_number'] >= turn_start
                   for entry in requests):
                self.nlu.contemplate(text)
                self.world.context.append_message({'role': 'assistant', 'content': utterance})
                self.world.context.append_message({'role': 'user', 'content': '[contemplate] '
                    'NLU re-routed the stalled flow; act on the stack as it stands.'})
                completed = self.pex.completed_this_turn  # prepare() resets it on re-entry
                utterance = self.pex.execute(self.system_prompt, text='[contemplate] NLU '
                    're-routed the stalled flow; act on the stack as it stands.')
                self.pex.completed_this_turn = completed + self.pex.completed_this_turn

            self.world.context.append_message({'role': 'assistant', 'content': utterance})
            self.mem.recap(utterance, self.pex.last_prompt_tokens, self.pex.completed_this_turn)
            log.info('AGENT: %s', utterance[:256])
            return self._build_payload(utterance, self.world.latest_artifact())
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn crashed: %s', ecp)
            return self._fallback_response("Something went wrong on my end. Please try again.")

    def _ensure_session(self):
        """Orchestrator session start. Runs once per session: bind a session dir when
        none is open (the dir IS the persistence format), bind the shared scratchpad to the
        session's scratchpad.jsonl so completion entries land on disk, then build
        and FREEZE the three-tier system prompt."""
        if self.system_prompt is not None:
            return
        if self.world.conversation_id is None:
            self.world.open_session(datetime.now().strftime(f'{self.username}_%Y%m%d_%H%M%S'))
        # The shared scratchpad (owned by the World; seen by NLU/PEX/policies) is bound to the
        # session's file so completion entries land on disk.
        self.world.scratchpad._scratchpad_path = self.world.session_dir() / 'scratchpad.jsonl'
        state = self.world.state
        state.conversation_id = self.world.conversation_id
        state.username = self.username
        self.system_prompt = build_orchestrator_prompt(
            self.engineer, self.mem, self.world.conversation_id, self.username,
            datetime.now().strftime('%Y-%m-%d'))

    def _fallback_response(self, message: str) -> dict:
        self.world.context.add_turn('Agent', message, turn_type='agent_response')
        payload = {'message': message, 'actions': [], 'artifact': None, 'block': 'default'}
        return payload

    def _build_payload(self, utterance: str, artifact: TaskArtifact) -> dict:
        return {'message': utterance, 'actions': [], 'artifact': artifact.to_dict()}

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.world.ambiguity.resolve()
        self.conversation_id = None
        self.system_prompt = None  # next session rebuilds + refreezes

    def close(self):
        pass
