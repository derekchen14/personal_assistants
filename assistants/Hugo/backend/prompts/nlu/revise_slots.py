REWORK_PROMPT = {
    'instructions': (
        "The Rework Flow is major revision of prose that already exists — restructuring sections, "
        "replacing weak arguments, or weaving in itemized edits across more than one section. "
        "Source can carry sections or a snippet target.\n\n"
        "Source is typically pre-filled with the post; the user may add one or more section names. "
        "Beyond that, the user usually fills exactly one of: `category` (a tightly-defined verb that "
        "maps to a deterministic operation), `suggestions` (a numbered or bulleted list of specific "
        "edits), or `remove` (an explicit piece to cut). When the request does not map cleanly, leave "
        "all electives null so the flow can clarify."
    ),
    'rules': (
        "1. Source: post is pre-filled. If the user names a section, fill `sec`. For a swap utterance "
        "('swap A and B'), source.values must carry BOTH section names. If the user names a "
        "paragraph/sentence/phrase scope, fill `source.snip` instead and leave `post`/`sec` off — this "
        "triggers a re-route to Polish.\n"
        "2. Exactly one of `category` / `suggestions` / `remove` must fill (or all null when no clean "
        "direction):\n"
        "  a. `category` is a CategorySlot. Pick the closest option only when the verb maps cleanly. "
        "Lean toward null on the fence.\n"
        "     - `swap`: explicit 'swap' / 'interchange' / 'switch the order of' with two named sections.\n"
        "     - `to_top`: 'move to top' / 'make it first' / 'promote to first'.\n"
        "     - `to_end`: 'move to end' / 'make it last' / 'put at the bottom'.\n"
        "     - `trim`: 'shorten' / 'trim down' / 'reduce length' applied to multiple sections.\n"
        "     - `sharpen`: 'add evidence' / 'strengthen the arguments' / 'more depth across the post'.\n"
        "     - `reframe`: 'different angle' / 'different audience' / 'shift the lens'.\n"
        "  b. `suggestions` fires on numbered or bulleted lists with at least 2 items. Each item is one "
        "suggestion. Ambiguous verbs like 'tighten' or 'improve flow' leave this null.\n"
        "  c. `remove` fires only on explicit cut/drop/delete language targeting a specific piece. Vague "
        "dissatisfaction does NOT fill this slot.\n"
        "  d. Most utterances fill ONE of category / suggestions / remove. They can co-fire (e.g., a "
        "numbered list that includes one explicit deletion → `suggestions` + `remove`), but `category` "
        "and `suggestions` rarely co-occur — categories are deterministic verbs, suggestions are "
        "itemized prose.\n"
        "3. Treat rework directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. References the target of the rework. Typically pre-filled with the post; "
        "the user may add one or more section names. For swap, BOTH section names must appear as two "
        "separate entries in `source.values`. If the user names a paragraph/sentence/phrase scope, "
        "fill `snip` instead — this triggers a re-route to Polish.\n\n"
        "### category (elective)\n\n"
        "Type: CategorySlot. Options: swap, to_top, to_end, trim, sharpen, reframe (see rule 2a "
        "for verb mappings).\n\n"
        "### suggestions (elective)\n\n"
        "Type: ChecklistSlot. A list of specific changes the user has itemized. Each item is one "
        "suggestion. Fires on numbered or bulleted lists with at least 2 items. Leave null on "
        "prose-only critique.\n\n"
        "### remove (optional)\n\n"
        "Type: RemovalSlot. A specific piece of content to cut during the rework. Fill only when the "
        "user clearly targets something to remove ('drop the tangent', 'cut the footnote'). Vague "
        "dissatisfaction does NOT fill this slot."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Swap the order of the Process and Ideas sections in my agent design post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit 'swap' verb with two named sections → category=swap. Source must carry BOTH section names per rule 1.",
  "slots": {
    "source": {"post": "agent design", "sec": ["process", "ideas"]},
    "category": "swap",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Move the Limitations section to the bottom of my regularization post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Move to the bottom' maps cleanly to to_end. One named section in source.",
  "slots": {
    "source": {"post": "regularization", "sec": "limitations"},
    "category": "to_end",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Promote the Findings section to the top of my eval post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Promote to the top' maps cleanly to to_top. Single named section.",
  "slots": {
    "source": {"post": "eval", "sec": "findings"},
    "category": "to_top",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to rework my methods section."
Agent: "Sure — what changes do you want?"
User: "1) lead with the experiment design, 2) cut the historical preamble, 3) add a comparison table."

## Input

Active post: **regularization** (id: `8a9b0c1d`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "8a9b0c1d", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Section comes from the first turn. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title. Numbered list of 3 items → suggestions. Item #2 is also explicit removal language → remove fires alongside. category stays null since the verbs are itemized prose, not a single canonical operation.",
  "slots": {
    "source": [{"post": "8a9b0c1d", "sec": "methods"}],
    "category": null,
    "suggestions": [
      "lead with the experiment design",
      "cut the historical preamble",
      "add a comparison table"
    ],
    "remove": "the historical preamble"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Strengthen the arguments throughout my agent design post — they need more concrete evidence."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Strengthen the arguments' / 'more concrete evidence' across the post → category=sharpen. No itemized list.",
  "slots": {
    "source": {"post": "agent design"},
    "category": "sharpen",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Trim the regularization post down — every section is too long."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Trim down' applied to multiple sections → category=trim. The policy will fall back to Simplify.",
  "slots": {
    "source": {"post": "regularization"},
    "category": "trim",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Reframe my agent design post for a business audience instead of researchers."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit 'reframe' with an audience shift → category=reframe. The policy will ask for concrete bullet points to capture as suggestions.",
  "slots": {
    "source": {"post": "agent design"},
    "category": "reframe",
    "suggestions": null,
    "remove": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Rework the second paragraph in my methods section — it's too dense."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User named a paragraph scope ('the second paragraph'). Per rule 1, fill source.snip and leave post/sec off — this triggers a re-route to Polish. No category fits.",
  "slots": {
    "source": {"snip": "the second paragraph in my methods section"},
    "category": null,
    "suggestions": null,
    "remove": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Rework the methods section."
Agent: "Got it — what specifically?"
User: "Actually scratch that, rework the intro instead and tighten it."

## Input
Active post: My ML Paper

## Output

```json
{
  "reasoning": "User retracts the prior section choice with 'scratch that' and switches to intro. 'Tighten' is ambiguous between trim and sharpen — per rule 2, lean toward null on the fence so the flow clarifies.",
  "slots": {
    "source": {"post": "My ML Paper", "sec": "intro"},
    "category": null,
    "suggestions": null,
    "remove": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Rework the conclusion of my RL post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Bare rework directive — section named, no category verb, no itemized list. All electives stay null so the flow asks what direction.",
  "slots": {
    "source": {"post": "RL", "sec": "conclusion"},
    "category": null,
    "suggestions": null,
    "remove": null
  }
}
```
</edge_case>''',
}

POLISH_PROMPT = {
    'instructions': (
        "The Polish Flow covers fine-grained editing within a paragraph, sentence, or phrase — improving "
        "word choice, tightening sentences, fixing transitions, and smoothing flow without changing "
        "meaning or structure. Scope is always within a single paragraph or an image caption, not "
        "across sections or the whole post; bigger revisions go through Rework instead.\n"
        "Extract the `source` which must include a snippet or section along with the post, and any stylistic "
        "direction as `style_notes`. The `image` slot is relevant only when the user asks to add or edit "
        "an image caption, or to regenerate an existing image."
    ),
    'rules': (
        "1. `source` fills `snip` when the user names a paragraph/sentence/phrase ('the opening "
        "paragraph'), or `sec` when they name a section ('the methods section'), or both when context "
        "mentions both (e.g., 'the opening of the methods section' → sec=methods, snip=opening).\n"
        "  a. The `post` should already be known, so only change it if the user has mentioned a completely "
        "  new one."
        "  b. Since Polish is for targeted edits, we require that `sec` or `snip` are filled. If neither "
        "  is mentioned, then leave them so `null` so we can ask the user for clarification. "
        "2. Decide whether `image` or `suggestions` are mentioned (or both stay `null` if neither image-level "
        "language nor user proposals are made):\n"
        "  a. `image` fires only on explicit image-level language — caption edits or image "
        "  regeneration. Leave null when no picture is present or mentioned.\n"
        "  b. `suggestions` fills when the user gives an enumerated list of polish edits — "
        "  numbered or bulleted, each describing one individual polish step. As a follow-up mechanism, "
        "  you can also fill via co-reference to prior agent proposals ('yes, do all three', 'just the "
        "  first two') when the prior agent turn surfaced options to choose from.\n"
        "3. `style_notes` (optional) captures stylistic direction verbatim and is often a phrase or "
        "short sentence. Specific single words ('shorter', 'punchier', 'warmer') are fine, but "
        "vague single words ('better', 'improve') leave style_notes null so the agent can clarify.\n"
        "  a. `style_notes` captures only directives from the CURRENT turn; prior-turn directives "
        "  are assumed to have been handled already.\n"
        "4. When the user says 'polish it' with only an active post grounded (no sub-section named "
        "and no direction given), leave all slots null — the agent should ask for clarification on "
        "both target and direction."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. What to polish. Most often a snippet — the user names a paragraph, "
        "sentence, or phrase. Less often a whole section, and sometimes both (sec + snip). Include "
        "`post` only when the user disambiguates across posts; otherwise active_post provides that "
        "context.\n\n"
        "### style_notes (optional)\n\n"
        "Type: FreeTextSlot. The user's stylistic direction, captured verbatim. Often a phrase or "
        "short sentence. Examples: 'short sentences, no passive voice', 'warmer tone, less academic'. "
        "Leave null on vague single-word directives like 'better' or 'punchier'.\n\n"
        "### image (elective)\n\n"
        "Type: ImageSlot. Fires only when the user asks to add or edit an image caption or to "
        "regenerate the current image. Leave null when a picture is not present and not mentioned.\n\n"
        "### suggestions (elective)\n\n"
        "Type: ChecklistSlot. A list of specific polish edits the user has itemized. Each item "
        "is one polish step. Fires primarily on user-supplied enumerations (numbered or "
        "bulleted lists). You can also look at prior turns to fill via co-reference if the agent " 
        "surfaced concrete options. Otherwise emit `null`."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Tighten up the opening paragraph of my Deep NLP post. Make it punchier — short sentences, no passive voice, and open with the hook."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User names a paragraph scope ('opening paragraph') with explicit cross-post context → source fills post + snip. Style direction is a specific phrase → fill style_notes verbatim.",
  "slots": {
    "source": {"post": "Deep NLP", "snip": "opening paragraph"},
    "style_notes": "punchier — short sentences, no passive voice, and open with the hook",
    "image": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Clean up my conclusion."

## Input

Active post: **My ML Post** (id: `4b5c6d7e`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "4b5c6d7e", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Section scope ('conclusion') captured. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title. No style direction given — leave style_notes null so the agent can ask what kind of cleanup.",
  "slots": {
    "source": [{"post": "4b5c6d7e", "sec": "conclusion"}],
    "style_notes": null,
    "image": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Clean up my conclusion."
Agent: "Any specific direction?"
User: "Make it shorter and more active voice."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Same opening as the prior example, now continued. Section captured from first turn; post inherits from active_post. Style direction arrives in the third turn → fill style_notes verbatim.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "conclusion"},
    "style_notes": "shorter and more active voice",
    "image": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I need to tweak a specific line."
Agent: "Which line?"
User: "The 'less is more' hook at the start of my design post — make it snappier."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Target is a specific line — snippet fills with the user's full reference. Post is explicit. Style direction is specific → style_notes fills.",
  "slots": {
    "source": {"post": "design", "snip": "'less is more' hook at the start"},
    "style_notes": "snappier",
    "image": null,
    "suggestions": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Rewrite the caption on the hero image of my transformer post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Explicit image-level edit request → image slot fires with img_type='hero'. Source carries the post. No prose style direction → style_notes null.",
  "slots": {
    "source": {"post": "transformer"},
    "style_notes": null,
    "image": {"img_type": "hero", "src": null, "alt": null, "position": null},
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Polish my methods section."
Agent: "What direction?"
User: "Actually polish the conclusion instead, make it punchier."

## Input
Active post: My ML Paper

## Output

```json
{
  "reasoning": "User retracts 'methods' with 'actually...instead' — ignore prior section, use 'conclusion' from current turn. Style direction is specific → style_notes fills.",
  "slots": {
    "source": {"post": "My ML Paper", "sec": "conclusion"},
    "style_notes": "punchier",
    "image": null,
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Refine the opening sentence of my RL primer."
Agent: "What would you like changed?"
User: "Just make it better."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Snippet scope captured from the first turn. Current turn gives a vague directive ('just make it better') → style_notes stays null per rule 2 so the agent can ask for a specific direction.",
  "slots": {
    "source": {"post": "RL primer", "snip": "opening sentence"},
    "style_notes": null,
    "image": null,
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Tighten all three sentences in the methods paragraph — make them shorter and parallel."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Both snip and sec fire in one utterance: sec='methods' for the paragraph's home section, snip names the specific lines. Style direction is a specific phrase.",
  "slots": {
    "source": {"sec": "methods", "snip": "all three sentences in the methods paragraph"},
    "style_notes": "shorter and parallel",
    "image": null,
    "suggestions": null
  }
}
```
</edge_case>

<positive_example>
## Conversation History

User: "Polish the opening paragraph of the Methods section so it flows better."
Agent: "Three options for flow: (1) merge sentences 0-1 to drop the redundant transition; (2) flip passive in sentence 1 to active; (3) tighten sentence 2's 'the way that we' to 'we'. Pick any subset, or 'all three'."
User: "Yes, do all three."

## Input
Active post: My ML Paper

## Output

```json
{
  "reasoning": "Agent's prior turn proposed 3 polish options; current user turn accepts the full list with 'yes, do all three'. Source carries forward from turn 1 (sec=methods, snip=opening paragraph). Style_notes already absorbed in turn 1 ('flows better' is now stale). Suggestions fills with the full proposed list per rule 2b.",
  "slots": {
    "source": {"post": "My ML Paper", "sec": "Methods", "snip": "opening paragraph"},
    "style_notes": null,
    "image": null,
    "suggestions": [
      {"name": "merge sentences 0-1", "description": "drop the redundant transition"},
      {"name": "flip passive in sentence 1", "description": "convert to active voice"},
      {"name": "tighten sentence 2", "description": "'the way that we' → 'we'"}
    ]
  }
}
```
</positive_example>''',
}


TONE_PROMPT = {
    'instructions': (
        "The Tone Flow adjusts register and voice across a whole post — shifting sentence length, "
        "vocabulary complexity, and stylistic feel. The six canonical tones are: formal, casual, "
        "technical, academic, witty, natural. When the user names one directly (or an obvious "
        "synonym), fill `chosen_tone`; when they describe a tone in their own words that doesn't "
        "map cleanly, fill `custom_tone`; both can fire together when the user gives a canonical tone "
        "plus qualifiers.\n\n"
        "Source is required and typically inherits from active_post. When the user names a channel "
        "('for LinkedIn') that maps to multiple canonical tones, leave `chosen_tone` null and fill "
        "`custom_tone` with the channel phrase so the policy can resolve."
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user "
        "names a different post.\n"
        "2. Exactly one of `chosen_tone` / `custom_tone` / `suggestions` fills (or all stay null "
        "on bare 'tone' / 'rewrite' utterances with no target tone, e.g. 'tone my intro down' "
        "alone):\n"
        "  a. `chosen_tone` fills when the user names one of the six canonical options or an "
        "  obvious synonym. Map common variants conservatively: 'professional' → formal; 'laid "
        "  back' → casual; 'scholarly' → academic; 'playful' → witty; 'softer' → natural. If the "
        "  mapping is too far, leave null and fill `custom_tone` instead.\n"
        "  b. `custom_tone` fills when the user describes a tone that doesn't map cleanly to the "
        "  six canonicals ('warmer and more welcoming', 'serious but approachable'). Capture as a "
        "  short string.\n"
        "  c. `suggestions` fills when the user gives an enumerated list of tone shifts — "
        "  numbered or bulleted, 2+ items, each describing one tonal change (e.g., '1) shift "
        "  methods to casual, 2) tighten intro to academic, 3) warmer conclusion'). As a "
        "  follow-up mechanism, can also fill via co-reference to prior agent-proposed options "
        "  ('yes, all three', 'just option 2'). The primary path is direct user input — the "
        "  co-reference path is secondary.\n"
        "  d. `chosen_tone` and `custom_tone` can co-fire when the user gives a canonical tone "
        "  plus qualifying language ('formal but not stiff' → chosen_tone=formal, "
        "  custom_tone='formal but not stiff') OR when channel + canonical are both mentioned.\n"
        "  e. When the user names only a channel that maps to a single canonical (GitHub → "
        "  technical), fill `chosen_tone` directly. When the channel maps to multiple canonicals "
        "  (LinkedIn → formal/academic, Medium → natural/formal/witty), leave `chosen_tone` null "
        "  and put the channel phrase in `custom_tone` so the policy can resolve.\n"
        "3. Treat tone directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn "
        "explicitly references them via co-reference ('yes', 'do option 2', 'all three'). "
        "`source` is the exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. The post whose tone is being adjusted.\n\n"
        "### chosen_tone (elective)\n\n"
        "Type: CategorySlot. Options: formal, casual, technical, academic, witty, natural (see rule "
        "2a for synonym mapping).\n\n"
        "### custom_tone (elective)\n\n"
        "Type: ExactSlot. A free-form tone description when the user's phrasing doesn't match a "
        "canonical option. Also filled when the user names a channel that maps to multiple canonicals "
        "— store the channel phrase here so the policy can resolve.\n\n"
        "### suggestions (elective)\n\n"
        "Type: ChecklistSlot. A list of specific tone shifts the user has itemized. Each item "
        "is one tonal change. Fires primarily on user-supplied enumerations (numbered or "
        "bulleted lists with 2+ items). As a secondary path, can also fill via co-reference "
        "when a prior agent turn surfaced concrete options ('all three', 'just the first "
        "two'). Otherwise emit `null`."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Make my transformer post more professional."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Professional' maps cleanly to canonical 'formal'. No qualifier → custom_tone stays null.",
  "slots": {
    "source": {"post": "transformer"},
    "chosen_tone": "formal",
    "custom_tone": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Tone my intro warmer and more welcoming."

## Input

Active post: **RL primer** (id: `ef012345`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "ef012345", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "'Warmer and more welcoming' doesn't map to a canonical option — fill custom_tone. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "ef012345"}],
    "chosen_tone": null,
    "custom_tone": "warmer and more welcoming",
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Rewrite this one in a different voice."
Agent: "Which voice?"
User: "Witty — like the way I write on Twitter."

## Input
Active post: My Latest Post

## Output

```json
{
  "reasoning": "'Witty' is canonical. 'Like the way I write on Twitter' is a qualifier — not strictly custom_tone since the canonical is already given. Source inherits from active_post.",
  "slots": {
    "source": {"post": "My Latest Post"},
    "chosen_tone": "witty",
    "custom_tone": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Tune my RL primer formal but not stiff."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Formal' is canonical; 'but not stiff' qualifies it — both slots fire.",
  "slots": {
    "source": {"post": "RL primer"},
    "chosen_tone": "formal",
    "custom_tone": "formal but not stiff",
    "suggestions": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Adjust my RL primer for LinkedIn."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'LinkedIn' maps to multiple canonicals (formal, academic) — leave chosen_tone null and put the channel phrase in custom_tone so the policy can resolve which canonical to use.",
  "slots": {
    "source": {"post": "RL primer"},
    "chosen_tone": null,
    "custom_tone": "for LinkedIn",
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Tone my intro down."
Agent: "Down how — more casual? softer?"
User: "Softer."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "'Softer' maps to canonical 'natural' per rule 1. Source inherits from active_post.",
  "slots": {
    "source": {"post": "My ML Post"},
    "chosen_tone": "natural",
    "custom_tone": null,
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Rewrite it in a voice that feels like a seasoned practitioner talking shop."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "Descriptive phrase with no clean canonical mapping (could lean technical or casual, but neither fits exactly) → fill custom_tone. Source inherits from active_post.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "chosen_tone": null,
    "custom_tone": "like a seasoned practitioner talking shop",
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Adjust my transformer post."
Agent: "What tone are you going for?"
User: "Actually, let's first get it suitable for GitHub."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'GitHub' maps cleanly to a single canonical (technical) per the channel mapping, so chosen_tone fills directly rather than going to custom_tone.",
  "slots": {
    "source": {"post": "transformer"},
    "chosen_tone": "technical",
    "custom_tone": null,
    "suggestions": null
  }
}
```
</edge_case>

<positive_example>
## Conversation History

User: "Tune the voice of my RL primer."
Agent: "Three options: (1) shift the methods section toward a casual register; (2) tighten the intro to a more academic feel; (3) make the conclusion warmer with second-person framing. Pick any subset, or 'all three'."
User: "All three."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Agent's prior turn proposed 3 tone options; user accepts the full list with 'all three'. Source carries forward from active_post per rule 1. chosen_tone and custom_tone stay null since the proposal mixes registers per-section. Suggestions fills with the full proposed list per rule 2c.",
  "slots": {
    "source": {"post": "RL primer"},
    "chosen_tone": null,
    "custom_tone": null,
    "suggestions": [
      {"name": "casual methods", "description": "shift register toward casual"},
      {"name": "academic intro", "description": "tighten and add academic feel"},
      {"name": "warmer conclusion", "description": "second-person framing"}
    ]
  }
}
```
</positive_example>''',
}


AUDIT_PROMPT = {
    'instructions': (
        "The Audit Flow checks that a post is written in the user's voice rather than sounding like "
        "AI. It compares voice, terminology, formatting conventions, and stylistic patterns against "
        "previous posts, flagging sections that drift above a confidence threshold. Audit is distinct "
        "from Rework (which restructures content) and Tone (which shifts register deliberately).\n\n"
        "Extract the target post (`source`, usually inherited from active_post), the number of prior "
        "posts to reference (`reference_count`, optional), and the AI-likelihood threshold "
        "(`threshold`, optional). All elective extraction fires strictly on explicit triggers — vague "
        "descriptors leave slots null and let the policy apply defaults."
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user "
        "names a post.\n"
        "2. `reference_count` (optional) fills on explicit count language: 'compare against my "
        "last 5 posts' → 5; 'against my previous post' (singular) → 1.\n"
        "  a. Qualitative comparison without an explicit count ('against my recent posts', "
        "  'compare to past stuff', 'check it against my old drafts') fills `reference_count` "
        "  with 5 as a sensible default.\n"
        "  b. Bare audit with no comparison language → leave `reference_count` null. The skill "
        "  will default to running editor + structural checks only, without comparison.\n"
        "3. `threshold` (optional) fills on explicit probability language: '80%' → 0.8; 'above "
        "0.3' → 0.3; 'flag anything over 50%' → 0.5. Percentages convert to decimals. 'At least "
        "95%' → 0.95.\n"
        "  a. Vague descriptors like 'strict' or 'loose' do NOT fill `threshold` — leave null so "
        "  the policy can default.\n"
        "4. `delegates` (optional) fills when the user names which sub-flows should fix audit "
        "findings ('audit and route fixes to rework', 'send any voice issues to polish and "
        "structural drift to rework'). Each delegate is one sub-flow name with a description. "
        "As a follow-up mechanism, can also fill via co-reference to prior agent-proposed "
        "delegates ('yes, all three', 'just rework and polish'). The policy more commonly "
        "populates this from a frontend selection payload after presenting audit findings — "
        "leave null in that case.\n"
        "5. Treat audit directives as current-turn-only. Prior-turn directives (e.g. an earlier "
        "reference_count or threshold) are assumed already applied — do NOT carry them into the "
        "current slot fill unless the current turn explicitly references them via co-reference. "
        "`source` is the exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot. The post being audited.\n\n"
        "### reference_count (optional)\n\n"
        "Type: LevelSlot (threshold=1). Number of prior posts to reference as voice samples. Fires "
        "on explicit integers ('last 5 posts' → 5; 'against my previous post' → 1) and on "
        "qualitative comparison language ('against my recent posts' → 5 as a default). Leave null "
        "only when the user makes no comparison ask at all — non-null `reference_count` is the "
        "signal that tells the skill to run `compare_style`.\n\n"
        "### threshold (optional)\n\n"
        "Type: ProbabilitySlot. AI-likelihood cutoff in [0, 1] — sections with a score above this "
        "are flagged. Fill on explicit probability language; percentages convert ('80%' → 0.8). "
        "Leave null on vague qualifiers like 'strict' so the policy can default.\n\n"
        "### delegates (optional)\n\n"
        "Type: ChecklistSlot. A list of sub-flow names the audit should route findings to "
        "(e.g., rework, polish, tone). Fires primarily on direct user routing directives "
        "('send the voice issues to polish, structural drift to rework'). As a secondary "
        "path, can also fill via co-reference when a prior agent turn proposed delegates "
        "('all three', 'yes'). The policy more commonly populates this from frontend "
        "selection payloads after presenting findings — leave null in that case."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Audit my transformer post against my last 5 posts with a 0.8 threshold."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Full spec: explicit post, explicit reference count (5), explicit threshold (0.8).",
  "slots": {
    "source": {"post": "transformer"},
    "reference_count": 5,
    "threshold": 0.8,
    "delegates": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Check if my RL primer sounds too much like GPT wrote it."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Indirect audit request — source is explicit, no comparison ask (\"sounds like GPT\" is editorial-style, not a comparison against prior posts). Both optional slots stay null; the skill will run editor + structural checks only.",
  "slots": {
    "source": {"post": "RL primer"},
    "reference_count": null,
    "threshold": null,
    "delegates": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compare my new post against my last few drafts."
Agent: "How many?"
User: "Last 7 posts, and use a strict check."

## Input
Active post: My New Post

## Output

```json
{
  "reasoning": "Reference count fills with 7 from the third turn. 'Strict check' is vague per rule 3 → threshold stays null. Source inherits from active_post.",
  "slots": {
    "source": {"post": "My New Post"},
    "reference_count": 7,
    "threshold": null,
    "delegates": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Audit my RL primer against my previous post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'My previous post' (singular) → reference_count=1 per rule 4. No threshold given.",
  "slots": {
    "source": {"post": "RL primer"},
    "reference_count": 1,
    "threshold": null,
    "delegates": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Audit my intro post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Bare audit — source fills, no comparison ask, no threshold. Both optional slots stay null; the skill will run editor + structural checks only.",
  "slots": {
    "source": {"post": "intro"},
    "reference_count": null,
    "threshold": null,
    "delegates": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Audit my calibration post."
Agent: "At what threshold?"
User: "Never mind — audit my RL primer instead, at 0.5."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts calibration with 'never mind...instead' → source switches to RL primer. Threshold filled explicitly.",
  "slots": {
    "source": {"post": "RL primer"},
    "reference_count": null,
    "threshold": 0.5,
    "delegates": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Audit against my recent stuff, be strict."

## Input
Active post: My Post

## Output

```json
{
  "reasoning": "Source inherits from active_post. 'Against my recent stuff' is comparison language without an explicit count → reference_count fills with 5 per rule 5. 'Strict' is vague → threshold null.",
  "slots": {
    "source": {"post": "My Post"},
    "reference_count": 5,
    "threshold": null,
    "delegates": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Audit it — reference 10 posts, threshold 0.5."

## Input

Active post: **Trustworthy AI** (id: `d1e2f3a4`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "d1e2f3a4", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Terse audit with both optional numbers explicitly provided. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "d1e2f3a4"}],
    "reference_count": 10,
    "threshold": 0.5,
    "delegates": null
  }
}
```
</edge_case>

<positive_example>
## Conversation History

User: "Audit my RL primer against my last 3 posts."
Agent: "Found 4 issues. I can route them to: (1) rework — for the structural drift in the intro; (2) polish — for sentence-level voice mismatches in methods; (3) tone — for the abrupt register shift in the conclusion. Want me to dispatch all three?"
User: "Yes, all three."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Agent's prior turn proposed 3 delegate flows; user accepts all three with 'yes, all three'. Source carries forward (RL primer). reference_count and threshold were absorbed in turn 1 and are now stale per rule 5 — leave null. Delegates fills with the proposed list per rule 4.",
  "slots": {
    "source": {"post": "RL primer"},
    "reference_count": null,
    "threshold": null,
    "delegates": [
      {"name": "rework", "description": "structural drift in the intro"},
      {"name": "polish", "description": "voice mismatches in methods"},
      {"name": "tone", "description": "register shift in the conclusion"}
    ]
  }
}
```
</positive_example>''',
}

SIMPLIFY_PROMPT = {
    'instructions': (
        "The Simplify Flow reduces the complexity of a section's prose or swaps out an overly "
        "complex image. The primary use case is removing unnecessary content or obvious AI slop. "
        "Simplify is distinct from Rework (which restructures) and Polish (which tightens individual "
        "phrases for style).\n\n"
        "Extract the `source` post along with the section, and a notion of what should be simplified. "
        "This should come from a specific user directive about WHAT to cut, which is then used to fill "
        "the slots related to `guidance`, `suggestions`, or `image`. If only vague directives are "
        "provided, then leave the elective slots empty."
    ),
    'rules': (
        "1. Fill `source.post` from the active_post and include the `sec` as provided by the user.\n"
        "  a. The scope of this flow only covers individual sections, so `sec` is required."
        "  b. If a request applies post-wide ('simplify the whole post', 'trim the whole thing') or "
        "  doesn't include information on the section, leave `sec` null so we can ask the user for clarification. "
        "2. Decide on what the user is deciding to trim or simplify:\n"
        "  a. Fill the `suggestions` when the user provides a list of instructions or bulletpoints "
        "  to follow. Any enumeration with more than one time belongs here."
        "  b. `guidance` captures the user's specific request about what to cut when the directive "
        "  is based on re-writing specific paragraphs, rather than removing specific words."
        "  c. Fill the `image` slot when there is language targeting an image, graph or diagram. This "
        "  effectively means the user wants to remove the image from the post."
        "3. Simplify is NOT meant to target rewording for style. If the user's request is stylistic "
        "  ('punchier', 'warmer'), leave all electives `null`.\n"
        "4. You may have to look to prior turns to better understand exactly what is being requested.\n"
        "  a. You can use previous turns to provide context for a user's request, such as when a user "
        "  accepts a prior turn's suggestions ('yea, go for it') through co-reference."
        "  b. Do NOT add or pay any attention to previous requests if there isn't a reference to it in "
        "  the current turn. Previous directives should be considered already complete."
    ),
    'slots': (
        "### source (elective)\n\n"
        "Type: SourceSlot. The target section (and its post) to simplify. Always includes `post`; "
        "fills `sec` when the user names a section.\n\n"
        "### image (elective)\n\n"
        "Type: ImageSlot. An image reference to simplify. Fill when the user asks to swap, replace, "
        "or remove an image for something simpler.\n\n"
        "### guidance (elective)\n\n"
        "Type: FreeTextSlot. A list of specific user directives about what to cut or how to "
        "simplify. Captures phrases like 'strip the academic hedging', 'cut the historical "
        "preamble', 'remove every other adjective'. Leave null on bare simplify requests.\n\n"
        "### suggestions (elective)\n\n"
        "Type: ChecklistSlot. A list of specific simplification edits the user has itemized — "
        "each item targets specific words or sentences (vs. `guidance` which targets general "
        "areas of text). Fires primarily on user-supplied enumerations (numbered or bulleted "
        "lists with 2+ items). As a secondary path, can also fill via co-reference when a "
        "prior agent turn proposed concrete options ('yes, all three', 'just the first two'). "
        "Otherwise emit `null`."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Shorten the Methods section of my regularization post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Single-turn section simplify. Source fills post + sec; no image or specific guidance given.",
  "slots": {
    "source": {"post": "regularization", "sec": "Methods"},
    "image": null,
    "guidance": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compose the intro of my RL primer based on my outline."
Agent: "Here's the drafted intro..."
User: "Boil it down — cut the historical preamble and keep it to three sentences."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "First turn is a Compose. Current turn asks to simplify what was just composed, with specific guidance — which parts to cut and target length.",
  "slots": {
    "source": {"post": "RL primer", "sec": "intro"},
    "image": null,
    "guidance": ["cut the historical preamble and keep it to three sentences"],
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Get rid of the redundant content in my Discussion section."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "User names the Discussion section; 'redundant content' is a mild directive that fills guidance.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "Discussion"},
    "image": null,
    "guidance": ["get rid of the redundant content"],
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "The Conclusion is too repetitive."
Agent: "Should I trim it?"
User: "Yeah, cut it in half."

## Input

Active post: **My ML Post** (id: `4b5c6d7e`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "4b5c6d7e", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "Indirect opener (critique, not simplify verb). Section named in prior turn; current turn adds guidance on how much to cut. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title.",
  "slots": {
    "source": [{"post": "4b5c6d7e", "sec": "Conclusion"}],
    "image": null,
    "guidance": ["cut it in half"],
    "suggestions": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Rework my Methods section."
Agent: "Rewriting the methods — here's the revised version..."
User: "Actually, just simplify the Discussion section instead — trim the fluff."

## Input
Active post: My Paper

## Output

```json
{
  "reasoning": "First turn is a Rework. User retracts with 'actually...instead' and pivots to a Simplify on a different section. 'Trim the fluff' fills guidance.",
  "slots": {
    "source": {"post": "My Paper", "sec": "Discussion"},
    "image": null,
    "guidance": ["trim the fluff"],
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Trim the whole post."

## Input
Active post: My Tutorial

## Output

```json
{
  "reasoning": "Post-wide simplify is invalid per rule 5 — fill `post` but leave `sec` null so the flow can flag and ask which section to simplify.",
  "slots": {
    "source": {"post": "My Tutorial"},
    "image": null,
    "guidance": null,
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Streamline my Results section and get rid of the scatter plot."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Both slots fill in one utterance — section simplify + image removal. Source carries sec; image carries the plot description; the 'streamline + scatter plot' directive goes into guidance.",
  "slots": {
    "source": {"sec": "Results"},
    "image": {"img_type": "photo", "src": null, "alt": "scatter plot", "position": null},
    "guidance": ["streamline and remove the scatter plot"],
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Simplify the Methods section of my calibration post — strip the academic hedging and tighten the opening sentences."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Specific simplify directive with two named actions → fill guidance as a list of two items. Source carries post + sec.",
  "slots": {
    "source": {"post": "calibration", "sec": "Methods"},
    "image": null,
    "guidance": ["strip the academic hedging", "tighten the opening sentences"],
    "suggestions": null
  }
}
```
</edge_case>

<positive_example>
## Conversation History

User: "Simplify the Methods section of my calibration post — strip the academic hedging and cut the historical preamble."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Both directives target a general area of text (academic hedging across the section, historical preamble at the top), not specific words or sentences. Two general-area directives → guidance fills as a list of two strings. The list shape doesn't make this suggestions; the items describe scope-of-text, not enumerated specific edits.",
  "slots": {
    "source": {"post": "calibration", "sec": "Methods"},
    "image": null,
    "guidance": ["strip the academic hedging", "cut the historical preamble"],
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Simplify the Methods section of my calibration post: 1) strip out the word 'academic' wherever it appears, 2) cut the preamble sentence, 3) replace 'utilize' with 'use'."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Three enumerated edits, each targeting specific words or sentences ('academic' the word, the preamble sentence, 'utilize' → 'use'). The list-of-three plus word-and-sentence specificity puts this in suggestions, not guidance. Guidance is general-area scope; suggestions is enumerated specific edits.",
  "slots": {
    "source": {"post": "calibration", "sec": "Methods"},
    "image": null,
    "guidance": null,
    "suggestions": [
      {"name": "one", "description": "strip out the word 'academic' wherever it appears"},
      {"name": "two", "description": "cut the preamble sentence"},
      {"name": "three", "description": "replace 'utilize' with 'use'"}
    ]
  }
}
```
</positive_example>''',
}


REMOVE_PROMPT = {
    'instructions': (
        "The Remove Flow deletes an entity — a section, paragraph, image, note, or an entire draft "
        "or post. The `type` slot tags WHAT is being removed so the policy can dispatch to the "
        "correct delete tool. Remove is distinct from Rework (which edits in place) and from "
        "Simplify: **Simplify operates at paragraph or sentence scale (shortening inside a "
        "section); Remove operates at section or post scale, a larger unit of deletion.**\n\n"
        "Extract the target (`target` for text-based entities or `image` for images) and the "
        "removal type (`type`, required). Target and image are elective; type is required so the "
        "policy knows which tool to call. Map the user's noun to the closest of six type "
        "categories."
    ),
    'rules': (
        "1. `type` is required. Map user nouns to the closest category: 'article' / 'post' → post; "
        "'draft' → draft; 'section' → section; 'paragraph' / 'sentence' → paragraph; 'note' / "
        "'snippet' → note; 'image' / 'photo' / 'diagram' → image.\n"
        "2. Exactly one of `target` / `image` must fill:\n"
        "  a. `target` fills when removing a text-based entity. Section-level removals fill `sec`. "
        "Paragraph-level removals fill BOTH `sec` (the parent section, when named) AND `snip` (the "
        "paragraph description).\n"
        "  b. `image` fills when type='image'. Carries img_type from phrasing (diagram/hero/photo).\n"
        "3. On terse utterances ('delete it') with only active_post as context, infer type='post' "
        "from the active_post.\n"
        "4. Treat remove directives as current-turn-only. Prior-turn directives are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn explicitly "
        "references them via co-reference ('yes', 'do option 2', 'all three'). `source` is the "
        "exception: it carries forward from `state.active_post`."
    ),
    'slots': (
        "### target (elective)\n\n"
        "Type: RemovalSlot. The text-based target of removal. Always includes `post`; fills `sec` "
        "for section removal and `snip` for paragraph/sentence/note removal. Paragraph-level "
        "removals fill BOTH sec and snip when both are named.\n\n"
        "### image (elective)\n\n"
        "Type: ImageSlot. The image being removed. Fill only when the user asks to delete an "
        "image, diagram, or photo.\n\n"
        "### type (required)\n\n"
        "Type: CategorySlot. Options: post, draft, section, paragraph, note, image. What kind of "
        "entity is being removed. The policy routes to different delete tools based on this."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Kill my RL primer draft."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Kill' removes the whole draft; 'draft' triggers type='draft'. Strip the trailing 'draft' status word from the title.",
  "slots": {
    "target": {"post": "RL primer"},
    "image": null,
    "type": "draft"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Rework my Methods section."
Agent: "Done — here's the revised Methods section..."
User: "Actually, just delete this section entirely."

## Input
Active post: My Paper

## Output

```json
{
  "reasoning": "First turn is a Rework. User pivots to removing the section that was just reworked. Target.sec carries 'Methods' from the prior turn; post inherits from active_post.",
  "slots": {
    "target": {"post": "My Paper", "sec": "Methods"},
    "image": null,
    "type": "section"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Cut the third paragraph of the Conclusion section."

## Input
Active post: My Post

## Output

```json
{
  "reasoning": "Paragraph-level removal inside a named section. Target fills post + sec (Conclusion) + snip (third paragraph). Type='paragraph'.",
  "slots": {
    "target": {"post": "My Post", "sec": "Conclusion", "snip": "third paragraph"},
    "image": null,
    "type": "paragraph"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I added a hero image to my transformer post."
Agent: "Looks good."
User: "Actually, trash it — doesn't add anything."

## Input
Active post: None

## Output

```json
{
  "reasoning": "First turn references adding an image (not a remove flow). Current turn removes it. Target carries the post; image captures the hero reference; type='image'.",
  "slots": {
    "target": {"post": "transformer"},
    "image": {"img_type": "hero", "src": null, "alt": null, "position": null},
    "type": "image"
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Compose the intro of my RL primer."
Agent: "Here's the intro..."
User: "Actually delete the methods section instead."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "First turn is Compose. User pivots to removing a different section than the one just composed. Target.sec switches to 'methods'; type='section'. Post inherits from active_post.",
  "slots": {
    "target": {"post": "RL primer", "sec": "methods"},
    "image": null,
    "type": "section"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Get rid of my snippet on attention dropout."

## Input
Active post: None

## Output

```json
{
  "reasoning": "'Snippet' maps to type='note'. Target carries the snippet description.",
  "slots": {
    "target": {"snip": "attention dropout"},
    "image": null,
    "type": "note"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Delete it."

## Input

Active post: **My Old Draft** (id: `0f1e2d3c`)

## Output

```json
{
  "reasoning": "Terse removal with only active_post as context. Per rule 4, infer type='post' from the active_post. Active post id is shown in the input header — copy `post_id` verbatim from the header rather than re-deriving from the title.",
  "slots": {
    "target": [{"post": "0f1e2d3c"}],
    "image": null,
    "type": "post"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Cut the last two paragraphs of my intro."

## Input
Active post: My Post

## Output

```json
{
  "reasoning": "Paragraph-level removal with a multi-paragraph description in snip. Sec names the parent section ('intro'); post inherits.",
  "slots": {
    "target": {"post": "My Post", "sec": "intro", "snip": "last two paragraphs"},
    "image": null,
    "type": "paragraph"
  }
}
```
</edge_case>''',
}


TIDY_PROMPT = {
    'instructions': (
        "The Tidy Flow normalizes structural formatting across a post — heading hierarchy, list "
        "indentation, paragraph spacing, whitespace cleanup. It does NOT change wording. Tidy is "
        "distinct from Polish (which adjusts phrasing) and Rework (which restructures content).\n\n"
        "Extract the target post (`source`, usually inherited from active_post) and any formatting "
        "settings the user specifies (`settings`, a DictionarySlot of key-value pairs like "
        "`{headings: 'H2'}`). The `image` slot is optional and fills only when the user asks to "
        "tidy image alignment or captions."
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Tidy is post-wide by default so "
        "`sec` is rarely filled.\n"
        "2. `settings` fills when the user specifies formatting rules — 'use H2 headings', "
        "'normalize list indents'. Parse into key-value pairs: 'H2 headings' → "
        "`{headings: 'H2'}`. Capture the user's wording as the dict key.\n"
        "  a. Bare 'clean it up' or 'tidy this' has no formatting direction — leave `settings` "
        "  null so the flow can ask.\n"
        "3. `image` (optional) fills only on explicit image-formatting language ('fix the image "
        "alignment', 'center the diagrams'). Leave null for prose-only tidying.\n"
        "4. Treat tidy directives as current-turn-only. Prior-turn settings are assumed already "
        "applied — do NOT carry them into the current slot fill unless the current turn "
        "explicitly references them via co-reference. `source` is the exception: it carries "
        "forward from `state.active_post`."
    ),
    'slots': (
        "### source (required)\n\n"
        "Type: SourceSlot (entity_part='post'). The post to tidy. Tidy is post-wide; `sec` rarely "
        "fills.\n\n"
        "### settings (required)\n\n"
        "Type: DictionarySlot. Key-value pairs capturing formatting rules the user specifies ("
        "'H2 headings' → `{headings: 'H2'}`). Leave null on bare tidy requests — the policy "
        "applies defaults.\n\n"
        "### image (optional)\n\n"
        "Type: ImageSlot. Image-formatting target. Fills on alignment/caption tidying requests "
        "('fix the image alignment', 'center the diagrams'). Leave null for prose-only tidying."
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Compose the Methods section of my transformer post."
Agent: "Done — here's the composed Methods section..."
User: "Now tidy the heading hierarchy — H2 for top-level, H3 for sub."

## Input

Active post: **transformer** (id: `6c7d8e9f`)

Filled slots are shown as part of the input; slots not shown are empty so far.
source slot: {"post": "6c7d8e9f", "sec": "", "snip": "", "chl": ""}

## Output

```json
{
  "reasoning": "First turn is Compose. Current turn switches to Tidy. Active post is grounded — copy `post_id` verbatim from the source slot rather than re-deriving from the title. Settings parse the heading rules into a dict.",
  "slots": {
    "source": [{"post": "6c7d8e9f"}],
    "settings": {"headings_top": "H2", "headings_sub": "H3"},
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Clean up my RL primer."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Bare tidy with no specific rules. Source named; settings stays null because there's not enough information to populate it — the policy will apply defaults or clarify.",
  "slots": {
    "source": {"post": "RL primer"},
    "settings": null,
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Normalize the regularization post: H2 headings and bullet indents at 2 spaces."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two formatting rules given in one utterance → settings dict has two entries.",
  "slots": {
    "source": {"post": "regularization"},
    "settings": {"headings": "H2", "bullet-indent": "2 spaces"},
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "The layout feels off on my calibration post."
Agent: "Formatting or images?"
User: "Images — center the diagrams."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Indirect opener ('layout feels off'); clarified in the third turn that image alignment is the target. Source named in first turn; image fills with the diagram reference.",
  "slots": {
    "source": {"post": "calibration"},
    "settings": null,
    "image": {"img_type": "diagram", "src": null, "alt": null, "position": null}
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Fix the spacing on my intro post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Single formatting directive ('fix the spacing') → settings captures the user's wording.",
  "slots": {
    "source": {"post": "intro"},
    "settings": {"spacing": "fix"},
    "image": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Standardize the bullet formatting in my RL primer — use dashes, not asterisks."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Specific bullet-style rule → settings captures the user's exact directive as a key-value pair.",
  "slots": {
    "source": {"post": "RL primer"},
    "settings": {"bullet-style": "dashes"},
    "image": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Normalize the indentation on just the Methods section of my regularization post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Unusual section-level tidy — source carries both post and sec. Settings captures the indentation directive.",
  "slots": {
    "source": {"post": "regularization", "sec": "Methods"},
    "settings": {"indentation": "normalize"},
    "image": null
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'rework': REWORK_PROMPT,
    'polish': POLISH_PROMPT,
    'tone': TONE_PROMPT,
    'audit': AUDIT_PROMPT,
    'simplify': SIMPLIFY_PROMPT,
    'remove': REMOVE_PROMPT,
    'tidy': TIDY_PROMPT,
}
