RELEASE_PROMPT = {
    'instructions': (
        'The Release Flow immediately publishes a finished post to its primary channel as the terminal '
        'step in the drafting lifecycle. It typically comes after other flows, such as Compose, Rework, '
        'and Polish.\n\n'
        'Identify the post being released and, if named, the channel(s). The post is usually pre-filled '
        'from the active post; the user may name a different one or several. The channel slot is always '
        'a list — one item per channel mentioned, empty list when none. Capture channels even when '
        'misspelled or merely implied.'
    ),
    'rules': (
        '1. Pull `source` from the utterance or carry over from the grounded active post when the '
        'utterance is terse ("publish it"). Strip trailing status words from titles ("draft", "post", '
        '"article", "note").\n'
        '2. Fill `channel` on any channel mention — explicit name, misspelling, or implied. Map common '
        'surfaces: "X" / "twitter" → Twitter/X; "lnkdin" → LinkedIn; "my blog" → MoreThanOneTurn.\n'
        '3. `channel` is always a list of channel name strings. One mention → one-item list. Multiple '
        'mentions → multi-item list. No mention → empty list `[]`.\n'
        '4. When the user names multiple posts to release, `source` returns a list of post dicts.\n'
        '5. Future-time language ("publish tomorrow at 9am") leaves both slots null — the schedule flow '
        'handles that.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. References the post (or list of posts) to publish. Always carries '
        '`{post: <title>}`. If the user says "publish it" with an active post in context, source is '
        'inherited from `state.active_post`.\n\n'
        '### channel (required)\n\n'
        'Type: ChannelSlot. Always a list of channel name strings: `["Substack", ...]`. One channel → '
        'one-item list. Multiple → multi-item list. None mentioned → empty list `[]`. Common values: '
        'blog (the user\'s primary, MoreThanOneTurn), Substack, Medium, LinkedIn, Twitter/X, dev.to. '
        'Fill on misspellings and implied references.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Publish it."

## Input
Active post: Attention is All You Need

## Output

```json
{
  "reasoning": "Terse release after a preview-style turn. Source inherits from active_post. No channel named → empty list.",
  "slots": {
    "source": {"post": "Attention is All You Need"},
    "channel": []
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Push the History of Seq2Seq draft live on Substack."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit post + channel. Strip the trailing 'draft' status word from the title. Single channel → one-item list.",
  "slots": {
    "source": {"post": "History of Seq2Seq"},
    "channel": ["Substack"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Ship the crypto investing post now."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Title given, no channel named. 'Now' is emphasis, not schedule. Channel stays empty.",
  "slots": {
    "source": {"post": "crypto investing"},
    "channel": []
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Let's publish my regularization post."
Agent: "Which channel?"
User: "Substack."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source from the first turn; channel from the third. Single channel → one-item list.",
  "slots": {
    "source": {"post": "regularization"},
    "channel": ["Substack"]
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Time to publish."
Agent: "Which channels?"
User: "Substack and LinkedIn."

## Input
Active post: Calibrating LLM Judges

## Output

```json
{
  "reasoning": "Source inherits from active_post. Two channels in current turn → two-item list.",
  "slots": {
    "source": {"post": "Calibrating LLM Judges"},
    "channel": ["Substack", "LinkedIn"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Publish on substak."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "Misspelled channel — still fill it. Map 'substak' to canonical 'Substack'. Source inherits from active_post.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "channel": ["Substack"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Release my regularization post and my batch norm draft on my blog."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two posts in one utterance → source returns a list. 'My blog' maps to the user's primary blog channel (MoreThanOneTurn). Strip 'draft' status word from the second title.",
  "slots": {
    "source": [{"post": "regularization"}, {"post": "batch norm"}],
    "channel": ["MoreThanOneTurn"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "I'm working on my RL primer."
Agent: "Should I help you draft a section?"
User: "Hold off — publish my data augmentation post on Medium instead."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Active post is 'RL primer', but the user explicitly redirects to a different post ('data augmentation post') with 'instead'. Ignore active_post here and use the explicitly named post. Channel is 'Medium' (one-item list).",
  "slots": {
    "source": {"post": "data augmentation"},
    "channel": ["Medium"]
  }
}
```
</edge_case>''',
}

SYNDICATE_PROMPT = {
    'instructions': (
        'The Syndicate Flow cross-posts a finished piece to one or more secondary channels. Channel is '
        'the primary slot — always a list of channel name strings, one item per channel mentioned. '
        'Source is required and typically inherits from the active post; fill explicitly only when the '
        'user names a different post. Map misspellings and implied channels to canonical names.'
    ),
    'rules': (
        '1. `channel` is always a list of channel name strings. Single mention → one-item list. '
        'Multiple mentions → multi-item list. Empty list `[]` only when no channel is mentioned or '
        'when the only channel named is MoreThanOneTurn (see rule 2).\n'
        '2. When the user names MoreThanOneTurn (the primary blog), drop it from the channel list and '
        'note the exclusion in the reasoning — syndicate is for secondary channels only.\n'
        '3. Map common surfaces: "X" / "twitter" → Twitter/X; "lnkdin" → LinkedIn; "dev to" → dev.to. '
        'Fill on misspellings and implied references.\n'
        '4. `source` typically inherits from `state.active_post`; fill explicitly when the user names '
        'a different post or several. Multi-post syndication fills source as a list of post dicts.\n'
        '5. Future-time phrases ("syndicate tomorrow at 9am") leave both slots null — the schedule '
        'flow handles that.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post being syndicated. Usually inherits from `state.active_post`. Fill '
        'explicitly only when the user names a different post. Returns a list of post dicts for '
        'multi-post syndication.\n\n'
        '### channel (required)\n\n'
        'Type: ChannelSlot. Always a list of channel name strings: `["Medium", ...]`. Fill on any '
        'channel mention including misspellings and implied references. Common values: Substack, '
        'Medium, LinkedIn, Twitter/X, dev.to. MoreThanOneTurn (the primary blog) is never included '
        '— it goes through Release instead.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Cross-post my data pipeline article to Medium."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit post + single channel. Strip 'article' status word from title.",
  "slots": {
    "source": {"post": "data pipeline"},
    "channel": ["Medium"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Send it to Substack and LinkedIn."

## Input
Active post: Attention is All You Need

## Output

```json
{
  "reasoning": "Source inherits from active_post. Two channels in current turn → two-item list.",
  "slots": {
    "source": {"post": "Attention is All You Need"},
    "channel": ["Substack", "LinkedIn"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to push my RL primer out."
Agent: "Which channels?"
User: "Medium and dev.to."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source from the first turn; channels from the third. Two-item channel list.",
  "slots": {
    "source": {"post": "RL primer"},
    "channel": ["Medium", "dev.to"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Syndicate my attention mechanism post."
Agent: "Where?"
User: "linkden."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Misspelled channel — still fill it. Map 'linkden' to canonical 'LinkedIn'.",
  "slots": {
    "source": {"post": "attention mechanism"},
    "channel": ["LinkedIn"]
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Blast my Trustworthy AI post to Medium."
Agent: "Done — it's live on Medium."
User: "Now also send my data pipelines post there."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "Prior syndicate action is completed. Current turn names a new source ('data pipelines post') and refers to the prior channel with 'there' → channel carries forward as 'Medium'. Active post is the prior source; override with the explicitly named new post.",
  "slots": {
    "source": {"post": "data pipelines"},
    "channel": ["Medium"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Cross-post my regularization and batch norm posts to LinkedIn."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two posts in one utterance → source returns a list of post dicts. Single channel → one-item list.",
  "slots": {
    "source": [{"post": "regularization"}, {"post": "batch norm"}],
    "channel": ["LinkedIn"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Let's share my latest."
Agent: "Which channels?"
User: "Medium and LinkedIn, tomorrow at 9am."

## Input
Active post: My RL Primer

## Output

```json
{
  "reasoning": "Future-time phrase ('tomorrow at 9am') triggers schedule flow — leave both slots null per rule 5 so flow-detection can reroute.",
  "slots": {
    "source": null,
    "channel": []
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Post my trustworthy AI to MoreThanOneTurn and Medium."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User names two channels but one is MoreThanOneTurn (the primary blog). Per rule 2, drop it from the list and note the exclusion — syndicate covers secondary channels only; MoreThanOneTurn would go through Release.",
  "slots": {
    "source": {"post": "trustworthy AI"},
    "channel": ["Medium"]
  }
}
```
</edge_case>''',
}


SCHEDULE_PROMPT = {
    'instructions': (
        'The Schedule Flow sets a future publication time for a post on one or more channels. It '
        'parallels Release but adds a structured time slot — future-time phrases (specific or '
        'recurring) are what distinguish scheduling from immediate release.\n\n'
        'Extract three slots: `source` (the post, usually inherited from active_post), `channel` '
        '(list of channel name strings), and `datetime` (a RangeSlot dict describing WHEN to '
        'publish). The `datetime` slot carries an ISO-format `start` timestamp plus optional `stop`, '
        '`time_len`+`unit` for duration/recurrence, and a `recurrence` boolean.'
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`; fill explicitly when the user "
        "names a post.\n"
        "2. `channel` is always a list of channel name strings (same convention as Release/Syndicate).\n"
        "3. `datetime` is a structured dict: `{start, stop, time_len, unit, recurrence}`. Granularity "
        "ranges from **week** (coarsest) through **day**, **hour**, to **minute** (finest). NEVER put "
        "free-text like 'later this week' or 'tomorrow morning' into `start` — always emit an ISO 8601 "
        "timestamp (e.g. `2026-04-19T09:00:00`) or a date-only string (`2026-04-19`) for day "
        "granularity.\n"
        "3a. **Day granularity**: 'tomorrow', 'Monday', 'April 24' → `start: '2026-04-19'`, "
        "`unit: 'day'`.\n"
        "3b. **Hour granularity**: 'Friday at 8am', 'tomorrow at 9am' → "
        "`start: '2026-04-24T08:00:00'`, `unit: 'hour'`.\n"
        "3c. **Minute granularity**: 'Friday at 8:30am', 'tomorrow at 9:15am' → "
        "`start: '2026-04-24T08:30:00'`, `unit: 'minute'`.\n"
        "3d. **Timezone**: assume the user's local time zone unless they explicitly state one. When "
        "they do say 'EST', 'UTC', etc., append the offset (`'2026-04-24T08:00:00-04:00'`).\n"
        "3e. **Time range**: 'Monday between 9am and noon' → `start: '2026-04-20T09:00:00'`, "
        "`stop: '2026-04-20T12:00:00'`, `unit: 'hour'`.\n"
        "3f. **Recurrence**: When recurrence=true, `unit` + `time_len` express the interval (every "
        "time_len * unit). 'Every Friday at 8am' → `unit: 'week'`, `time_len: 1`, `recurrence: true`. "
        "'Every other Monday' → `unit: 'week'`, `time_len: 2`. 'Daily at 9am' → `unit: 'day'`, "
        "`time_len: 1`. 'Every 3 hours' → `unit: 'hour'`, `time_len: 3`. Unit is constrained to "
        "`minute`/`hour`/`day`/`week` in this domain.\n"
        "4. Vague phrases that lack even day-level granularity ('later this week', 'sometime soon', "
        "'when convenient') leave `datetime` null — the agent asks for clarification.\n"
        "5. If the user changes just the time in a follow-up turn ('actually Monday at 9am instead'), "
        "only the `datetime` slot updates; `source` and `channel` carry forward from earlier turns."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post being scheduled. Usually inherits from `state.active_post`. Fill '
        'explicitly when the user names a different post.\n\n'
        '### channel (required)\n\n'
        'Type: ChannelSlot. Always a list of channel name strings: `["Substack", ...]`. Fill on any '
        'channel mention including misspellings and implied references. Empty list `[]` when no '
        'channel is named.\n\n'
        '### datetime (required)\n\n'
        'Type: RangeSlot. A structured dict describing the publish time. Shape: '
        '`{start, stop, time_len, unit, recurrence}`.\n'
        '- `start` (string, ISO 8601 or date-only): the scheduled moment. Day granularity at '
        'coarsest (`\'2026-04-19\'`), minute granularity at finest (`\'2026-04-19T09:00:00\'`).\n'
        '- `stop` (string, ISO 8601 or date-only): the end bound when the user names a time range. '
        'Null for point-in-time schedules.\n'
        '- `unit` (enum of `minute`/`hour`/`day`/`week`): for non-recurring schedules, the finest '
        'granularity the user specified (`8am` → `hour`, `8:30am` → `minute`, `Monday` → `day`). For '
        'recurring schedules, the unit of the recurrence interval (weekly → `week`, daily → `day`, '
        'etc.).\n'
        '- `time_len` (int): for recurring schedules, the interval count in `unit` units (every 7 '
        'days, every 14 days, etc.). 0 for non-recurring schedules.\n'
        '- `recurrence` (bool): true when the user requests a repeating schedule.\n'
        'Never put free-text like \'tomorrow morning\' into `start`. Assume local timezone unless one '
        'is explicitly named.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Schedule my regularization post on Substack for Friday 8am EST."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Post + channel + specific time all in one utterance. 'Friday 8am EST' → ISO timestamp with UTC offset (EST in April is EDT → -04:00). '8am' has hour precision (no minutes) → unit='hour'.",
  "slots": {
    "source": {"post": "regularization"},
    "channel": ["Substack"],
    "datetime": {"start": "2026-04-24T08:00:00-04:00", "stop": null, "time_len": 0, "unit": "hour", "recurrence": false}
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to queue up my RL primer."
Agent: "When and where?"
User: "Next Monday at 9am on Medium."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source from first turn; current turn supplies both datetime and channel. '9am' is hour precision → unit='hour'. No timezone named → leave naive.",
  "slots": {
    "source": {"post": "RL primer"},
    "channel": ["Medium"],
    "datetime": {"start": "2026-04-20T09:00:00", "stop": null, "time_len": 0, "unit": "hour", "recurrence": false}
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Schedule my newsletter every Friday at 8am on Substack."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Recurring weekly schedule. First occurrence is the upcoming Friday → start timestamp. Weekly → unit='week', time_len=1, recurrence=true.",
  "slots": {
    "source": {"post": "newsletter"},
    "channel": ["Substack"],
    "datetime": {"start": "2026-04-24T08:00:00", "stop": null, "time_len": 1, "unit": "week", "recurrence": true}
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Send my latest out tomorrow on Substack."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Source inherits from active_post. 'Tomorrow' is day granularity (no time given) → date-only start, unit='day'. Channel is single item.",
  "slots": {
    "source": {"post": "My ML Post"},
    "channel": ["Substack"],
    "datetime": {"start": "2026-04-19", "stop": null, "time_len": 0, "unit": "day", "recurrence": false}
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Schedule my RL primer for Friday on Medium."
Agent: "Done — set for Friday on Medium."
User: "Actually, make it Monday at 9am instead."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Per rule 5, only the datetime slot updates in the follow-up. Source and channel carry forward from the first turn; datetime becomes the revised Monday timestamp with hour precision.",
  "slots": {
    "source": {"post": "RL primer"},
    "channel": ["Medium"],
    "datetime": {"start": "2026-04-20T09:00:00", "stop": null, "time_len": 0, "unit": "hour", "recurrence": false}
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Schedule my batch norm post for LinkedIn."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source and channel are clear, but no time information is supplied. Datetime stays null so the agent can ask when.",
  "slots": {
    "source": {"post": "batch norm"},
    "channel": ["LinkedIn"],
    "datetime": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Send my latest out later this week on Medium."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "'Later this week' lacks even day-level granularity (per rule 4) — leave datetime null so the agent can ask for a specific date. Source and channel fill normally.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "channel": ["Medium"],
    "datetime": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Post my weekly digest every Monday at 9am on Substack and LinkedIn."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Recurring weekly schedule across two channels. First occurrence is the upcoming Monday at 9am. Weekly recurrence → unit='week', time_len=1, recurrence=true.",
  "slots": {
    "source": {"post": "weekly digest"},
    "channel": ["Substack", "LinkedIn"],
    "datetime": {"start": "2026-04-20T09:00:00", "stop": null, "time_len": 1, "unit": "week", "recurrence": true}
  }
}
```
</edge_case>''',
}


PREVIEW_PROMPT = {
    'instructions': (
        'The Preview Flow renders a post in a target channel\'s format so the user can review layout, '
        'images, and formatting before going live. Preview is read-only — no content is modified. '
        'Preview is distinct from Release (which publishes immediately) and Syndicate (which cross-'
        'posts to secondary channels).\n\n'
        'Extract the post being previewed (`source`, usually inherited from active_post) and the '
        'target channel (`channel`, optional — empty list defaults to the primary blog). Preview '
        'renders one channel at a time: when the user names multiple channels, pick only the first '
        'and ignore the rest.'
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user names "
        "a post. Strip trailing status words ('post', 'draft', 'article', 'note') from titles.\n"
        "2. `channel` is a list of channel name strings, but preview renders one at a time — so the "
        "list holds at most one item. When the user names multiple channels, pick only the first "
        "and drop the rest.\n"
        "3. Empty list `[]` when no channel is named — the policy defaults to the primary blog "
        "format.\n"
        "4. Map channel misspellings and synonyms to canonical names: 'lnkdin' → LinkedIn, 'X' / "
        "'twitter' → Twitter/X, 'medim' → Medium.\n"
        "5. Phrases outside the channel taxonomy ('for mobile', 'for dark mode') do NOT fill "
        "`channel` — leave `[]` and let the policy figure it out."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post to preview. Typically inherits from `state.active_post`. Fill '
        'explicitly when the user names a different post; strip trailing status words from titles.\n\n'
        '### channel (optional)\n\n'
        'Type: ChannelSlot. A list holding at most one channel name string. Fill on any channel '
        'mention including misspellings. When the user names multiple channels, keep only the first. '
        'Empty list `[]` when no channel is named — the policy defaults to the primary blog.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "What will my transformer post look like on Substack?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Indirect preview request ('what will it look like'). Post and channel both explicit; one-item list.",
  "slots": {
    "source": {"post": "transformer"},
    "channel": ["Substack"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Give me a mock-up."

## Input
Active post: Attention is All You Need

## Output

```json
{
  "reasoning": "Terse mock-up request — source inherits from active_post; no channel named → empty list. Policy falls back to primary blog.",
  "slots": {
    "source": {"post": "Attention is All You Need"},
    "channel": []
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "How will my RL post render?"
Agent: "On which channel?"
User: "Medium."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source from first turn; channel from third. Single-item list.",
  "slots": {
    "source": {"post": "RL"},
    "channel": ["Medium"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to see how my regularization post reads as a LinkedIn article."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'See how it reads as a LinkedIn article' is preview phrasing. Post and channel both explicit; one-item list.",
  "slots": {
    "source": {"post": "regularization"},
    "channel": ["LinkedIn"]
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Pull up my calibration post."
Agent: "Want to see how it'll render?"
User: "Yeah, on medim."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Misspelled channel mapped to canonical 'Medium'. Source from first turn; the user's yes-plus-channel in turn 3 is what fills the preview intent's channel.",
  "slots": {
    "source": {"post": "calibration"},
    "channel": ["Medium"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Show me how my RL post looks on Medium."
Agent: "Here it is."
User: "Actually let me see the transformer post on Substack instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts with 'actually...instead' → source switches to transformer, channel to Substack. Prior Medium preview is dropped.",
  "slots": {
    "source": {"post": "transformer"},
    "channel": ["Substack"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Can I see my RL post on Substack and Medium?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two channels named but preview renders one at a time — pick the first ('Substack') and drop Medium per rule 2.",
  "slots": {
    "source": {"post": "RL"},
    "channel": ["Substack"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Let me see how this reads on mobile."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "'Mobile' is outside the channel taxonomy per rule 5 → channel stays empty. Source inherits from active_post. Policy handles the rendering hint.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "channel": []
  }
}
```
</edge_case>''',
}


PROMOTE_PROMPT = {
    'instructions': (
        'The Promote Flow amplifies a published post\'s reach — pins to the top of the blog, marks '
        'as featured, announces to subscribers, or shares to social channels. Promote operates '
        'after Release or Syndicate has made the post live. Promote is distinct from Release '
        '(initial publication) and Syndicate (cross-posting to secondary channels).\n\n'
        'Extract the post being promoted (`source`, usually inherited from active_post) and the '
        'promotion mode (`channel`, optional). Channel is a CategorySlot with four options: `pin`, '
        '`feature`, `announce`, `social`. Fill the mode that best matches the user\'s language; '
        'leave null when the user is unspecific.'
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user "
        "names a post.\n"
        "2. `channel` picks one of: pin, feature, announce, social. Map user language to a canonical "
        "mode: 'pin to the top' / 'pin it' → pin; 'feature on the homepage' / 'mark as featured' → "
        "feature; 'announce to subscribers' / 'email the list' → announce; 'share on social' / "
        "'tweet it' / 'post to LinkedIn' / 'share on Twitter' → social.\n"
        "3. Specific social platforms (Twitter, LinkedIn, Facebook, Mastodon, etc.) map to the "
        "`social` canonical mode.\n"
        "4. When the user names a publishing-channel-like destination for generic distribution "
        "('Substack', 'Medium' without a social context), that routes to Syndicate not Promote — "
        "leave promote's channel null.\n"
        "5. Multi-mode requests ('pin and feature it') — pick the first mode since CategorySlot is "
        "single-valued. Additional modes need separate turns."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post being promoted. Typically inherits from `state.active_post`; '
        'fill explicitly when the user names a post.\n\n'
        '### channel (optional)\n\n'
        'Type: CategorySlot. One of four promotion modes (pin / feature / announce / social). Pick '
        'the mode that best matches the user\'s language; null when unspecified. Specific social '
        'platforms (Twitter, LinkedIn) map to `social`.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Pin my calibration post to the top of the blog."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Pin to the top' → channel='pin'. Post explicitly named.",
  "slots": {
    "source": {"post": "calibration"},
    "channel": "pin"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "My RL primer went live yesterday — let's give it a push."
Agent: "What kind of push?"
User: "Email the mailing list."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Indirect opener ('give it a push'); mode clarified in third turn ('email the mailing list' → announce).",
  "slots": {
    "source": {"post": "RL primer"},
    "channel": "announce"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "My transformer post is good to promote."
Agent: "Which mode — pin, feature, email, or social?"
User: "Put it on the homepage as the featured article."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Homepage as the featured article' → channel='feature'. Post named in first turn.",
  "slots": {
    "source": {"post": "transformer"},
    "channel": "feature"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Blast it out on socials."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "'Blast it out on socials' → channel='social'. Source inherits from active_post.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "channel": "social"
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "My calibration post just went live."
Agent: "Nice — congrats."
User: "Send it out on LinkedIn."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Send it out on LinkedIn' — LinkedIn is a specific social platform → maps to channel='social' per rule 3.",
  "slots": {
    "source": {"post": "calibration"},
    "channel": "social"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Share my regularization post to Medium."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Share to Medium' — Medium is a publishing channel, not a social-share context. Per rule 4, this routes to Syndicate; promote's channel stays null.",
  "slots": {
    "source": {"post": "regularization"},
    "channel": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Pin and feature my transformer post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two modes named; CategorySlot is single-valued → pick the first ('pin') per rule 5.",
  "slots": {
    "source": {"post": "transformer"},
    "channel": "pin"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Feature my regularization post."
Agent: "Featured — it's on the homepage."
User: "Actually, pin it instead — more visibility."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts 'feature' with 'actually...instead' → channel switches to 'pin'. Prior mode dropped.",
  "slots": {
    "source": {"post": "regularization"},
    "channel": "pin"
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'release': RELEASE_PROMPT,
    'syndicate': SYNDICATE_PROMPT,
    'schedule': SCHEDULE_PROMPT,
    'preview': PREVIEW_PROMPT,
    'promote': PROMOTE_PROMPT,
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
