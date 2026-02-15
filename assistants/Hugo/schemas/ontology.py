from enum import Enum


class Intent(str, Enum):
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'
    RESEARCH = 'Research'     # browse topics, search previous posts
    DRAFT = 'Draft'           # outline generation, content expansion
    REVISE = 'Revise'         # deep revision, formatting, style refinement
    PUBLISH = 'Publish'       # publish or schedule to blog, social media


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


DACT_CATALOG = {
    'chat':     {'hex': '0', 'pos': 'noun'},
    'search':   {'hex': '1', 'pos': 'verb'},
    'outline':  {'hex': '2', 'pos': 'verb'},
    'compose':  {'hex': '3', 'pos': 'verb'},
    'share':    {'hex': '4', 'pos': 'verb'},
    'insert':   {'hex': '5', 'pos': 'verb'},
    'update':   {'hex': '6', 'pos': 'verb'},
    'delete':   {'hex': '7', 'pos': 'verb'},
    'user':     {'hex': '8', 'pos': 'adj'},
    'agent':    {'hex': '9', 'pos': 'adj'},
    'post':     {'hex': 'A', 'pos': 'noun'},
    'section':  {'hex': 'B', 'pos': 'noun'},
    'platform': {'hex': 'C', 'pos': 'noun'},
    'rough':    {'hex': 'D', 'pos': 'adj'},
    'approve':  {'hex': 'E', 'pos': 'adj'},
    'reject':   {'hex': 'F', 'pos': 'adj'},
}

