from enum import Enum

INTENTS = [
    'Converse',
    'Research',     # find, browse, summarize, compare
    'Draft',        # brainstorm, outline, compose, refine
    'Revise',       # rework, write, audit, propose
    'Publish',      # release, schedule, cite
    'Plan',
    'Clarify',
]


class FlowLifecycle(str, Enum):
    PENDING = 'Pending'
    ACTIVE = 'Active'
    COMPLETED = 'Completed'
    INVALID = 'Invalid'


class AmbiguityLevel(str, Enum):
    GENERAL = 'general'
    PARTIAL = 'partial'
    SPECIFIC = 'specific'
    CONFIRMATION = 'confirmation'


DACT_ONTOLOGY = {
    'chat':     {'hex': '0', 'pos': 'noun'},
    'find':     {'hex': '1', 'pos': 'verb'},
    'outline':  {'hex': '2', 'pos': 'verb'},
    'write':    {'hex': '3', 'pos': 'verb'},
    'share':    {'hex': '4', 'pos': 'verb'},
    'insert':   {'hex': '5', 'pos': 'verb'},
    'update':   {'hex': '6', 'pos': 'verb'},
    'delete':   {'hex': '7', 'pos': 'verb'},
    'user':     {'hex': '8', 'pos': 'adj'},
    'agent':    {'hex': '9', 'pos': 'adj'},
    'post':     {'hex': 'A', 'pos': 'noun'},
    'section':  {'hex': 'B', 'pos': 'noun'},
    'channel':  {'hex': 'C', 'pos': 'noun'},
    'rough':    {'hex': 'D', 'pos': 'adj'},
    'approve':  {'hex': 'E', 'pos': 'adj'},
    'reject':   {'hex': 'F', 'pos': 'adj'},
}


