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
        "triggers a re-route to Write.\n"
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
        "fill `snip` instead — this triggers a re-route to Write.\n\n"
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
        "dissatisfaction does NOT fill this slot.\n\n"
        "### image (optional)\n\n"
        "Type: ImageSlot. The image being deleted. Fill only when the user asks "
        "to delete an image, diagram, or photo.\n\n"
        "### type (optional)\n\n"
        "Type: CategorySlot. Post, draft, section, paragraph, note, image — what "
        "kind of entity a destructive rework is removing. The policy routes to the matching delete "
        "tool. Leave null for non-destructive reworks."
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
  "reasoning": "'Trim down' applied to multiple sections → category=trim. The policy will fall back to Write.",
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
  "reasoning": "User named a paragraph scope ('the second paragraph'). Per rule 1, fill source.snip and leave post/sec off — this triggers a re-route to Write. No category fits.",
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

WRITE_PROMPT = {
    'instructions': (
        "The Write Flow covers fine-grained editing within a paragraph, sentence, or phrase — improving "
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
        "  b. Since Write is for targeted edits, we require that `sec` or `snip` are filled. If neither "
        "  is mentioned, then leave them so `null` so we can ask the user for clarification. "
        "2. Decide whether `image` or `suggestions` are mentioned (or both stay `null` if neither image-level "
        "language nor user proposals are made):\n"
        "  a. `image` fires only on explicit image-level language — caption edits or image "
        "  regeneration. Leave null when no picture is present or mentioned.\n"
        "  b. `suggestions` fills when the user gives an enumerated list of edits — "
        "  numbered or bulleted, each describing one individual edit. As a follow-up mechanism, "
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
        "Type: SourceSlot. What to edit. Most often a snippet — the user names a paragraph, "
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
        "Type: ChecklistSlot. A list of specific edits the user has itemized. Each item "
        "is one edit. Fires primarily on user-supplied enumerations (numbered or "
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
  "reasoning": "Agent's prior turn proposed 3 edit options; current user turn accepts the full list with 'yes, do all three'. Source carries forward from turn 1 (sec=methods, snip=opening paragraph). Style_notes already applied in turn 1 ('flows better' is now stale). Suggestions fills with the full proposed list per rule 2b.",
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
        "4. Treat audit directives as current-turn-only. Prior-turn directives (e.g. an earlier "
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
        "### tone (optional)\n\n"
        "Type: ExactSlot. The target register, captured verbatim. May be a "
        "common register word ('formal', 'casual', 'technical', 'academic', 'witty', 'natural') or "
        "a free-form description ('warmer and more welcoming', 'like a seasoned practitioner') — "
        "there is no fixed list, the skill interprets whatever the user says. Fills when the audit "
        "also asks for a register shift; leave null otherwise.\n\n"
        "### suggestions (optional)\n\n"
        "Type: ChecklistSlot. A list of specific tonal shifts the user itemized. "
        "Fires on user-supplied enumerations. Otherwise emit `null`."
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
    "threshold": 0.8  }
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
    "threshold": null  }
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
    "threshold": null  }
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
    "threshold": null  }
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
    "threshold": null  }
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
    "threshold": 0.5  }
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
    "threshold": null  }
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
    "threshold": 0.5  }
}
```
</edge_case>''',
}


PROMPTS = {
    'rework': REWORK_PROMPT,
    'write': WRITE_PROMPT,
    'audit': AUDIT_PROMPT,
}
