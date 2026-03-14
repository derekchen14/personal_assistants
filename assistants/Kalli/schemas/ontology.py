from enum import Enum


class Intent:
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'
    EXPLORE = 'Explore'           # see existing assistants, browse specs, check progress
    GATHER = 'Gather'             # collect requirements, propose flows, finalize drafts
    PERSONALIZE = 'Personalize'   # modify existing config, iterate grammar, refine slots
    DELIVER = 'Deliver'            # generate, package, test, deploy, secure, version


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
    'chat':        {'hex': '0', 'pos': 'noun'},
    'browse':      {'hex': '1', 'pos': 'verb'},
    'scope':       {'hex': '2', 'pos': 'verb'},
    'iterate':     {'hex': '3', 'pos': 'verb'},
    'generate':    {'hex': '4', 'pos': 'verb'},
    'insert':      {'hex': '5', 'pos': 'verb'},
    'update':      {'hex': '6', 'pos': 'verb'},
    'delete':      {'hex': '7', 'pos': 'verb'},
    'user':        {'hex': '8', 'pos': 'adj'},
    'agent':       {'hex': '9', 'pos': 'adj'},
    'assistant':   {'hex': 'A', 'pos': 'noun'},
    'requirement': {'hex': 'B', 'pos': 'noun'},
    'spec':        {'hex': 'C', 'pos': 'noun'},
    'draft':       {'hex': 'D', 'pos': 'adj'},
    'accept':      {'hex': 'E', 'pos': 'adj'},
    'reject':      {'hex': 'F', 'pos': 'adj'},
}

