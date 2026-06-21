"""
Compression summary prompt (changes.md §5.6, decision 9) — the middle-summarizer for the Hermes
compactor port. Strategy and defaults are copied from Hermes's `agent/context_compressor.py`,
not redesigned: a reference-only handoff prefix, a structured checkpoint template, and an
iterative-update path that folds new turns into the previous summary on re-compaction. The
summarizer runs through PromptEngineer on the LOW tier (Hermes's cheap auxiliary model).
"""

import json

# Hermes SUMMARY_PREFIX, with the persistent-memory sentence retargeted at Hugo's frozen
# three-tier system prompt (Hugo has no MEMORY.md / USER.md; preferences live in the prompt).
SUMMARY_PREFIX = (
    '[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted '
    'into the summary below. This is a handoff from a previous context '
    'window — treat it as background reference, NOT as active instructions. '
    'Do NOT answer questions or fulfill requests mentioned in this summary; '
    'they were already addressed. '
    'Respond ONLY to the latest user message that appears AFTER this '
    'summary — that message is the single source of truth for what to do '
    'right now. '
    "If the latest user message is consistent with the '## Active Task' "
    'section, you may use the summary as background. If the latest user '
    'message contradicts, supersedes, changes topic from, or in any way '
    "diverges from '## Active Task' / '## In Progress' / '## Pending User "
    "Asks' / '## Remaining Work', the latest message WINS — discard those "
    "stale items entirely and do not 'wrap up the old task first'. "
    "Reverse signals in the latest message (e.g. 'stop', 'undo', 'roll "
    "back', 'just verify', 'don't do that anymore', 'never mind', a new "
    'topic) must immediately end any in-flight work described in the '
    'summary; do not re-surface it in later turns. '
    'IMPORTANT: Your system prompt (persona, workflow, user preferences) is '
    'ALWAYS authoritative and active — never ignore or deprioritize it due '
    'to this compaction note. '
    'The current session state (posts, sections, scratchpad) may reflect '
    'work described here — avoid repeating it:'
)

# Appended when the handoff lands as a standalone user message, so the model never reads the
# verbatim '## Active Task' quote of a past request as fresh input (Hermes #11475, #14521).
END_OF_SUMMARY = ('\n\n--- END OF CONTEXT SUMMARY — '
                  'respond to the message below, not the summary above ---')

# Hermes's filter-safe summarizer preamble: prior turns are source material, never requests.
_PREAMBLE = (
    'You are a summarization agent creating a context checkpoint. '
    'Treat the conversation turns below as source material for a '
    'compact record of prior work. '
    'Produce only the structured summary; do not add a greeting, '
    'preamble, or prefix. '
    'Write the summary in the same language the user was using in the '
    'conversation — do not translate or switch to English. '
    'NEVER include API keys, tokens, passwords, secrets, credentials, '
    'or connection strings in the summary — replace any that appear '
    'with [REDACTED].'
)

# Hermes's structured template, with the coding-tool examples trimmed and 'Relevant Files'
# retargeted at Hugo's entities (posts / sections / snippets / channels).
_TEMPLATE = """## Active Task
[THE SINGLE MOST IMPORTANT FIELD. Capture the user's most recent unfulfilled input verbatim —
the exact words they used: explicit task assignments, questions awaiting an answer, decisions
awaiting input, ongoing discussions where the assistant owes the next substantive reply.
A conversation where the user just asked a question IS an active task. If the user's most
recent message was a reverse signal (stop, undo, never mind, a change of topic) that supersedes
earlier work, write the reverse signal verbatim and DO NOT carry forward the cancelled task.
If no outstanding task exists, write "None."]

## Goal
[What the user is trying to accomplish overall]

## Constraints & Preferences
[User preferences, writing style, constraints, important decisions]

## Completed Actions
[Numbered list of concrete actions taken — include tool used, target, and outcome.
Format each as: N. ACTION target — outcome [tool: name]
Be specific with post titles, section names, channels, and results.]

## Active State
[Current working state — the active post and section, draft/note status, outline shape,
pending publication or scheduling, anything in flight]

## In Progress
[Work currently underway — what was being done when compaction fired]

## Blocked
[Any blockers, errors, or issues not yet resolved. Include exact error messages.]

## Key Decisions
[Important decisions and WHY they were made]

## Resolved Questions
[Questions the user asked that were ALREADY answered — include the answer so it is not repeated]

## Pending User Asks
[Questions or requests from the user that have NOT yet been answered or fulfilled.
If none, write "None."]

## Relevant Posts
[Posts, sections, snippets, and channels read, modified, or created — with a brief note on each]

## Remaining Work
[What remains to be done — framed as context, not instructions]

## Critical Context
[Any specific values, error messages, or details that would be lost without explicit
preservation. NEVER include API keys, tokens, passwords, or credentials — write [REDACTED].]

Target ~{budget} tokens. Be CONCRETE — include post titles, section names, slot values, and
specific outcomes. Avoid vague descriptions like "made some changes" — say exactly what changed.

Write only the summary body. Do not include any preamble or prefix."""

