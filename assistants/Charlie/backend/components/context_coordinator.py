import json
from datetime import datetime
from pathlib import Path

from backend.prompts.for_compressor import END_OF_SUMMARY, SUMMARY_PREFIX

# Hermes compactor defaults (changes.md §5.6, decision 9 — copied, not redesigned). The trigger
# threshold and the protected-tail size are config values read by the Agent post-hook; the rest
# mirrors Hermes's `agent/context_compressor.py` constants.
_PROTECT_HEAD = 3                    # Hermes protect_first_n — first messages kept verbatim
_SUMMARY_RATIO = 0.20                # summary budget as a share of the compressed middle
_MIN_SUMMARY_TOKENS = 2000           # Hermes floor
_MAX_SUMMARY_TOKENS = 12000          # Hermes ceiling
_CHARS_PER_TOKEN = 4                 # Hermes rough token estimate
_PRUNE_MIN_CHARS = 200               # tool results at or below this size are kept as-is
_PRUNED_TOOL_PLACEHOLDER = '[Old tool output cleared to save context space]'


def _is_tool_results(message:dict) -> bool:
    """True for the user-role message that carries a loop round's tool_result blocks."""
    content = message['content']
    return isinstance(content, list) and content[0]['type'] == 'tool_result'


def _estimate_tokens(messages:list[dict]) -> int:
    """Hermes's rough chars-per-token estimate over message contents."""
    chars = 0
    for message in messages:
        content = message['content']
        chars += len(content) if isinstance(content, str) else len(json.dumps(content, default=str))
    return chars // _CHARS_PER_TOKEN


class Turn:

    def __init__(self, speaker:str, text:str, turn_type:str='utterance', turn_id:int=0):
        self.speaker = speaker
        self.text = text
        self.turn_type = turn_type
        self.turn_id = turn_id
        self.timestamp = datetime.now().isoformat()
        self.is_revised = False
        self.original:str|None = None

    def action_target(self) -> tuple[str, str]:
        if '|' in self.text:
            parts = self.text.split('|', 1)
            return parts[0].strip(), parts[1].strip()
        return self.text, ''

    def add_revision(self, new_text:str):
        if not self.is_revised:
            self.original = self.text
        self.text = new_text
        self.is_revised = True

    def utt(self, as_dict:bool=False):
        if as_dict:
            turn = {'speaker': self.speaker, 'text': self.text, 'turn_id': self.turn_id, 'turn_type': self.turn_type}
        else:
            turn = f'{self.speaker}: {self.text}'
        return turn

