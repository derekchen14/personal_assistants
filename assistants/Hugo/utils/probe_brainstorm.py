"""Throwaway probe for BrainstormFlow bug candidates.

Run from the Hugo directory:
    python -m utils.probe_brainstorm

Targets:
  - ExactSlot.to_dict() rendering in the starter.
  - flow.entity_slot mutation persistence across instances.
  - Mode B routing (source.snip filled vs only post filled).
  - Default entity_slot resolution.

Delete this file once the bugs are fixed."""

from backend.components.flow_stack.slots import ExactSlot
from backend.components.flow_stack.flows import BrainstormFlow
from backend.prompts.pex.starters import brainstorm


def section(label):
    print(f'\n=== {label} ===')


# Probe 1: ExactSlot.to_dict() — bare string or dict literal?
section('1. ExactSlot.to_dict() rendering')
topic = ExactSlot(priority='elective')
topic.add_one('interpretability')
print(f'topic.value      = {topic.value!r}')
print(f'topic.criteria   = {topic.criteria!r}')
print(f'topic.to_dict()  = {topic.to_dict()!r}')
print(f'starter f-string:  Topic: {topic.to_dict()}')


# Probe 2: full Brainstorm starter — topic mode
section('2. Brainstorm starter — topic mode')
flow = BrainstormFlow()
flow.slots['topic'].add_one('interpretability')
print(f'entity_slot before policy mutation = {flow.entity_slot!r}')
try:
    out = brainstorm.build(flow, {}, 'angle for interpretability')
    print(out)
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 3: Brainstorm starter — snippet (Mode B) routing
section('3. Brainstorm starter — source.snip filled, no topic')
flow = BrainstormFlow()
flow.slots['source'].add_one(post='abcd0123', sec='motivation', snip='dirt cheap')
try:
    out = brainstorm.build(flow, {}, 'better phrasings for "dirt cheap"')
    print(out)
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 4: Brainstorm starter — only post filled (no snip, no topic).
# This is the routing gap I flagged: branches to topic mode but topic is null.
section('4. Brainstorm starter — only source.post filled (routing gap)')
flow = BrainstormFlow()
flow.slots['source'].add_one(post='abcd0123')
try:
    out = brainstorm.build(flow, {}, 'angles for the transformer post')
    print(out)
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 5: entity_slot mutation persistence — does flow.entity_slot='topic'
# leak into a later BrainstormFlow instance?
section('5. BrainstormFlow.entity_slot mutation persistence')
flow1 = BrainstormFlow()
print(f'fresh flow1.entity_slot                = {flow1.entity_slot!r}')
flow1.entity_slot = 'topic'
print(f'after mutate flow1.entity_slot         = {flow1.entity_slot!r}')
flow2 = BrainstormFlow()
print(f'fresh flow2.entity_slot (new instance) = {flow2.entity_slot!r}')


# Probe 6: ideas slot priority (flow says optional, NLU says elective)
section('6. BrainstormFlow ideas slot priority')
flow = BrainstormFlow()
print(f'ideas.priority   = {flow.slots["ideas"].priority!r}')
print(f'topic.priority   = {flow.slots["topic"].priority!r}')
print(f'source.priority  = {flow.slots["source"].priority!r}')
