from enum import Enum

class Intent(str, Enum):
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'
    EXPLORE = 'Explore'       # browse specs, look up components
    PROVIDE = 'Provide'       # give project info, intents, entities
    DESIGN = 'Design'         # iterate on dact grammar and flows
    DELIVER = 'Deliver'       # review final config, export files


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
    'browse':   {'hex': '1', 'pos': 'verb'},
    'describe': {'hex': '2', 'pos': 'verb'},
    'iterate':  {'hex': '3', 'pos': 'verb'},
    'export':   {'hex': '4', 'pos': 'verb'},
    'insert':   {'hex': '5', 'pos': 'verb'},
    'update':   {'hex': '6', 'pos': 'verb'},
    'delete':   {'hex': '7', 'pos': 'verb'},
    'user':     {'hex': '8', 'pos': 'adj'},
    'agent':    {'hex': '9', 'pos': 'adj'},
    'config':   {'hex': 'A', 'pos': 'noun'},
    'lesson':   {'hex': 'B', 'pos': 'noun'},
    'spec':     {'hex': 'C', 'pos': 'noun'},
    'draft':    {'hex': 'D', 'pos': 'adj'},
    'accept':   {'hex': 'E', 'pos': 'adj'},
    'reject':   {'hex': 'F', 'pos': 'adj'},
}

