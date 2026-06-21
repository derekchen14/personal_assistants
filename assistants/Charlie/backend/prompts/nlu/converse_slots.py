PROMPTS = {
    'explain': {
        'instructions': '''Hugo explains what it did or plans to do — transparency into the writing process and recent actions.

Explain is a Converse flow, so the grounding is the *topic of discussion* (the action being explained), NOT the underlying post or section. The user is asking about a decision or behavior; that decision is what the conversation is about. Source is a secondary pointer (which post the action touched), and turn_id is a temporal pointer ("your last edit"). Prefer filling `topic` over `source` whenever the user names what they're asking about.''',
        'rules': '''- topic (elective): A short reference to the action being explained — "the removal", "your edit", "the restructure", "why you cited that". This is the primary grounding for explain.
- turn_id (elective): A specific turn number when the user references it temporally. "3 turns ago" → 3, "what you just did" → 1.
- source (optional): A post or section the user mentions in passing. Only fill when the user explicitly names an artifact AND the topic is not already clear; do NOT default to filling source as the primary grounding.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Why did you restructure the introduction like that?"
## Output

```json
{
  "reasoning": "topic = the restructure; the introduction is incidental context, not the entity being asked about",
  "slots": {
    "topic": "the restructure",
    "turn_id": null,
    "source": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "What did you do 3 turns ago?"
## Output

```json
{
  "reasoning": "purely temporal — fill turn_id, no specific topic named",
  "slots": {
    "topic": null,
    "turn_id": 3,
    "source": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Why did you delete that paragraph?"
## Output

```json
{
  "reasoning": "topic = the deletion; the paragraph reference is the action's target, not the conversation subject",
  "slots": {
    "topic": "the deletion",
    "turn_id": null,
    "source": null
  }
}
```
</positive_example>''',
    },
    'chat': {
        'instructions': 'Open-ended conversation — general Q&A about writing craft, blogging strategy, SEO, audience engagement, or any topic not tied to a specific post action. The agent grounds on the topic of discussion, even when the user is just chatting.',
        'rules': '- topic (optional): A free-text description of what the user is talking about. Capture the subject phrase, not the full utterance.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's a good way to think about audience engagement on technical blogs?"
## Output

```json
{
  "reasoning": "topic of conversation",
  "slots": {
    "topic": ["audience engagement on technical blogs"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Just curious — how do you handle SEO for evergreen content?"
## Output

```json
{
  "reasoning": "open question about SEO practice",
  "slots": {
    "topic": ["SEO for evergreen content"]
  }
}
```
</positive_example>''',
    },
    'preference': {
        'instructions': 'Set a persistent writing preference stored in long-term memory — tone defaults, post length, heading style, Oxford comma, channel defaults. The grounding is the preference being set; emit as `target` with key + value.',
        'rules': '- target (required): A dict with "key" (preference name) and "value" (preference value). Parse the user\'s statement into a key-value pair: "use Oxford comma" → {"key": "oxford_comma", "value": true}, "default length 1500 words" → {"key": "default_length", "value": 1500}.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "I always want to use the Oxford comma"
## Output

```json
{
  "reasoning": "boolean preference",
  "slots": {
    "target": {
      "key": "oxford_comma",
      "value": true
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Set my default post length to 1500 words"
## Output

```json
{
  "reasoning": "numeric preference",
  "slots": {
    "target": {
      "key": "default_length",
      "value": 1500
    }
  }
}
```
</positive_example>''',
    },
    'suggest': {
        'instructions': 'Hugo proactively suggests a next step based on current context — what to write next, which section needs attention, a new angle to explore, or an improvement to try. The user grounds the suggestion on a specific topic.',
        'rules': '- topic (optional): A short specific phrase naming what the suggestion should be about. "ideas for the intro" → "the intro"; "what should I write next?" → null (no specific topic).',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Got any ideas for the conclusion?"
## Output

```json
{
  "reasoning": "specific topic = the conclusion",
  "slots": {
    "topic": "the conclusion"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Suggest something for me"
## Output

```json
{
  "reasoning": "no specific topic",
  "slots": {
    "topic": null
  }
}
```
</positive_example>''',
    },
    'undo': {
        'instructions': 'Reverse a recent writing mutation — roll back the most recent K edits on a post. K defaults to 1 ("undo that"). The user can name a specific post via `target`, otherwise the active post is implicit.',
        'rules': '''- rewind (required): How many mutations back to undo. "last edit" / "undo that" / bare "undo" → 1. "back two" / "undo my last 3 changes" → 2 / 3. Always emit a number; default 1 when the user does not name one.
- target (required): The post to undo on. Copy the post_id from the `Active post` line in the input into a single-entry list `[{"post": "<post_id>"}]`. If the input shows `Active post: None`, leave target as an empty list — the policy will declare ambiguity and ask which post.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Go back to that last edit"

Active post: **The Joy of Riding a Bike** (id: `1234abcd`)

## Output
```json
{
  "reasoning": "bare undo — default to 1; copy active post id into target",
  "slots": {
    "rewind": 1,
    "target": [{"post": "1234abcd"}]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Revert my last two changes on the Substack draft"

Active post: None

## Output

```json
{
  "reasoning": "K=2 with reference to a post by name, but no post_id available",
  "slots": {
    "rewind": 2,
    "target": []
  }
}
```
</positive_example>''',
    },
    'endorse': {
        'instructions': '''Accept Hugo's proactive suggestion and trigger the corresponding action. The grounding `target` is the suggestion being accepted.''',
        'rules': '- target (optional): Which suggestion to accept. Emit a single-element list with the description in `snip`: "yes, go ahead with the outline" → [{"snip": "outline"}]. If the user just says "yes" without naming what, leave null and rely on conversational context.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Yes, go ahead with that outline"
## Output

```json
{
  "reasoning": "endorsing the outline suggestion",
  "slots": {
    "target": [{"snip": "outline"}]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Sure, publish it to Medium like you suggested"
## Output

```json
{
  "reasoning": "endorsing the publish-to-Medium suggestion",
  "slots": {
    "target": [{"snip": "publish to Medium"}]
  }
}
```
</positive_example>''',
    },
    'dismiss': {
        'instructions': '''Decline Hugo's proactive suggestion without providing detailed feedback. Hugo notes the dismissal and moves on. The grounding `target` is the suggestion being declined; usually optional because "no" / "skip it" is enough on its own.''',
        'rules': '- target (optional): Which suggestion is being declined. Emit a single-element list with the description in `snip`: "no, skip the outline" → [{"snip": "outline"}]. If the user just says "no" without naming what, leave null.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "No, skip that outline suggestion"
## Output

```json
{
  "reasoning": "dismissing the outline suggestion",
  "slots": {
    "target": [{"snip": "outline"}]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Nah, not now"
## Output

```json
{
  "reasoning": "generic dismissal — no specific target",
  "slots": {
    "target": null
  }
}
```
</positive_example>''',
    },
}
