INSPECT_PROMPT = {
    'instructions': (
        "The Inspect Flow reports metrics and metadata about the user's content — word count, section "
        "count, reading time, image count, post size, category tags, featured image, "
        "publication/edit/scheduled dates, channels, and status. Questions may be scoped to one post "
        "('how long is my caching post?') or span the library ('how many posts did I publish last "
        "month?').\n\n"
        "Extract WHICH content is being measured (source), WHAT is being measured (metrics), and any "
        "numeric bound the user wants the metric checked against (threshold). The agent gathers the "
        "numbers itself — never guess values, only capture what to measure."
    ),
    'rules': (
        "1. `source` holds the post being inspected. Library-wide questions ('how many posts...', "
        "'which drafts...') leave `source` null — the empty source IS the library-wide signal.\n"
        "2. `metrics` is the list of things to measure, one item per metric, named with the user's "
        "own noun ('word count', 'reading time', 'tags', 'status', 'posts published last month').\n"
        "3. `threshold` fills ONLY when the user states a numeric bound to check against ('is it "
        "under 1500 words?' → 1500). Descriptive numbers that are not bounds do not fill it.\n"
        "4. Treat inspect directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'that one too'). `source` is the exception: it "
        "carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (elective)\n\n"
        "Type: SourceSlot. The post whose metrics/metadata the user wants. Null for library-wide "
        "questions.\n\n"
        "### metrics (elective)\n\n"
        "Type: ChecklistSlot. One item per requested metric or metadata field: "
        "{\"name\": <metric>, \"description\": <qualifier or null>}.\n\n"
        "### threshold (optional)\n\n"
        "Type: ScoreSlot. A numeric bound the user wants the metric compared against. Only explicit "
        "bounds fill it."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "How long is my post on container orchestration?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Post named by topic. 'How long' asks for length — word count / reading time. No bound stated.",
  "slots": {
    "source": [{"post": "container orchestration", "sec": null, "snip": null, "chl": null}],
    "metrics": [{"name": "word count", "description": "length of the post"}],
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "How many posts did I publish last month?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Library-wide count — no single post, so source stays null (rule 1). The metric is the published-post count with a time qualifier.",
  "slots": {
    "source": null,
    "metrics": [{"name": "posts published", "description": "last month"}],
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Is the draft still under 1500 words?"

## Input
Active post: **Soil Health for Small Farms** (id: `7c2d9e1f`)

## Output

```json
{
  "reasoning": "'The draft' refers to the active post — copy its id verbatim (rule 4 exception). 'Under 1500' is an explicit bound → threshold=1500.",
  "slots": {
    "source": [{"post": "7c2d9e1f", "sec": null, "snip": null, "chl": null}],
    "metrics": [{"name": "word count", "description": "check against the limit"}],
    "threshold": 1500
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "What tags and status does my ferment guide have?"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two metadata fields requested for one named post: tags and status — one metrics item each.",
  "slots": {
    "source": [{"post": "ferment guide", "sec": null, "snip": null, "chl": null}],
    "metrics": [{"name": "tags", "description": null}, {"name": "status", "description": null}],
    "threshold": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "My intro feels bloated at around 300 words."

## Input
Active post: **Bird Migration Myths** (id: `2e8a4c6b`)

## Output

```json
{
  "reasoning": "'Around 300 words' is descriptive, not a bound to check against — threshold stays null (rule 3). The measured thing is the intro's word count on the active post.",
  "slots": {
    "source": [{"post": "2e8a4c6b", "sec": "intro", "snip": null, "chl": null}],
    "metrics": [{"name": "word count", "description": "intro section"}],
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Give me the stats."

## Input
Active post: **Night Photography Basics** (id: `9b1f3d5a`)

## Output

```json
{
  "reasoning": "'Stats' names no specific metric — leave metrics null and let the agent report the standard set. Source carries from the active post.",
  "slots": {
    "source": [{"post": "9b1f3d5a", "sec": null, "snip": null, "chl": null}],
    "metrics": null,
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Which channels is the sourdough post live on?"
Agent: "It went out on the blog and Substack."
User: "And when was it last edited?"

## Input
Active post: **Sourdough Starters Demystified** (id: `4f7e2a9c`)

## Output

```json
{
  "reasoning": "Current turn asks one new metadata field (last edited date) about the same post. Prior turn's channels question was already answered — current-turn-only (rule 4).",
  "slots": {
    "source": [{"post": "4f7e2a9c", "sec": null, "snip": null, "chl": null}],
    "metrics": [{"name": "last edited date", "description": null}],
    "threshold": null
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
        "paragraph density, heading patterns, vocabulary, and tonal consistency. It also handles "
        "version-to-version contrasts (additions/deletions between two drafts of the same section). "
        "It requires at least two posts and supports at most three in a single comparison.\n\n"
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
        "Type: PositionSlot. Which earlier version to compare against, 0-based from "
        "the latest. Fires on version language ('vs the previous draft' → 1). Leave null for a "
        "plain post-to-post comparison.\n\n"
        "### mapping (optional)\n\n"
        "Type: DictionarySlot. Key-value field/term pairings that align the two "
        "posts for a side-by-side comparison. Leave null unless the user spells out a mapping."
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
    'summarize': SUMMARIZE_PROMPT,
    'find': FIND_PROMPT,
    'compare': COMPARE_PROMPT,
}
