"""Throwaway probe for AddFlow bug candidates.

Run from the Hugo directory:
    python -m utils.probe_add

Targets:
  - ImageSlot rendering inside the starter (does it use slot attrs cleanly?).
  - ChecklistSlot rendering for points & suggestions (description vs name).
  - section_ids passthrough from resolved dict.
  - Default entity_slot.

Delete this file once the bugs are fixed."""

from backend.components.flow_stack.slots import ImageSlot
from backend.components.flow_stack.flows import AddFlow
from backend.prompts.pex.starters import add


def section(label):
    print(f'\n=== {label} ===')


# Probe 1: ImageSlot rendering helper directly
section('1. AddFlow image rendering — _render_image output shape')
img = ImageSlot(priority='elective')
img.assign_one(img_type='hero', src='https://cdn.example.com/diag.png', alt='lineage diagram', position=-1)
print(f'img.value      = {img.value!r}')
print(f'img.image_type = {img.image_type!r}')
print(f'img.image_desc = {img.image_desc!r}')
print(f'_render_image -> {add._render_image(img)!r}')


# Probe 2: full Add starter — image branch (note: src must be set or check_if_filled() is False)
section('2. Add starter — image filled with src')
flow = AddFlow()
flow.slots['source'].add_one(post='abcd0123', sec='intro')
flow.slots['image'].assign_one(img_type='hero', src='https://cdn.example.com/diag.png', alt='lineage diagram', position=-1)
out = add.build(flow, {'post_title': 'My Paper'}, 'add a hero image')
print(out)


# Probe 3: full Add starter — points branch (single section, ordinal-named items).
# Confirms description (not just ordinal name) reaches the skill.
section('3. Add starter — points filled (single section)')
flow = AddFlow()
flow.slots['source'].add_one(post='abcd0123', sec='conclusion')
flow.slots['points'].add_one(name='one', description='cite the recent paper')
flow.slots['points'].add_one(name='two', description='note the limitations')
out = add.build(flow, {'post_title': 'My Paper'}, 'add three bullets')
print(out)
print()
if 'cite the recent paper' in out:
    print('OK: point descriptions appear')
else:
    print('PROBLEM: point descriptions missing')


# Probe 4: full Add starter — suggestions branch (multi-section, natural-language directives).
# Replaced the old `additions` DictionarySlot in master.
section('4. Add starter — suggestions filled (multi-section directives)')
flow = AddFlow()
flow.slots['source'].add_one(post='abcd0123', sec='methods')
flow.slots['suggestions'].add_one(name='one', description='comparison table is needed in Methods')
flow.slots['suggestions'].add_one(name='two', description='cite the follow-up paper in Conclusion')
out = add.build(flow, {'post_title': 'My Paper'}, 'add stuff')
print(out)
print()
if 'comparison table' in out and 'cite the follow-up paper' in out:
    print('OK: suggestion descriptions appear')
else:
    print('PROBLEM: suggestion descriptions missing')


# Probe 5: section_ids passthrough — the starter should surface them when the policy
# pre-resolves them, so the skill can pick anchors for "before X" / "after X".
section('5. section_ids passthrough into prompt')
flow = AddFlow()
flow.slots['source'].add_one(post='abcd0123')
flow.slots['suggestions'].add_one(name='one', description='add a new section before methods')
resolved_with_sections = {
    'post_title': 'My Paper',
    'section_ids': ['intro', 'background', 'methods', 'results'],
}
out = add.build(flow, resolved_with_sections, 'add a section before methods')
print(out)
print()
if 'background' in out and 'methods' in out:
    print('OK: section_ids reach the skill prompt')
else:
    print('PROBLEM: section_ids missing from prompt')


# Probe 6: default entity_slot
section('6. AddFlow default entity_slot')
print(f'AddFlow().entity_slot = {AddFlow().entity_slot!r}')
