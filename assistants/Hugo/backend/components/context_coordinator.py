import json
import logging
from datetime import datetime
from pathlib import Path

from backend.prompts.for_compactor import END_OF_SUMMARY, SUMMARY_PREFIX
from utils.helper import dax2flow

log = logging.getLogger(__name__)

# Compactor defaults. The trigger threshold and the protected-tail size are config values read
# by the Agent post-hook; the rest are the compaction constants. Sizes count TURNS (round 6.1).
_PROTECT_HEAD = 3                    # first turns kept verbatim
_SUMMARY_RATIO = 0.20                # summary budget as a share of the compressed middle
_MIN_SUMMARY_TOKENS = 2000           # summary floor
_MAX_SUMMARY_TOKENS = 12000          # summary ceiling
_CHARS_PER_TOKEN = 4                 # rough token estimate
_PRUNE_MIN_CHARS = 200               # tool results at or below this size are kept as-is
_PRUNED_TOOL_PLACEHOLDER = '[Old tool output cleared to save context space]'


class Turn:
    """One event in the history with `content` as the main dict holding the most critical info
    turn_type (utterance, action) x role (user, agent, system) = 6 kinds of turns.
    The role is a speaker on an utterance and an actor on an action
    """
    def __init__(self, role:str, turn_type:str, content:dict, turn_id:int=0):
        self.role = role                # user, agent, or system
        self.turn_type = turn_type      # utterances or action
        self.content = content
        self.turn_id = turn_id
        self.timestamp = datetime.now().isoformat()

    @property
    def text(self) -> str:
        return self.content['text']

    def action_target(self) -> tuple[str, str]:
        if '|' in self.text:
            parts = self.text.split('|', 1)
            return parts[0].strip(), parts[1].strip()
        return self.text, ''

    def utt(self, as_dict:bool=False):
        if as_dict:
            return self.to_dict()
        return f'{self.role.capitalize()}: {self.text}'

    def to_dict(self) -> dict:
        return {'role': self.role, 'turn_type': self.turn_type, 'turn_id': self.turn_id,
                'timestamp': self.timestamp, 'content': self.content}


