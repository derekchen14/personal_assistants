REWORK_PROMPT = {
    'instructions': (
        'The Rework Flow is major revision of prose that already exists — restructuring a section, '
        'replacing weak arguments, or rewriting a post-level passage after reviewer feedback.\n\n'
        'Source is typically already pre-filled with the post (and possibly the section) being reworked. '
        'Beyond that, the user usually adds a critique or directive that lands in `changes`, OR a '
        'numbered/bulleted list of specific edits that lands in `suggestions`. The `remove` slot fires '
        'only when the user explicitly calls out a specific piece to cut.'
    ),
    'rules': (
        '1. Source is pre-filled with the post; if the user names a section, fill `sec`. If the user names '
        'a paragraph/sentence/phrase scope, fill `source.snip` instead and leave `post`/`sec` off — this '
        'triggers a re-route to Polish.\n'
        '2. `remove` fires only on explicit cut/drop/delete language targeting a specific piece. Vague '
        'dissatisfaction goes in `changes`.\n'
        '3. `changes` is the user\'s critique or directive. Ambiguous verbs like "tighten" or "improve '
        'flow" leave `changes` null so the flow can clarify.\n'
        '4. `suggestions` fires on numbered or bulleted lists with at least 2 items. Each item is one '
        'suggestion. Leave null on prose-only critique.\n'
        '5. A single utterance most often fills `changes` OR `suggestions`, not both — bullets are '
        'explicit, prose is interpretive. Both can fire when the user mixes a prose critique with a '
        'separate numbered list.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. References the target of the rework. Typically pre-filled with the post; the '
        'user may add a section name. If the user names a paragraph/sentence/phrase scope, fill `snip` '
        'instead (omit `post`/`sec`) — this triggers a re-route to Polish.\n\n'
        '### remove (optional)\n\n'
        'Type: RemovalSlot. A specific piece of content to cut during the rework. Fill only when the '
        'user clearly targets something to remove (\'drop the tangent\', \'cut the footnote\'). Vague '
        'dissatisfaction does NOT fill this slot.\n\n'
        '### changes (elective)\n\n'
        'Type: FreeTextSlot. The user\'s critique or directive — what\'s wrong, what to improve. '
        'Ambiguous verbs like "tighten" or "improve flow" leave this null so the flow can clarify.\n\n'
        '### suggestions (elective)\n\n'
        'Type: ChecklistSlot. A list of specific changes the user has itemized. Each item is one '
        'suggestion. Fires on numbered or bulleted lists with at least 2 items. Leave null on prose-only '
        'critique.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "The Components of Dialogue Systems post needs a full rewrite — the argument is buried and the pacing drags."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Whole-post rework with a prose critique. Source carries just the post. Critique becomes `changes`. No explicit removal, no itemized list.",
  "slots": {
    "source": {"post": "Components of Dialogue Systems"},
    "remove": null,
    "changes": "the argument is buried and the pacing drags",
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Rework the methods section of my regularization post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Section-level rework, named section. Source fills both post and sec. No critique, no removal, no itemized list.",
  "slots": {
    "source": {"post": "regularization", "sec": "methods"},
    "remove": null,
    "changes": null,
    "suggestions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Let's revise the introduction to my reinforcement learning post."
Agent: "OK — what should I change?"
User: "Cut the part about AlphaGo."

## Input
Active post: reinforcement learning

## Output

```json
{
  "reasoning": "Source resolves from the prior turn (post=reinforcement learning, sec=introduction). Current turn carries explicit removal language → fill `remove`. No critique text, no itemized list.",
  "slots": {
    "source": {"post": "reinforcement learning", "sec": "introduction"},
    "remove": "the part about AlphaGo",
    "changes": null,
    "suggestions": null
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
Active post: regularization

## Output

```json
{
  "reasoning": "Section comes from the first turn; post inherits from active_post. Numbered list of 3 items → `suggestions`. Item #2 is also explicit removal language → `remove` fires in addition. `changes` stays null since the bullets are explicit, not interpretive.",
  "slots": {
    "source": {"post": "regularization", "sec": "methods"},
    "remove": "the historical preamble",
    "changes": null,
    "suggestions": [
      "lead with the experiment design",
      "cut the historical preamble",
      "add a comparison table"
    ]
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
  "reasoning": "User named a paragraph scope ('the second paragraph'). Per rule 1, fill source.snip and leave post/sec off — this triggers a re-route to Polish. Critique fills `changes`.",
  "slots": {
    "source": {"snip": "the second paragraph in my methods section"},
    "remove": null,
    "changes": "it's too dense",
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "I want to rework two sections of my RL post."
Agent: "Which ones?"
User: "Intro and conclusion."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two section names supplied across turns. Sec becomes a list. Post pulled from the prior turn.",
  "slots": {
    "source": {"post": "RL", "sec": ["intro", "conclusion"]},
    "remove": null,
    "changes": null,
    "suggestions": null
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
  "reasoning": "User explicitly retracts the prior section choice with 'scratch that' and switches to intro — ignore the earlier 'methods' section. 'Tighten it' is an ambiguous directive (rule 3) → leave `changes` null so the flow can clarify what direction the user wants.",
  "slots": {
    "source": {"post": "My ML Paper", "sec": "intro"},
    "remove": null,
    "changes": null,
    "suggestions": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Rework the conclusion."
Agent: "Sure — anything specific?"
User: "Tighten it up."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Source resolves from prior turn + active_post. 'Tighten it up' is an ambiguous verb → `changes` stays null per rule 3 so the flow can clarify what direction the user wants.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "conclusion"},
    "remove": null,
    "changes": null,
    "suggestions": null
  }
}
```
</edge_case>''',
}

POLISH_PROMPT = {
    'instructions': (
        'The Polish Flow is fine-grained editing within a paragraph, sentence, or phrase — improving '
        'word choice, tightening sentences, fixing transitions, and smoothing flow without changing '
        'meaning or structure. Scope is always within a single paragraph or an image caption, not '
        'across a section or post; bigger revisions go through Rework.\n\n'
        'Extract the target (`source`) — usually a snippet or section — and any stylistic direction '
        '(`style_notes`). The `image` slot fires only when the user asks to add or edit an image '
        'caption, or to regenerate an existing image.'
    ),
    'rules': (
        '1. `source` fills `snip` when the user names a paragraph/sentence/phrase ("the opening '
        'paragraph"), or `sec` when they name a section ("the methods section"), or both when context '
        'mentions both (e.g., "the opening of the methods section" → sec=methods, snip=opening). '
        'Include `post` only when the user disambiguates across posts.\n'
        '2. `style_notes` captures stylistic direction verbatim and is often a phrase or short '
        'sentence. Specific single words ("shorter", "punchier", "warmer") are fine, but vague single '
        'words ("better", "improve") leave style_notes null so the agent can clarify.\n'
        '3. `style_notes` captures only directives from the CURRENT turn; prior-turn directives are '
        'assumed to have been handled already.\n'
        '4. `image` fires only on explicit image-level language — caption edits or image regeneration. '
        'Leave null when no picture is present or mentioned.\n'
        '5. When the user says "polish it" with only an active post grounded (no sub-section named '
        'and no direction given), leave all slots null — the agent should ask for clarification on '
        'both target and direction.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. What to polish. Most often a snippet — the user names a paragraph, '
        'sentence, or phrase. Less often a whole section, and sometimes both (sec + snip). Include '
        '`post` only when the user disambiguates across posts; otherwise active_post provides that '
        'context.\n\n'
        '### style_notes (optional)\n\n'
        'Type: FreeTextSlot. The user\'s stylistic direction, captured verbatim. Often a phrase or '
        'short sentence. Examples: "punchier — short sentences, no passive voice", "warmer tone, '
        'less academic", "shorter". Leave null on vague single-word directives like "better".\n\n'
        '### image (optional)\n\n'
        'Type: ImageSlot. Fires only when the user asks to add or edit an image caption or to '
        'regenerate the current image. Leave null when a picture is not present and not mentioned.'
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
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Clean up my conclusion."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Section scope ('conclusion') captured; post inherits from active_post. No style direction given — leave style_notes null so the agent can ask what kind of cleanup.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "conclusion"},
    "style_notes": null,
    "image": null
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
    "image": null
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
    "image": null
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
  "reasoning": "Explicit image-level edit request → image slot fires with image_type='hero'. Source carries the post. No prose style direction → style_notes null.",
  "slots": {
    "source": {"post": "transformer"},
    "style_notes": null,
    "image": {"image_type": "hero", "src": null, "alt": null, "position": null}
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
    "image": null
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
    "image": null
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
    "image": null
  }
}
```
</edge_case>''',
}


TONE_PROMPT = {
    'instructions': (
        'The Tone Flow adjusts register and voice across a whole post — shifting sentence length, '
        'vocabulary complexity, and stylistic feel. The six canonical tones are: formal, casual, '
        'technical, academic, witty, natural. When the user names one directly (or an obvious '
        'synonym), fill `chosen_tone`; when they describe a tone in their own words that doesn\'t '
        'map cleanly, fill `custom_tone`; both can fire together when the user gives a canonical tone '
        'plus qualifiers.\n\n'
        'Source is required and typically inherits from active_post. When the user names a channel '
        '(\'for LinkedIn\') that maps to multiple canonical tones, leave `chosen_tone` null and fill '
        '`custom_tone` with the channel phrase so the policy can resolve.'
    ),
    'rules': (
        "1. `chosen_tone` fills when the user names one of the six canonical options or an obvious "
        "synonym. Map common variants conservatively: 'professional' → formal; 'laid back' → casual; "
        "'scholarly' → academic; 'playful' → witty; 'softer' → natural. If the mapping is too far "
        "(no clear canonical fit), leave `chosen_tone` null and fill `custom_tone` instead.\n"
        "2. `custom_tone` fills when the user describes a tone that doesn't map cleanly to the six "
        "canonicals ('warmer and more welcoming', 'serious but approachable'). Capture as a short "
        "string.\n"
        "3. Both slots can fire together when the user gives a canonical tone plus qualifying "
        "language ('formal but not stiff' → chosen_tone=formal, custom_tone='formal but not stiff') "
        "OR when channel + canonical are both mentioned.\n"
        "4. When the user names only a channel that maps to a single canonical (GitHub → technical), "
        "fill `chosen_tone` directly. When the channel maps to multiple canonicals (LinkedIn → "
        "formal/academic, Medium → natural/formal/witty), leave `chosen_tone` null and put the "
        "channel phrase in `custom_tone` so the policy can resolve.\n"
        "5. When the user uses the verb 'tone' or 'rewrite' with no specific target tone or channel "
        "('tone my intro down' alone), leave both tone slots null so the agent can clarify."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post whose tone is being adjusted. Inherits from active_post on terse '
        'utterances.\n\n'
        '### chosen_tone (elective)\n\n'
        'Type: CategorySlot. Options: formal, casual, technical, academic, witty, natural. Fill when '
        'the user names one directly or uses an obvious synonym (\'professional\' → formal, \'laid '
        'back\' → casual, \'softer\' → natural). Leave null when the wording doesn\'t map cleanly.\n\n'
        '### custom_tone (elective)\n\n'
        'Type: ExactSlot. A free-form tone description when the user\'s phrasing doesn\'t match a '
        'canonical option. Also filled when the user names a channel that maps to multiple canonicals '
        '— store the channel phrase here so the policy can resolve.'
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
    "custom_tone": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Tone my intro warmer and more welcoming."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "'Warmer and more welcoming' doesn't map to a canonical option — fill custom_tone. Source inherits from active_post.",
  "slots": {
    "source": {"post": "RL primer"},
    "chosen_tone": null,
    "custom_tone": "warmer and more welcoming"
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
    "custom_tone": null
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
    "custom_tone": "formal but not stiff"
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
    "custom_tone": "for LinkedIn"
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
    "custom_tone": null
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
    "custom_tone": "like a seasoned practitioner talking shop"
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
    "custom_tone": null
  }
}
```
</edge_case>''',
}


AUDIT_PROMPT = {
    'instructions': (
        'The Audit Flow checks that a post is written in the user\'s voice rather than sounding like '
        'AI. It compares voice, terminology, formatting conventions, and stylistic patterns against '
        'previous posts, flagging sections that drift above a confidence threshold. Audit is distinct '
        'from Rework (which restructures content) and Tone (which shifts register deliberately).\n\n'
        'Extract the target post (`source`, usually inherited from active_post), the number of prior '
        'posts to reference (`reference_count`, optional), and the AI-likelihood threshold '
        '(`threshold`, optional). All elective extraction fires strictly on explicit triggers — vague '
        'descriptors leave slots null and let the policy apply defaults.'
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Fill explicitly when the user names "
        "a post.\n"
        "2. `threshold` fills on explicit probability language: '80%' → 0.8; 'above 0.3' → 0.3; "
        "'flag anything over 50%' → 0.5. Percentages convert to decimals. 'At least 95%' → 0.95.\n"
        "3. Vague descriptors like 'strict' or 'loose' do NOT fill `threshold` — leave null so the "
        "policy can default.\n"
        "4. `reference_count` fills on explicit count language: 'compare against my last 5 posts' → "
        "5; 'against my previous post' (singular) → 1. Leave null on qualitative phrasing ('my "
        "recent stuff', 'a few past posts') — the policy defaults to 10.\n"
        "5. Bare audit with no explicit numbers → source fills, threshold null, reference_count "
        "null — the policy applies defaults."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post being audited. Typically inherits from `state.active_post`; fill '
        'explicitly when the user names a different post.\n\n'
        '### reference_count (optional)\n\n'
        'Type: LevelSlot (threshold=1). Number of prior posts to reference as voice samples. Fires '
        'only on explicit integers (\'last 5 posts\' → 5; \'against my previous post\' → 1). Leave '
        'null on qualitative phrasing — the policy defaults to 10.\n\n'
        '### threshold (optional)\n\n'
        'Type: ProbabilitySlot. AI-likelihood cutoff in [0, 1] — sections with a score above this '
        'are flagged. Fill on explicit probability language; percentages convert (\'80%\' → 0.8). '
        'Leave null on vague qualifiers like \'strict\' so the policy can default.'
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
    "threshold": 0.8
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
  "reasoning": "Indirect audit request — source is explicit, but no threshold or reference count supplied. Both optional slots stay null for the policy to default.",
  "slots": {
    "source": {"post": "RL primer"},
    "reference_count": null,
    "threshold": null
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
    "threshold": null
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
    "threshold": null
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
  "reasoning": "Bare audit — source fills, no numbers given. Both optional slots stay null; the policy defaults.",
  "slots": {
    "source": {"post": "intro"},
    "reference_count": null,
    "threshold": null
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
    "threshold": 0.5
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
  "reasoning": "Source inherits from active_post. 'Recent stuff' is vague → reference_count null. 'Strict' is vague → threshold null. All defaults handled by the policy.",
  "slots": {
    "source": {"post": "My Post"},
    "reference_count": null,
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Audit it — reference 10 posts, threshold 0.5."

## Input
Active post: Trustworthy AI

## Output

```json
{
  "reasoning": "Terse audit with both optional numbers explicitly provided. Source inherits from active_post.",
  "slots": {
    "source": {"post": "Trustworthy AI"},
    "reference_count": 10,
    "threshold": 0.5
  }
}
```
</edge_case>''',
}


SIMPLIFY_PROMPT = {
    'instructions': (
        'The Simplify Flow reduces the complexity of a section\'s prose or swaps out an overly '
        'complex image. The primary use case is removing unnecessary content or obvious AI slop. '
        'Simplify is distinct from Rework (which restructures) and Polish (which tightens individual '
        'phrases for style).\n\n'
        'Extract the target (`source`, which post + section), any image being simplified (`image`), '
        'and any specific user directive about WHAT to cut (`guidance`). At least one of source or '
        'image must fill. Source typically inherits the post from active_post; the user usually '
        'names the specific section being simplified.'
    ),
    'rules': (
        "1. `source` always carries `post` when filled. Fill `sec` when the user names a section. "
        "Inherits post from active_post on terse utterances.\n"
        "2. `image` fills on explicit image-simplify language ('swap that diagram for something "
        "simpler', 'replace the hero image'). Leave null for prose-only simplification.\n"
        "3. `guidance` fills with the user's specific directive about what to cut or how to "
        "simplify ('strip the academic hedging', 'cut the historical preamble'). Captured as a "
        "list of short strings. Leave null on bare simplify requests.\n"
        "4. At least one of `source` or `image` must fill. When both would be null, leave them "
        "null so the flow can clarify.\n"
        "5. Post-wide simplify (no section named, just 'simplify the whole post') is NOT valid — "
        "leave `sec` null so the flow can flag the issue and ask which section.\n"
        "6. Preserve the meaning — simplify is NOT rewording for style (that's Polish)."
    ),
    'slots': (
        '### source (elective)\n\n'
        'Type: SourceSlot. The target section (and its post) to simplify. Always includes `post`; '
        'fills `sec` when the user names a section. Inherits post from active_post on terse '
        'utterances.\n\n'
        '### image (elective)\n\n'
        'Type: ImageSlot. An image reference to simplify. Fill when the user asks to swap, replace, '
        'or remove an image for something simpler.\n\n'
        '### guidance (optional)\n\n'
        'Type: FreeTextSlot. A list of specific user directives about what to cut or how to '
        'simplify. Captures phrases like "strip the academic hedging", "cut the historical '
        'preamble", "remove every other adjective". Leave null on bare simplify requests.'
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
    "guidance": null
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
    "guidance": ["cut the historical preamble and keep it to three sentences"]
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
    "guidance": ["get rid of the redundant content"]
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
Active post: My ML Post

## Output

```json
{
  "reasoning": "Indirect opener (critique, not simplify verb). Section named in prior turn; current turn adds guidance on how much to cut.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "Conclusion"},
    "image": null,
    "guidance": ["cut it in half"]
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
    "guidance": ["trim the fluff"]
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
    "guidance": null
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
    "image": {"image_type": "photo", "src": null, "alt": "scatter plot", "position": null},
    "guidance": ["streamline and remove the scatter plot"]
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
    "guidance": ["strip the academic hedging", "tighten the opening sentences"]
  }
}
```
</edge_case>''',
}


REMOVE_PROMPT = {
    'instructions': (
        'The Remove Flow deletes an entity — a section, paragraph, image, note, or an entire draft '
        'or post. The `type` slot tags WHAT is being removed so the policy can dispatch to the '
        'correct delete tool. Remove is distinct from Rework (which edits in place) and from '
        'Simplify: **Simplify operates at paragraph or sentence scale (shortening inside a '
        'section); Remove operates at section or post scale, a larger unit of deletion.**\n\n'
        'Extract the target (`source` for text-based entities or `image` for images) and the '
        'removal type (`type`, required). Source and image are elective; type is required so the '
        'policy knows which tool to call. Map the user\'s noun to the closest of six type '
        'categories.'
    ),
    'rules': (
        "1. `type` is required. Map user nouns to the closest category: 'article' / 'post' → post; "
        "'draft' → draft; 'section' → section; 'paragraph' / 'sentence' → paragraph; 'note' / "
        "'snippet' → note; 'image' / 'photo' / 'diagram' → image.\n"
        "2. `source` fills when the target is text-based. Section-level removals fill `sec`. "
        "Paragraph-level removals fill BOTH `sec` (the parent section, when named) AND `snip` (the "
        "paragraph description).\n"
        "3. `image` fills when type='image'. Carries image_type from phrasing (diagram/hero/photo).\n"
        "4. On terse utterances ('delete it') with only active_post as context, infer type='post' "
        "from the active_post."
    ),
    'slots': (
        '### source (elective)\n\n'
        'Type: SourceSlot. The text-based target of removal. Always includes `post`; fills `sec` '
        'for section removal and `snip` for paragraph/sentence/note removal. Paragraph-level '
        'removals fill BOTH sec and snip when both are named.\n\n'
        '### image (elective)\n\n'
        'Type: ImageSlot. The image being removed. Fill only when the user asks to delete an '
        'image, diagram, or photo.\n\n'
        '### type (required)\n\n'
        'Type: CategorySlot. Options: post, draft, section, paragraph, note, image. What kind of '
        'entity is being removed. The policy routes to different delete tools based on this.'
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
    "source": {"post": "RL primer"},
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
  "reasoning": "First turn is a Rework. User pivots to removing the section that was just reworked. Source.sec carries 'Methods' from the prior turn; post inherits from active_post.",
  "slots": {
    "source": {"post": "My Paper", "sec": "Methods"},
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
  "reasoning": "Paragraph-level removal inside a named section. Source fills post + sec (Conclusion) + snip (third paragraph). Type='paragraph'.",
  "slots": {
    "source": {"post": "My Post", "sec": "Conclusion", "snip": "third paragraph"},
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
  "reasoning": "First turn references adding an image (not a remove flow). Current turn removes it. Source carries the post; image captures the hero reference; type='image'.",
  "slots": {
    "source": {"post": "transformer"},
    "image": {"image_type": "hero", "src": null, "alt": null, "position": null},
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
  "reasoning": "First turn is Compose. User pivots to removing a different section than the one just composed. Source.sec switches to 'methods'; type='section'. Post inherits from active_post.",
  "slots": {
    "source": {"post": "RL primer", "sec": "methods"},
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
  "reasoning": "'Snippet' maps to type='note'. Source carries the snippet description.",
  "slots": {
    "source": {"snip": "attention dropout"},
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
Active post: My Old Draft

## Output

```json
{
  "reasoning": "Terse removal with only active_post as context. Per rule 4, infer type='post' from the active_post — source carries the post title.",
  "slots": {
    "source": {"post": "My Old Draft"},
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
    "source": {"post": "My Post", "sec": "intro", "snip": "last two paragraphs"},
    "image": null,
    "type": "paragraph"
  }
}
```
</edge_case>''',
}


TIDY_PROMPT = {
    'instructions': (
        'The Tidy Flow normalizes structural formatting across a post — heading hierarchy, list '
        'indentation, paragraph spacing, whitespace cleanup. It does NOT change wording. Tidy is '
        'distinct from Polish (which adjusts phrasing) and Rework (which restructures content).\n\n'
        'Extract the target post (`source`, usually inherited from active_post) and any formatting '
        'settings the user specifies (`settings`, a DictionarySlot of key-value pairs like '
        '`{headings: \'H2\'}`). The `image` slot is optional and fills only when the user asks to '
        'tidy image alignment or captions.'
    ),
    'rules': (
        "1. `source` typically inherits from `state.active_post`. Tidy is post-wide by default so "
        "`sec` is rarely filled.\n"
        "2. `settings` fills when the user specifies formatting rules — 'use H2 headings', "
        "'normalize list indents'. Parse into key-value pairs: 'H2 headings' → `{headings: 'H2'}`. "
        "Capture the user's wording as the dict key.\n"
        "3. Leave `settings` null on bare 'clean it up' or 'tidy this' — the policy applies "
        "defaults.\n"
        "4. `image` fills only on explicit image-formatting language ('fix the image alignment', "
        "'center the diagrams'). Leave null for prose-only tidying."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot (entity_part=\'post\'). The post to tidy. Typically inherits from '
        '`state.active_post`. Tidy is post-wide; `sec` rarely fills.\n\n'
        '### settings (required)\n\n'
        'Type: DictionarySlot. Key-value pairs capturing formatting rules the user specifies ('
        '\'H2 headings\' → `{headings: \'H2\'}`). Leave null on bare tidy requests — the policy '
        'applies defaults.\n\n'
        '### image (optional)\n\n'
        'Type: ImageSlot. Image-formatting target. Fills on alignment/caption tidying requests '
        '(\'fix the image alignment\', \'center the diagrams\'). Leave null for prose-only tidying.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Compose the Methods section of my transformer post."
Agent: "Done — here's the composed Methods section..."
User: "Now tidy the heading hierarchy — H2 for top-level, H3 for sub."

## Input
Active post: transformer

## Output

```json
{
  "reasoning": "First turn is Compose. Current turn switches to Tidy — source inherits post from active_post; settings parse the heading rules into a dict.",
  "slots": {
    "source": {"post": "transformer"},
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
    "image": {"image_type": "diagram", "src": null, "alt": null, "position": null}
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Rework my transformer post."
Agent: "Reworking the whole post — here's the revised version..."
User: "Actually, just tidy it up — H2 headings throughout."

## Input
Active post: transformer

## Output

```json
{
  "reasoning": "First turn is Rework. User pivots to Tidy with specific heading rules. Source inherits post; settings parses the heading directive.",
  "slots": {
    "source": {"post": "transformer"},
    "settings": {"headings": "H2"},
    "image": null
  }
}
```
</edge_case>

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
