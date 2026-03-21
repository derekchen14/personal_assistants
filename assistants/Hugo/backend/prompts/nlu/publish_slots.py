INSTRUCTIONS = {

'release': (
    'Goal: Publish the post immediately on the primary blog.\n\n'
    'Slots:\n'
    '- source (required): The post to publish. '
    'Strip status words: "my X draft" → just "X".\n'
    '- channel (optional): Which channel to publish on. '
    'Only extract if explicitly mentioned; defaults to the primary blog.'
),

'syndicate': (
    'Goal: Cross-post to a secondary channel — adapts formatting '
    'for the target platform.\n\n'
    'Slots:\n'
    '- channel (required): The destination channel '
    '(Medium, Dev.to, LinkedIn, Substack). This is the primary slot.\n'
    '- source (optional): The post to cross-post. '
    'May be inferred from recent conversation context.'
),

'schedule': (
    'Goal: Set a date and time for automatic future publication.\n\n'
    'Slots:\n'
    '- source (required): The post to schedule.\n'
    '- channel (required): Which channel to schedule on.\n'
    '- datetime (optional): When to publish. '
    'Pass the raw date/time expression exactly as stated — '
    'do not parse or reformat (e.g., "Friday 8am EST", "March 20th").'
),

'preview': (
    'Goal: Render how the post will look when published on a channel, '
    'so the user can review layout, images, and formatting.\n\n'
    'Slots:\n'
    '- source (required): The post to preview.\n'
    '- channel (optional): Which channel\'s formatting to render. '
    'Only extract if mentioned.'
),

'promote': (
    'Goal: Amplify a published post\'s reach — pin, feature, announce, or share.\n\n'
    'Slots:\n'
    '- source (required): The published post to promote.\n'
    '- channel (optional): The promotion method. Choose from: '
    'pin (top of blog), feature (mark as featured), '
    'announce (email subscribers), social (share to social channels).'
),

'cancel': (
    'Goal: Cancel a scheduled publication or unpublish a live post.\n\n'
    'Slots:\n'
    '- source (required): The post to cancel or unpublish.\n'
    '- reason (optional): Why it\'s being cancelled. '
    'Only extract if the user provides a reason.'
),

'survey': (
    'Goal: View connected publishing channels and their status — '
    'API health, last sync date, credential validity.\n\n'
    'Slots:\n'
    '- channel (optional): A specific channel to check. '
    'If omitted, shows all connected channels.'
),

}


EXEMPLARS = {

'release': '''
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Push the History of Seq2Seq draft live on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "History of Seq2Seq"}}, "channel": "Substack"}}, "missing": []}}
```
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Release the crypto investing post now"
_Output_
```json
{{"slots": {{"source": {{"post": "crypto investing"}}, "channel": null}}, "missing": []}}
```
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Go ahead and publish it"
_Output_
```json
{{"slots": {{"source": null, "channel": null}}, "missing": ["source"]}}
```
''',

'syndicate': '''
---
Flow: syndicate
Slots: channel (ChannelSlot, required), source (SourceSlot, optional)
User: "Cross-post my data pipeline article to Medium"
_Output_
```json
{{"slots": {{"channel": "Medium", "source": {{"post": "data pipeline"}}}}, "missing": []}}
```
---
Flow: syndicate
Slots: channel (ChannelSlot, required), source (SourceSlot, optional)
User: "Syndicate the latest post to LinkedIn and Dev.to"
_Output_
```json
{{"slots": {{"channel": "LinkedIn", "source": null}}, "missing": []}}
```
''',

'schedule': '''
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "Schedule my AI roundup post for Friday at 8am EST on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "AI roundup"}}, "channel": "Substack", "datetime": "Friday 8am EST"}}, "missing": []}}
```
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "schedule the post for tomorrow on Medium"
_Output_
```json
{{"slots": {{"source": null, "channel": "Medium", "datetime": "tomorrow"}}, "missing": ["source"]}}
```
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "Queue the Attention Mechanism post for March 20th"
_Output_
```json
{{"slots": {{"source": {{"post": "Attention Mechanism"}}, "channel": null, "datetime": "March 20th"}}, "missing": ["channel"]}}
```
''',

'preview': '''
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Preview my 100 Research Papers post as it would appear on the blog"
_Output_
```json
{{"slots": {{"source": {{"post": "100 Research Papers"}}, "channel": "blog"}}, "missing": []}}
```
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Show me how the newsletter will look on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "newsletter"}}, "channel": "Substack"}}, "missing": []}}
```
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Let me see a preview of that"
_Output_
```json
{{"slots": {{"source": null, "channel": null}}, "missing": ["source"]}}
```
''',

'promote': '''
---
Flow: promote
Slots: source (SourceSlot, required), channel (CategorySlot, optional)
User: "Pin my Conversational AI Revolution post to the top of the blog"
_Output_
```json
{{"slots": {{"source": {{"post": "Conversational AI Revolution"}}, "channel": "pin"}}, "missing": []}}
```
---
Flow: promote
Slots: source (SourceSlot, required), channel (CategorySlot, optional)
User: "Feature the latest post and announce it to subscribers"
_Output_
```json
{{"slots": {{"source": null, "channel": "feature"}}, "missing": ["source"]}}
```
''',

'cancel': '''
---
Flow: cancel
Slots: source (SourceSlot, required), reason (ExactSlot, optional)
User: "Cancel the scheduled publication of my AI roundup post"
_Output_
```json
{{"slots": {{"source": {{"post": "AI roundup"}}, "reason": null}}, "missing": []}}
```
---
Flow: cancel
Slots: source (SourceSlot, required), reason (ExactSlot, optional)
User: "Unpublish the crypto post — I found an error in the data"
_Output_
```json
{{"slots": {{"source": {{"post": "crypto"}}, "reason": "found an error in the data"}}, "missing": []}}
```
''',

'survey': '''
---
Flow: survey
Slots: channel (ChannelSlot, optional)
User: "Show me my connected publishing channels"
_Output_
```json
{{"slots": {{"channel": null}}, "missing": []}}
```
---
Flow: survey
Slots: channel (ChannelSlot, optional)
User: "Is my Medium connection still working?"
_Output_
```json
{{"slots": {{"channel": "Medium"}}, "missing": []}}
```
''',

}
