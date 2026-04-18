OUTLINE_PROMPT = {
    'instructions': (
        'Generate section headings, reading order, and optional nesting depth for a blog post. The user '
        'typically already has an active post grounded (its title appears in `### Active Post`). Populate '
        '`topic` when the user supplies a descriptive angle that adds information beyond the title. Populate '
        '`sections` when the user enumerates named section headings. Populate `depth` when the user mentions '
        'nesting or levels (not counts). At least one of `topic` or `sections` must be filled for the flow '
        'to proceed.'
    ),
    'rules': (
        '1. `topic` is a short descriptive sentence, not a single word. Only fill when the user supplies '
        'more information than the post title already carries. A bare restatement of the title '
        '("regularization methods" on a post titled *Regularization Techniques*) → `topic=null`. A '
        'full angle sentence ("why batch beats streaming for small teams") → populate.\n'
        '2. `sections` needs named headings, not a count. "With 4 sections" → `sections=null`. "Cover X, '
        'Y, Z" → fill with those items. Each item is `{"name": <Proper Case heading>, "description": "", '
        '"checked": false}`. Drop filler words like "their" that break heading consistency.\n'
        '3. `depth` is nesting depth only: 1 = top-level headings, 2 = headings + bullets, 3 = bullets + '
        'sub-bullets. A section count is NEVER depth. Phrasing like "at the next level, we should discuss…" '
        'implies `depth=2` even without the literal words "depth" or "levels".\n'
        '4. Infer `topic` from conversation history when the current utterance is terse but earlier turns '
        'established the subject.\n'
        '5. When the same number appears alongside a matching enumeration ("Make a 4-section outline: A, B, '
        'C, D"), the number is redundant with the enumeration — fill `sections` from the names and leave '
        '`depth` empty.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. Reference to the existing post being outlined. When an active post is grounded, '
        'this slot is pre-filled and omitted from the schema above. When the user explicitly references a '
        'different post, populate `{"post": <title>}` with trailing status words ("post", "draft", '
        '"article", "note") stripped.\n\n'
        '### topic (elective)\n\n'
        'Type: ExactSlot. A short descriptive sentence capturing the angle or framing beyond the post '
        'title. `null` when the utterance only restates the title or offers no angle.\n\n'
        '### sections (elective)\n\n'
        'Type: ChecklistSlot. Each item is `{"name": <Proper Case heading>, "description": "", "checked": '
        'false}`. Fill only when the user enumerates actual section headings — bare counts leave this '
        '`null`.\n\n'
        '### depth (optional)\n\n'
        'Type: LevelSlot (integer 1-3). 1 = headings only, 2 = headings + bullets, 3 = bullets + '
        'sub-bullets. Section counts never fill this slot.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Make a post about reinforcement learning — cover markov decision processes, value functions, policy gradients, and real-world applications."
## Output

```json
{
  "reasoning": "Four named headings follow 'cover' → populate sections, Proper-Cased. No nesting phrasing → depth empty. 'Post about...' isn't descriptive enough to fill topic separately.",
  "slots": {
    "source": {"post": "reinforcement learning"},
    "topic": null,
    "sections": [
      {"name": "Markov Decision Processes", "description": "", "checked": false},
      {"name": "Value Functions", "description": "", "checked": false},
      {"name": "Policy Gradients", "description": "", "checked": false},
      {"name": "Real-World Applications", "description": "", "checked": false}
    ],
    "depth": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Outline my data augmentation post — focus on how paraphrasing beats back-translation for low-resource languages."
## Output

```json
{
  "reasoning": "Descriptive sentence beyond the title → topic populated. No enumerated headings → sections empty. No nesting cue → depth empty.",
  "slots": {
    "source": {"post": "data augmentation"},
    "topic": "how paraphrasing beats back-translation for low-resource languages",
    "sections": null,
    "depth": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want the post to include sections on jailbreaks, guardrails, and red-teaming. At the next level, we should discuss the pros and cons of each method and their reliability in keeping things safe."
## Output

```json
{
  "reasoning": "Three named headings → sections. 'At the next level, we should discuss…' implies two levels of content → depth=2. No source stated and no active post assumed here.",
  "slots": {
    "source": null,
    "topic": null,
    "sections": [
      {"name": "Jailbreaks", "description": "", "checked": false},
      {"name": "Guardrails", "description": "", "checked": false},
      {"name": "Red-Teaming", "description": "", "checked": false}
    ],
    "depth": 2
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "For my data pipelines post, I want the angle to be why batch beats streaming for small teams."
## Output

```json
{
  "reasoning": "Explicit angle sentence distinct from the title → topic populated. No headings → sections empty. No nesting cue → depth empty.",
  "slots": {
    "source": {"post": "data pipelines"},
    "topic": "why batch beats streaming for small teams",
    "sections": null,
    "depth": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Make an outline with 4 sections."
## Output

```json
{
  "reasoning": "'4 sections' is a count — not headings, not depth. No post is grounded and the utterance names none. All slots stay empty so downstream clarification can ask.",
  "slots": {
    "source": null,
    "topic": null,
    "sections": null,
    "depth": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "I want to write about how to spot regressions in agent traces."
Agent: "Here's your post about Spotting Regressions in Traces."
User: "Make an outline with 3 sections."
## Output

```json
{
  "reasoning": "Current turn is terse ('3 sections' is a count, not headings). Prior turn established the subject — spotting regressions in agent traces — so topic is inferable from history. Source is empty since no post was named or grounded here.",
  "slots": {
    "source": null,
    "topic": "how to spot regressions in agent traces",
    "sections": null,
    "depth": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Outline my scaffolding post about agent scaffolding."
## Output

```json
{
  "reasoning": "'Agent scaffolding' restates the title with no added angle → topic stays empty. No headings → sections empty.",
  "slots": {
    "source": {"post": "scaffolding"},
    "topic": null,
    "sections": null,
    "depth": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Make a 4-section outline for my cooking post: knife skills, stocks, sauces, and plating."
## Output

```json
{
  "reasoning": "The '4' matches the enumeration that follows — fill sections from the named headings, not depth. No descriptive angle beyond the title → topic empty.",
  "slots": {
    "source": {"post": "cooking"},
    "topic": null,
    "sections": [
      {"name": "Knife Skills", "description": "", "checked": false},
      {"name": "Stocks", "description": "", "checked": false},
      {"name": "Sauces", "description": "", "checked": false},
      {"name": "Plating", "description": "", "checked": false}
    ],
    "depth": null
  }
}
```
</edge_case>''',
}

REFINE_PROMPT = {
    'instructions': (
        'Apply user-requested changes to an existing outline. The user either enumerates structured edits '
        '(items to reorder, bullets to add, sections to rename) or gives prose-style critique about the '
        'feel of the outline. Route each utterance to the right slot; an utterance can populate both slots '
        'when it mixes enumeration and prose.'
    ),
    'rules': (
        '1. Structured enumeration fills `steps`. Triggers: numbered lists, comma-separated items, "Under '
        'X, add: a, b, c" shapes, explicit reorder specs, rename directives. Each step is a free-form '
        'string carrying the action plus any section anchor inline (e.g. `"Add \'pick an encoder\' '
        'bulletpoint under \'Process\' section"`).\n'
        '2. Prose critique fills `feedback`. A short interpretive paragraph — "more detail in the methods '
        'section", "make the intro punchier", "trim to 4 sections" — goes here verbatim as a single '
        'string.\n'
        '3. Count-only directives are prose, not enumeration. "Trim to 4 sections" → `feedback`, not '
        '`steps`, because no specific headings are named.\n'
        '4. Mixed utterances populate BOTH slots. An enumerated reorder followed by "and make the intro '
        'punchier" → `steps` from the enumeration, `feedback` from the trailing prose.\n'
        '5. `source.sec` becomes a list when the user references multiple sections in one utterance (e.g. '
        '"Under Process, add… Under Ideas, add…" → `sec=["Process", "Ideas"]`).'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post whose outline is being refined. When an active post is grounded, this '
        'slot is pre-filled and omitted from the schema above. The `sec` sub-key may be a list when the '
        'utterance references multiple sections.\n\n'
        '### steps (elective)\n\n'
        'Type: ChecklistSlot where each item is a free-form string describing one discrete change. Section '
        'anchors are embedded in the string (not in a separate description field).\n\n'
        '### feedback (elective)\n\n'
        'Type: FreeTextSlot. A single short prose string capturing interpretive direction — one value, not '
        'a list.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Outline my agent harness post."
Agent: "Here's a 5-section outline…"
User: "Reorder to background, experiments, breakthrough, results, and legacy."
## Output

```json
{
  "reasoning": "Five named headings announce a reorder → each becomes a step item. No prose critique → feedback empty. Source inherited from prior turn.",
  "slots": {
    "source": {"post": "agent harness"},
    "steps": ["Background", "Experiments", "Breakthrough", "Results", "Legacy"],
    "feedback": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "The outline for my calibration post needs more detail in the evaluation section."
## Output

```json
{
  "reasoning": "Short prose critique about a single section → feedback populated verbatim. No enumerated items → steps empty.",
  "slots": {
    "source": {"post": "calibration"},
    "steps": null,
    "feedback": "more detail in the evaluation section"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Reorder to background, experiments, results, and make the intro punchier."
## Output

```json
{
  "reasoning": "Three enumerated reorder items → steps. Trailing prose directive about the intro → feedback. One utterance, both slots filled.",
  "slots": {
    "source": null,
    "steps": ["Background", "Experiments", "Results"],
    "feedback": "make the intro punchier"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Trim the data augmentation post outline down to just 4 sections."
## Output

```json
{
  "reasoning": "'4 sections' is a count, not named headings → feedback captures the directive. No enumerated items → steps empty.",
  "slots": {
    "source": {"post": "data augmentation"},
    "steps": null,
    "feedback": "trim down to just 4 sections"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Outline my reinforcement learning post."
Agent: "Here's a 4-section outline: Intro, Algorithms, Tricks, Applications."
User: "Under the Tricks section, the points should be: reward shaping, generalized advantage estimation, and gradient clipping."
## Output

```json
{
  "reasoning": "Structured 'Under X, add:' shape → three step items, each anchored inline to the Tricks section. No prose critique → feedback empty. Source inherited; sec resolves to the named section.",
  "slots": {
    "source": {"post": "reinforcement learning", "sec": "Tricks"},
    "steps": [
      "Add 'reward shaping' as a bulletpoint under 'Tricks'",
      "Add 'generalized advantage estimation' as a bulletpoint under 'Tricks'",
      "Add 'gradient clipping' as a bulletpoint under 'Tricks'"
    ],
    "feedback": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Outline my trustworthy AI post."
Agent: "Here's a 4-section outline: Intro, Methods, Case Studies, Future."
User: "Under Methods, add: red-team simulations, interpretability probes, chain-of-thought audits. Under Case Studies, add: jailbreak incident reviews."
## Output

```json
{
  "reasoning": "Two section anchors in one utterance → source.sec becomes a list. Four enumerated bullets across the two sections → four step items with section inline.",
  "slots": {
    "source": {"post": "trustworthy AI", "sec": ["Methods", "Case Studies"]},
    "steps": [
      "Add 'red-team simulations' bulletpoint under 'Methods' section",
      "Add 'interpretability probes' bulletpoint under 'Methods' section",
      "Add 'chain-of-thought audits' bulletpoint under 'Methods' section",
      "Add 'jailbreak incident reviews' bulletpoint under 'Case Studies' section"
    ],
    "feedback": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Rename 'Ideas' to 'Breakthrough Ideas' and move it before 'Process'."
## Output

```json
{
  "reasoning": "Two discrete actions joined by 'and' → each becomes a step. No prose critique → feedback empty. No post grounded in the current utterance.",
  "slots": {
    "source": null,
    "steps": [
      "Rename 'Ideas' to 'Breakthrough Ideas'",
      "Move 'Ideas' before 'Process'"
    ],
    "feedback": null
  }
}
```
</edge_case>''',
}

CREATE_PROMPT = {
    'instructions': (
        'Initialize a new post record with a clean title and type. This flow does NOT generate content — '
        'use outline or compose for that. Titles are always multi-word Proper Case; distill or preserve per '
        'the rules below. Default `type` to `draft` unless the user explicitly asks for a short-form note.'
    ),
    'rules': (
        '1. `title` is ALWAYS ≥2 words; single-word titles are rejected. Examples:\n'
        '   - *"Create a post called Regularization Techniques"* → `"Regularization Techniques"` '
        '(preserved verbatim)\n'
        '   - *"Write a new draft about how batch normalization works"* → `"How Batch Normalization '
        'Works"` (distilled)\n'
        '   - *"Start a post on calibration, focusing on isotonic regression"* → `"Isotonic Regression '
        'for Calibration"` (title follows the elaboration; "calibration" alone would be one word and '
        'is rejected)\n'
        '2. Preserve verbatim when the user wraps the title in quotes OR supplies explicit Proper Case. '
        'Otherwise distill the subject into a short Proper Case phrase.\n'
        '3. Strip trailing status words ("post", "draft", "article", "note") from the title. *"Create an '
        'article titled Trustworthy AI post"* → `"Trustworthy AI"`.\n'
        '4. `type` defaults to `draft` for formal article-like content. Switch to `note` when the user uses '
        'snippet-style language ("quick note", "snippet", "start a note"). "Post" and "article" → `draft`.\n'
        '5. `topic` fills only when the user elaborates past the title phrasing — a longer description '
        'beyond what the title already carries. A bare "about X" where X IS the title → `topic=null`.'
    ),
    'slots': (
        '### title (required)\n\n'
        'Type: ExactSlot. A short Proper Case title, always ≥2 words. Preserve verbatim when the user '
        'presented a specific title (quoted or Proper-Cased). Otherwise distill the subject. Strip trailing '
        'status words.\n\n'
        '### type (required)\n\n'
        'Type: CategorySlot. Options: `draft`, `note`. Default to `draft` for article-like content; use '
        '`note` for explicit snippet-style language.\n\n'
        '### topic (optional)\n\n'
        'Type: ExactSlot. A longer description beyond the title. `null` when the utterance offers no '
        'elaboration past the title phrasing.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Start a post on scaffolding, focusing on why thin harnesses outperform thick ones for long-horizon tasks."
## Output

```json
{
  "reasoning": "Core subject 'scaffolding' is one word — rejected as a title. The elaboration narrows to thin-harness design, so the distilled Proper Case title is 'Thin Harnesses for Agent Scaffolding'. 'Post' → draft. The elaboration is a genuine angle beyond the title → topic populated.",
  "slots": {
    "title": "Thin Harnesses for Agent Scaffolding",
    "type": "draft",
    "topic": "why thin harnesses outperform thick ones for long-horizon tasks"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Write a new draft about how data augmentation helps low-resource NLP."
## Output

```json
{
  "reasoning": "Lowercase phrasing → distill to Proper Case: 'How Data Augmentation Helps Low-Resource NLP'. 'Draft' names the type directly. No elaboration beyond the title itself → topic empty.",
  "slots": {
    "title": "How Data Augmentation Helps Low-Resource NLP",
    "type": "draft",
    "topic": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Create a post called Regularization Techniques."
## Output

```json
{
  "reasoning": "Title given in Proper Case after 'called' → preserve verbatim. 'Post' → draft. No elaboration → topic empty.",
  "slots": {
    "title": "Regularization Techniques",
    "type": "draft",
    "topic": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Start a note about why batch normalization helps training stability."
## Output

```json
{
  "reasoning": "'Note' → type=note. Distill the subject into Proper Case: 'Batch Normalization and Training Stability'. The 'why' clause elaborates the framing → topic populated.",
  "slots": {
    "title": "Batch Normalization and Training Stability",
    "type": "note",
    "topic": "why batch normalization helps training stability"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Create an article titled Calibrating LLM Judges post."
## Output

```json
{
  "reasoning": "Title is already Proper Case; 'post' is a trailing status word tacked on the end → strip it. 'Article' → draft. No elaboration → topic empty.",
  "slots": {
    "title": "Calibrating LLM Judges",
    "type": "draft",
    "topic": null
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'outline': OUTLINE_PROMPT,
    'refine': REFINE_PROMPT,
    'create': CREATE_PROMPT,
    'brainstorm': {
        'instructions': 'Generate ideas, angles, hooks, or new perspectives for a topic — can be open-ended or anchored to an existing post.',
        'rules': '''- source (elective): An existing post or section to brainstorm about. When present, ideas are grounded to that content.
- topic (elective): A topic or phrase to brainstorm around. Used when no existing post is referenced.
- ideas (optional): Agent-generated options — not typically filled during slot extraction.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Brainstorm some angles for a post about prompt engineering"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "topic": "prompt engineering",
    "ideas": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Give me ideas for the introduction of my transformer post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "transformer",
      "sec": "introduction"
    },
    "topic": null,
    "ideas": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "What could I write about next?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "topic": null,
    "ideas": null
  }
}
```
</positive_example>''',
    },
    'cite': {
        'instructions': 'Attach a citation to a note. If a URL is provided, use it directly; otherwise search the web for a supporting source.',
        'rules': '''- source (elective): The note to cite. This slot looks for snippet references specifically — use the "snip" entity key.
- url (elective): A direct URL to attach. Preserve the full URL verbatim.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Add a citation to my attention mechanism note"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "snip": "attention mechanism"
    },
    "url": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Cite https://arxiv.org/abs/1706.03762 in my transformer post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "transformer"
    },
    "url": "https://arxiv.org/abs/1706.03762"
  }
}
```
</positive_example>''',
    },
    'compose': {
        'instructions': 'Write a section from scratch based on instructions or an outline.',
        'rules': '''- source (required): The post and optionally section to write for. If the user only gives a topic, the post title may match the topic.
- steps (elective): Sub-points to cover in order, as a ChecklistSlot. When the user lists points to cover ("cover X, Y, Z"), put them here.
- instructions (elective): Qualitative writing guidance — tone, length, angle, constraints, or stylistic direction. Descriptive text about how to write goes here, not what to write about.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Compose a new post about prompt engineering best practices"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "prompt engineering best practices"
    },
    "steps": null,
    "instructions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Write the positional encoding section in my transformer deep dive post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "transformer deep dive",
      "sec": "positional encoding"
    },
    "steps": null,
    "instructions": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Draft something about how LLMs handle context windows"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "how LLMs handle context windows"
    },
    "steps": null,
    "instructions": null
  }
}
```
</positive_example>''',
    },
    'add': {
        'instructions': 'Insert new sections into an existing post.',
        'rules': '''- source (required): The post to add sections to.
- steps (elective): The new sections to create. Each item's "name" becomes the section heading.
- instructions (elective): Guidance for the new sections (e.g., content direction, length hints).
- image (elective): Images to include in the new sections.
- position (optional): Where to insert among existing sections as a 0-based index. "Right after the intro" → 1. Only extract if the user specifies placement.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Add a street food section to my Bangkok travel post, right after the intro"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Bangkok travel"
    },
    "steps": [
      {
        "name": "street food",
        "description": "",
        "checked": false
      }
    ],
    "instructions": null,
    "image": null,
    "position": 1
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Add sections on evaluation metrics and future work to my ML post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ML"
    },
    "steps": [
      {
        "name": "Evaluation Metrics",
        "description": "",
        "checked": false
      },
      {
        "name": "Future Work",
        "description": "",
        "checked": false
      }
    ],
    "instructions": null,
    "image": null,
    "position": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I need a new section on evaluation metrics"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "steps": [
      {
        "name": "evaluation metrics",
        "description": "",
        "checked": false
      }
    ],
    "instructions": null,
    "image": null,
    "position": null
  }
}
```
</positive_example>''',
    },
}