FLOW_CATALOG = {
    'status': {
        'dax': '{01A}',
        'intent': Intent.EXPLORE,
        'description': 'View current state of the config being built',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['summarize', 'inspect'],
        'policy_path': 'policies.explore_policies.status',
    },
    'review_lessons': {
        'dax': '{01B}',
        'intent': Intent.EXPLORE,
        'description': 'Browse stored lessons and patterns',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['recall', 'lookup'],
        'policy_path': 'policies.explore_policies.review_lessons',
    },
    'lookup': {
        'dax': '{01C}',
        'intent': Intent.EXPLORE,
        'description': 'Look up a specific spec file or section',
        'slots': {
            'spec_name': {'type': 'SpecSlot', 'priority': 'required'},
            'section': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['explain', 'read_spec'],
        'policy_path': 'policies.explore_policies.lookup',
    },
    'recommend': {
        'dax': '{18C}',
        'intent': Intent.EXPLORE,
        'description': 'Find specs relevant to the user\'s target domain',
        'slots': {
            'domain': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['lookup', 'research'],
        'policy_path': 'policies.explore_policies.recommend',
    },
    'summarize': {
        'dax': '{19A}',
        'intent': Intent.EXPLORE,
        'description': 'Agent summarizes overall build progress',
        'slots': {},
        'output': 'card',
        'edge_flows': ['status', 'inspect'],
        'policy_path': 'policies.explore_policies.summarize',
    },
    'explain': {
        'dax': '{19C}',
        'intent': Intent.EXPLORE,
        'description': 'Agent explains an architecture concept',
        'slots': {
            'concept': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['lookup', 'chat'],
        'policy_path': 'policies.explore_policies.explain',
    },
    'inspect': {
        'dax': '{1AD}',
        'intent': Intent.EXPLORE,
        'description': 'Inspect a draft config section in detail',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
            'detail_level': {
                'type': 'CategorySlot', 'priority': 'elective',
            },
        },
        'output': 'card',
        'edge_flows': ['status', 'compare'],
        'policy_path': 'policies.explore_policies.inspect',
    },
    'compare': {
        'dax': '{1CD}',
        'intent': Intent.EXPLORE,
        'description': 'Compare draft config section against spec requirements',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['validate', 'inspect'],
        'policy_path': 'policies.explore_policies.compare',
    },

    # ── Provide (8 flows) ─────────────────────────────────────────────

    'scope': {
        'dax': '{02A}',
        'intent': Intent.PROVIDE,
        'description': 'Define assistant scope — name, task, boundaries',
        'slots': {
            'name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'task': {'type': 'FreeTextSlot', 'priority': 'required'},
            'boundaries': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'form',
        'panel': 'top',
        'edge_flows': ['persona', 'entity'],
        'policy_path': 'policies.provide_policies.scope',
    },
    'teach': {
        'dax': '{02B}',
        'intent': Intent.PROVIDE,
        'description': 'Share a learning or pattern for Kalli to remember',
        'slots': {
            'pattern': {'type': 'FreeTextSlot', 'priority': 'required'},
            'context': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['log', 'feedback'],
        'policy_path': 'policies.provide_policies.teach',
    },
    'intent': {
        'dax': '{05A}',
        'intent': Intent.PROVIDE,
        'description': 'Provide a domain intent definition',
        'slots': {
            'intent_name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'description': {'type': 'FreeTextSlot', 'priority': 'required'},
            'abstract_slot': {
                'type': 'CategorySlot', 'priority': 'elective',
            },
        },
        'output': 'form',
        'edge_flows': ['entity', 'revise'],
        'policy_path': 'policies.provide_policies.intent',
    },
    'log': {
        'dax': '{05B}',
        'intent': Intent.PROVIDE,
        'description': 'Log a new lesson or convention',
        'slots': {
            'content': {'type': 'FreeTextSlot', 'priority': 'required'},
            'category': {
                'type': 'CategorySlot', 'priority': 'elective',
            },
        },
        'output': 'toast',
        'edge_flows': ['teach', 'style'],
        'policy_path': 'policies.provide_policies.log',
    },
    'revise': {
        'dax': '{06A}',
        'intent': Intent.PROVIDE,
        'description': 'Update a previously defined config section',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
            'field': {'type': 'FreeTextSlot', 'priority': 'required'},
            'value': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['remove', 'refine'],
        'policy_path': 'policies.provide_policies.revise',
    },
    'remove': {
        'dax': '{07A}',
        'intent': Intent.PROVIDE,
        'description': 'Remove a config section or entry',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
        },
        'output': 'confirmation',
        'panel': 'top',
        'edge_flows': ['revise', 'decline'],
        'policy_path': 'policies.provide_policies.remove',
    },
    'persona': {
        'dax': '{28A}',
        'intent': Intent.PROVIDE,
        'description': 'Define persona preferences — tone, name, style, colors',
        'slots': {
            'tone': {'type': 'CategorySlot', 'priority': 'elective'},
            'name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'response_style': {
                'type': 'CategorySlot', 'priority': 'elective',
            },
            'colors': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'form',
        'edge_flows': ['scope', 'entity'],
        'policy_path': 'policies.provide_policies.persona',
    },
    'entity': {
        'dax': '{2AC}',
        'intent': Intent.PROVIDE,
        'description': 'Define key entities grounded in domain concepts',
        'slots': {
            'entities': {'type': 'GroupSlot', 'priority': 'required'},
        },
        'output': 'form',
        'edge_flows': ['intent', 'scope'],
        'policy_path': 'policies.provide_policies.entity',
    },

    # ── Design (8 flows) ──────────────────────────────────────────────

    'propose': {
        'dax': '{03A}',
        'intent': Intent.DESIGN,
        'description': 'Review proposed core dacts for the domain',
        'slots': {},
        'output': 'list',
        'edge_flows': ['compose', 'suggest_flow'],
        'policy_path': 'policies.design_policies.propose',
    },
    'compose': {
        'dax': '{03C}',
        'intent': Intent.DESIGN,
        'description': 'Review composed flows generated from dact grammar',
        'slots': {
            'intent_filter': {
                'type': 'IntentSlot', 'priority': 'optional',
            },
        },
        'output': 'list',
        'edge_flows': ['propose', 'validate'],
        'policy_path': 'policies.design_policies.compose',
    },
    'revise_flow': {
        'dax': '{03D}',
        'intent': Intent.DESIGN,
        'description': 'Revise an in-progress flow design',
        'slots': {
            'flow_name': {'type': 'FlowSlot', 'priority': 'required'},
            'field': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['refine', 'compose'],
        'policy_path': 'policies.design_policies.revise_flow',
    },
    'approve': {
        'dax': '{0AE}',
        'intent': Intent.DESIGN,
        'description': 'Approve a proposed flow or dact',
        'slots': {
            'flow_name': {'type': 'FlowSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['endorse', 'decline'],
        'policy_path': 'policies.design_policies.approve',
    },
    'decline': {
        'dax': '{0AF}',
        'intent': Intent.DESIGN,
        'description': 'Reject a proposed flow or dact with reason',
        'slots': {
            'flow_name': {'type': 'FlowSlot', 'priority': 'required'},
            'reason': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['dismiss', 'approve'],
        'policy_path': 'policies.design_policies.decline',
    },
    'suggest_flow': {
        'dax': '{39A}',
        'intent': Intent.DESIGN,
        'description': 'Agent suggests new flows; user reviews',
        'slots': {
            'intent_hint': {
                'type': 'IntentSlot', 'priority': 'optional',
            },
        },
        'output': 'card',
        'edge_flows': ['propose', 'compose'],
        'policy_path': 'policies.design_policies.suggest_flow',
    },
    'refine': {
        'dax': '{3AD}',
        'intent': Intent.DESIGN,
        'description': 'Refine a flow\'s slot signature or output type',
        'slots': {
            'flow_name': {'type': 'FlowSlot', 'priority': 'required'},
            'slot_name': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'change': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['revise_flow', 'validate'],
        'policy_path': 'policies.design_policies.refine',
    },
    'validate': {
        'dax': '{3AC}',
        'intent': Intent.DESIGN,
        'description': 'Validate current flow catalog against spec rules',
        'slots': {},
        'output': 'list',
        'edge_flows': ['compose', 'compare'],
        'policy_path': 'policies.design_policies.validate',
    },

    # ── Deliver (6 flows) ─────────────────────────────────────────────

    'generate': {
        'dax': '{04A}',
        'intent': Intent.DELIVER,
        'description': 'Generate the final domain config files',
        'slots': {
            'format': {'type': 'CategorySlot', 'priority': 'elective'},
        },
        'output': 'list',
        'edge_flows': ['ontology', 'preview'],
        'policy_path': 'policies.deliver_policies.generate',
    },
    'confirm_export': {
        'dax': '{04E}',
        'intent': Intent.DELIVER,
        'description': 'Confirm and execute the file export',
        'slots': {},
        'output': 'confirmation',
        'edge_flows': ['generate', 'package'],
        'policy_path': 'policies.deliver_policies.confirm_export',
    },
    'preview': {
        'dax': '{4AD}',
        'intent': Intent.DELIVER,
        'description': 'Preview generated output before committing',
        'slots': {
            'file_type': {
                'type': 'CategorySlot', 'priority': 'elective',
            },
        },
        'output': 'card',
        'edge_flows': ['generate', 'inspect'],
        'policy_path': 'policies.deliver_policies.preview',
    },
    'ontology': {
        'dax': '{4AC}',
        'intent': Intent.DELIVER,
        'description': 'Generate ontology.py specifically',
        'slots': {},
        'output': 'card',
        'edge_flows': ['generate', 'preview'],
        'policy_path': 'policies.deliver_policies.ontology',
    },
    'report': {
        'dax': '{4AB}',
        'intent': Intent.DELIVER,
        'description': 'Generate a build report with lessons learned',
        'slots': {},
        'output': 'card',
        'edge_flows': ['review_lessons', 'summarize'],
        'policy_path': 'policies.deliver_policies.report',
    },
    'package': {
        'dax': '{48A}',
        'intent': Intent.DELIVER,
        'description': 'Package the full domain for the user\'s environment',
        'slots': {
            'target_dir': {
                'type': 'FreeTextSlot', 'priority': 'optional',
            },
        },
        'output': 'list',
        'edge_flows': ['generate', 'confirm_export'],
        'policy_path': 'policies.deliver_policies.package',
    },

    # ── Converse (7 flows) ────────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': Intent.CONVERSE,
        'description': 'Open-ended conversation about building assistants',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['explain', 'feedback'],
        'policy_path': 'policies.converse_policies.chat',
    },
    'next_step': {
        'dax': '{019}',
        'intent': Intent.CONVERSE,
        'description': 'Ask Kalli what to do next',
        'slots': {},
        'output': 'card',
        'edge_flows': ['summarize', 'suggest_flow'],
        'policy_path': 'policies.converse_policies.next_step',
    },
    'feedback': {
        'dax': '{029}',
        'intent': Intent.CONVERSE,
        'description': 'Give feedback on the build process or Kalli\'s behavior',
        'slots': {},
        'output': 'toast',
        'edge_flows': ['chat', 'style'],
        'policy_path': 'policies.converse_policies.feedback',
    },
    'preference': {
        'dax': '{08A}',
        'intent': Intent.CONVERSE,
        'description': 'Set a user preference for the build process',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'required'},
            'value': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['style', 'persona'],
        'policy_path': 'policies.converse_policies.preference',
    },
    'style': {
        'dax': '{08B}',
        'intent': Intent.CONVERSE,
        'description': 'Tell Kalli about preferred working style',
        'slots': {
            'preference': {
                'type': 'FreeTextSlot', 'priority': 'required',
            },
        },
        'output': 'toast',
        'edge_flows': ['preference', 'feedback'],
        'policy_path': 'policies.converse_policies.style',
    },
    'endorse': {
        'dax': '{09E}',
        'intent': Intent.CONVERSE,
        'description': 'Approve Kalli\'s unsolicited suggestion',
        'slots': {
            'action': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['approve', 'next_step'],
        'policy_path': 'policies.converse_policies.endorse',
    },
    'dismiss': {
        'dax': '{09F}',
        'intent': Intent.CONVERSE,
        'description': 'Dismiss Kalli\'s unsolicited suggestion',
        'slots': {},
        'output': 'toast',
        'edge_flows': ['decline', 'feedback'],
        'policy_path': 'policies.converse_policies.dismiss',
    },

    # ── Plan (5 flows) ────────────────────────────────────────────────

    'research': {
        'dax': '{13C}',
        'intent': Intent.PLAN,
        'description': 'Plan to research specs before design decisions',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['lookup', 'explain'],
        'policy_path': 'policies.plan_policies.research',
    },
    'finalize': {
        'dax': '{24A}',
        'intent': Intent.PLAN,
        'description': 'Plan the final export sequence',
        'slots': {},
        'output': 'list',
        'edge_flows': ['generate', 'package'],
        'policy_path': 'policies.plan_policies.finalize',
    },
    'onboard': {
        'dax': '{25A}',
        'intent': Intent.PLAN,
        'description':
            'Full onboarding plan: scope, intents, entities, persona',
        'slots': {
            'domain': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['scope', 'intent'],
        'policy_path': 'policies.plan_policies.onboard',
    },
    'expand': {
        'dax': '{35A}',
        'intent': Intent.PLAN,
        'description': 'Plan to add a batch of new flows at once',
        'slots': {
            'intent_filter': {
                'type': 'IntentSlot', 'priority': 'optional',
            },
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['compose', 'suggest_flow'],
        'policy_path': 'policies.plan_policies.expand',
    },
    'redesign': {
        'dax': '{36A}',
        'intent': Intent.PLAN,
        'description': 'Plan to redesign a section of the config',
        'slots': {
            'section': {'type': 'SectionSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['revise', 'refine'],
        'policy_path': 'policies.plan_policies.redesign',
    },

    'recap': {
        'dax': '{018}',
        'intent': Intent.INTERNAL,
        'description':
            'Pull a snippet from current conversation (scratchpad L1)',
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
        'description': 'Retrieve relevant lessons from memory (L2/L3)',
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
    'read_spec': {
        'dax': '{29C}',
        'intent': Intent.INTERNAL,
        'description': 'Internally read a spec file to answer a question',
        'slots': {
            'spec_name': {'type': 'SpecSlot', 'priority': 'required'},
            'section': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['lookup', 'explain'],
        'policy_path': 'policies.internal_policies.read_spec',
    },
    'auto_validate': {
        'dax': '{39D}',
        'intent': Intent.INTERNAL,
        'description': 'Internally validate config consistency',
        'slots': {},
        'output': '(internal)',
        'edge_flows': ['validate', 'compare'],
        'policy_path': 'policies.internal_policies.auto_validate',
    },
    'auto_generate': {
        'dax': '{49A}',
        'intent': Intent.INTERNAL,
        'description':
            'Internally trigger file generation after approval',
        'slots': {
            'file_type': {
                'type': 'CategorySlot', 'priority': 'required',
            },
        },
        'output': '(internal)',
        'edge_flows': ['generate', 'ontology'],
        'policy_path': 'policies.internal_policies.auto_generate',
    },
}


# Key entities for this domain
KEY_ENTITIES = ['config', 'lesson', 'spec']