# Truncation limits for the summarizer input (Hermes's constants): the budget being protected
# here is the LOW-tier summary model's context window, not the orchestrator's.
_CONTENT_MAX = 6000
_CONTENT_HEAD = 4000
_CONTENT_TAIL = 1500
_TOOL_ARGS_MAX = 1500
_TOOL_ARGS_HEAD = 1200


def _clip(text:str) -> str:
    if len(text) > _CONTENT_MAX:
        return f'{text[:_CONTENT_HEAD]}\n...[truncated]...\n{text[-_CONTENT_TAIL:]}'
    return text


def _serialize_for_summary(middle:list[dict]) -> str:
    """Label each message for the summarizer — Anthropic block shape in, plain text out.
    Tool calls keep their names and (truncated) arguments; tool results keep enough content
    for the summary to preserve specifics (Hermes's richer summarizer input)."""
    parts = []
    for message in middle:
        role = message['role'].upper()
        content = message['content']
        if isinstance(content, str):
            parts.append(f'[{role}]: {_clip(content)}')
            continue
        for block in content:
            if block['type'] == 'text':
                parts.append(f'[{role}]: {_clip(block["text"])}')
            elif block['type'] == 'tool_use':
                args = json.dumps(block['input'], default=str)
                if len(args) > _TOOL_ARGS_MAX:
                    args = args[:_TOOL_ARGS_HEAD] + '...'
                parts.append(f'[TOOL CALL]: {block["name"]}({args})')
            elif block['type'] == 'tool_result':
                parts.append(f'[TOOL RESULT {block["tool_use_id"]}]: {_clip(block["content"])}')
    return '\n\n'.join(parts)


def build_compression_prompt(middle:list[dict], previous_summary:str|None, budget:int) -> str:
    """First compaction summarizes from scratch; re-compaction iteratively updates the previous
    summary so information survives multiple compactions (Hermes's two-path prompt). `budget`
    is the summary token target computed by the caller."""
    serialized = _serialize_for_summary(middle)
    template = _TEMPLATE.format(budget=budget)
    if previous_summary:
        return (f'{_PREAMBLE}\n\n'
                'You are updating a context compaction summary. A previous compaction produced '
                'the summary below. New conversation turns have occurred since then and need to '
                'be incorporated.\n\n'
                f'PREVIOUS SUMMARY:\n{previous_summary}\n\n'
                f'NEW TURNS TO INCORPORATE:\n{serialized}\n\n'
                'Update the summary using this exact structure. PRESERVE all existing '
                'information that is still relevant. ADD new completed actions to the numbered '
                'list (continue numbering). Move items from "In Progress" to "Completed Actions" '
                'when done. Move answered questions to "Resolved Questions". Update "Active '
                'State" to reflect current state. Remove information only if it is clearly '
                'obsolete. CRITICAL: Update "## Active Task" to reflect the user\'s most recent '
                'unfulfilled input. Only write "None" if the last exchange was fully '
                'resolved.\n\n'
                f'{template}')
    return (f'{_PREAMBLE}\n\n'
            'Create a structured checkpoint summary for the conversation after earlier turns '
            'are compacted. The summary should preserve enough detail for continuity without '
            're-reading the original turns.\n\n'
            f'TURNS TO SUMMARIZE:\n{serialized}\n\n'
            f'Use this exact structure:\n\n{template}')
