"""Live-API validation of NLU JSON schemas against Anthropic.

One tiny Messages API call per schema. Asserts no 4xx invalid_request_error.
Covers whatever the offline linter (`test_nlu_schemas.py`) may have missed —
provider rules we haven't encoded yet.

Marked `@pytest.mark.llm` so it only runs when explicitly opted in:
    pytest utils/tests/test_nlu_contract.py -m llm -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))

import anthropic

from schemas.config import load_config
from backend.components.flow_stack import flow_classes
from backend.components.prompt_engineer import PromptEngineer
from backend.modules.nlu import (
    _intent_schema, _flow_detection_schema, _fill_slots_schema,
)


pytestmark = pytest.mark.llm


@pytest.fixture(scope='module')
def engineer():
    return PromptEngineer(load_config(overrides={'debug': True}))


def _probe(engineer:PromptEngineer, schema:dict, label:str):
    """Fire a minimal structured-output call; fail only on schema-shape rejection."""
    try:
        engineer('ping', task='fill_slots', schema=schema, max_tokens=128)
    except anthropic.BadRequestError as ecp:
        msg = str(ecp)
        if 'output_config' in msg or 'schema' in msg.lower():
            pytest.fail(f'{label}: Anthropic rejected schema — {msg}')
        raise


def test_intent_schema_accepted(engineer):
    _probe(engineer, _intent_schema(), 'intent_schema')


def test_flow_detection_schema_accepted(engineer):
    _probe(engineer, _flow_detection_schema(list(flow_classes.keys())), 'flow_detection_schema')


@pytest.mark.parametrize('flow_name', sorted(flow_classes.keys()))
def test_fill_slots_schema_accepted(engineer, flow_name):
    flow = flow_classes[flow_name]()
    _probe(engineer, _fill_slots_schema(flow), flow_name)
