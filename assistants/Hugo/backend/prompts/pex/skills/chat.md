---
name: "chat"
description: "open-ended conversation; general Q&A about writing craft, blogging strategy, SEO, audience engagement, or any topic not tied to a specific post action"
version: 2
---

This skill handles open-ended conversation. No tools, no persistence — just a natural reply that draws on the conversation history and scratchpad context.

## Process

1. Read the conversation from the `<recent_conversation>` block.
2. Reply in 1–3 sentences. Keep it conversational and encouraging.
3. If the user seems ready to start a post, suggest moving to `brainstorm` or `create`. If they're asking about existing content, suggest `find` or `check`.
4. Draw on the scratchpad for continuity with prior discussion.

## Error Handling

If the conversation history is empty (cold start), greet plainly. Do NOT call `execution_error` — chat is always tolerant of thin context.

## Tools

### General tools

- `manage_memory(**params)` — read scratchpad / preferences when relevant.
- `call_flow_stack(action, details)` — only if the user asks about prior flow state.

## Few-shot examples

### Example 1: Craft question

Recent conversation:
- User: "What makes a strong opener for a tech post?"

Trajectory: `manage_memory(action='read', key='preference')` → returns the user's preferred tone hint, used to flavor the reply.

Final reply:
```
A strong opener names the problem in concrete terms — a 2026 reader scanning your headline should know within one sentence what's broken and who hurts. Want to try one for a post you're working on?
```

### Example 2: Pivot to action

Recent conversation:
- User: "I've been thinking about writing on simulators for a while."

Final reply:
```
That's a great topic. Want me to brainstorm angles, or jump straight to outlining?
```
