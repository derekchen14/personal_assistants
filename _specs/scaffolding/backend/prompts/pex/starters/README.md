# Starters

One Python module per agentic flow: `<flow_name>.py`. Exports a `TEMPLATE`
string and a `build(flow, resolved, user_text)` function that returns the
per-turn user message — Layer 2 of the three-layer prompt architecture.

## Canonical envelope

```xml
<task>
{flow_verb} {target} of "{post_title}". {tool_sequence}. {optional end_condition}.
</task>

<post_content>  <!-- or <section_content>, <line_snippet>, <channel_content> -->
{preloaded content — omit block entirely if nothing to preload}
</post_content>

<resolved_details>
Source: {render_source(...)}
Feedback: {render_freetext(...)}
Guidance: {render_freetext(...)}
</resolved_details>

<recent_conversation>
{compiled convo history — tail is the latest utterance}
</recent_conversation>
```

Starters preload what the skill would otherwise re-fetch. When a starter can
carry post content, embed it in `<post_content>` so the skill skips a
redundant `read_section` / `read_metadata`. Counter-example: scope-varying
flows preload nothing and read at runtime.

## Slot serialization

Helpers live in `for_pex.py` (3–5 across all flows, not one per slot):

- `render_source` — SourceSlot → `post=<id>, section=<sec_id>` line
- `render_freetext` — FreeTextSlot → quoted prose
- `render_checklist` — ChecklistSlot → bullet list

Render values in `<resolved_details>` with semantic labels (`Source:`,
`Feedback:`, `Guidance:`, `Steps:`, `Tone:`, etc.) — never raw slot names.
The LLM is in execution mode; grounding is already done by NLU.
