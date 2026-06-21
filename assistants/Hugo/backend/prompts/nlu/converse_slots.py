PROMPTS = {
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
}
