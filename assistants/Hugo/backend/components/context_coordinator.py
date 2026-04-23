from __future__ import annotations

from datetime import datetime
from types import MappingProxyType


class Turn:

    def __init__(self, speaker:str, text:str, turn_type:str='utterance',
                 turn_id:int=0):
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
            return {
                'speaker': self.speaker,
                'text': self.text,
                'turn_id': self.turn_id,
                'turn_type': self.turn_type,
            }
        return f'{self.speaker}: {self.text}'


class ContextCoordinator:

    def __init__(self, config:MappingProxyType):
        self.config = config
        self._history: list[Turn] = []
        self._checkpoints: list[dict] = []
        self.recent: list[Turn] = []
        self.lookback_count: int = 7
        self.num_utterances: int = 0
        self.bookmark:int|None = None
        self.completed_flows: list[str] = []
        self.last_actions: dict[str, list[str]] = {}

    def add_turn(self, speaker:str, text:str, turn_type:str) -> Turn:
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

    def recent_turns(self, count:int=3) -> list[Turn]:
        """Return last n Turn objects."""
        return self._history[-count:]

    def get_turn(self, turn_id:int) -> Turn | None:
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
    def last_user_turn(self) -> Turn | None:
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

    def find_turn_by_id(self, turn_id:int, clearbookmark:bool=False) -> Turn | None:
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

    def find_action_by_name(self, action_name:str) -> Turn | None:
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
