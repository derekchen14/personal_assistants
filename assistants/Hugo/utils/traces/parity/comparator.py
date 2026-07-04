"""Parity comparator — compares a NEW-pipeline run against an oracle fixture (changes.md §9.1).

The oracle fixtures under `utils/traces/parity/fixtures/` are recordings of the OLD
NLU→PEX→RES pipeline captured by `capture_oracle.py`. The old pipeline never re-runs for a
comparison: Phase 3/4 agents run the new orchestrator on the same scenario steps, then call
the three axis functions below.

Axes (changes.md §9.1):
  1. End-state DB checks — `compare_db_end_state(oracle['db_end_state'], post_id)`
  2. Grounding check     — `compare_grounding(oracle_turn, state.active_post)` per turn
  3. Utterance judge     — `judge_utterance(oracle_turn, new_utterance)` (stub until Phase 3)

Every axis returns a list of issue strings; empty list = parity on that axis.
"""

import json
import sys
from pathlib import Path

_HUGO_ROOT = Path(__file__).resolve().parents[3]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

FIXTURE_DIR = Path(__file__).parent / 'fixtures'


def load_fixture(scenario:str) -> dict:
    """Load the oracle fixture for one scenario ('vision' / 'observability' / 'voice')."""
    return json.loads((FIXTURE_DIR / f'{scenario}.json').read_text())


def capture_db_state(post_id:str) -> dict:
    """Snapshot the on-disk shape of one post: title, status, sections, outline shape."""
    from backend.utilities.services import PostService, PostNotFoundError
    svc = PostService()
    try:
        meta = svc.read_metadata(post_id, include_outline=True)
    except PostNotFoundError:
        return {'exists': False}
    sections = {}
    for sec_id in meta['section_ids']:
        sec = svc.read_section(post_id, sec_id)
        sections[sec_id] = sec['content'] if sec['_success'] else ''
    return {
        'exists': True, 'post_id': post_id, 'title': meta['title'], 'status': meta['status'],
        'section_ids': meta['section_ids'], 'outline_shape': _outline_shape(meta['outline']),
        'sections': sections,
    }


def _outline_shape(outline:str) -> dict:
    """Count outline structure per the 4 outline levels (AGENTS.md): ##, ###, '- ', '* '."""
    lines = [line.strip() for line in outline.split('\n')]
    return {
        'h2_count': sum(1 for line in lines if line.startswith('## ')),
        'h3_count': sum(1 for line in lines if line.startswith('### ')),
        'bullet_count': sum(1 for line in lines if line.startswith('- ')),
        'sub_bullet_count': sum(1 for line in lines if line.startswith('* ')),
    }


def compare_db_end_state(oracle_db:dict, post_id:str) -> list:
    """Axis 1 — end-of-scenario DB checks against the oracle. Exact on structure
    (title / status / section order / heading count), presence-only on LLM prose."""
    actual = capture_db_state(post_id)
    if not actual['exists']:
        return [f'post {post_id} missing on disk — oracle has it']
    issues = []
    if actual['title'] != oracle_db['title']:
        issues.append(f"title {actual['title']!r} != oracle {oracle_db['title']!r}")
    if actual['status'] != oracle_db['status']:
        issues.append(f"status {actual['status']!r} != oracle {oracle_db['status']!r}")
    if actual['section_ids'] != oracle_db['section_ids']:
        issues.append(f"section_ids {actual['section_ids']} != oracle {oracle_db['section_ids']}")
    if actual['outline_shape']['h2_count'] != oracle_db['outline_shape']['h2_count']:
        issues.append(f"h2_count {actual['outline_shape']['h2_count']} != "
                      f"oracle {oracle_db['outline_shape']['h2_count']}")
    if oracle_db['outline_shape']['bullet_count'] > 0 and \
            actual['outline_shape']['bullet_count'] == 0:
        issues.append('oracle outline has bullets but the new run has none')
    for sec_id, content in oracle_db['sections'].items():
        if content and not actual['sections'].get(sec_id, ''):
            issues.append(f'section {sec_id!r} is empty — oracle has content')
    return issues


