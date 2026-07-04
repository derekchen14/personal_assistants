RELEASE_PROMPT = {
    'instructions': (
        "The Release Flow publishes a finished post to its primary blog channel as the terminal step in "
        "the drafting lifecycle. It typically comes after other flows, such as Compose and Rework.\n\n"
        "Release goes to the primary blog by default and can also cross-post to secondary channels named "
        "in the `channel` slot ('publish to Medium', 'post on LinkedIn'). Identify which post(s) are "
        "being released and any secondary channels. Source is usually pre-filled from the active post; "
        "the user may name a different one or several."
    ),
    'rules': (
        "1. Pull `source` from the utterance or carry over from the grounded active post when the "
        "utterance is terse ('publish it').\n"
        "  a. When the user names multiple posts to release, `source` returns a list of post dicts.\n"
        "2. Future-time language ('publish tomorrow at 9am') leaves source null — the schedule flow "
        "handles that.\n"
        "3. Treat release directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. References the post (or list of posts) to publish.\n\n"
        "### channel (optional)\n\n"
        "Type: ChannelSlot. A list of secondary channel name strings to "
        "cross-post to (`['Medium', ...]`). Fill on any channel mention including misspellings. "
        "The primary blog is never included — a bare release goes there by default. Leave null "
        "when the user only publishes to the main blog."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Publish it."

## Input

Active post: **Attention is All You Need** (id: `1a2b3c4d`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "1a2b3c4d", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Terse release. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "1a2b3c4d"}]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Push the History of Seq2Seq draft live."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit post; strip trailing 'draft' status word.",
  "slots": {
    "source": {"post": "History of Seq2Seq"}
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
  "reasoning": "Title given. 'Now' is emphasis, not schedule.",
  "slots": {
    "source": {"post": "crypto investing"}
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Release my regularization post and my batch norm draft."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two posts in one utterance → source returns a list. Strip 'draft' status word from the second title.",
  "slots": {
    "source": [{"post": "regularization"}, {"post": "batch norm"}]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "I'm working on my RL primer."
Agent: "Should I help you draft a section?"
User: "Hold off — publish my data augmentation post instead."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Active post is 'RL primer', but the user explicitly redirects to a different post with 'instead'. Use the named post.",
  "slots": {
    "source": {"post": "data augmentation"}
  }
}
```
</edge_case>''',
}

SCHEDULE_PROMPT = {
    'instructions': (
        "The Schedule Flow sets a future publication time for a post on one or more channels. It "
        "parallels Release but adds a structured time slot — future-time phrases (specific or "
        "recurring) are what distinguish scheduling from immediate release.\n\n"
        "Extract three slots: `source` (the post, usually inherited from active_post), `channel` "
        "(list of channel name strings), and `datetime` (a RangeSlot dict describing WHEN to "
        "publish). The `datetime` slot carries an ISO-format `start` timestamp plus optional `stop`, "
        "`time_len`+`unit` for duration/recurrence, and a `recurrence` boolean."
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`; fill explicitly when the user "
        "names a post.\n"
        "2. `channel` is always a list of channel name strings (same convention as Release).\n"
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
        "3g. Vague phrases that lack even day-level granularity ('later this week', 'sometime soon', "
        "'when convenient') leave `datetime` null — the agent asks for clarification.\n"
        "4. If the user changes just the time in a follow-up turn ('actually Monday at 9am instead'), "
        "only the `datetime` slot updates; `source` and `channel` carry forward from earlier turns.\n"
        "5. Treat schedule directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. The post being scheduled.\n\n"
        "### channel (required)\n\n"
        "Type: ChannelSlot. Always a list of channel name strings: `['Substack', ...]`. Fill on any "
        "channel mention including misspellings and implied references. Empty list `[]` when no "
        "channel is named.\n\n"
        "### datetime (required)\n\n"
        "Type: RangeSlot. A structured dict describing the publish time. Shape: "
        "`{start, stop, time_len, unit, recurrence}`.\n"
        "- `start` (string, ISO 8601 or date-only): the scheduled moment. Day granularity at "
        "coarsest (`'2026-04-19'`), minute granularity at finest (`'2026-04-19T09:00:00'`).\n"
        "- `stop` (string, ISO 8601 or date-only): the end bound when the user names a time range. "
        "Null for point-in-time schedules.\n"
        "- `unit` (enum of `minute`/`hour`/`day`/`week`): for non-recurring schedules, the finest "
        "granularity the user specified (`8am` → `hour`, `8:30am` → `minute`, `Monday` → `day`). For "
        "recurring schedules, the unit of the recurrence interval (weekly → `week`, daily → `day`, "
        "etc.).\n"
        "- `time_len` (int): for recurring schedules, the interval count in `unit` units (every 7 "
        "days, every 14 days, etc.). 0 for non-recurring schedules.\n"
        "- `recurrence` (bool): true when the user requests a repeating schedule.\n"
        "Never put free-text like 'tomorrow morning' into `start`. Assume local timezone unless one "
        "is explicitly named."
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

Active post: **My ML Post** (id: `4b5c6d7e`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "4b5c6d7e", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title. 'Tomorrow' is day granularity (no time given) → date-only start, unit='day'. Channel is single item.",
  "slots": {
    "source": [{"post": "4b5c6d7e"}],
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


PROMPTS = {
    'release': RELEASE_PROMPT,
    'schedule': SCHEDULE_PROMPT,
}
