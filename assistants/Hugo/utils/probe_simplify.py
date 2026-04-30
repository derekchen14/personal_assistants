"""Throwaway probe for SimplifyFlow bug candidates.

Run from the Hugo directory:
    python -m utils.probe_simplify

Targets:
  - ImageSlot has no `.values` — does the starter crash on image-only?
  - guidance.required vs is_filled() routing.
  - suggestions slot ghost (declared but never rendered).

Delete this file once the bugs are fixed."""

from backend.components.flow_stack.slots import ImageSlot
from backend.components.flow_stack.flows import SimplifyFlow
from backend.prompts.pex.starters import simplify


def section(label):
    print(f'\n=== {label} ===')


# Probe 1: does ImageSlot expose .values?
section('1. ImageSlot — does .values exist?')
img = ImageSlot(priority='elective')
img.assign_one(img_type='hero', src='', alt='complex diagram', position=-1)
print(f'img.value      = {img.value!r}')
print(f'img.image_type = {img.image_type!r}')
print(f'has .values?     {hasattr(img, "values")}')
try:
    out = simplify._render_image(img)
    print(f'_render_image -> {out!r}')
except Exception as ecp:
    print(f'_render_image CRASH: {type(ecp).__name__}: {ecp}')


# Probe 2: full Simplify starter — image-only branch
section('2. Simplify starter — image filled, source empty')
flow = SimplifyFlow()
flow.slots['image'].assign_one(img_type='hero', src='', alt='complex diagram', position=-1)
flow.slots['guidance'].add_one('replace with simpler version')
try:
    out = simplify.build(flow, {'post_title': 'transformers'}, 'simplify the hero image')
    print(out)
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 3: full Simplify starter — section-only branch (most common path)
section('3. Simplify starter — source filled, guidance filled')
flow = SimplifyFlow()
flow.slots['source'].add_one(post='abcd0123', sec='methods')
flow.slots['guidance'].add_one('cut the historical preamble')
try:
    out = simplify.build(flow, {'post_title': 'regularization'}, 'simplify methods')
    print(out)
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 4: guidance-required contract drift. Flow declares guidance as required;
# NLU/starter treat it as optional. Does is_filled() then block the policy?
section('4. SimplifyFlow.is_filled() with only source filled (no guidance)')
flow = SimplifyFlow()
flow.slots['source'].add_one(post='abcd0123', sec='methods')
print(f'source.check_if_filled()    = {flow.slots["source"].check_if_filled()}')
print(f'guidance.check_if_filled()  = {flow.slots["guidance"].check_if_filled()}')
print(f'guidance.priority           = {flow.slots["guidance"].priority!r}')
print(f'flow.is_filled()            = {flow.is_filled()}')


# Probe 5: suggestions slot ghost — does the starter render it when filled?
# (Audit chains into Simplify by filling suggestions before stackon.)
section('5. Simplify starter — suggestions filled (audit chain)')
flow = SimplifyFlow()
flow.slots['source'].add_one(post='abcd0123', sec='methods')
flow.slots['guidance'].add_one('cut redundancy')
flow.slots['suggestions'].add_one(name='trim opening', description='shorter opening')
flow.slots['suggestions'].add_one(name='remove footnote', description='delete footnote')
try:
    out = simplify.build(flow, {'post_title': 'regularization'}, '')
    print(out)
    print()
    if 'trim opening' in out or 'shorter opening' in out:
        print('OK: suggestions made it into the prompt')
    else:
        print('GHOST CONFIRMED: suggestions content does NOT appear in the prompt')
except Exception as ecp:
    print(f'CRASH: {type(ecp).__name__}: {ecp}')


# Probe 6: default entity_slot
section('6. SimplifyFlow default entity_slot')
print(f'SimplifyFlow().entity_slot = {SimplifyFlow().entity_slot!r}')