class ContextCoordinator:

    def __init__(self, config):
        self.config = config
        self._history: list[Turn] = []
        self._checkpoints: list[dict] = []
        self.recent: list[Turn] = []
        self.lookback_count: int = 7
        self.num_utterances: int = 0
        self.bookmark:int|None = None
        self.completed_flows: list[str] = []
        self.last_actions: dict[str, list[str]] = {}
        self.messages: list[dict] = []
        self._messages_path: Path|None = None
        # Last compaction summary, kept for Hermes-style iterative updates (§5.6).
        self.previous_summary: str|None = None

    def add_turn(self, speaker:str, text:str, turn_type:str):
        turn = Turn(speaker, text, turn_type, turn_id=self.num_utterances)
        self._history.append(turn)
        if turn_type == 'utterance':
            self.num_utterances += 1
        if speaker != 'System' and turn_type == 'utterance':
            self.recent.append(turn)
            if len(self.recent) > self.lookback_count:
                self.recent.pop(0)
        return turn

    def compile_history(self, look_back:int=5, keep_system:bool=False) -> str:
        """Return recent conversation as a formatted string for prompt context."""
        if look_back > self.lookback_count and not keep_system:
            turns = self.recent[-look_back:]
        else:
            turns = self.full_conversation(keep_system=keep_system, as_turns=True)
            turns = turns[-look_back:]
        return '\n'.join(turn.utt() for turn in turns)

    def full_conversation(self, keep_system:bool=True, as_turns:bool=False) -> list:
        """Return all utterance turns as formatted strings or Turn objects."""
        allowed = {'User', 'Agent'}
        if keep_system:
            allowed.add('System')
        filtered = [turn for turn in self._history if turn.speaker in allowed]
        if as_turns:
            return filtered
        return [turn.utt() for turn in filtered]

    def get_turn(self, turn_id:int):
        for turn in self._history:
            if turn.turn_id == turn_id:
                return turn
        return None

    def save_checkpoint(self, label:str, data:dict|None=None):
        self._checkpoints.append({
            'label': label,
            'turn_count': len(self._history),
            'history_snapshot': [turn.utt(as_dict=True) for turn in self._history],
            'data': data or {},
        })

    def get_checkpoint(self, label:str) -> dict | None:
        for cp in reversed(self._checkpoints):
            if cp['label'] == label:
                return cp
        return None

    def reset(self):
        self._history.clear()
        self._checkpoints.clear()
        self.recent.clear()
        self.completed_flows.clear()
        self.last_actions.clear()
        self.num_utterances = 0
        self.bookmark = None
        self.messages.clear()
        self.previous_summary = None
        if self._messages_path is not None and self._messages_path.exists():
            self._messages_path.write_text('', encoding='utf-8')

    # ── Persistent message list (changes.md §5.5, decisions 6, 12) ─────
    # The API-shaped orchestrator transcript: user / assistant / tool-call / tool-result
    # messages in order, resumed every loop round and every turn. Turn records above stay
    # the human-readable view (compile_history is unchanged and feeds compression).

    def attach_messages(self, path):
        """Bind the message list to messages.jsonl in the session dir (path passed in from
        World). An existing file rehydrates the list; a fresh session starts empty."""
        self._messages_path = Path(path)
        if self._messages_path.exists():
            lines = self._messages_path.read_text(encoding='utf-8').splitlines()
            self.messages = [json.loads(line) for line in lines]

    def append_message(self, message:dict) -> dict:
        """Append one API-shaped message, mirroring it to messages.jsonl when attached
        (decision 12 — restart-safe resume; the raw transcript lands on disk). The session
        dir is created lazily on the first write, matching World.session_dir()."""
        self.messages.append(message)
        if self._messages_path is not None:
            self._messages_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._messages_path, 'a', encoding='utf-8') as file:
                file.write(json.dumps(message) + '\n')
        return message

    # ── Context compression (changes.md §5.6, decision 9 — the Hermes compactor) ──────
    # Copied strategy: prune old tool outputs (cheap, no LLM), protect the head and the
    # recent tail with tool pairs intact, summarize the middle on the cheap auxiliary model,
    # splice in ONE reference-only handoff message. The trigger (real prompt-token usage vs
    # the configured threshold) is checked by the Agent post-hook, never mid-loop.

    def compress_messages(self, summarize, protect_tail:int, prompt_tokens:int=0) -> bool:
        """Middle-out compaction of the persistent message list. `summarize(middle,
        previous_summary, budget)` is the auxiliary summarizer (LOW tier through
        PromptEngineer). A checkpoint records the compression event — Hugo's substitution
        for Hermes's session rotation. Returns True when a compaction happened."""
        before = len(self.messages)
        if before <= _PROTECT_HEAD + protect_tail + 1:
            return False
        start = self._align_forward(_PROTECT_HEAD)
        cut = self._anchor_last_user(self._align_backward(before - protect_tail))
        middle = self._middle_window(start, cut)
        if not middle:
            return False
        pruned = self._prune_tool_results(before - protect_tail)
        if pruned:
            self._rewrite_messages_file()  # keep the mirror consistent even if summarize fails
        budget = max(_MIN_SUMMARY_TOKENS,
                     min(int(_estimate_tokens(middle) * _SUMMARY_RATIO), _MAX_SUMMARY_TOKENS))
        summary = summarize(middle, self.previous_summary, budget)
        self.previous_summary = summary
        handoff = {'role': 'user', 'content': f'{SUMMARY_PREFIX}\n{summary}{END_OF_SUMMARY}'}
        self.messages = self.messages[:start] + [handoff] + self.messages[cut:]
        self._rewrite_messages_file()
        self.save_checkpoint('compression', data={
            'messages_before': before, 'messages_after': len(self.messages),
            'pruned_tool_results': pruned, 'prompt_tokens': prompt_tokens})
        return True

    def _align_forward(self, idx:int) -> int:
        """Slide the compress-start past tool results so the summarized region never begins
        mid tool group — the head keeps the whole assistant + results pair."""
        while idx < len(self.messages) and _is_tool_results(self.messages[idx]):
            idx += 1
        return idx

    def _align_backward(self, idx:int) -> int:
        """Pull the tail cut before a tool-result message so an assistant tool_use is never
        separated from its results (Hermes's pair-integrity boundary alignment)."""
        if _is_tool_results(self.messages[idx]):
            idx -= 1
        return idx

    def _anchor_last_user(self, cut:int) -> int:
        """The most recent real user utterance must stay in the protected tail; if the cut
        would summarize it away, the agent loses its active task (Hermes #10896)."""
        for idx in range(len(self.messages) - 1, _PROTECT_HEAD - 1, -1):
            content = self.messages[idx]['content']
            if self.messages[idx]['role'] == 'user' and isinstance(content, str) \
                    and not content.startswith(SUMMARY_PREFIX):
                return min(cut, idx)
        return cut

    def _middle_window(self, start:int, cut:int) -> list[dict]:
        """Messages to summarize. A handoff from an earlier compaction inside the window
        seeds the iterative update (Hermes's rehydration) and is never re-summarized."""
        if start >= cut:
            return []
        middle = self.messages[start:cut]
        for idx in range(len(middle) - 1, -1, -1):
            content = middle[idx]['content']
            if isinstance(content, str) and content.startswith(SUMMARY_PREFIX):
                if self.previous_summary is None:
                    body = content[len(SUMMARY_PREFIX):].removesuffix(END_OF_SUMMARY)
                    self.previous_summary = body.strip()
                return middle[idx + 1:]
        return middle

    def _prune_tool_results(self, boundary:int) -> int:
        """Hermes's cheap pre-pass (no LLM): tool results older than the protected tail are
        replaced with the pruning placeholder; tool_use blocks and pairing stay intact."""
        pruned = 0
        for message in self.messages[:boundary]:
            if not _is_tool_results(message):
                continue
            for block in message['content']:
                if len(block['content']) > _PRUNE_MIN_CHARS:
                    block['content'] = _PRUNED_TOOL_PLACEHOLDER
                    pruned += 1
        return pruned

    def _rewrite_messages_file(self):
        """Compression shrinks the list in place, so the append-only mirror is rewritten
        wholesale to keep messages.jsonl identical to memory (decision 12)."""
        if self._messages_path is None:
            return
        self._messages_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ''.join(json.dumps(message) + '\n' for message in self.messages)
        self._messages_path.write_text(lines, encoding='utf-8')

    @property
    def turn_count(self) -> int:
        return len(self._history)

    @property
    def turn_id(self) -> int:
        """Official turn counter across the conversation — the next utterance's
        turn_id. Used by scratchpad writes so findings can be dated precisely."""
        return self.num_utterances

    @property
    def last_user_text(self) -> str | None:
        for turn in reversed(self._history):
            if turn.speaker == 'User':
                return turn.text
        return None

    @property
    def last_user_turn(self):
        for turn in reversed(self._history):
            if turn.speaker == 'User':
                return turn
        return None

    # ── New methods ────────────────────────────────────────────────────

    def rewrite_history(self, revised:str):
        """Revise the most recent user utterance."""
        for turn in reversed(self._history):
            if turn.speaker == 'User' and turn.turn_type == 'utterance':
                turn.add_revision(revised)
                return

    def setbookmark(self, speaker:str=''):
        """Set bookmark to the most recent turn_id, optionally filtered by speaker."""
        for turn in reversed(self._history):
            if not speaker or turn.speaker == speaker:
                self.bookmark = turn.turn_id
                return

    def find_turn_by_id(self, turn_id:int, clearbookmark:bool=False):
        for turn in self._history:
            if turn.turn_id == turn_id:
                if clearbookmark:
                    self.bookmark = None
                return turn
        return None

    def contains_keyword(self, keyword:str, look_back:int=3) -> bool:
        """Check recent turns for a keyword (splits on space/hyphen/underscore)."""
        tokens = set()
        for sep in (' ', '-', '_'):
            tokens.update(keyword.lower().split(sep))
        tokens.discard('')
        for turn in self.recent[-look_back:]:
            text_lower = turn.text.lower()
            if any(token in text_lower for token in tokens):
                return True
        return False

    def storecompleted_flows(self, completed_flows:list[str]):
        self.completed_flows = list(completed_flows)

    def find_action_by_name(self, action_name:str):
        """Reverse scan history for action turns matching name."""
        for turn in reversed(self._history):
            if turn.turn_type == 'action' and action_name in turn.text:
                return turn
        return None

    def actions_include(self, target_actions:list[str], speaker:str='Agent') -> bool:
        actions = self.last_actions.get(speaker, [])
        return any(act in actions for act in target_actions)

    def add_actions(self, actions:list[str], actor:str):
        self.last_actions[actor] = []
        for action in actions:
            turn = self.add_turn(actor, action, turn_type='action')
            self.last_actions[actor].append(action)

    def revise_user_utterance(self, turns_back:int):
        """Truncate history to the nth-back user turn and rebuild recent."""
        user_turns = [turn for turn in self._history if turn.speaker == 'User'
                      and turn.turn_type == 'utterance']
        if turns_back > len(user_turns):
            return
        target = user_turns[-turns_back]
        index = self._history.index(target)
        self._history = self._history[:index]
        self._rebuild_recent()

    def _rebuild_recent(self):
        self.recent.clear()
        for turn in self._history:
            if turn.speaker != 'System' and turn.turn_type == 'utterance':
                self.recent.append(turn)
        if len(self.recent) > self.lookback_count:
            self.recent = self.recent[-self.lookback_count:]