FLOW_CATALOG = {

    # ── Research (8 flows) ───────────────────────────────────────────

    'browse': {
        'dax': '{012}',
        'intent': Intent.RESEARCH,
        'description': 'Browse available topic ideas',
        'slots': {
            'category': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['search', 'brainstorm'],
        'policy_path': 'policies.research_policies.browse',
    },
    'search': {
        'dax': '{01A}',
        'intent': Intent.RESEARCH,
        'description': 'Search previous blog posts by keyword',
        'slots': {
            'query': {'type': 'FreeTextSlot', 'priority': 'required'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'view'],
        'policy_path': 'policies.research_policies.search',
    },
    'view': {
        'dax': '{1AD}',
        'intent': Intent.RESEARCH,
        'description': 'View a specific post or draft in detail',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['search', 'check'],
        'policy_path': 'policies.research_policies.view',
    },
    'survey': {
        'dax': '{01C}',
        'intent': Intent.RESEARCH,
        'description': 'View configured publishing platforms',
        'slots': {},
        'output': 'list',
        'edge_flows': ['syndicate', 'schedule'],
        'policy_path': 'policies.research_policies.survey',
    },
    'check': {
        'dax': '{0AD}',
        'intent': Intent.RESEARCH,
        'description': 'Check current draft posts and their status',
        'slots': {},
        'output': 'list',
        'edge_flows': ['view', 'rework'],
        'policy_path': 'policies.research_policies.check',
    },
    'explain': {
        'dax': '{19A}',
        'intent': Intent.RESEARCH,
        'description': 'Hugo explains a writing or blogging concept',
        'slots': {
            'concept': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['chat', 'browse'],
        'policy_path': 'policies.research_policies.explain',
    },
    'find': {
        'dax': '{1AB}',
        'intent': Intent.RESEARCH,
        'description': 'Find related content across existing posts',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['search', 'audit'],
        'policy_path': 'policies.research_policies.find',
    },
    'compare': {
        'dax': '{18A}',
        'intent': Intent.RESEARCH,
        'description': 'Compare style or structure across posts',
        'slots': {
            'post_ids': {'type': 'GroupSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['find', 'audit'],
        'policy_path': 'policies.research_policies.compare',
    },

    # ── Draft (8 flows) ─────────────────────────────────────────────

    'outline': {
        'dax': '{02A}',
        'intent': Intent.DRAFT,
        'description': 'Generate outline options for a topic',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
            'depth': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['select', 'brainstorm'],
        'policy_path': 'policies.draft_policies.outline',
    },
    'select': {
        'dax': '{2AE}',
        'intent': Intent.DRAFT,
        'description': 'Select and approve an outline to work with',
        'slots': {
            'outline_id': {'type': 'BaseSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['outline', 'refine'],
        'policy_path': 'policies.draft_policies.select',
    },
    'refine': {
        'dax': '{02B}',
        'intent': Intent.DRAFT,
        'description': 'Refine a specific section of the outline',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
            'feedback': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['outline', 'expand'],
        'policy_path': 'policies.draft_policies.refine',
    },
    'expand': {
        'dax': '{03A}',
        'intent': Intent.DRAFT,
        'description': 'Expand outline into full prose',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'section': {'type': 'SectionSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['write', 'rework'],
        'policy_path': 'policies.draft_policies.expand',
    },
    'write': {
        'dax': '{03B}',
        'intent': Intent.DRAFT,
        'description': 'Write or rewrite a specific section',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
            'instructions': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['expand', 'polish'],
        'policy_path': 'policies.draft_policies.write',
    },
    'add': {
        'dax': '{05B}',
        'intent': Intent.DRAFT,
        'description': 'Add a new section to the post',
        'slots': {
            'title': {'type': 'FreeTextSlot', 'priority': 'required'},
            'position': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['write', 'refine'],
        'policy_path': 'policies.draft_policies.add',
    },
    'create': {
        'dax': '{05A}',
        'intent': Intent.DRAFT,
        'description': 'Start a new post from scratch',
        'slots': {
            'title': {'type': 'FreeTextSlot', 'priority': 'required'},
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'form',
        'panel': 'top',
        'edge_flows': ['outline', 'blueprint'],
        'policy_path': 'policies.draft_policies.create',
    },
    'brainstorm': {
        'dax': '{29A}',
        'intent': Intent.DRAFT,
        'description': 'Hugo brainstorms ideas for a topic',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'outline'],
        'policy_path': 'policies.draft_policies.brainstorm',
    },

    # ── Revise (8 flows) ────────────────────────────────────────────

    'rework': {
        'dax': '{03D}',
        'intent': Intent.REVISE,
        'description': 'Major revision of draft content based on feedback',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'section': {'type': 'SectionSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['expand', 'polish'],
        'policy_path': 'policies.revise_policies.rework',
    },
    'polish': {
        'dax': '{3BD}',
        'intent': Intent.REVISE,
        'description': 'Polish and refine a specific section',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
            'style_notes': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['rework', 'write'],
        'policy_path': 'policies.revise_policies.polish',
    },
    'tone': {
        'dax': '{38A}',
        'intent': Intent.REVISE,
        'description': 'Adjust tone or style across the post',
        'slots': {
            'tone': {'type': 'CategorySlot', 'priority': 'elective'},
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['rework', 'audit'],
        'policy_path': 'policies.revise_policies.tone',
    },
    'audit': {
        'dax': '{13A}',
        'intent': Intent.REVISE,
        'description': "Check consistency with the user's previous posts",
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'reference_count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['tone', 'compare'],
        'policy_path': 'policies.revise_policies.audit',
    },
    'format': {
        'dax': '{3AD}',
        'intent': Intent.REVISE,
        'description': 'Format the post for publication',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'format': {'type': 'CategorySlot', 'priority': 'elective'},
        },
        'output': 'card',
        'edge_flows': ['rework', 'release'],
        'policy_path': 'policies.revise_policies.format',
    },
    'accept': {
        'dax': '{0AE}',
        'intent': Intent.REVISE,
        'description': 'Accept and finalize a revision',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'comment': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['amend', 'format'],
        'policy_path': 'policies.revise_policies.accept',
    },
    'amend': {
        'dax': '{0AF}',
        'intent': Intent.REVISE,
        'description': 'Request further changes to a revision',
        'slots': {
            'feedback': {'type': 'FreeTextSlot', 'priority': 'required'},
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['accept', 'rework'],
        'policy_path': 'policies.revise_policies.amend',
    },
    'diff': {
        'dax': '{0BD}',
        'intent': Intent.REVISE,
        'description': 'Compare two versions of a section side by side',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['polish', 'view'],
        'policy_path': 'policies.revise_policies.diff',
    },

    # ── Publish (6 flows) ───────────────────────────────────────────

    'release': {
        'dax': '{04A}',
        'intent': Intent.PUBLISH,
        'description': 'Publish the post to the primary blog',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['syndicate', 'confirm'],
        'policy_path': 'policies.publish_policies.release',
    },
    'syndicate': {
        'dax': '{04C}',
        'intent': Intent.PUBLISH,
        'description': 'Cross-post to a specific platform',
        'slots': {
            'platform': {'type': 'PlatformSlot', 'priority': 'required'},
            'post_id': {'type': 'PostSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['release', 'schedule'],
        'policy_path': 'policies.publish_policies.syndicate',
    },
    'schedule': {
        'dax': '{4AC}',
        'intent': Intent.PUBLISH,
        'description': 'Schedule a post for future publication',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'platform': {'type': 'PlatformSlot', 'priority': 'required'},
            'datetime': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['release', 'syndicate'],
        'policy_path': 'policies.publish_policies.schedule',
    },
    'preview': {
        'dax': '{4AD}',
        'intent': Intent.PUBLISH,
        'description': 'Preview how the post will look when published',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'platform': {'type': 'PlatformSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['format', 'release'],
        'policy_path': 'policies.publish_policies.preview',
    },
    'confirm': {
        'dax': '{04E}',
        'intent': Intent.PUBLISH,
        'description': 'Confirm publication',
        'slots': {},
        'output': 'confirmation',
        'panel': 'top',
        'edge_flows': ['release', 'cancel'],
        'policy_path': 'policies.publish_policies.confirm',
    },
    'cancel': {
        'dax': '{04F}',
        'intent': Intent.PUBLISH,
        'description': 'Cancel or unpublish a post',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'reason': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'confirmation',
        'edge_flows': ['confirm', 'release'],
        'policy_path': 'policies.publish_policies.cancel',
    },

    # ── Converse (7 flows) ──────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': Intent.CONVERSE,
        'description': 'Open-ended conversation about writing and blogging',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['explain', 'feedback'],
        'policy_path': 'policies.converse_policies.chat',
    },
    'next': {
        'dax': '{019}',
        'intent': Intent.CONVERSE,
        'description': 'Ask Hugo what to do next',
        'slots': {},
        'output': 'card',
        'edge_flows': ['check', 'brainstorm'],
        'policy_path': 'policies.converse_policies.next',
    },
    'feedback': {
        'dax': '{029}',
        'intent': Intent.CONVERSE,
        'description': "Give feedback on Hugo's work or the drafting process",
        'slots': {},
        'output': 'toast',
        'edge_flows': ['chat', 'style'],
        'policy_path': 'policies.converse_policies.feedback',
    },
    'preference': {
        'dax': '{08A}',
        'intent': Intent.CONVERSE,
        'description': 'Set a writing preference',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'required'},
            'value': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['style', 'tone'],
        'policy_path': 'policies.converse_policies.preference',
    },
    'style': {
        'dax': '{08B}',
        'intent': Intent.CONVERSE,
        'description': 'Tell Hugo about preferred writing style',
        'slots': {
            'preference': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['preference', 'feedback'],
        'policy_path': 'policies.converse_policies.style',
    },
    'endorse': {
        'dax': '{09E}',
        'intent': Intent.CONVERSE,
        'description': "Approve Hugo's unsolicited suggestion",
        'slots': {
            'action': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['accept', 'next'],
        'policy_path': 'policies.converse_policies.endorse',
    },
    'dismiss': {
        'dax': '{09F}',
        'intent': Intent.CONVERSE,
        'description': "Dismiss Hugo's unsolicited suggestion",
        'slots': {},
        'output': 'toast',
        'edge_flows': ['amend', 'feedback'],
        'policy_path': 'policies.converse_policies.dismiss',
    },

    # ── Plan (5 flows) ──────────────────────────────────────────────

    'blueprint': {
        'dax': '{25A}',
        'intent': Intent.PLAN,
        'description': 'Plan the full post creation workflow',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['create', 'outline'],
        'policy_path': 'policies.plan_policies.blueprint',
    },
    'triage': {
        'dax': '{23A}',
        'intent': Intent.PLAN,
        'description': 'Plan a revision sequence',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'scope': {'type': 'CategorySlot', 'priority': 'elective'},
        },
        'output': 'list',
        'edge_flows': ['rework', 'format'],
        'policy_path': 'policies.plan_policies.triage',
    },
    'calendar': {
        'dax': '{24A}',
        'intent': Intent.PLAN,
        'description': 'Plan a content calendar',
        'slots': {
            'timeframe': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['schedule', 'browse'],
        'policy_path': 'policies.plan_policies.calendar',
    },
    'scope': {
        'dax': '{12A}',
        'intent': Intent.PLAN,
        'description': 'Plan topic research before writing',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'search'],
        'policy_path': 'policies.plan_policies.scope',
    },
    'digest': {
        'dax': '{25B}',
        'intent': Intent.PLAN,
        'description': 'Plan a multi-part blog series',
        'slots': {
            'theme': {'type': 'FreeTextSlot', 'priority': 'required'},
            'part_count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['blueprint', 'create'],
        'policy_path': 'policies.plan_policies.digest',
    },

    # ── Internal (6 flows) ──────────────────────────────────────────

    'recap': {
        'dax': '{018}',
        'intent': Intent.INTERNAL,
        'description': 'Pull a snippet from current conversation (scratchpad)',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recall', 'remember'],
        'policy_path': 'policies.internal_policies.recap',
    },
    'remember': {
        'dax': '{19B}',
        'intent': Intent.INTERNAL,
        'description': 'Retrieve relevant lessons from memory',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'scope': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recall', 'recap'],
        'policy_path': 'policies.internal_policies.remember',
    },
    'recall': {
        'dax': '{289}',
        'intent': Intent.INTERNAL,
        'description': 'Retrieve stored user preferences',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recap', 'remember'],
        'policy_path': 'policies.internal_policies.recall',
    },
    'study': {
        'dax': '{1AC}',
        'intent': Intent.INTERNAL,
        'description': 'Internally read a previous post for style reference',
        'slots': {
            'post_id': {'type': 'PostSlot', 'priority': 'required'},
            'scope': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['search', 'explain'],
        'policy_path': 'policies.internal_policies.study',
    },
    'tidy': {
        'dax': '{3AB}',
        'intent': Intent.INTERNAL,
        'description': 'Auto-format post sections',
        'slots': {},
        'output': '(internal)',
        'edge_flows': ['format', 'rework'],
        'policy_path': 'policies.internal_policies.tidy',
    },
    'suggest': {
        'dax': '{29B}',
        'intent': Intent.INTERNAL,
        'description': 'Auto-suggest topic or outline improvements',
        'slots': {},
        'output': '(internal)',
        'edge_flows': ['brainstorm', 'outline'],
        'policy_path': 'policies.internal_policies.suggest',
    },
}

KEY_ENTITIES = ['post', 'section', 'draft']
