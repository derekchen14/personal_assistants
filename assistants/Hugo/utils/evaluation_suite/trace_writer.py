"""Structured trace artifacts for evaluation-suite live runs."""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from backend.modules.pex import _FALLBACK_MESSAGE
from utils.evaluation_suite.scoring import _CRASH_FALLBACK, _TIMEOUT

REPORT = Path(__file__).resolve().parent / 'report'


def make_report_path(prefix:str='traces') -> Path:
    REPORT.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return REPORT / f'{prefix}_{stamp}.jsonl'


def write_record(path:Path, record:dict):
    path.parent.mkdir(exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')


def belief_snapshot(agent) -> dict:
    state = agent.world.state
    return {
        'intent': state.pred_intent,
        'pred_flows': list(state.pred_flows or []),
        'confidence': state.confidence,
    }


def grounding_snapshot(agent) -> dict:
    grounding = agent.world.state.grounding or {}
    return {
        'choices': list(grounding.get('choices') or []),
        'notes': list(grounding.get('notes') or []),
        'entities': list(grounding.get('entities') or []),
    }


def ambiguity_snapshot(agent) -> dict:
    ambiguity = agent.world.ambiguity
    return {
        'present': bool(ambiguity.is_present),
        'level': ambiguity.get_level() if ambiguity.is_present else '',
        'metadata': dict(ambiguity.metadata or {}),
        'observation': ambiguity.observation or '',
    }


def flow_stack_snapshot(agent) -> list[dict]:
    return list(agent.world.flows.to_list())


def artifact_snapshot(result:dict) -> dict:
    artifact = result.get('artifact') or {}
    blocks = artifact.get('blocks') or []
    block_types = [
        block.get('type') or block.get('block_type') or block.get('kind')
        for block in blocks if isinstance(block, dict)
    ]
    return {
        'origin': artifact.get('origin', ''),
        'block_types': [kind for kind in block_types if kind],
        'has_content': bool(artifact.get('thoughts') or blocks or artifact.get('completion')),
    }


def message_preview(message:str, limit:int=180) -> str:
    text = ' '.join((message or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '...'


def diagnose_turn(completion_ok:bool, result:dict, expected_flow:str|None,
                  pred_flow:str|None, ambiguity_after:dict, expected_domain_tools:list,
                  actual_domain_tools:list, similarity:float,
                  flow_stack_after:list[dict]) -> str:
    if completion_ok:
        return 'completed'
    message = result.get('message') or ''
    if message == _TIMEOUT:
        return 'turn_timeout'
    if message == _CRASH_FALLBACK:
        return 'crash_fallback'
    if message == _FALLBACK_MESSAGE:
        return 'loop_fallback'
    if expected_flow and pred_flow and pred_flow != expected_flow:
        return 'wrong_belief'
    if ambiguity_after.get('present'):
        return 'ambiguity_pending'
    if expected_domain_tools and not actual_domain_tools:
        return 'no_domain_tools'
    if expected_domain_tools and similarity < 0.75:
        return 'tool_mismatch'
    if any(entry.get('status') in ('Active', 'Pending') for entry in flow_stack_after):
        return 'policy_incomplete'
    if not artifact_snapshot(result)['has_content']:
        return 'empty_artifact'
    return 'unknown'


def trace_record(case:dict, turn_index:int, user_turn_number:int, turn:dict, result:dict,
                 expected_actions:list, actual_domain_tools:list, all_tools:list,
                 completion_ok:bool, completion_reason:str, similarity:float,
                 latency_seconds:float, belief_before:dict, belief_after:dict,
                 flow_stack_after:list[dict], grounding_after:dict,
                 ambiguity_after:dict, diagnosis:str) -> dict:
    transcript = Path('database') / 'sessions' / case['convo_id'] / 'history.jsonl'
    return {
        'convo_id': case['convo_id'],
        'turn_index': turn_index,
        'user_turn_number': user_turn_number,
        'utterance': turn.get('utterance', ''),
        'expected_actions': list(expected_actions or []),
        'actual_domain_tools': list(actual_domain_tools or []),
        'all_tools': list(all_tools or []),
        'completion_ok': bool(completion_ok),
        'completion_reason': completion_reason,
        'tool_similarity': round(similarity, 4),
        'latency_seconds': round(latency_seconds, 2),
        'belief_before': belief_before,
        'belief_after': belief_after,
        'flow_stack_after': flow_stack_after,
        'grounding_after': grounding_after,
        'ambiguity_after': ambiguity_after,
        'artifact': artifact_snapshot(result),
        'message_preview': message_preview(result.get('message', '')),
        'transcript_path': str(transcript),
        'diagnosis': diagnosis,
    }


def diagnosis_counts(records:list[dict]) -> str:
    counts = Counter(record['diagnosis'] for record in records)
    return ' '.join(f'{name}={count}' for name, count in sorted(counts.items()))
