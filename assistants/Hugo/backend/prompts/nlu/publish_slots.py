PROMPTS = {
    'release': {
        'instructions': 'Publish the post immediately on the primary blog.',
        'rules': '''- source (required): The post to publish. Strip status words: "my X draft" → just "X".
- channel (optional): Which channel to publish on. Only extract if explicitly mentioned; defaults to the primary blog.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Push the History of Seq2Seq draft live on Substack"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "History of Seq2Seq"
    },
    "channel": "Substack"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Release the crypto investing post now"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "crypto investing"
    },
    "channel": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Go ahead and publish it"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "channel": null
  }
}
```
</positive_example>''',
    },
    'syndicate': {
        'instructions': 'Cross-post to a secondary channel — adapts formatting for the target platform.',
        'rules': '''- channel (required): The destination channel (Medium, Dev.to, LinkedIn, Substack). This is the primary slot.
- source (optional): The post to cross-post. May be inferred from recent conversation context.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Cross-post my data pipeline article to Medium"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "channel": "Medium",
    "source": {
      "post": "data pipeline"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Syndicate the latest post to LinkedIn and Dev.to"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "channel": "LinkedIn",
    "source": null
  }
}
```
</positive_example>''',
    },
    'schedule': {
        'instructions': 'Set a date and time for automatic future publication.',
        'rules': '''- source (required): The post to schedule.
- channel (required): Which channel to schedule on.
- datetime (optional): When to publish. Pass the raw date/time expression exactly as stated — do not parse or reformat (e.g., "Friday 8am EST", "March 20th").''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Schedule my AI roundup post for Friday at 8am EST on Substack"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "AI roundup"
    },
    "channel": "Substack",
    "datetime": "Friday 8am EST"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "schedule the post for tomorrow on Medium"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "channel": "Medium",
    "datetime": "tomorrow"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Queue the Attention Mechanism post for March 20th"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Attention Mechanism"
    },
    "channel": null,
    "datetime": "March 20th"
  }
}
```
</positive_example>''',
    },
    'preview': {
        'instructions': 'Render how the post will look when published on a channel, so the user can review layout, images, and formatting.',
        'rules': '''- source (required): The post to preview.
- channel (optional): Which channel's formatting to render. Only extract if mentioned.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Preview my 100 Research Papers post as it would appear on the blog"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "100 Research Papers"
    },
    "channel": "blog"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Show me how the newsletter will look on Substack"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "newsletter"
    },
    "channel": "Substack"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Let me see a preview of that"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "channel": null
  }
}
```
</positive_example>''',
    },
    'promote': {
        'instructions': '''Amplify a published post's reach — pin, feature, announce, or share.''',
        'rules': '''- source (required): The published post to promote.
- channel (optional): The promotion method. Choose from: pin (top of blog), feature (mark as featured), announce (email subscribers), social (share to social channels).''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Pin my Conversational AI Revolution post to the top of the blog"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Conversational AI Revolution"
    },
    "channel": "pin"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Feature the latest post and announce it to subscribers"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "channel": "feature"
  }
}
```
</positive_example>''',
    },
    'cancel': {
        'instructions': 'Cancel a scheduled publication or unpublish a live post.',
        'rules': '''- source (required): The post to cancel or unpublish.
- reason (optional): Why it's being cancelled. Only extract if the user provides a reason.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Cancel the scheduled publication of my AI roundup post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "AI roundup"
    },
    "reason": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Unpublish the crypto post — I found an error in the data"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "crypto"
    },
    "reason": "found an error in the data"
  }
}
```
</positive_example>''',
    },
    'survey': {
        'instructions': 'View connected publishing channels and their status — API health, last sync date, credential validity.',
        'rules': '- channel (optional): A specific channel to check. If omitted, shows all connected channels.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Show me my connected publishing channels"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "channel": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Is my Medium connection still working?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "channel": "Medium"
  }
}
```
</positive_example>''',
    },
}
