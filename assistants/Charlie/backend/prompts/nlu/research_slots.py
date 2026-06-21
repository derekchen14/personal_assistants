INSPECT_PROMPT = {
    'instructions': (
        "Report numeric content metrics for a post — word count, section count, reading time, image count, "
        "link count, or file size. Inspect is strictly numeric; metadata-style asks (tags, status, "
        "channels, publish date) belong to the `check` flow, so leave `aspect` null when the user names "
        "only metadata and downstream will fall back to `check`. Populate `aspect` when the user names a "
        "specific numeric metric (or clearly implies one). Populate `threshold` only when the utterance "
        "expresses a comparative boundary — descriptive or raw counts do NOT fill `threshold`."
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user names a "
        "different post.\n"
        "2. `aspect` maps phrases to the closed option set {word_count, num_sections, time_to_read, "
        "image_count, num_links, post_size}. 'How long' can match word_count, time_to_read, or post_size "
        "— leave `null` when the phrasing is ambiguous so downstream can clarify. 'How many sections' → "
        "num_sections. 'Stats' or 'metrics' with no specific phrasing → `null`.\n"
        "3. `threshold` ONLY fills on comparative phrasing: 'over X', 'at least X', 'more than X', 'under "
        "X', 'below X', 'at most X'. Raw counts or descriptive numbers don't fill it.\n"
        "  a. 'My post is about 1000 words' is descriptive, not comparative — `threshold=null`.\n"
        "  b. When the user pairs a length framing with 'is that enough?' style follow-up, the length term "
        "still maps to an aspect but the subjective follow-up does NOT provide a comparative threshold.\n"
        "  c. A terse comparative follow-up ('is that over 2000?') after a prior aspect was reported "
        "carries the prior aspect forward and fills `threshold` from the new number.\n"
        "4. Treat inspect directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. The post to measure.\n\n"
        "### aspect (required)\n\n"
        "Type: CategorySlot. Options: `word_count`, `num_sections`, `time_to_read`, `image_count`, "
        "`num_links`, `post_size`. Fill when the user names or clearly implies a specific numeric metric. "
        "Leave `null` on genuinely ambiguous phrasing or when the user names only metadata (tags, status, "
        "channels) — downstream falls back to `check`.\n\n"
        "### threshold (optional)\n\n"
        "Type: ScoreSlot. The numeric boundary for the inspect comparison."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Is my data augmentation post over 1500 words?"

## Input
Active post: data augmentation

## Output

```json
{
  "reasoning": "'Over 1500 words' is explicit comparison → threshold=1500, aspect=word_count. Source matches the active post.",
  "slots": {
    "source": {"post": "data augmentation"},
    "aspect": "word_count",
    "threshold": 1500
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "How long is my calibration post?"

## Input
Active post: calibration

## Output

```json
{
  "reasoning": "'How long' could match word_count, time_to_read, or post_size — no single metric dominates, so leave aspect empty for downstream clarification. No comparison → threshold empty.",
  "slots": {
    "source": {"post": "calibration"},
    "aspect": null,
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to dig into my observability traces post."
Agent: "Pulled it up — what's next?"
User: "How many sections does it have?"

## Input

Active post: **observability traces** (id: `abcd0123`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "abcd0123", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "'How many sections' → aspect=num_sections. Raw count, no comparison → threshold empty. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "abcd0123"}],
    "aspect": "num_sections",
    "threshold": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Give me stats on my batch normalization post."

## Input
Active post: batch normalization

## Output

```json
{
  "reasoning": "'Stats' names no specific metric from the allowed set → aspect stays empty so downstream can ask. No comparison → threshold empty. Source matches the active post.",
  "slots": {
    "source": {"post": "batch normalization"},
    "aspect": null,
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "My trustworthy AI post is about 1200 words — is that enough?"

## Input
Active post: trustworthy AI

## Output

```json
{
  "reasoning": "'About 1200 words' is descriptive, not comparative. 'Is that enough' is subjective. Aspect picks up word_count from the length framing, but threshold stays empty. Source matches the active post.",
  "slots": {
    "source": {"post": "trustworthy AI"},
    "aspect": "word_count",
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Does my cooking post have at least 3 images?"

## Input
Active post: cooking

## Output

```json
{
  "reasoning": "'At least 3' is comparison phrasing → threshold=3. 'Images' maps directly to image_count. Source matches the active post.",
  "slots": {
    "source": {"post": "cooking"},
    "aspect": "image_count",
    "threshold": 3
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Polish the intro of my transformer deep dive post."
Agent: "Done — I've tightened the opener and cut the filler. Want to see it?"
User: "How long is it now? Like estimated time."

## Input
Active post: transformer deep dive

## Output

```json
{
  "reasoning": "Prior turns were a polish on an existing post that wrapped up. Current turn asks 'how long...like estimated time' — bare 'how long' is ambiguous between word_count / time_to_read / post_size, but the 'like estimated time' qualifier narrows it → aspect=time_to_read. No comparison phrasing → threshold empty. Active post carries forward since the user is asking about the same post just polished.",
  "slots": {
    "source": {"post": "transformer deep dive"},
    "aspect": "time_to_read",
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "How many words are in my data augmentation post?"
Agent: "It has 1,847 words."
User: "Is that over 2000 words?"

## Input
Active post: data augmentation

## Output

```json
{
  "reasoning": "Prior turn established aspect=word_count. Current terse follow-up 'is that over 2000 words' is a comparative follow-up on the same metric → aspect=word_count carries forward; 'over 2000' fills threshold=2000. Source inherits.",
  "slots": {
    "source": {"post": "data augmentation"},
    "aspect": "word_count",
    "threshold": 2000
  }
}
```
</edge_case>''',
}


BROWSE_PROMPT = {
    'instructions': (
        "The Browse Flow is a discovery flow over the user's saved notes and tagged content — surfacing "
        "trending subjects, ideas, and content gaps. The two main objects in Hugo are posts (blog "
        "articles; drafts are just unpublished posts) and notes (shorter saved snippets). Browse handles "
        "tag-level and note-level discovery; post-level lookup belongs to the Find Flow.\n\n"
        "Map any canonical tags the user names — close synonyms permitted but stay conservative. Infer "
        "the target from the user's wording: tag-leaning phrasing points at the tag taxonomy itself, "
        "note-leaning phrasing points at the saved notes, and explicit catch-alls cover both."
    ),
    'rules': (
        "1. `query` is a list of canonical tags forming the search filter. Tag set: ai, agents, "
        "ambiguity, conference, data-strategy, dialogue, explainer, gpu, lists, machine-learning, "
        "modeling, nlp, product-strategy, research, rl, startups, trends.\n"
        "  a. Map close synonyms conservatively: 'AI/ML' → ai; 'reinforcement learning' → rl; 'NLP topics' "
        "→ nlp; 'agent stuff' → agents. Drop phrases without a clean match.\n"
        "2. `target` defaults to inference from wording: 'topics', 'tags', 'subjects' → 'tag'; 'notes', "
        "'ideas', 'snippets' → 'note'; 'everything', 'all', 'both' → 'both'.\n"
        "  a. When the user is not clearly asking about tag-level discovery, default `target` to 'note' — "
        "notes are the more common browse object.\n"
        "3. Utterances about specific posts, drafts, or titles do NOT belong here — leave both slots null.\n"
        "4. Treat browse directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### query (required)\n\n"
        "Type: FreeTextSlot. The list of canonical tags (see rule 1 for the closed set).\n\n"
        "### target (required)\n\n"
        "Type: CategorySlot. Options: tag, note, both. Tells the agent where to search (see rule "
        "3 for inference cues)."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "What topics have I been writing about lately?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Open-ended discovery, no specific tag named. 'Topics' phrasing leans toward tag-level discovery. Tags is empty (no filter); target is 'tag'.",
  "slots": {
    "query": [],
    "target": "tag"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Show me explainer ideas I haven't explored yet."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Explainer' is a canonical tag. 'Ideas' phrasing leans toward note.",
  "slots": {
    "query": ["explainer"],
    "target": "note"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I'm working on something around RL."
Agent: "Want me to surface related material?"
User: "Yeah, browse my notes on it."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Tag carries from prior turn ('RL' → 'rl'). Current turn supplies the target via 'my notes' → 'note'.",
  "slots": {
    "query": ["rl"],
    "target": "note"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Browse my saved content."
Agent: "Filtered by what?"
User: "Anything tagged agents or dialogue — show me both notes and tags."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two canonical tags supplied in current turn. Explicit 'notes and tags' phrasing → target='both'.",
  "slots": {
    "query": ["agents", "dialogue"],
    "target": "both"
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Any productivity angles?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Productivity' does not cleanly map to any canonical tag — drop it rather than forcing a closest match. 'Angles' leans tag.",
  "slots": {
    "query": [],
    "target": "tag"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Browse my AI stuff."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'AI' maps to canonical 'ai'. 'Stuff' is too vague to lean tag or note — fall back to 'note' per rule 4 (notes are the more common browse object when not clearly tag-level).",
  "slots": {
    "query": ["ai"],
    "target": "note"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Find my regularization post."
Agent: "Found it — want me to open it?"
User: "Actually, browse my agents notes instead."

## Input
Active post: regularization

## Output

```json
{
  "reasoning": "Prior turn was a Find on a specific post. Current turn switches intent with 'actually...instead' to browsing notes by tag. Active post 'regularization' is irrelevant to the new browse — ignore it. Tag = 'agents'; target = 'note'.",
  "slots": {
    "query": ["agents"],
    "target": "note"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Show me what's saved under modeling."
Agent: "Just the modeling tag, or related ones too?"
User: "Add nlp and research to that."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Tags accumulate across turns: 'modeling' from the first turn, 'nlp' and 'research' from the third. 'Saved under' phrasing leans toward note-level discovery.",
  "slots": {
    "query": ["modeling", "nlp", "research"],
    "target": "note"
  }
}
```
</edge_case>''',
}


SUMMARIZE_PROMPT = {
    'instructions': (
        "The Summarize Flow synthesizes a post (or set of posts) into a short paragraph capturing the "
        "core argument, target audience, and main takeaways. Common uses: generating excerpts, SEO "
        "descriptions, or pre-reads before a follow-up post.\n\n"
        "Extract the target post(s) into `source` as a list of post dicts. Each dict must carry "
        "`post`; add `sec` when the user narrows to a section. Length is optional, measured in number "
        "of sentences, and defaults to 5 downstream when left null."
    ),
    'rules': (
        "1. `source` is always a list of post dicts. Single post → one-item list: `[{post: X}]`. "
        "Multi-post summarization (e.g., for comparison) → multi-item list. Each dict must carry "
        "`post`; add `sec` when the user narrows to a section.\n"
        "  a. Inherit source from active_post on terse utterances ('summarize it'); fill explicitly "
        "when the user names a post.\n"
        "2. `length` is the number of sentences the user wants. Fire on explicit sentence counts "
        "('in 3 sentences') and on paragraph counts via approximation (1 paragraph ≈ 5 sentences, "
        "2 paragraphs ≈ 10 sentences, etc.).\n"
        "  a. Word-based specifications ('in 200 words') and qualitative descriptors ('short', "
        "'brief', 'quick') do NOT fill length — leave null.\n"
        "  b. Range phrasing ('between 2 and 4 sentences') fills with the AVERAGE: "
        "`length = round((low + high) / 2)`. Examples: '2 to 4' → 3; '5 to 9' → 7.\n"
        "3. Treat summarize directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. Always a list of post dicts. Each dict must carry `post`; optionally add "
        "`sec` when the user narrows to a section. Single-post summarization still returns a "
        "one-item list.\n\n"
        "### length (optional)\n\n"
        "Type: LevelSlot. Number of sentences the user wants in the summary. Fill on explicit "
        "sentence counts ('in 3 sentences' → 3) and on paragraph counts via approximation (1 "
        "paragraph ≈ 5 sentences, 2 paragraphs ≈ 10, etc.). Leave null on qualitative descriptors "
        "('short', 'brief') and word-based counts."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Give me a summary of my transformer deep dive post in 3 sentences."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit post + explicit sentence count. Source is a one-item list; length captured directly.",
  "slots": {
    "source": [{"post": "transformer deep dive"}],
    "length": 3
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Can you summarize my RL primer?"
Agent: "How long?"
User: "Two paragraphs."

## Input

Active post: **RL primer** (id: `ef012345`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "ef012345", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Active post is grounded — copy `post_id` verbatim from the source slot. Current turn gives paragraph count → approximate to sentences (2 paragraphs × 5 sentences/paragraph = 10).",
  "slots": {
    "source": [{"post": "ef012345"}],
    "length": 10
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I need a summary of my regularization post."
Agent: "Whole post or a specific section?"
User: "Just the methods section, in 4 sentences."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Post from first turn; section narrowed in third turn → source dict carries both. Length is explicit sentence count.",
  "slots": {
    "source": [{"post": "regularization", "sec": "methods"}],
    "length": 4
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Give me a short summary of my calibration post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Short' is a qualitative descriptor — does NOT fill length per rule 4. Source is a one-item list.",
  "slots": {
    "source": [{"post": "calibration"}],
    "length": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "TL;DR my RL post."
Agent: "How long?"
User: "Actually, summarize my transformer post instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts the prior post with 'actually...instead' — ignore 'RL post' and use 'transformer' from the current turn. No length given → null.",
  "slots": {
    "source": [{"post": "transformer"}],
    "length": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Condense my methods post in 2 to 4 sentences."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Range phrasing → use the average per rule 5: round((2 + 4) / 2) = 3.",
  "slots": {
    "source": [{"post": "methods"}],
    "length": 3
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Boil down my regularization and batch norm posts."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Multi-post comparison — source returns two post dicts in the list. No length given → null.",
  "slots": {
    "source": [{"post": "regularization"}, {"post": "batch norm"}],
    "length": null
  }
}
```
</edge_case>''',
}


FIND_PROMPT = {
    'instructions': (
        "The Find Flow searches the user's previous posts by keyword or title. It returns matching "
        "posts with their titles, excerpts, and publication dates, sorted by relevance. Find is the "
        "post-level counterpart to Browse (which handles tags and notes); there is no separate "
        "'topic' categorization — tag-based discovery routes to Browse.\n\n"
        "Extract the search term (`query`) and the number of results requested (`count`). Query "
        "should be stripped of filler like 'posts about' or 'anything on' — the downstream search "
        "expands synonyms across a few candidate queries, so a clean phrase performs better than "
        "verbose wording. Count is optional and only fires when an integer clearly refers to the "
        "number of results to return."
    ),
    'rules': (
        "1. `query` captures the search term as a clean keyword or phrase. Strip filler like 'posts "
        "about', 'anything on', 'my writing on', 'stuff about'.\n"
        "  a. Multi-topic queries ('posts on dropout and batch norm') go into `query` as a single "
        "string with the conjunction preserved — the search policy expands synonyms and deduplicates "
        "post_ids downstream.\n"
        "  b. If the user names a specific post title as the query ('find my transformer deep dive "
        "post'), fill `query` with the title phrase — the search engine will exact-match it.\n"
        "2. `count` fires ONLY when an integer clearly refers to the number of results to return "
        "('show me 5 posts', 'top 3', 'the 10 most recent'). Integers that are part of the query "
        "itself or refer to something other than result count do NOT fill count (e.g., 'posts about "
        "GPT-3' → query='GPT-3', count=null).\n"
        "3. When the user is terse with no query phrase ('show me more like that'), leave `query` "
        "null so the agent can ask what to search for; `count` still fires if a number is mentioned.\n"
        "4. Treat find directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### query (required)\n\n"
        "Type: ExactSlot. The search term or phrase. Strip filler words like 'posts about', "
        "'anything on' to get a clean searchable keyword. Multi-topic queries stay as a single "
        "string. Also accepts a full post title when the user names one directly.\n\n"
        "### count (optional)\n\n"
        "Type: LevelSlot (threshold=1). Number of search results requested. Fill only when the "
        "integer clearly refers to result count, not part of the query itself."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Show me my top 5 posts on NLP."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit count (5) refers to number of results. Strip filler ('my top'), preserve keyword ('NLP').",
  "slots": {
    "query": "NLP",
    "count": 5
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Find something for me."
Agent: "What would you like to search for?"
User: "Anything on reward shaping."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Query arrives in current turn; 'anything on' is filler → strip. No count.",
  "slots": {
    "query": "reward shaping",
    "count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Find my transformer deep dive post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User named a specific title. Fill query with the title phrase — search will exact-match.",
  "slots": {
    "query": "transformer deep dive",
    "count": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Brainstorm angles on RL."
Agent: "Here are five angles..."
User: "Never mind — find all my posts on calibration instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts the brainstorm with 'never mind — ... instead' and pivots to find. Ignore the prior RL context; extract calibration as the new query.",
  "slots": {
    "query": "calibration",
    "count": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Find posts on dropout and batch norm."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Multi-topic query — kept as a single string with the conjunction preserved per rule 2. The search policy expands synonyms downstream.",
  "slots": {
    "query": "dropout and batch norm",
    "count": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Find posts about GPT-3."

## Input
Active post: None

## Output

```json
{
  "reasoning": "The integer '3' is part of the keyword 'GPT-3' — it does NOT refer to the number of results to return per rule 3. Query preserves the keyword; count stays null.",
  "slots": {
    "query": "GPT-3",
    "count": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Pull up anything I've written recently."
Agent: "What topic?"
User: "Anything — just the 10 most recent."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User doesn't supply a keyword even on clarification — query stays null so the policy can list recent posts without filtering. Count captures the explicit integer referring to number of results.",
  "slots": {
    "query": null,
    "count": 10
  }
}
```
</edge_case>''',
}


COMPARE_PROMPT = {
    'instructions': (
        "The Compare Flow contrasts style or structure across two or more posts — sentence length, "
        "paragraph density, heading patterns, vocabulary, and tonal consistency. It requires at "
        "least two posts and supports at most three in a single comparison. Compare is distinct from "
        "Diff (which shows additions/deletions between two versions of the same section).\n\n"
        "Extract the posts being compared (`source`, a list of post dicts). When the user names "
        "both posts explicitly, fill both. When only one is named and active_post is set, fill "
        "source as `[active_post, named_post]`. When only one post is resolvable, fill source with "
        "just that one — the policy clarifies for the second."
    ),
    'rules': (
        "1. `source` always carries a list of post dicts. Each dict has at minimum `post`; "
        "optionally `sec` when the user scopes to a specific section.\n"
        "  a. When the user names multiple posts in one utterance, fill source with all of them "
        "  — up to a maximum of three.\n"
        "  b. When the user names one post and active_post is set, fill source as "
        "  `[{post: <active_post>}, {post: <named_post>}]` — active_post first, named post "
        "  second.\n"
        "  c. When only one post is resolvable total (no active_post, only one explicit "
        "  reference), fill source with just that one; the policy will ask for the second.\n"
        "  d. NLU does not reach into conversation history for implicit post references — only "
        "  what the current utterance and active_post provide.\n"
        "2. `category` fires when the user names what to compare. Map synonyms: 'metrics' / "
        "'numbers' / 'length' / 'sentence variance' → inspect; 'metadata' / 'tags' / 'dates' / "
        "'status' → check; 'voice' / 'sound' / 'tone' / 'feel' / 'register' → tone. Leave null on "
        "bare comparisons so the flow can clarify."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot (min_size=2). A list of post dicts, at least 2 entries and at most 3. "
        "Each dict carries `{post: <title>}` at minimum; optionally `sec` when the user names a "
        "section-level comparison. Fill with every post the user explicitly names; prepend "
        "active_post as the first entry when only one post is named.\n\n"
        "### category (required)\n\n"
        "Type: CategorySlot. Options: inspect (compare metrics like length and sentence "
        "variance), check (compare metadata like tags, status, dates), tone (compare voice, "
        "register, story arc). Pick the closest option when the user names what to compare "
        "('compare the metrics' → inspect; 'how do they sound different' → tone). Leave "
        "null when no comparison kind is named so the flow can clarify.\n\n"
        "### lookback (optional)\n\n"
        "Type: PositionSlot. Grafted from diff: which earlier version to diff against, 0-based from "
        "the latest. Fires on version language ('vs the previous draft' → 1). Leave null for a "
        "plain post-to-post comparison.\n\n"
        "### mapping (optional)\n\n"
        "Type: DictionarySlot. Grafted from diff: key-value field/term pairings that align the two "
        "posts for a side-by-side diff. Leave null unless the user spells out a mapping."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "How does my ML as Software 2.0 draft differ from The Hype of Machine Learning?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Differ from' is a comparison phrase. Two posts named; strip 'draft' status word. No comparison kind named so category stays null.",
  "slots": {
    "source": [{"post": "ML as Software 2.0"}, {"post": "The Hype of Machine Learning"}],
    "category": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Put this side by side with my RL primer."

## Input

Active post: **calibration** (id: `7e8f9012`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "7e8f9012", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "'Side by side with' is a comparison synonym. Active post 'calibration' is grounded — copy `post_id` verbatim from the source slot for the first entry. The second entry uses the title 'RL primer' since no id is available for it. Per rule 3, source = [active_post, named_post] — active first. No kind named so category stays null.",
  "slots": {
    "source": [{"post": "7e8f9012"}, {"post": "RL primer"}],
    "category": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to see how my transformer post stacks up against another one."
Agent: "Which one?"
User: "My attention mechanism post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Stacks up against' is a comparison phrase. Both posts arrive across two turns; fill source with both. No kind named so category stays null.",
  "slots": {
    "source": [{"post": "transformer"}, {"post": "attention mechanism"}],
    "category": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Contrast the intro of my transformer post with the intro of my RL primer."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Contrast' triggers comparison. Section-level — both entries carry post + sec. No kind named so category stays null.",
  "slots": {
    "source": [
      {"post": "transformer", "sec": "intro"},
      {"post": "RL primer", "sec": "intro"}
    ],
    "category": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compare my transformer post and my RL primer."
Agent: "Should I compare metrics, metadata, or tone?"
User: "Tone."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two posts named in the first turn; the third turn picks the comparison kind. 'Tone' maps cleanly to category=tone per rule 7. Source already covers both posts.",
  "slots": {
    "source": [{"post": "transformer"}, {"post": "RL primer"}],
    "category": "tone"
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Where does my calibration post feel different from my other one?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Feel different' maps to category=tone per rule 7 ('feel' synonym). Only one post resolvable ('calibration'); 'my other one' is an implicit reference that NLU does not resolve. Source fills with just the one post per rule 4.",
  "slots": {
    "source": [{"post": "calibration"}],
    "category": "tone"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Stack my RL post and my calibration post against each other."
Agent: "Here's the comparison..."
User: "Wait — do it for my regularization and batch norm posts instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts the prior pair with 'wait...instead' → source switches to regularization + batch norm. Prior pair dropped. No kind named so category stays null.",
  "slots": {
    "source": [{"post": "regularization"}, {"post": "batch norm"}],
    "category": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "How does my agent harness post read next to my transformer primer?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "'How does X read next to Y' is a comparison phrase. Two posts named. No kind named so category stays null.",
  "slots": {
    "source": [{"post": "agent harness"}, {"post": "transformer primer"}],
    "category": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Put my transformer, RL primer, and calibration posts side by side."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Three posts named — at the maximum allowed per rule 2. Fill all three. No kind named so category stays null.",
  "slots": {
    "source": [
      {"post": "transformer"},
      {"post": "RL primer"},
      {"post": "calibration"}
    ],
    "category": null
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'inspect': INSPECT_PROMPT,
    'browse': BROWSE_PROMPT,
    'summarize': SUMMARIZE_PROMPT,
    'check': {
        'instructions': 'Show technical metadata for a post — status (draft/scheduled/published), dates, category tags, channels, featured image flag.',
        'rules': '- source (optional): A specific post to check. If omitted, shows an overview of all drafts.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's the status?"

## Input

Active post: **EMNLP 2020 Highlights** (id: `3a4b5c6d`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "3a4b5c6d", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "3a4b5c6d"}]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Which of my drafts are scheduled?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null
  }
}
```
</positive_example>''',
    },
    'find': FIND_PROMPT,
    'compare': COMPARE_PROMPT,
    'diff': {
        'instructions': 'Show what changed between two versions of a post or section — additions, deletions, and modifications.',
        'rules': '''- source (required): The post (and optionally section) to diff.
- lookback (elective): How many versions back to compare. "Last revision" → 1, "two versions ago" → 2. Use this when the user specifies a numeric distance.
- mapping (elective): Named version comparison as key-value pairs (e.g., {"draft": "published"}). Use this when the user names specific stages rather than a numeric lookback. Only one of lookback or mapping should be filled.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What changed since the last revision?"

## Input

Active post: **Solving the Long Tail** (id: `b1c2d3e4`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "b1c2d3e4", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title. 'Last revision' → lookback=1.",
  "slots": {
    "source": [{"post": "b1c2d3e4"}],
    "lookback": 1,
    "mapping": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Show me the differences between the draft and published version of Data Augmentation"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Data Augmentation"
    },
    "lookback": null,
    "mapping": {
      "draft": "published"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compare the current draft of my ML post against two versions ago"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ML"
    },
    "lookback": 2,
    "mapping": null
  }
}
```
</positive_example>''',
    },
}