class ContextCoordinator:
    """L1 — the append-only event stream and the session's single source of truth. Three read
    surfaces, one per consumer: full_conversation() (every turn, all kinds), compile_history()
    (utterances for prompts), and compile_messages() (the on-demand API projection for the PEX
    agent). Turns persist to history.jsonl; compaction only appends (a summary turn plus an
    event turn) and the projection applies the skip range at render time."""

    def __init__(self, config):
        self.config = config
        self.protect_tail = config.get('compaction', {}).get('protect_tail', 20)
        self._history: list[Turn] = []
        self.num_utterances: int = 0
        self._history_path: Path|None = None
        # Last compaction summary, kept for iterative summary updates.
        self.previous_summary: str|None = None

    # ── Writes ─────

    def add_turn(self, role:str, content:dict, turn_type:str='utterance') -> Turn:
        log.info(f"{role.upper()} ({turn_type}): {content['text']}")
        turn = Turn(role, turn_type, content, turn_id=self.num_utterances)
        self._history.append(turn)
        if turn_type == 'utterance' and role in ('user', 'agent'):
            self.num_utterances += 1
        self._write_line(turn)
        return turn

    def save_checkpoint(self, label:str, data:dict|None=None, text:str=''):
        """A checkpoint is a named marker at a position in the stream — never a copy of it:
        history as of the checkpoint is the slice of turns up to its turn_id."""
        content = {'text': text or f'checkpoint: {label}', 'activity': 'checkpoint',
                   'result': {'label': label, 'turn_id': self.turn_id, 'data': data or {}}}
        return self.add_turn('system', content, turn_type='action')

    def get_checkpoint(self, label:str) -> dict | None:
        for turn in reversed(self._history):
            if turn.turn_type == 'action' and turn.role == 'system' \
                    and turn.content.get('activity') == 'checkpoint' \
                    and turn.content['result']['label'] == label:
                return turn.content['result']
        return None

    def rewrite_history(self, revised:str):
        """Revise the most recent user utterance — append-only, like compaction: a kind-5 turn
        holds the revised text, a kind-6 revision event points views at it, and the original
        turn is unchanged."""
        for idx in range(len(self._history) - 1, -1, -1):
            turn = self._history[idx]
            if turn.role == 'user' and turn.turn_type == 'utterance':
                self.add_turn('system', {'text': revised})
                self.add_turn('system', {'text': f'Revised turn {idx}.', 'activity': 'revision',
                    'result': {'target': idx, 'revised_index': len(self._history) - 1}},
                    turn_type='action')
                return

    def reset(self):
        self._history.clear()
        self.num_utterances = 0
        self.previous_summary = None
        if self._history_path is not None and self._history_path.exists():
            self._history_path.write_text('', encoding='utf-8')

    # ── The three read surfaces ─────

    def full_conversation(self, as_turns:bool=False) -> list:
        """Every turn, all six kinds, in order — the raw view."""
        if as_turns:
            return list(self._history)
        return [turn.utt() for turn in self._history]

    def compile_history(self, look_back:int=5, keep_system:bool=False) -> str:
        """The human-readable prompt window: user and agent utterances (plus system
        utterances when keep_system), rendered 'Role: text' with revisions applied."""
        revised, hidden = self._revision_map()
        allowed = {'user', 'agent'} | ({'system'} if keep_system else set())
        lines = []
        for idx, turn in enumerate(self._history):
            if idx in hidden or turn.turn_type != 'utterance' or turn.role not in allowed:
                continue
            text = self._history[revised[idx]].text if idx in revised else turn.text
            lines.append(f'{turn.role.capitalize()}: {text}')
        return '\n'.join(lines[-look_back:])

    def compile_messages(self) -> list[dict]:
        """The API projection for the PEX agent, computed on demand: per-kind rendering, the
        latest compaction's summary spliced over its skip range, revisions applied, old tool
        results rendered as the pruning placeholder."""
        skip, splice_start, summary_index = self._compaction_plan()
        revised, hidden = self._revision_map()
        messages = []
        for idx in range(len(self._history)):
            if idx == splice_start:
                messages.append({'role': 'user', 'content': self._history[summary_index].text})
            if idx in skip or idx in hidden:
                continue
            if idx in revised:  # revision targets are always user utterances
                messages.append({'role': 'user', 'content': self._history[revised[idx]].text})
                continue
            messages.extend(self._render_turn(idx))
        return messages

    # ── Projection internals ─────

    def _revision_map(self) -> tuple[dict, set]:
        """Revision events, append-only like compaction: target index → revised-text index,
        plus the revised-text turns to hide at their own position."""
        revised, hidden = {}, set()
        for turn in self._history:
            if turn.turn_type == 'action' and turn.role == 'system' \
                    and turn.content.get('activity') == 'revision':
                result = turn.content['result']
                revised[result['target']] = result['revised_index']
                hidden.add(result['revised_index'])
        return revised, hidden

    def _compaction_plan(self) -> tuple[set, int|None, int|None]:
        """Skip set and splice point from the kind-6 compaction events. Summaries chain
        iteratively (each new one folds in previous_summary), so only the LATEST summary is
        emitted; every earlier summary turn is skipped outright."""
        skip, splice_start, summary_index = set(), None, None
        for turn in self._history:
            if turn.turn_type == 'action' and turn.role == 'system' \
                    and turn.content.get('activity') == 'compaction':
                result = turn.content['result']
                skip.update(range(result['start'], result['cut']))
                skip.add(result['summary_index'])
                splice_start, summary_index = result['start'], result['summary_index']
        return skip, splice_start, summary_index

    def _render_turn(self, idx:int) -> list[dict]:
        """One turn's API messages. Kind 6 is invisible to the model; a kind-4 turn emits the
        assistant round and, when tools ran, the paired results message."""
        turn = self._history[idx]
        content = turn.content
        if turn.turn_type == 'utterance':
            if turn.role == 'agent':
                return [{'role': 'assistant', 'content': content['text']}]
            return [{'role': 'user', 'content': content['text']}]
        if turn.role == 'user':
            return [{'role': 'user', 'content': _decorate_click(content)}]
        if turn.role == 'agent':
            if not content['tool_uses']:
                return [{'role': 'assistant', 'content': content['text']}]
            blocks = [{'type': 'text', 'text': content['text']}] if content['text'] else []
            messages = [{'role': 'assistant', 'content': blocks + content['tool_uses']}]
            results = content['tool_results']
            if idx < len(self._history) - self.protect_tail:  # pruning is a rendering rule
                results = [{**block, 'content': _PRUNED_TOOL_PLACEHOLDER}
                           if len(block['content']) > _PRUNE_MIN_CHARS else block
                           for block in results]
            messages.append({'role': 'user', 'content': results})
            return messages
        return []  # system action — activities never reach the model

    # ── Storage: history.jsonl ─────

    def load_history(self, path):
        """Bind the store to history.jsonl in the session dir (path passed in from World) and
        load it: an existing file rebuilds the turn list; a fresh path stays lazy — the first
        write flushes everything, so disk matches memory from then on."""
        self._history_path = Path(path)
        if not self._history_path.exists():
            return
        self._history = []
        for line in self._history_path.read_text(encoding='utf-8').splitlines():
            entry = json.loads(line)
            turn = Turn(entry['role'], entry['turn_type'], entry['content'], entry['turn_id'])
            turn.timestamp = entry['timestamp']
            self._history.append(turn)
        self.num_utterances = sum(1 for turn in self._history
                                  if turn.turn_type == 'utterance'
                                  and turn.role in ('user', 'agent'))
        for turn in reversed(self._history):  # newest summary seeds the iterative update
            if turn.turn_type == 'utterance' and turn.role == 'system' \
                    and turn.text.startswith(SUMMARY_PREFIX):
                body = turn.text[len(SUMMARY_PREFIX):].removesuffix(END_OF_SUMMARY)
                self.previous_summary = body.strip()
                break

    def _write_line(self, turn:Turn):
        """Strictly append-only — the first write flushes any pre-attach turns (the seed), and
        nothing ever rewrites the file (revisions and compactions append)."""
        if self._history_path is None:
            return
        if not self._history_path.exists():
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            lines = ''.join(json.dumps(entry.to_dict(), default=str) + '\n'
                            for entry in self._history)
            self._history_path.write_text(lines, encoding='utf-8')
            return
        with open(self._history_path, 'a', encoding='utf-8') as file:
            file.write(json.dumps(turn.to_dict(), default=str) + '\n')

    # ── Context compaction ─────
    # Strategy: protect the head and the recent tail, summarize the middle on the cheap
    # auxiliary model, and APPEND a kind-5 summary turn plus a kind-6 compaction event — the
    # projection splices the summary and skips the range at render time, so nothing is
    # destroyed. Kind-4 turns hold their tool calls and results together, so a boundary can
    # never split a pair. The trigger (real prompt-token usage vs the configured threshold)
    # is checked by the Agent post-hook, never mid-loop.

    def compact_messages(self, summarize, protect_tail:int, prompt_tokens:int=0) -> bool:
        """Middle-out compaction over the visible turns. `summarize(middle, previous_summary,
        budget)` is the auxiliary summarizer (LOW tier through PromptEngineer). Returns True
        when a compaction happened."""
        skip = self._compaction_plan()[0]
        visible = [idx for idx in range(len(self._history)) if idx not in skip]
        if len(visible) <= _PROTECT_HEAD + protect_tail + 1:
            return False
        start = visible[_PROTECT_HEAD]
        cut = visible[-protect_tail]
        last_user = next((idx for idx in reversed(visible)
                          if self._history[idx].role == 'user'
                          and self._history[idx].turn_type == 'utterance'), None)
        if last_user is not None:  # the newest user utterance must stay out of the summary
            cut = min(cut, last_user)
        middle = [idx for idx in visible if start <= idx < cut]
        if not middle:
            return False
        rendered = [message for idx in middle for message in self._render_turn(idx)]
        budget = max(_MIN_SUMMARY_TOKENS,
                     min(int(_estimate_tokens(rendered) * _SUMMARY_RATIO), _MAX_SUMMARY_TOKENS))
        summary = summarize(rendered, self.previous_summary, budget)
        self.previous_summary = summary
        self.add_turn('system', {'text': f'{SUMMARY_PREFIX}\n{summary}{END_OF_SUMMARY}'})
        self.add_turn('system', {
            'text': f'Compacted turns {start}-{cut} into a summary.', 'activity': 'compaction',
            'result': {'start': start, 'cut': cut, 'summary_index': len(self._history) - 1,
                       'prompt_tokens': prompt_tokens}}, turn_type='action')
        return True

    # ── Lookups ─────

    def get_turn(self, turn_id:int):
        for turn in self._history:
            if turn.turn_id == turn_id:
                return turn
        return None

    def contains_keyword(self, keyword:str, look_back:int=3) -> bool:
        """Check recent utterances for a keyword (splits on space/hyphen/underscore)."""
        tokens = set()
        for sep in (' ', '-', '_'):
            tokens.update(keyword.lower().split(sep))
        tokens.discard('')
        turns = [turn for turn in self._history
                 if turn.turn_type == 'utterance' and turn.role != 'system']
        for turn in turns[-look_back:]:
            text_lower = turn.text.lower()
            if any(token in text_lower for token in tokens):
                return True
        return False

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
            if turn.role == 'user':
                return turn.text
        return None

    @property
    def last_user_turn(self):
        for turn in reversed(self._history):
            if turn.role == 'user':
                return turn
        return None


def _decorate_click(content:dict) -> str:
    """Render a kind-2 click turn as the model-facing user message."""
    dax, payload, text = content['dax'], content['payload'], content['text']
    if not text.strip():
        return f'[click] dax={dax} flow={dax2flow(dax)} payload={json.dumps(payload, default=str)}'
    return (f'[action] This turn arrived with a resolved flow: {dax2flow(dax)!r} '
            f'(dax {dax}, payload {payload}). Do not re-decide the click — build on it.\n{text}')


def _estimate_tokens(messages:list[dict]) -> int:
    """Rough chars-per-token estimate over message contents."""
    chars = 0
    for message in messages:
        content = message['content']
        chars += len(content) if isinstance(content, str) else len(json.dumps(content, default=str))
    return chars // _CHARS_PER_TOKEN