FLOW_CATALOG = {

    # ── Explore (8 flows) ──────────────────────────────────────────────
    # See what assistants exist, answer capability questions, browse specs,
    # check progress, compare against requirements.

    'status': {
        'dax': '{01A}',
        'intent': Intent.EXPLORE,
        'description': 'View current state of the assistant being built',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['summarize', 'inspect'],
        'policy_path': 'policies.explore.status',
    },
    'lessons': {
        'dax': '{01B}',
        'intent': Intent.EXPLORE,
        'description': 'Browse stored requirements and patterns',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'teach'],
        'policy_path': 'policies.explore.lessons',
    },
    'browse': {
        'dax': '{001}',
        'intent': Intent.EXPLORE,
        'description': 'Look up a specific spec file or section',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'query': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['explain', 'inspect'],
        'policy_path': 'policies.explore.browse',
    },
    'recommend': {
        'dax': '{18C}',
        'intent': Intent.EXPLORE,
        'description': 'Find specs relevant to the user\'s target domain',
        'slots': {
            'context': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'research'],
        'policy_path': 'policies.explore.recommend',
    },
    'summarize': {
        'dax': '{19A}',
        'intent': Intent.EXPLORE,
        'description': 'Agent summarizes overall build progress',
        'slots': {},
        'output': 'card',
        'edge_flows': ['status', 'inspect'],
        'policy_path': 'policies.explore.summarize',
    },
    'explain': {
        'dax': '{19C}',
        'intent': Intent.EXPLORE,
        'description': 'Agent explains an architecture concept or capability',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['browse', 'chat'],
        'policy_path': 'policies.explore.explain',
    },
    'inspect': {
        'dax': '{1AD}',
        'intent': Intent.EXPLORE,
        'description': 'Inspect a draft assistant section in detail',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'detail': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['status', 'compare'],
        'policy_path': 'policies.explore.inspect',
    },
    'compare': {
        'dax': '{1CD}',
        'intent': Intent.EXPLORE,
        'description': 'Compare draft assistant section against spec rules',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'reference': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['validate', 'inspect'],
        'policy_path': 'policies.explore.compare',
    },

    # ── Gather (6 flows) ───────────────────────────────────────────────
    # Collect all user requirements: scope, persona, preferences, entities.
    # Go through the checklist, collect info to build dact grammar, propose
    # flows, finalize drafts. (log absorbed into teach)

    'scope': {
        'dax': '{002}',
        'intent': Intent.GATHER,
        'description': 'Define assistant scope: name, task, boundaries',
        'slots': {
            'name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'task': {'type': 'FreeTextSlot', 'priority': 'required'},
            'boundaries': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'form',
        'panel': 'top',
        'edge_flows': ['persona', 'entity'],
        'policy_path': 'policies.gather.scope',
    },
    'teach': {
        'dax': '{02B}',
        'intent': Intent.GATHER,
        'description': 'Share a learning, pattern, or requirement for Kalli to remember',
        'slots': {
            'pattern': {'type': 'FreeTextSlot', 'priority': 'required'},
            'category': {'type': 'CategorySlot', 'priority': 'optional'},
            'context': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['lessons', 'feedback'],
        'policy_path': 'policies.gather.teach',
    },
    'intent': {
        'dax': '{005}',
        'intent': Intent.GATHER,
        'description': 'Define a domain intent for the assistant',
        'slots': {
            'name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'description': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'form',
        'edge_flows': ['entity', 'revise'],
        'policy_path': 'policies.gather.intent',
    },
    'persona': {
        'dax': '{28A}',
        'intent': Intent.GATHER,
        'description': 'Define persona preferences: name, tone, style',
        'slots': {
            'name': {'type': 'FreeTextSlot', 'priority': 'required'},
            'tone': {'type': 'CategorySlot', 'priority': 'elective'},
            'style': {'type': 'CategorySlot', 'priority': 'elective'},
        },
        'output': 'form',
        'edge_flows': ['scope', 'entity'],
        'policy_path': 'policies.gather.persona',
    },
    'entity': {
        'dax': '{2AC}',
        'intent': Intent.GATHER,
        'description': 'Define key entities grounded in domain concepts',
        'slots': {
            'entities': {'type': 'GroupSlot', 'priority': 'required'},
        },
        'output': 'form',
        'edge_flows': ['intent', 'scope'],
        'policy_path': 'policies.gather.entity',
    },
    'propose': {
        'dax': '{003}',
        'intent': Intent.GATHER,
        'description': 'Propose core dacts for the domain grammar',
        'slots': {},
        'output': 'list',
        'edge_flows': ['suggest', 'validate'],
        'policy_path': 'policies.gather.propose',
    },

    # ── Personalize (8 flows) ──────────────────────────────────────────
    # Only acts on existing requirements. Modifies existing assistant and
    # configs, iterations on grammar, refine slots, finalize assistant.

    'revise': {
        'dax': '{006}',
        'intent': Intent.PERSONALIZE,
        'description': 'Update a previously defined assistant section',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'value': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['remove', 'refine'],
        'policy_path': 'policies.personalize.revise',
    },
    'remove': {
        'dax': '{007}',
        'intent': Intent.PERSONALIZE,
        'description': 'Remove an assistant section or entry',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
        },
        'output': 'confirmation',
        'panel': 'top',
        'edge_flows': ['revise', 'decline'],
        'policy_path': 'policies.personalize.remove',
    },
    'rework': {
        'dax': '{03D}',
        'intent': Intent.PERSONALIZE,
        'description': 'Revise an existing flow design',
        'slots': {
            'flow': {'type': 'ExactSlot', 'priority': 'required'},
            'change': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'card',
        'edge_flows': ['refine', 'propose'],
        'policy_path': 'policies.personalize.rework',
    },
    'approve': {
        'dax': '{0AE}',
        'intent': Intent.PERSONALIZE,
        'description': 'Approve a proposed flow or dact',
        'slots': {
            'flow': {'type': 'ExactSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['endorse', 'decline'],
        'policy_path': 'policies.personalize.approve',
    },
    'decline': {
        'dax': '{0AF}',
        'intent': Intent.PERSONALIZE,
        'description': 'Reject a proposed flow or dact with reason',
        'slots': {
            'flow': {'type': 'ExactSlot', 'priority': 'required'},
            'reason': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'toast',
        'edge_flows': ['dismiss', 'approve'],
        'policy_path': 'policies.personalize.decline',
    },
    'suggest': {
        'dax': '{39A}',
        'intent': Intent.PERSONALIZE,
        'description': 'Agent suggests changes to existing flows',
        'slots': {
            'filter': {'type': 'CategorySlot', 'priority': 'optional'},
            'scope': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['propose', 'refine'],
        'policy_path': 'policies.personalize.suggest',
    },
    'refine': {
        'dax': '{3AD}',
        'intent': Intent.PERSONALIZE,
        'description': 'Refine a flow\'s slot signature or output type',
        'slots': {
            'flow': {'type': 'ExactSlot', 'priority': 'required'},
            'change': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['rework', 'validate'],
        'policy_path': 'policies.personalize.refine',
    },
    'validate': {
        'dax': '{3AC}',
        'intent': Intent.PERSONALIZE,
        'description': 'Validate current flow catalog against spec rules',
        'slots': {},
        'output': 'list',
        'edge_flows': ['propose', 'compare'],
        'policy_path': 'policies.personalize.validate',
    },

    # ── Deliver (6 flows) ──────────────────────────────────────────────
    # Everything needed to get the assistant working for real users:
    # generate configs, package, test, secure, version, deploy.

    'generate': {
        'dax': '{004}',
        'intent': Intent.DELIVER,
        'description': 'Generate domain config files (ontology, yaml, or all)',
        'slots': {
            'format': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['package', 'test'],
        'policy_path': 'policies.deliver.generate',
    },
    'package': {
        'dax': '{48A}',
        'intent': Intent.DELIVER,
        'description': 'Package the full domain for deployment — bundles config, prompts, and dependencies into a deployable artifact',
        'slots': {
            'target': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['test', 'deploy'],
        'policy_path': 'policies.deliver.package',
    },
    'test': {
        'dax': '{4BC}',
        'intent': Intent.DELIVER,
        'description': 'Run validation tests against the built assistant — test conversations, flow coverage, slot filling accuracy, and policy behavior',
        'slots': {
            'scope': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['generate', 'deploy'],
        'policy_path': 'policies.deliver.test',
    },
    'deploy': {
        'dax': '{4AE}',
        'intent': Intent.DELIVER,
        'description': 'Deploy the assistant to a target environment — staging or production. Automatically generates a build report on deployment',
        'slots': {
            'environment': {'type': 'CategorySlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['test', 'secure'],
        'policy_path': 'policies.deliver.deploy',
    },
    'secure': {
        'dax': '{89A}',
        'intent': Intent.DELIVER,
        'description': 'Configure authentication, API keys, rate limits, and access permissions for the deployed assistant',
        'slots': {
            'setting': {'type': 'DictionarySlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['deploy', 'version'],
        'policy_path': 'policies.deliver.secure',
    },
    'version': {
        'dax': '{4AD}',
        'intent': Intent.DELIVER,
        'description': 'Tag a release version of the assistant — creates a versioned snapshot with changelog and diff from the previous release',
        'slots': {
            'tag': {'type': 'ExactSlot', 'priority': 'required'},
            'notes': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['deploy', 'package'],
        'policy_path': 'policies.deliver.version',
    },

    # ── Converse (7 flows) ─────────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': Intent.CONVERSE,
        'description': 'Open-ended conversation about building assistants',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': ['explain', 'feedback'],
        'policy_path': 'policies.converse.chat',
    },
    'next': {
        'dax': '{019}',
        'intent': Intent.CONVERSE,
        'description': 'Ask Kalli what to do next',
        'slots': {},
        'output': 'card',
        'edge_flows': ['summarize', 'suggest'],
        'policy_path': 'policies.converse.next',
    },
    'feedback': {
        'dax': '{029}',
        'intent': Intent.CONVERSE,
        'description': 'Give feedback on the build process or Kalli\'s behavior',
        'slots': {},
        'output': 'toast',
        'edge_flows': ['chat', 'style'],
        'policy_path': 'policies.converse.feedback',
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
        'policy_path': 'policies.converse.preference',
    },
    'style': {
        'dax': '{08B}',
        'intent': Intent.CONVERSE,
        'description': 'Tell Kalli about preferred working style',
        'slots': {
            'preference': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['preference', 'feedback'],
        'policy_path': 'policies.converse.style',
    },
    'endorse': {
        'dax': '{09E}',
        'intent': Intent.CONVERSE,
        'description': 'Approve Kalli\'s unsolicited suggestion',
        'slots': {
            'action': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': 'toast',
        'edge_flows': ['approve', 'next'],
        'policy_path': 'policies.converse.endorse',
    },
    'dismiss': {
        'dax': '{09F}',
        'intent': Intent.CONVERSE,
        'description': 'Dismiss Kalli\'s unsolicited suggestion',
        'slots': {},
        'output': 'toast',
        'edge_flows': ['decline', 'feedback'],
        'policy_path': 'policies.converse.dismiss',
    },

    # ── Plan (5 flows) ─────────────────────────────────────────────────

    'research': {
        'dax': '{13C}',
        'intent': Intent.PLAN,
        'description': 'Plan to research specs before design decisions',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'required'},
            'depth': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['browse', 'explain'],
        'policy_path': 'policies.plan.research',
    },
    'finalize': {
        'dax': '{24A}',
        'intent': Intent.PLAN,
        'description': 'Plan the final export sequence',
        'slots': {},
        'output': 'list',
        'edge_flows': ['generate', 'package'],
        'policy_path': 'policies.plan.finalize',
    },
    'onboard': {
        'dax': '{25A}',
        'intent': Intent.PLAN,
        'description':
            'Full onboarding plan: scope, intents, entities, persona',
        'slots': {
            'context': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['scope', 'intent'],
        'policy_path': 'policies.plan.onboard',
    },
    'expand': {
        'dax': '{35A}',
        'intent': Intent.PLAN,
        'description': 'Plan to add a batch of new flows at once',
        'slots': {
            'filter': {'type': 'CategorySlot', 'priority': 'optional'},
            'count': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['propose', 'suggest'],
        'policy_path': 'policies.plan.expand',
    },
    'redesign': {
        'dax': '{36A}',
        'intent': Intent.PLAN,
        'description': 'Plan to redesign a section of the assistant',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'goal': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['revise', 'refine'],
        'policy_path': 'policies.plan.redesign',
    },

    # ── Internal (8 flows) ─────────────────────────────────────────────

    'recap': {
        'dax': '{018}',
        'intent': Intent.INTERNAL,
        'description':
            'Pull a snippet from current conversation (scratchpad L1)',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'turns': {'type': 'LevelSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recall', 'retrieve'],
        'policy_path': 'policies.internal.recap',
    },
    'recall': {
        'dax': '{289}',
        'intent': Intent.INTERNAL,
        'description': 'Retrieve stored user preferences (L2)',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recap', 'retrieve'],
        'policy_path': 'policies.internal.recall',
    },
    'retrieve': {
        'dax': '{19B}',
        'intent': Intent.INTERNAL,
        'description':
            'Retrieve general business context from memory (L3 unvetted)',
        'slots': {
            'key': {'type': 'FreeTextSlot', 'priority': 'optional'},
            'scope': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['recall', 'recap'],
        'policy_path': 'policies.internal.retrieve',
    },
    'search': {
        'dax': '{1BC}',
        'intent': Intent.INTERNAL,
        'description':
            'Search vetted FAQs and curated reference content',
        'slots': {
            'query': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': '(internal)',
        'edge_flows': ['browse', 'retrieve'],
        'policy_path': 'policies.internal.search',
    },
    'peek': {
        'dax': '{09A}',
        'intent': Intent.INTERNAL,
        'description':
            'Quick internal computation (count flows, check coverage)',
        'slots': {
            'target': {'type': 'FreeTextSlot', 'priority': 'required'},
        },
        'output': '(internal)',
        'edge_flows': ['recap', 'audit'],
        'policy_path': 'policies.internal.peek',
    },
    'study': {
        'dax': '{29C}',
        'intent': Intent.INTERNAL,
        'description': 'Internally read a spec file to answer a question',
        'slots': {
            'source': {'type': 'SourceSlot', 'priority': 'required'},
            'query': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': '(internal)',
        'edge_flows': ['browse', 'explain'],
        'policy_path': 'policies.internal.study',
    },
    'audit': {
        'dax': '{39D}',
        'intent': Intent.INTERNAL,
        'description': 'Internally validate assistant consistency',
        'slots': {},
        'output': '(internal)',
        'edge_flows': ['validate', 'compare'],
        'policy_path': 'policies.internal.audit',
    },
    'emit': {
        'dax': '{49A}',
        'intent': Intent.INTERNAL,
        'description':
            'Internally trigger file generation after approval',
        'slots': {
            'format': {'type': 'CategorySlot', 'priority': 'required'},
        },
        'output': '(internal)',
        'edge_flows': ['generate', 'deploy'],
        'policy_path': 'policies.internal.emit',
    },
}


KEY_ENTITIES = ['assistant', 'requirement', 'spec']
