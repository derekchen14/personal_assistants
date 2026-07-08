"""TypeSafe flow-detection helper.

TypeSafe (docs: `utils/typesafe/SKILL.md`) is a non-LLM decision model: it evaluates a `document`
against typed `questions` and returns typed answers your code acts on directly. Flow detection is a
single **Choice** question — pick one flow from the 18-flow ontology — so the whole decision is one
call with no JSON to coax out of a prose reply.

`model_tests.py` imports `predict_flow` for its `--provider typesafe` path; the derivation of
conversation history + active post stays there, mirroring the LLM path. Key from `TYPESAFE_API_KEY`.
"""
import os

import requests

from schemas.ontology import FLOW_ONTOLOGY

_ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
_MODEL = 'speed_latest'
_QUESTION = 'Which flow best captures what the user wants on their latest turn?'


def _flow_criteria() -> dict:
    """Option value → rubric for every flow the model may pick: the 18-flow menu (16 policy flows +
    plan {29D} + clarify {09F}), descriptions straight from FLOW_ONTOLOGY so the two surfaces agree."""
    return {name: cat['description'] for name, cat in FLOW_ONTOLOGY.items()}


def _api_key() -> str:
    key = os.getenv('TYPESAFE_API_KEY')
    if not key:
        raise RuntimeError('TYPESAFE_API_KEY not set. Add it to .env or environment.')
    return key


def predict_flow(convo_history:str, user_text:str, active_post:dict|None=None,
                 ontology:str='', examples:str='') -> tuple[str, float]:
    """One TypeSafe Choice call — which flow fits the latest user turn, given the conversation so far.
    Returns `(chosen flow_name, confidence)` — the calibrated confidence TypeSafe derives from its
    probability distribution over the 18 options. The document grounds the model the same way the LLM
    providers are grounded: the full flow ontology (`ontology`) and the authored exemplars (`examples`),
    plus the recent history + current turn (+ active post title when one is grounded). The Choice's
    `criteria` supplies the 18 options with their rubric descriptions."""
    document = {'flow_definitions': ontology, 'examples': examples,
                'conversation': convo_history, 'current_user_turn': user_text}
    if active_post:
        document['active_post'] = active_post['title']
    payload = {
        'document': document,
        'model': _MODEL,
        'questions': {
            'flow': {'type': 'choice', 'instructions': _QUESTION, 'criteria': _flow_criteria()},
        },
    }
    headers = {'Authorization': f'Bearer {_api_key()}', 'Content-Type': 'application/json'}
    resp = requests.post(_ENDPOINT, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    answer = resp.json()['answers']['flow']
    return answer['choice'], answer['confidence']
