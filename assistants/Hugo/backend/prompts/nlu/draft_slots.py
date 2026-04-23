OUTLINE_PROMPT = {
    'instructions': (
        'Generate section headings, reading order, and optional nesting depth for a blog post. The user '
        'typically already has an active post grounded (its title appears in the `## Input` block). The '
        'flow runs in two modes downstream, and slot-filling decides which: when the user supplies named '
        'section headings, fill `sections` (direct mode); when they only supply an angle, fill `topic` and '
        'leave `sections` null (propose mode — downstream generates candidate headings). Populate `depth` '
        'only when the user mentions nesting or levels (not counts). At least one of `topic` or `sections` '
        'must be filled for the flow to proceed.'
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

## Input
Active post: None

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

## Input
Active post: data augmentation

## Output

```json
{
  "reasoning": "Descriptive sentence beyond the title → topic populated. No enumerated headings → sections empty. No nesting cue → depth empty. Source matches the active post the user is focused on.",
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

## Input
Active post: None

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

## Input
Active post: data pipelines

## Output

```json
{
  "reasoning": "Explicit angle sentence distinct from the title → topic populated. No headings → sections empty. No nesting cue → depth empty. Source matches the active post.",
  "slots": {
    "source": {"post": "data pipelines"},
    "topic": "why batch beats streaming for small teams",
    "sections": null,
    "depth": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Create a post called Knowledge Distillation."
Agent: "Done — 'Knowledge Distillation' is saved as a draft."
User: "Let's fill in the outline to talk about teacher-student pairs, soft targets, and distillation loss."

## Input
Active post: Knowledge Distillation

## Output

```json
{
  "reasoning": "Turn 1 created the active post; turn 3 asks to outline it. Source inherits from the active post since the current request is about the same post. Three named headings after 'talk about' → fill sections Proper-Cased (propose-mode not needed because the user supplied them directly). No separate angle sentence → topic empty. No nesting cue → depth empty.",
  "slots": {
    "source": {"post": "Knowledge Distillation"},
    "topic": null,
    "sections": [
      {"name": "Teacher-Student Pairs", "description": "", "checked": false},
      {"name": "Soft Targets", "description": "", "checked": false},
      {"name": "Distillation Loss", "description": "", "checked": false}
    ],
    "depth": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Create a post about synthetic data for low-resource languages."
Agent: "Created draft 'Synthetic Data for Low-Resource Languages'."
User: "Make an outline — propose a few options I can pick from."
Agent: "### Option 1 ... ### Option 2 ... ### Option 3 ..."
User: "Make an outline with 3 sections: Pipeline, Evaluation, and Limitations. Under Pipeline, add bullets about teacher-forced generation, back-translation filtering, and quality triage."

## Input
Active post: Synthetic Data for Low-Resource Languages

## Output

```json
{
  "reasoning": "Prior turn showed propose options but the user is now supplying their own named enumeration — that takes precedence. 'With 3 sections: Pipeline, Evaluation, Limitations' is the section list → fill sections Proper-Cased. The trailing 'Under Pipeline, add bullets about...' is direction for the outline skill's body, not a separate slot. No nesting cue → depth empty. Topic stays null because the enumeration is present.",
  "slots": {
    "source": {"post": "Synthetic Data for Low-Resource Languages"},
    "topic": null,
    "sections": [
      {"name": "Pipeline", "description": "", "checked": false},
      {"name": "Evaluation", "description": "", "checked": false},
      {"name": "Limitations", "description": "", "checked": false}
    ],
    "depth": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Just 4 sections."

## Input
Active post: None

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
Agent: "Got it — want to shape it into an outline?"
User: "Let's go with 3 sections."

## Input
Active post: None

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

User: "The scaffolding post should be about agent scaffolding."

## Input
Active post: None

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

## Input
Active post: cooking

## Output

```json
{
  "reasoning": "The '4' matches the enumeration that follows — fill sections from the named headings, not depth. No descriptive angle beyond the title → topic empty. Source matches the active post.",
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

## Input
Active post: agent harness

## Output

```json
{
  "reasoning": "Five named headings announce a reorder → each becomes a step item. No prose critique → feedback empty. Source inherited from the active post established in turn 1.",
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

## Input
Active post: calibration

## Output

```json
{
  "reasoning": "Short prose critique about a single section → feedback populated verbatim. No enumerated items → steps empty. Source matches the active post.",
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

## Input
Active post: None

## Output

```json
{
  "reasoning": "Three enumerated reorder items → steps. Trailing prose directive about the intro → feedback. One utterance, both slots filled. No post named and no active post → source stays null.",
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

## Input
Active post: data augmentation

## Output

```json
{
  "reasoning": "'4 sections' is a count, not named headings → feedback captures the directive. No enumerated items → steps empty. Source matches the active post.",
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

## Input
Active post: reinforcement learning

## Output

```json
{
  "reasoning": "Structured 'Under X, add:' shape → three step items, each anchored inline to the Tricks section. No prose critique → feedback empty. Source inherited from active post; sec resolves to the named section.",
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

<positive_example>
## Conversation History

User: "How many words are in my RL primer?"
Agent: "RL primer has 2,340 words across 5 sections."
User: "Trim it down to 4 sections."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Prior turn was an Inspect on RL primer; current turn pivots to Refine on the same post → source inherits from active post. 'Trim down to 4 sections' is a count-only directive with no named headings → feedback captures the directive verbatim. No enumerated steps.",
  "slots": {
    "source": {"post": "RL primer"},
    "steps": null,
    "feedback": "trim it down to 4 sections"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Reorder my agent harness outline: background, experiments, results, legacy."
Agent: "Reordered — background first, legacy last."
User: "Now rename 'Legacy' to 'Impact'."

## Input
Active post: agent harness

## Output

```json
{
  "reasoning": "Prior turn was a Refine that was already applied — the agent confirmed the reorder, so those step values are done and must NOT carry forward. Current turn is a separate Refine on the same post; source inherits from active post. One rename action → one step item. No prose critique → feedback empty.",
  "slots": {
    "source": {"post": "agent harness"},
    "steps": ["Rename 'Legacy' to 'Impact'"],
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

## Input
Active post: trustworthy AI

## Output

```json
{
  "reasoning": "Two section anchors in one utterance → source.sec becomes a list. Four enumerated bullets across the two sections → four step items with section inline. Source inherited from active post.",
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

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two discrete actions joined by 'and' → each becomes a step. No prose critique → feedback empty. No post grounded in the current utterance or active post.",
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

User: "I've been wanting to document scaffolding in a post — specifically why thin harnesses outperform thick ones for long-horizon tasks."
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

User: "We should do a piece on how data augmentation helps low-resource NLP."
## Output

```json
{
  "reasoning": "Lowercase phrasing → distill to Proper Case: 'How Data Augmentation Helps Low-Resource NLP'. 'Piece' is article-like → type=draft. No elaboration beyond the title itself → topic empty.",
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

User: "A quick note on why batch normalization helps training stability."
## Output

```json
{
  "reasoning": "'Quick note' → type=note. Distill the subject into Proper Case: 'Batch Normalization and Training Stability'. The 'why' clause elaborates the framing → topic populated.",
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

User: "Can I get an article titled Calibrating LLM Judges post?"
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


BRAINSTORM_PROMPT = {
    'instructions': (
        'The Brainstorm Flow is called when the user wants ideas, angles, hooks, or new perspectives '
        'rather than a concrete write action. It is typically a discovery turn — before an outline, '
        'before a rewrite, or to expand a thin section.\n\n'
        'Identify whether the user has named a `topic` to brainstorm around and whether they have seeded '
        'the brainstorm with their own `ideas`. Topic is the primary slot to look for — `source` is '
        'typically filled by code before slot-filling runs, so if you do not see source pre-filled, '
        'assume it is missing. Ideas fills only when the user lists existing items they want extended. '
        'Both `topic` and `source` can be filled in the same turn when the user references an existing '
        'post and adds a new angle.'
    ),
    'rules': (
        '1. `topic` is a bare subject or phrase the user wants ideas around. Capture it as the user wrote it.\n'
        '2. `source` is typically filled by code before this prompt runs. If it is not pre-filled, assume '
        'it is missing and leave it null.\n'
        '3. `ideas` fills only when the user provides their own seed list (≥2 items). The shape is a list '
        'of short strings, one per item the user dictated. Leave null when no user-supplied items appear.\n'
        '4. `topic` and `source` can both fill in one turn when the user references an existing post AND '
        'adds a new subject phrase that goes beyond the post title.\n'
        '5. When the utterance has no subject and no seed list, leave all slots null so the flow can ask '
        'for one.'
    ),
    'slots': (
        '### source (elective)\n\n'
        'Type: SourceSlot. Reference to an existing post, section, or snippet that anchors the '
        'brainstorm. Typically pre-filled by code; if you do not see it pre-filled, leave it null.\n\n'
        '### topic (elective)\n\n'
        'Type: ExactSlot. A bare subject, phrase, or word to brainstorm around. Leave `null` when the '
        'utterance references an existing entity instead, or when no subject is named at all.\n\n'
        '### ideas (elective)\n\n'
        'Type: ProposalSlot. A list of items the user has proposed as seed material for the brainstorm. '
        'Fills when the user dictates their own starting items (e.g., "I have intro, methods, results — '
        'give me three more sections to add"). Leave `null` when no user-supplied items appear.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Come up with a few angles around interpretability."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Bare subject phrase, no entity reference, no seed list. Topic captures the subject; source and ideas stay null.",
  "slots": {
    "source": null,
    "topic": "interpretability",
    "ideas": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Give me hooks for the introduction of my transformer deep dive post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User anchors the brainstorm to an existing entity with a sub-part. Source carries post + sec; no separate topic phrase; no seed list.",
  "slots": {
    "source": {"post": "transformer deep dive", "sec": "introduction"},
    "topic": null,
    "ideas": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I'm starting a sales playbook post. I already have prospecting, qualifying, and closing — give me three more stages to write about."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User dictated a seed list of three stages and asked for more. Topic captures the broader subject; ideas captures the seed items.",
  "slots": {
    "source": null,
    "topic": "sales playbook",
    "ideas": ["prospecting", "qualifying", "closing"]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to write something about evaluation harnesses."
Agent: "Sure — should we jump into outline, or do you want me to pitch some angles first?"
User: "Pitch some angles."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Current utterance is terse and carries no subject. Prior turn established topic='evaluation harnesses'; carry that forward. No new entity, no seed list.",
  "slots": {
    "source": null,
    "topic": "evaluation harnesses",
    "ideas": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Brainstorm angles on transformers."
Agent: "Sure — here are five angles you could explore..."
User: "Actually, let's switch — give me angles on RL instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Prior turn set topic='transformers', but the current utterance explicitly switches subjects with 'actually, let's switch'. Ignore the prior topic and fill with the new one.",
  "slots": {
    "source": null,
    "topic": "RL",
    "ideas": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Brainstorm techniques for prompt engineering."
Agent: "What aspects do you want to focus on?"
User: "I've been exploring chain of thought, few-shot, and structured output."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Topic comes from the prior turn ('prompt engineering'). Current turn supplies a seed list of three techniques the user has been exploring — those fill ideas.",
  "slots": {
    "source": null,
    "topic": "prompt engineering",
    "ideas": ["chain of thought", "few-shot", "structured output"]
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Brainstorm angles on security for my agent harness post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Both source and topic fill in one turn. Source from the entity reference; topic from the new angle the user wants explored within that post.",
  "slots": {
    "source": {"post": "agent harness"},
    "topic": "security",
    "ideas": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Can you publish my latest draft tonight?"
Agent: "I can't publish without confirming the channel — what platform?"
User: "Brainstorm a couple of new ideas instead."

## Input
Active post: My RL Primer

## Output

```json
{
  "reasoning": "Prior turns are about a publish action that was abandoned. The current utterance is a context switch to brainstorming but names no subject. Active post 'My RL Primer' is unrelated to the new request — do NOT carry it as source. All slots stay null so clarification can ask for a topic.",
  "slots": {
    "source": null,
    "topic": null,
    "ideas": null
  }
}
```
</edge_case>''',
}

CITE_PROMPT = {
    'instructions': (
        'The Cite Flow attaches a citation (URL) to a snippet of text within a post — a sentence, '
        'phrase, or short quoted passage. Citations always anchor to snippets, not to whole posts or '
        'sections.\n\n'
        'Extract the snippet being cited (`target`) and the URL (`url`) when present. When the user '
        'supplies only a target, the policy will web-search for a supporting source. When the user '
        'supplies only a URL, the policy uses the active snippet from context. Both slots are elective '
        'so at least one must be present to proceed.'
    ),
    'rules': (
        '1. `target` carries the snippet text the user wants to cite. Fill the `snip` key with the '
        'sentence or phrase being cited. Leave null when the user provides only a URL without naming '
        'what to attach it to.\n'
        '2. `url` captures URLs verbatim as a single string. When the user supplies multiple URLs in '
        'one utterance, concatenate with semicolons: `"https://a.com; https://b.com"`.\n'
        '3. When only a URL is provided, leave `target` null — the policy uses the active snippet '
        'context.\n'
        '4. When only a target is provided, leave `url` null — the policy will search for a supporting '
        'source.\n'
        '5. When both are provided, fill both and trust the user\'s pairing.'
    ),
    'slots': (
        '### target (elective)\n\n'
        'Type: TargetSlot. The snippet of text the citation attaches to — typically a sentence or '
        'phrase. Fill the `snip` key with the snippet text. Leave null when the user provides only a '
        'URL.\n\n'
        '### url (elective)\n\n'
        'Type: ExactSlot. A URL supplied by the user as the citation source. Capture the full string '
        'exactly. Use semicolon-separated concatenation when multiple URLs are named in the same '
        'utterance. Leave null when the user names only a target and wants the agent to search.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Cite https://arxiv.org/abs/1706.03762 on the claim about self-attention in my transformer post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Both URL and target provided in one turn. Target carries the snippet ('the claim about self-attention'); the post reference is context, not a slot value. URL captured verbatim.",
  "slots": {
    "target": {"snip": "the claim about self-attention"},
    "url": "https://arxiv.org/abs/1706.03762"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Add a citation to the sentence about scaling laws in my transformer deep dive."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User names the snippet but no URL. Target fills with the sentence reference; url stays null so the policy can web-search for a supporting source.",
  "slots": {
    "target": {"snip": "the sentence about scaling laws"},
    "url": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to cite the claim about attention."
Agent: "Do you have the URL?"
User: "https://arxiv.org/abs/2307.15217"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Target comes from the first turn ('the claim about attention'); URL comes from the third turn. Both slots fill across turns.",
  "slots": {
    "target": {"snip": "the claim about attention"},
    "url": "https://arxiv.org/abs/2307.15217"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Can you add a citation?"
Agent: "Where and what URL?"
User: "On the sentence about bias in the intro of my calibration post — https://arxiv.org/abs/2305.18339"

## Input
Active post: None

## Output

```json
{
  "reasoning": "User gives both target and URL in the third turn. The 'in the intro of my calibration post' phrase scopes the snippet; target captures the sentence reference. URL captured verbatim.",
  "slots": {
    "target": {"snip": "the sentence about bias"},
    "url": "https://arxiv.org/abs/2305.18339"
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Cite https://old-link.com on the scaling claim in my RL post."
Agent: "Done — cited it."
User: "Wait — cite https://new-link.com instead."

## Input
Active post: RL

## Output

```json
{
  "reasoning": "Target carries over from the first turn ('the scaling claim'). Current turn retracts the prior URL with 'instead' — use the new URL, not the old one.",
  "slots": {
    "target": {"snip": "the scaling claim"},
    "url": "https://new-link.com"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Cite these two papers on my scaling hypothesis snippet: https://a.com and https://b.com"

## Input
Active post: None

## Output

```json
{
  "reasoning": "Two URLs in one utterance → concatenate with semicolon per rule 2. Target carries the snippet reference.",
  "slots": {
    "target": {"snip": "scaling hypothesis snippet"},
    "url": "https://a.com; https://b.com"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "I want to add a citation."
Agent: "What sentence or phrase?"
User: "The claim about compute scaling in my scaling laws post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Target arrives in the third turn; no URL supplied. Url stays null so the policy can web-search for a supporting source.",
  "slots": {
    "target": {"snip": "the claim about compute scaling"},
    "url": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "https://arxiv.org/abs/2305.18339 — cite this."

## Input
Active post: My Calibration Draft

## Output

```json
{
  "reasoning": "URL given without a named target. Target stays null — the policy uses the active snippet from context. URL captured verbatim.",
  "slots": {
    "target": null,
    "url": "https://arxiv.org/abs/2305.18339"
  }
}
```
</edge_case>''',
}


COMPOSE_PROMPT = {
    'instructions': (
        'The Compose Flow writes prose for a section from scratch, based on an outline, a list of '
        'process steps, or qualitative direction from the user. It operates on a named section of an '
        'existing post; for editing existing prose, Rework is used instead, and for bullet-level '
        'planning, Outline is used.\n\n'
        'Extract the target (`source`) — always a post, usually a section (or list of sections when '
        'the user names several) — and optionally a list of process-level `steps` the agent should '
        'follow, or qualitative `guidance` on how to write. Source is typically pre-filled from '
        'active_post. The most common entry point is the hand-off from an Outline Flow turn: the user '
        'reviews a bulleted outline and then signals they want prose ("full paragraphs", "turn this '
        'into prose", "flesh it out"). Treat those phrases as clear compose intent — fill `guidance` '
        'with the phrase so the policy proceeds without extra clarification.'
    ),
    'rules': (
        "1. `source` always carries `post`; fill `sec` when the user names a section. If the user "
        "names multiple sections in one utterance ('compose the MDPs, value functions, and policy "
        "gradients sections'), `sec` becomes a list — these are content anchors, not steps.\n"
        "2. `steps` is a process-level ChecklistSlot: discrete actions the compose policy should take "
        "('start with a hook', 'end with a takeaway', 'include a code sample'). Each item is "
        "`{name: <step>, description: ''}`. Do NOT use `steps` for content references — those belong "
        "in `source.sec`.\n"
        "3. `guidance` captures qualitative writing direction — tone, length, angle, audience, "
        "constraints ('casual tone', 'under 300 words', 'assume expert audience'). The hand-off "
        "phrase from outline → prose ('full paragraphs', 'flesh it out', 'turn this into prose') "
        "also fills `guidance` verbatim.\n"
        "4. Filler words can be stripped from `steps` names, but preserve load-bearing words that "
        "change meaning.\n"
        "5. When the utterance is fully terse ('write it') and no section, steps, or guidance is "
        "present, leave all elective slots null so the flow can clarify."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The target of the compose. Always references the `post` (and optionally '
        'section) being written. When the user names multiple sections, `sec` becomes a list.\n\n'
        '### steps (elective)\n\n'
        'Type: ChecklistSlot. An ordered list of process-level actions for the compose policy to '
        'follow. Each item is a dict `{name: <step>, description: \'\'}`. Fires on numbered or '
        'bulleted lists of actions (\'1) start with a hook, 2) use concrete examples, 3) end with a '
        'takeaway\'). Do NOT use for content-point references — those are sections on the post.\n\n'
        '### guidance (elective)\n\n'
        'Type: FreeTextSlot. Qualitative writing direction — tone, length, angle, audience, '
        'constraints. Also the natural place for the outline → prose hand-off phrase (\'full '
        'paragraphs\', \'flesh it out\'). Leave null when the user supplies only structural sub-points '
        'with no style guidance.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Draft the methods section of my regularization post in a casual tone, about 400 words."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Single section named → source fills post + sec. Guidance has both tone and length direction → fill verbatim. No process steps enumerated.",
  "slots": {
    "source": {"post": "regularization", "sec": "methods"},
    "steps": null,
    "guidance": "casual tone, about 400 words"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to draft something about prompt engineering."
Agent: "Great — here's a bulleted outline covering chain of thought, few-shot prompting, and system prompts. Look good?"
User: "Looks good, let's just move onto the next step to make it into full paragraphs."

## Input
Active post: prompt engineering

## Output

```json
{
  "reasoning": "Classic outline → prose hand-off. The prior turn shows a bulleted outline; the current turn signals compose intent with 'full paragraphs'. Source inherits from active_post. Guidance captures 'full paragraphs' so the policy proceeds without extra clarification.",
  "slots": {
    "source": {"post": "prompt engineering"},
    "steps": null,
    "guidance": "full paragraphs"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I need to keep writing my RL primer."
Agent: "Which section?"
User: "Write the methods section."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "Post inherits from active_post. Section named in current turn. No process list, no writing direction.",
  "slots": {
    "source": {"post": "RL primer", "sec": "methods"},
    "steps": null,
    "guidance": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compose the methods section: 1) start with the experiment setup, 2) walk through the three variants, 3) end with ablation results."

## Input
Active post: regularization

## Output

```json
{
  "reasoning": "Section named; numbered list of three process-level actions → fill `steps` (each is an action, not a sub-section). Post inherits from active_post.",
  "slots": {
    "source": {"post": "regularization", "sec": "methods"},
    "steps": [
      {"name": "start with the experiment setup", "description": ""},
      {"name": "walk through the three variants", "description": ""},
      {"name": "end with ablation results", "description": ""}
    ],
    "guidance": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Compose the introduction of my RL primer post — cover MDPs, value functions, and policy gradients."

## Input
Active post: None

## Output

```json
{
  "reasoning": "MDPs / value functions / policy gradients are content anchors (likely section names), NOT process steps. They go into `source.sec` as a list, not `steps`. The user is pointing the compose at multiple sub-sections of the introduction.",
  "slots": {
    "source": {"post": "RL primer", "sec": ["MDPs", "value functions", "policy gradients"]},
    "steps": null,
    "guidance": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Compose the methods section of my RL primer."
Agent: "What should it cover?"
User: "Actually, compose the results section instead — focus on benchmarks."

## Input
Active post: RL primer

## Output

```json
{
  "reasoning": "User retracts 'methods' with 'actually...instead' → section switches to 'results'. Post inherits from active_post. Qualitative direction arrives in same turn → guidance.",
  "slots": {
    "source": {"post": "RL primer", "sec": "results"},
    "steps": null,
    "guidance": "focus on benchmarks"
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Draft something about how LLMs handle context windows."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Topic with no existing post grounded. Source stays null so the flow can clarify whether to create a new post or search for an existing one — an empty source signals something is amiss and triggers re-routing.",
  "slots": {
    "source": null,
    "steps": null,
    "guidance": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Compose the intro, but first hook the reader with a counter-intuitive claim and keep it under 200 words."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Section named. 'Hook the reader with a counter-intuitive claim' is process-level → one step. 'Under 200 words' is qualitative → guidance. Both slots fire.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "intro"},
    "steps": [{"name": "hook the reader with a counter-intuitive claim", "description": ""}],
    "guidance": "under 200 words"
  }
}
```
</edge_case>''',
}


ADD_PROMPT = {
    'instructions': (
        'The Add Flow inserts new content into an existing post or section by drilling down to '
        'provide more details. This can include adding a sentence, paragraph, phrase, image, or '
        'sub-section — anchored to a specific section. In contrast, Compose writes a full section '
        'based on the outline, and Rework changes existing section content.\n\n'
        'Extract the target (`source`, which post + section) and the new content items: `points` '
        'for a list of notes going into a single section, `additions` for a dict mapping multiple '
        'sections to their additions, `image` for image additions, and `position` when the user '
        'specifies placement. Source typically inherits from active_post; at least one content slot '
        'should fire.'
    ),
    'rules': (
        "1. `source` always carries `post`; fill `sec` when the user names the target section. If "
        "the user distributes content across multiple sections in one utterance, prefer the "
        "`additions` dict and list all mentioned sections in `source.sec` as a list.\n"
        "2. Adding a wholly new top-level section to a post after the Compose phase is rare — "
        "sections should normally be added during the outline phase. When the user does ask for it, "
        "fill source and points as if inserting a new section.\n"
        "3. `points` is a ChecklistSlot — each item is a note or bulletpoint to insert into a single "
        "section. Each item's `name` is an ordinal ('one', 'two', 'three', 'four', ...) and "
        "`description` holds the actual content. Fill when all items target the same section.\n"
        "4. `additions` is a DictionarySlot keyed by section name: `{'Methods': 'add a comparison "
        "table', 'Conclusion': 'cite the recent paper'}`. Fill when the user maps items to "
        "DIFFERENT sections in one utterance.\n"
        "5. `image` fires on explicit image-add language. Image type comes from phrasing: 'diagram' "
        "→ diagram, 'hero image' → hero, 'photo'/'screenshot' → photo.\n"
        "6. `position` fills only when the user specifies placement numerically or relatively. "
        "'Right after the intro' → 1. 'At the start' / 'before everything' → 0. The `## Input` "
        "block lists the post's current sections so positional phrases like 'before X' or 'after X' "
        "can resolve. Leave null when unspecified."
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post and section to add content into. Always carries `post`; fill '
        '`sec` when the user names the target section (or list of sections when they distribute '
        'content across multiple). Inherits post from active_post on terse utterances.\n\n'
        '### points (elective)\n\n'
        'Type: ChecklistSlot. Ordered list of notes to add inside one section. Each item is '
        '`{name: <ordinal>, description: <content>}` — `name` counts up as \'one\', \'two\', '
        '\'three\', ..., and `description` carries the actual note text. Leave null when the user '
        'distributes content across multiple sections (use `additions` dict instead).\n\n'
        '### additions (elective)\n\n'
        'Type: DictionarySlot. Dict mapping section name → note content when the user adds items '
        'to MULTIPLE different sections in one utterance. Example: `{\'Methods\': \'add a comparison '
        'table\', \'Conclusion\': \'cite the recent paper\'}`. Leave null when all items target the '
        'same section.\n\n'
        '### image (elective)\n\n'
        'Type: ImageSlot. An image reference to insert. Fills when the user asks to add or insert '
        'an image, diagram, or screenshot. Image type comes from the user\'s word (\'diagram\' → '
        'diagram, \'hero image\' → hero, \'photo\'/\'screenshot\' → photo).\n\n'
        '### position (optional)\n\n'
        'Type: PositionSlot. 0-based index for where to insert the new content. \'Right after the '
        'intro\' → 1. \'At the start\' / \'before everything\' → 0. Leave null when the user does '
        'not specify placement.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "Add a note about validation tradeoffs to the Methods section of my regularization post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Single section named. Source fills post + sec. One note → points with a single item: name='one', description=the content.",
  "slots": {
    "source": {"post": "regularization", "sec": "Methods"},
    "points": [{"name": "one", "description": "validation tradeoffs"}],
    "additions": null,
    "image": null,
    "position": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Add three bulletpoints to the Conclusion: cite the recent paper, note the limitations, link to the code repo."

## Input
Active post: My ML Post

## Output

```json
{
  "reasoning": "Three items all targeting the Conclusion section. Names count up as ordinals; descriptions carry content. Source post inherits from active_post.",
  "slots": {
    "source": {"post": "My ML Post", "sec": "Conclusion"},
    "points": [
      {"name": "one", "description": "cite the recent paper"},
      {"name": "two", "description": "note the limitations"},
      {"name": "three", "description": "link to the code repo"}
    ],
    "additions": null,
    "image": null,
    "position": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to add a note about night markets to my Bangkok post."
Agent: "Where should it go?"
User: "Right after the intro."

## Input
Active post: None
Sections (in order): intro, transportation, street food, temples

## Output

```json
{
  "reasoning": "Note from first turn. Current turn anchors placement 'right after the intro' → position=1 (the slot after index 0). Source post named in first turn; no section explicitly named, so sec stays null.",
  "slots": {
    "source": {"post": "Bangkok"},
    "points": [{"name": "one", "description": "night markets"}],
    "additions": null,
    "image": null,
    "position": 1
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Add a hero image to my transformer post."
Agent: "Any description?"
User: "A diagram of the self-attention mechanism."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Image fills with type='hero' from the first turn, description added from the third. Source named in first turn.",
  "slots": {
    "source": {"post": "transformer"},
    "points": null,
    "additions": null,
    "image": {"image_type": "hero", "src": null, "alt": "self-attention mechanism", "position": null},
    "position": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Add a note to Methods saying the comparison table is needed, and to Conclusion saying to cite the follow-up paper."

## Input
Active post: My ML Post
Sections (in order): Intro, Methods, Results, Conclusion

## Output

```json
{
  "reasoning": "Two additions targeting different sections → `additions` dict. Source lists both sections per rule 1. `points` stays null (use additions when split across sections).",
  "slots": {
    "source": {"post": "My ML Post", "sec": ["Methods", "Conclusion"]},
    "points": null,
    "additions": {"Methods": "comparison table is needed", "Conclusion": "cite the follow-up paper"},
    "image": null,
    "position": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Add a disclaimer note after the case studies of my ethics post."

## Input
Active post: None
Sections (in order): intro, frameworks, case studies, tradeoffs

## Output

```json
{
  "reasoning": "'After the case studies' resolves via the Sections list — case studies is index 2, so 'after' inserts at position 3. The note is a disclaimer; one item in points.",
  "slots": {
    "source": {"post": "ethics"},
    "points": [{"name": "one", "description": "disclaimer"}],
    "additions": null,
    "image": null,
    "position": 3
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Add to my RL post."

## Input
Active post: None

## Output

```json
{
  "reasoning": "Source named but no content specified. All content slots stay null — the agent clarifies what to add.",
  "slots": {
    "source": {"post": "RL"},
    "points": null,
    "additions": null,
    "image": null,
    "position": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Add a hero image to my transformer post."
Agent: "What kind?"
User: "Actually scratch the image — add a paragraph about self-attention instead."

## Input
Active post: None

## Output

```json
{
  "reasoning": "User retracts the image request with 'scratch that...instead' — ignore the image slot from prior turn. Current turn adds a paragraph as a point. Source carried from the first turn.",
  "slots": {
    "source": {"post": "transformer"},
    "points": [{"name": "one", "description": "a paragraph about self-attention"}],
    "additions": null,
    "image": null,
    "position": null
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'outline': OUTLINE_PROMPT,
    'refine': REFINE_PROMPT,
    'create': CREATE_PROMPT,
    'brainstorm': BRAINSTORM_PROMPT,
    'cite': CITE_PROMPT,
    'compose': COMPOSE_PROMPT,
    'add': ADD_PROMPT,
}
