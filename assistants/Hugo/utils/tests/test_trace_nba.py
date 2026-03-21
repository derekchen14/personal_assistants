"""Trace two-turn conversation: create → outline for NBA traveling post.

Inspects every intermediate state to find where things break.
"""

import json
import sys
from pathlib import Path

import pytest

_HUGO_ROOT = Path(__file__).resolve().parents[2]
if str(_HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUGO_ROOT))


class TestNBATravelingPost:

    def test_create_then_outline(self, agent):
        # ── Turn 1: Create ────────────────────────────────────
        print("\n\n═══ TURN 1: Create ═══")
        r1 = agent.take_turn(
            "Create a new post about Traveling in the Modern NBA",
            dax='{05A}',
        )
        s1 = agent.world.current_state()
        flow1 = agent.world.flow_stack.get_active_flow()

        print(f"  flow_name:   {s1.flow_name}")
        print(f"  intent:      {s1.pred_intent}")
        print(f"  confidence:  {s1.confidence}")

        # Check slots
        if flow1:
            slots = flow1.slot_values_dict()
            print(f"  slots:       {slots}")
        else:
            # Flow already completed, check stack
            print(f"  flow_stack:  depth={agent.world.flow_stack.depth}")

        # Check result
        message1 = r1.get('message', '')
        frame1 = r1.get('frame') or {}
        frame_data1 = frame1.get('data', {})
        print(f"  message:     {message1[:200]}")
        print(f"  frame_type:  {frame1.get('type', 'none')}")
        print(f"  frame_data:  {json.dumps(frame_data1, indent=2, default=str)[:500]}")

        # Verify create succeeded
        post_id = frame_data1.get('post_id', '')
        title = frame_data1.get('title', '')
        print(f"  post_id:     {post_id}")
        print(f"  title:       {title}")

        assert s1.flow_name == 'create', f"Expected create, got {s1.flow_name}"
        assert s1.pred_intent == 'Draft', f"Expected Draft, got {s1.pred_intent}"
        assert post_id, "No post_id returned from create"

        # Check active_post propagation
        print(f"\n  state.active_post after create: {s1.active_post}")

        # ── Turn 2: Outline ───────────────────────────────────
        print("\n\n═══ TURN 2: Outline ═══")

        # Monkey-patch tool dispatch to log calls
        original_dispatch = agent.pex._dispatch_tool
        tool_calls_log = []
        def logging_dispatch(tool_name, tool_input):
            result = original_dispatch(tool_name, tool_input)
            tool_calls_log.append({
                'tool': tool_name,
                'input': {k: (v[:100] if isinstance(v, str) and len(v) > 100 else v) for k, v in tool_input.items()},
                'success': result.get('_success', None),
                'error': result.get('_error', None),
            })
            return result
        agent.pex._dispatch_tool = logging_dispatch

        r2 = agent.take_turn(
            "Make an outline that explores: (a) How traveling used to be called "
            "(b) What is a gather step (c) How the game has evolved and "
            "(d) some conclusion.",
            dax='{002}',
        )
        s2 = agent.world.current_state()

        print(f"  flow_name:   {s2.flow_name}")
        print(f"  intent:      {s2.pred_intent}")
        print(f"  confidence:  {s2.confidence}")

        # Check result
        message2 = r2.get('message', '')
        frame2 = r2.get('frame') or {}
        frame_data2 = frame2.get('data', {})
        content2 = frame_data2.get('content', '')
        print(f"  message:     {message2[:300]}")
        print(f"  frame_type:  {frame2.get('type', 'none')}")
        print(f"  content_len: {len(content2)}")
        print(f"  content:     {content2[:500]}")

        # Inspect raw result for tool call evidence
        print(f"\n  raw_utterance len: {len(r2.get('raw_utterance', ''))}")
        interaction = r2.get('interaction', {})
        print(f"  interaction type:  {interaction.get('type', 'none')}")

        # Print tool call log
        print(f"\n  Tool calls ({len(tool_calls_log)}):")
        for i, tc in enumerate(tool_calls_log):
            print(f"    [{i+1}] {tc['tool']}  success={tc['success']}  error={tc['error']}")
            print(f"        input: {tc['input']}")

        assert s2.flow_name == 'outline', f"Expected outline, got {s2.flow_name}"
        assert s2.pred_intent == 'Draft', f"Expected Draft, got {s2.pred_intent}"

        # Check the outline has real content
        assert len(content2) > 50, f"Outline too short ({len(content2)} chars)"

        # Check the outline references the sections user asked for
        content_lower = content2.lower()
        has_traveling = 'traveling' in content_lower or 'travel' in content_lower
        has_gather = 'gather' in content_lower
        has_evolved = 'evolv' in content_lower or 'evolution' in content_lower
        has_conclusion = 'conclusion' in content_lower or 'closing' in content_lower

        print(f"\n  Section checks:")
        print(f"    traveling ref:  {has_traveling}")
        print(f"    gather step:   {has_gather}")
        print(f"    evolved:       {has_evolved}")
        print(f"    conclusion:    {has_conclusion}")

        missing = []
        if not has_traveling:
            missing.append('traveling')
        if not has_gather:
            missing.append('gather step')
        if not has_evolved:
            missing.append('game evolution')
        if not has_conclusion:
            missing.append('conclusion')
        assert not missing, f"Outline missing sections: {missing}"

        # ── Verify post state on disk ─────────────────────────
        print("\n\n═══ POST STATE ═══")
        from backend.utilities.services import PostService
        ps = PostService()
        meta = ps.read_metadata(post_id, include_outline=True)
        print(f"  meta success: {meta.get('_success')}")
        if meta.get('_success'):
            print(f"  title:        {meta.get('title')}")
            print(f"  status:       {meta.get('status')}")
            print(f"  sections:     {meta.get('section_ids')}")
            outline = meta.get('outline', '')
            print(f"  outline_len:  {len(outline)}")
            print(f"  outline:\n{outline[:800]}")
        else:
            print(f"  ERROR: {meta.get('_message')}")