def compare_grounding(oracle_turn:dict, active_post:str|None) -> list:
    """Axis 2 — the entity the turn acted on matches the oracle's grounded entity."""
    if active_post != oracle_turn['active_post']:
        return [f"step {oracle_turn['step']} [{oracle_turn['flow']}]: active_post "
                f"{active_post!r} != oracle {oracle_turn['active_post']!r}"]
    return []


_JUDGE_ENGINEER = None

_JUDGE_PROMPT = (
    'You are evaluating a blog writing assistant called Hugo. Two versions of the assistant\n'
    'replied to the same user turn. The ORACLE reply is from a trusted reference build; judge\n'
    'whether the NEW reply is task-adequate compared to it — NOT whether the wording matches.\n\n'
    'Task adequacy means the new reply does the same job: it answered the question the oracle\n'
    'answered, OR asked the right clarification, OR proposed the right next step. Different\n'
    'phrasing, length, or formatting is fine. It fails if it stalls on work the oracle\n'
    'completed, asks an unnecessary question, acts on the wrong thing, or reports a blocker\n'
    'instead of a result.\n\n'
    'The oracle build sometimes prints raw JSON or debug-shaped output where the new build\n'
    'speaks conversationally. NEVER require the new reply to reproduce the oracle\'s format,\n'
    'JSON structures, or exact metric values (both builds generate prose independently, so\n'
    'word counts and similar metrics legitimately differ) — judge only whether the same task\n'
    'outcome was achieved and clearly communicated.\n\n'
    'The user said:\n  "{user}"\n\n'
    'ORACLE reply:\n  "{oracle}"\n\n'
    'NEW reply:\n  "{new}"\n\n'
    'Reply ONLY with this exact format:\n'
    'adequate: pass OR fail — one line explanation\n'
)


def judge_utterance(oracle_turn:dict, new_utterance:str) -> list:
    """Axis 3 — LLM judge scoring `new_utterance` against the oracle's for task adequacy
    (changes.md §9.1): answered the question / asked the right clarification / proposed the
    right next step — not string equality. Returns issues; empty list = parity."""
    global _JUDGE_ENGINEER
    if _JUDGE_ENGINEER is None:
        from schemas.config import load_config
        from backend.components.prompt_engineer import PromptEngineer
        _JUDGE_ENGINEER = PromptEngineer(load_config())

    prompt = _JUDGE_PROMPT.format(user=oracle_turn['user'], oracle=oracle_turn['utterance'],
                                  new=new_utterance)
    try:
        raw_output = _JUDGE_ENGINEER(prompt, model='high', max_tokens=256)
    except Exception as ecp:  # noqa: BLE001 — judge availability must not crash the harness
        if 'RESOURCE_EXHAUSTED' not in str(ecp) and '429' not in str(ecp):
            return [f'judge error: {type(ecp).__name__}: {ecp}']
        try:  # canonical gemini-pro judge quota-blocked → secondary claude-opus-4-6 judge
            raw_output = _judge_fallback(prompt)
        except Exception as ecp2:  # noqa: BLE001
            return [f'judge error: {type(ecp2).__name__}: {ecp2}']
    lines = [line.strip() for line in raw_output.strip().split('\n') if line.strip()]
    # The judge occasionally drops the 'adequate:' prefix — find the verdict line either way.
    verdict = next((line for line in lines if line.lower().startswith('adequate:')), lines[0])
    if 'pass' in verdict.lower().split('—')[0]:
        return []
    return [f"step {oracle_turn['step']} [{oracle_turn['flow']}]: {verdict}"]


def _judge_fallback(prompt:str) -> str:
    """Secondary judge — claude-opus-4-6, the adjudication model already used to confirm
    Phase-4 verdicts — for when the canonical gemini-pro judge is quota-blocked."""
    messages = [{'role': 'user', 'content': prompt}]
    response = _JUDGE_ENGINEER._call_claude('', messages, 'claude-opus-4-6', max_tokens=256)
    return ''.join(block.text for block in response.content if block.type == 'text')