FLOW_ONTOLOGY = {

    # ── Research (4 flows) ─────────────────────────────────

    'find': {
        'dax': '{001}',
        'intent': 'Research',
        'description': 'Search previous posts, drafts or notes by keyword or topic — returns matching titles, excerpts, and publication dates sorted by relevance',
        'output': 'list',
        'edge_flows': ['audit', 'summarize'],
        'policy_path': 'policies.research.find',
    },
    'inspect': {
        'dax': '{1AD}',
        'intent': 'Research',
        'description': 'Report one or more metrics — word count, section count, reading time, image count, post size (MB), or post metadata - category tags, has_featured_image, publication date, last edited date, scheduled date, channels, status',
        'output': 'card',
        'edge_flows': ['summarize'],
        'policy_path': 'policies.research.inspect',
    },
    'summarize': {
        'dax': '{19A}',
        'intent': 'Research',
        'description': 'Synthesize a post into a short paragraph capturing the core argument, target audience, and main takeaways — useful for excerpts, SEO descriptions, or pre-reads before writing a follow-up',
        'output': 'card',
        'edge_flows': ['find', 'compare'],
        'policy_path': 'policies.research.summarize',
    },
    'compare': {
        'dax': '{18A}',
        'intent': 'Research',
        'description': 'Compare style or structure across two or more posts — sentence length, paragraph density, heading patterns, vocabulary, tonal consistency — or diff two versions of a section side by side to see additions, deletions, and modifications',
        'output': 'compare',
        'edge_flows': ['find', 'audit'],
        'policy_path': 'policies.research.compare',
    },

    # ── Draft (4 flows) ─────────────────────────────────────────────

    'outline': {
        'dax': '{002}',
        'intent': 'Draft',
        'description': 'Generate an outline — section headings, key bullet points, estimated word counts, and suggested reading order',
        'output': 'list',
        'edge_flows': ['compose', 'refine', 'brainstorm'],
        'policy_path': 'policies.draft.outline',
    },
    'compose': {
        'dax': '{3AD}',
        'intent': 'Draft',
        'description': 'Draft a full post from its outline — converts outline bullets into prose paragraphs across the post (still rough). Input is an outline, output is a post. For section-level edits use write, for whole-post revision use rework',
        'output': 'card',
        'edge_flows': ['outline', 'refine'],
        'policy_path': 'policies.draft.compose',
    },
    'refine': {
        'dax': '{02B}',
        'intent': 'Draft',
        'description': 'Shape the outline into a clean, properly-formatted draft — adjust headings, reorder or add/remove bullet points and subsections, incorporate feedback, and normalize structural formatting',
        'output': 'card',
        'edge_flows': ['outline', 'write'],
        'policy_path': 'policies.draft.refine',
    },
    'brainstorm': {
        'dax': '{39D}',
        'intent': 'Draft',
        'description': 'Come up with new ideas or angles for a given topic, word, or phrase. This may include hooks, opening lines, synonyms, or new perspectives the user can choose from',
        'output': 'list',
        'edge_flows': ['find', 'outline'],
        'policy_path': 'policies.draft.brainstorm',
    },

    # ── Revise (4 flows) ─────────────────────────────

    'rework': {
        'dax': '{006}',
        'intent': 'Revise',
        'description': 'Major revision of draft content — restructures arguments, replaces weak sections, addresses reviewer comments. Also the destructive form: removing a section, draft, or note, previewing the change for the user before committing. Scope spans a section up to the whole post. For smaller changes, use write',
        'output': 'card',
        'edge_flows': ['write', 'refine', 'propose'],
        'policy_path': 'policies.revise.rework',
    },
    'write': {
        'dax': '{003}',
        'intent': 'Revise',
        'description': 'Sentence-level editing of a paragraph, sentence, or phrase — improves word choice, tightens sentences, fixes transitions, smooths flow. Also simplifies — reducing complexity and redundancy, warning the user before cutting content. Scoped within a single paragraph or image, not the whole post',
        'output': 'card',
        'edge_flows': ['rework', 'refine'],
        'policy_path': 'policies.revise.write',
    },
    'audit': {
        'dax': '{13A}',
        'intent': 'Revise',
        'description': "Check that the post is written in the user's voice rather than sounding like AI — compares voice, terminology, formatting, and stylistic patterns against previous posts — and adjusts tone or register (formal, casual, technical, academic, witty, natural) across the post",
        'output': 'card',
        'edge_flows': ['compare', 'rework'],
        'policy_path': 'policies.revise.audit',
    },
    'propose': {
        'dax': '{39B}',
        'intent': 'Revise',
        'description': 'Generate 2-3 targeted alternatives to fill a placeholder gap (`<fill in here>`, TODO, or blank slot) in existing content, presented inline for the user to pick — like brainstorm, but scoped to a specific slot in a draft',
        'output': 'selection',
        'edge_flows': ['refine', 'rework', 'brainstorm'],
        'policy_path': 'policies.revise.propose',
    },

    # ── Publish (3 flows) ──────────────────────────────────────────

    'release': {
        'dax': '{004}',
        'intent': 'Publish',
        'description': 'Publish the post to the primary blog and optionally cross-post (syndicate) to secondary channels (Medium, Dev.to, LinkedIn, Substack), adapting formatting per target',
        'output': 'toast',
        'edge_flows': ['schedule', 'cite'],
        'policy_path': 'policies.publish.release',
    },
    'schedule': {
        'dax': '{4AC}',
        'intent': 'Publish',
        'description': 'Schedule a post for future publication — sets a specific date and time for automatic publishing on a given channel',
        'output': 'toast',
        'edge_flows': ['release', 'cite'],
        'policy_path': 'policies.publish.schedule',
    },
    'cite': {
        'dax': '{15B}',
        'intent': 'Publish',
        'description': 'Add a citation to a note — if a URL is provided, attach it directly; if only a note is provided, search the web for a supporting source and propose it for user confirmation',
        'output': 'card',
        'edge_flows': ['release', 'rework'],
        'policy_path': 'policies.publish.cite',
    },

    # ── Converse (1 flow) ──────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': 'Converse',
        'description': 'Open-ended conversation — general Q&A about writing craft, blogging strategy, SEO, audience engagement; proactive suggestions for what to do next; and quick reference lookups (definitions, synonyms, antonyms). Anything not tied to a specific post action',
        'output': 'card',
        'edge_flows': ['brainstorm', 'find'],
        'policy_path': 'policies.converse.chat',
    }
}

KEY_ENTITIES = ['post', 'section', 'snippet', 'channel']