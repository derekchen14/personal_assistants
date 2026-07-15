"""Audit, review, and curate Hugo's evaluation corpus in bounded human-review rounds."""

import argparse
import copy
import json
import logging
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


SUITE_DIR = Path(__file__).resolve().parent
HUGO_ROOT = SUITE_DIR.parent.parent
if str(HUGO_ROOT) not in sys.path:
    sys.path.insert(0, str(HUGO_ROOT))
load_dotenv(HUGO_ROOT / '.env')

from schemas.config import load_config
from schemas.ontology import FLOW_ONTOLOGY


TRAIN = SUITE_DIR / 'datasets' / 'train.jsonl'
REPORT = SUITE_DIR / 'report'
AUDIT_PATH = REPORT / 'curation_audit.json'
SCORES_PATH = REPORT / 'curation_scores.jsonl'
ERRORS_PATH = REPORT / 'curation_score_errors.jsonl'
LEDGER_PATH = REPORT / 'curation_ledger.json'
CURRENT_ROUND = REPORT / 'curation_round_current.json'
SELECTION_PATH = REPORT / 'curation_selection.json'
SUMMARY_PATH = REPORT / 'curation_summary.json'
REVOICE_PLAN_PATH = REPORT / 'curation_revoice_plan.json'
REVOICE_RESULTS_PATH = REPORT / 'curation_revoice_results.jsonl'
REVOICE_ERRORS_PATH = REPORT / 'curation_revoice_errors.jsonl'
SEMANTIC_AUDIT_PATH = REPORT / 'curation_semantic_parts.jsonl'
SEMANTIC_FAILURES_PATH = REPORT / 'curation_semantic_failures.jsonl'
REPLACEMENT_MANIFEST_PATH = REPORT / 'curation_replacement_manifest.json'
REPLACEMENT_RESULTS_PATH = REPORT / 'curation_replacement_results.jsonl'
REPLACEMENT_ERRORS_PATH = REPORT / 'curation_replacement_errors.jsonl'
FULL_REVOICE_PLAN_PATH = REPORT / 'curation_full_revoice_plan.json'
FULL_REVOICE_RESULTS_PATH = REPORT / 'curation_full_revoice_results.jsonl'
FULL_REVOICE_ERRORS_PATH = REPORT / 'curation_full_revoice_errors.jsonl'
MANUAL_REVOICE_RESULTS_PATH = REPORT / 'curation_manual_revoice_results.jsonl'
HUMAN_BUDGET = 32
TARGET_SIZE = 128
TARGET_PART_RATIOS = (0.60, 0.30, 0.09, 0.01)
CURATED_DELETIONS = {
    'B04.C01', 'B04.C02', 'B04.C03', 'B04.C04', 'B04.C05', 'B04.C06',
    'B07.C01', 'B07.C02', 'B07.C03', 'B07.C05', 'B07.C06', 'B07.C07',
    'B07.C09', 'B07.C10', 'B07.C11', 'B07.C13', 'B07.C14',
    'B03.C12', 'B02.C08',
    'B08.C01', 'B08.C02', 'B08.C03', 'B08.C04', 'B08.C06', 'B08.C07',
    'B08.C09', 'B08.C10', 'B08.C13', 'B08.C15', 'B08.C16',
    'B09.C03', 'B09.C06',
}
REPLACEMENT_DELETIONS = {
    # Three failed semantic-split or reconstruction attempts.
    'B01.C02', 'B01.C03', 'B02.C06', 'B05.C08', 'B06.C10', 'B06.C13',
    'B06.C16', 'B11.C10',
    # Low-quality or duplicated structures selected for a fresh replacement batch.
    'B01.C01', 'B01.C08', 'B02.C13', 'B05.C07', 'B10.C01', 'B10.C03',
    'B10.C13', 'B10.C15',
}
PROTECTED_REVIEWED_IDS = {
    'B06.C14', 'B05.C15', 'B10.C08', 'B03.C09', 'B03.C06', 'B07.C15',
    'B12.C12', 'B10.C04', 'B02.C14', 'B10.C06', 'B01.C11', 'B07.C04',
    'B01.C06', 'B09.C07', 'B11.C14', 'B09.C14',
}
# High-confidence failures found by a conversation-context audit of the random trim plan.
UNSAFE_TRIM_KEYS = {
    ('B01.C08', 3), ('B01.C09', 1), ('B01.C11', 3), ('B01.C12', 7),
    ('B02.C04', 1), ('B02.C05', 1), ('B02.C13', 1), ('B03.C03', 7),
    ('B03.C04', 3), ('B03.C06', 1), ('B05.C02', 7), ('B05.C05', 1),
    ('B05.C05', 7), ('B05.C06', 5), ('B05.C07', 5), ('B06.C06', 3),
    ('B06.C07', 5), ('B06.C09', 3), ('B07.C16', 5), ('B09.C07', 3),
    ('B09.C09', 5), ('B10.C01', 3), ('B10.C03', 3), ('B10.C06', 3),
    ('B10.C07', 3), ('B10.C13', 3), ('B10.C13', 5), ('B10.C15', 3),
    ('B10.C15', 5),
}
MANUAL_UTTERANCE_REPAIRS = {
    ('B02.C14', 11): 'The voice pass can wait because I need this published to the main blog now.',
}
RETENTION_OVERRIDES = {
    ('B01.C04', 3): [2, 3],
    ('B01.C08', 1): [0, 1],
    ('B02.C13', 1): [1, 2], ('B02.C13', 3): [0, 1],
    ('B02.C13', 5): [1, 3], ('B02.C13', 7): [1, 2],
    ('B04.C14', 1): [0, 1], ('B04.C14', 3): [0, 1], ('B04.C14', 7): [0],
    ('B05.C02', 7): [0, 1],
    ('B05.C15', 3): [1],
    ('B06.C03', 1): [1], ('B06.C03', 3): [1], ('B06.C03', 7): [1],
    ('B06.C04', 3): [1], ('B06.C04', 5): [1],
    ('B10.C16', 3): [0, 1], ('B10.C16', 7): [1],
}
DOMAIN_FLOWS = set(FLOW_ONTOLOGY) - {'clarify', 'plan'}
AMBIGUITY_LEVELS = {'general', 'partial', 'specific', 'confirmation'}
ACTION_MAP = {
    'find': ['find_posts'], 'inspect': ['read_metadata'], 'summarize': ['summarize_text'],
    'compare': ['compare_style'], 'outline': ['generate_outline'],
    'compose': ['convert_to_prose'], 'refine': ['generate_outline'],
    'brainstorm': ['brainstorm_ideas'], 'rework': ['revise_content'],
    'write': ['write_text'], 'audit': ['editor_review'],
    'propose': ['read_section', 'revise_content'], 'release': ['release_post'],
    'schedule': ['release_post'], 'cite': ['revise_content'], 'chat': [],
}
PROACTIVE = re.compile(r'\b(want me to|should i|sound good|would you like me to)\b', re.I)
BANNED = re.compile(
    r'\b(load-bearing|byte-identical|delve|genuinely|absolutely|tighten)\b|'
    r'\bearn(?:s|ed|ing)? (?:its|their|the) (?:keep|conclusion)\b|'
    r'\b(?:that|this|the) constraint should carry through\b', re.I)
log = logging.getLogger('curate_corpus')

SEMANTIC_PART_EXAMPLES = r'''
HUMAN-LABELLED EXAMPLES:
1. "Summarize the Edison note on Menlo Park and pull out the key points worth using."
   => 2: ["Summarize the Edison note on Menlo Park", "Pull out the key points worth using"]
2. "Before we go any further, how long is the overnight trains draft and how many sections does it have?"
   => 2: ["Before we go any further, how long is the overnight trains draft?", "How many sections does it have?"]
3. "What have I already written about overnight trains? Pull the closest pieces, since the ending should earn its conclusion."
   => 3: ["What have I already written about overnight trains?", "Pull the closest pieces", "The ending should earn its conclusion"]
4. "Reading through the full draft now, does the whole thing hold together as one voice, or does the loopholes section drift away from the rest?"
   => 3: ["Reading through the full draft now", "Does the whole thing hold together as one voice?", "Does the loopholes section drift away from the rest?"]
5. "Yeah, that's exactly what I want, so go ahead and publish it."
   => 4: ["Yeah", "That's exactly what I want", "Go ahead", "Publish it"]
6. "Do a full voice pass across the piece and match the register I use in my other energy posts."
   => 2: ["Do a full voice pass across the piece", "Match the register I use in my other energy posts"]
7. "Given what you summarized about Edison, how do his note and Swan's note disagree on who deserves credit?"
   => 1: ["Given what you summarized about Edison, how do his note and Swan's note disagree on who deserves credit?"]
'''

REPLACEMENT_SPECS = [
    ('Agent Observability', "Don't Trace Prompts, Trace the Tool Calls",
     ['outline', 'refine', 'refine', 'compose', 'write'], 'repeated outline refinement'),
    ('Agent Evaluations', 'You Don\'t Need an Eval Framework, Just 20 Examples',
     ['brainstorm', 'outline', 'refine', 'refine', 'compose', 'audit'], 'two distinct outline fixes'),
    ('Agent Security', 'Prompt Injection Has No Fix, Only Blast Radius',
     ['outline', 'refine', 'refine', 'compose', 'write', 'audit'], 'outline iteration before prose'),
    ('RLVR / RL Environments', 'Why Reward Hacking Still Beats Us',
     ['compose', 'write', 'write', 'rework', 'write', 'audit'], 'independent prose fixes'),
    ('RAG on a Company Wiki', 'Your Wiki RAG Fails at Chunking, Not the Model',
     ['find', 'write', 'write', 'rework', 'write', 'audit'], 'existing-draft revision loop'),
    ('Thomas Edison', "Edison's Real Genius Was the Grid, Not the Bulb",
     ['compose', 'rework', 'write', 'write', 'rework', 'audit'], 'structural and line-edit rounds'),
    ('Ancient Roman Engineering', 'Roman Roads Weren\'t Built for Trade',
     ['compose', 'write', 'rework', 'write', 'write', 'audit'], 'four distinct revision rounds'),
    ('Personal Finance', 'How a Traditional IRA Quietly Loses You Money',
     ['outline', 'compose', 'write', 'write', 'rework', 'audit'], 'successive paragraph fixes'),
    ('Long-Distance Train Travel', 'An Overnight Train Is a Hotel in Disguise',
     ['compose', 'propose', 'write', 'propose', 'write', 'audit'], 'two literal placeholder fills'),
    ('Strength Training', 'Soreness Is Not Progress',
     ['compose', 'propose', 'propose', 'write', 'audit'], 'two independent blank proposals'),
    ('Urban Vegetable Gardening', 'Why Most Beginner Gardens Die in July',
     ['find', 'rework', 'propose', 'write', 'propose', 'audit'], 'draft repair with two gaps'),
    ('Amateur Astronomy', 'A Dark Sky Beats a Bigger Telescope',
     ['outline', 'refine', 'refine', 'compose', 'propose', 'write'], 'refine then fill a gap'),
    ('Adult Language Learning', 'Why Flashcards Stop Working at B1',
     ['outline', 'refine', 'refine', 'compose', 'audit'], 'planning-gated outline iteration'),
    ('Burnout & Mindfulness', 'Burnout Looks Like Cynicism, Not Exhaustion',
     ['rework', 'write', 'write', 'audit'], 'planning-gated revise loop'),
    ('Urban Cycling', 'Why Bike Lanes Pay for Themselves',
     ['compose', 'write', 'rework', 'write', 'write', 'audit'], 'cadence-varied revision loop'),
    ('Clean Energy', 'Rooftop Solar Is the Wrong First Move',
     ['compose', 'propose', 'write', 'propose', 'write', 'audit'], 'frontend-grounded blank fills'),
]
EXTRA_REPLACEMENT_SPECS = [
    ('Agent Observability', "Your Agent's Token Count Is a Vanity Metric",
     ['outline', 'refine', 'refine', 'compose', 'write', 'audit'], 'three-stage drafting loop'),
    ('Agent Evaluations', 'LLM-as-Judge Grades on a Curve',
     ['compose', 'write', 'write', 'rework', 'write', 'audit'], 'four independent prose revisions'),
    ('Agent Security', "Guardrails Won't Save You; Least Privilege Will",
     ['compose', 'propose', 'write', 'propose', 'write', 'audit'], 'two grounded security-term blanks'),
    ('RAG on a Company Wiki', 'Vector DBs Are Not Needed for RAG',
     ['outline', 'refine', 'refine', 'compose', 'rework', 'write'], 'outline and prose iteration'),
    ('Thomas Edison', 'Edison Didn\'t Invent the Lightbulb (and Knew It)',
     ['find', 'rework', 'write', 'write', 'rework', 'audit'], 'existing-draft revision loop'),
    ('Long-Distance Train Travel', 'Skip the Eurail Pass: Point Tickets Cost Less',
     ['compose', 'write', 'rework', 'write', 'write', 'audit'], 'four distinct editing rounds'),
    ('Urban Cycling', 'Skip the Road Bike: a Used Hybrid Commutes Better',
     ['outline', 'refine', 'refine', 'compose', 'propose', 'write'], 'refine then in-fill'),
    ('Burnout & Mindfulness', 'Delete Your Meditation App',
     ['compose', 'propose', 'propose', 'write', 'rework', 'audit'], 'two independent blank proposals'),
    ('Ancient Roman Engineering', 'Roman Concrete Heals Itself; Ours Just Crumbles',
     ['outline', 'refine', 'refine', 'compose', 'write', 'audit'], 'two outline fixes before prose'),
    ('Personal Finance', 'Index Funds for People Who Hate Spreadsheets',
     ['compose', 'write', 'write', 'rework', 'write', 'audit'], 'independent line and structure edits'),
    ('Strength Training', "Machines Aren't Cheating: Against Barbell Purism",
     ['compose', 'propose', 'write', 'rework', 'write', 'audit'], 'in-fill followed by revision'),
    ('Urban Vegetable Gardening', 'Skip the Raised Bed: a Bucket Grows More',
     ['outline', 'refine', 'refine', 'compose', 'propose', 'write'], 'refine then literal blank fill'),
    ('Amateur Astronomy', 'Skip the Telescope: Start With Binoculars',
     ['find', 'write', 'write', 'rework', 'write', 'audit'], 'existing-draft revision loop'),
    ('Adult Language Learning', "You Don't Need Immersion; You Need Output",
     ['compose', 'write', 'rework', 'write', 'write', 'audit'], 'four distinct prose fixes'),
    ('Clean Energy', 'Heat Pumps Beat Rooftop Solar for Most Homes',
     ['compose', 'propose', 'write', 'propose', 'write', 'audit'], 'two frontend-grounded gaps'),
    ('RLVR / RL Environments', 'Hidden Traps in a Verifiable-Reward Environment',
     ['outline', 'refine', 'refine', 'compose', 'rework', 'write'], 'outline and draft iteration'),
    ('Agent Observability', 'Building Observability Dashboards for LLM Apps',
     ['compose', 'write', 'write', 'rework', 'write', 'audit'], 'four independent dashboard edits'),
    ('Personal Finance', 'Why Cash Feels Safer Than It Really Is',
     ['outline', 'refine', 'refine', 'compose', 'propose', 'write'], 'outline iteration and a grounded fill'),
]


class TurnFinding(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    label_correct: bool
    human_voice: bool
    coherent: bool
    reason: str = ''
    suggested_labels: str = ''


class CaseJudgment(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    findings: list[TurnFinding]
    agent_quality: bool
    agent_reason: str = ''
    recommendation: Literal['keep', 'fix', 'delete']
    confidence: float
    generalized_pattern: str = ''


class RevoicedTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    utterance: str


class RevoicedCase(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    turns: list[RevoicedTurn]


class RevoicedUtterance(BaseModel):
    model_config = ConfigDict(extra='forbid')

    utterance: str


class SemanticTurnParts(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    part_count: int
    parts: list[str]
    source_utterance: str = ''


class SemanticCaseParts(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    turns: list[SemanticTurnParts]


class GeneratedStackItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    flow: str
    dax: str


class GeneratedLabels(BaseModel):
    model_config = ConfigDict(extra='forbid')

    intent: str | None
    stack: list[GeneratedStackItem]


class GeneratedUserTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    role: Literal['user']
    utterance: str
    labels: GeneratedLabels
    slots: dict
    ambiguity: str | None
    note: str | None = None


class GeneratedAgentTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    role: Literal['agent']
    actions: list[str]
    utterance: str | None = None


class GeneratedDraws(BaseModel):
    model_config = ConfigDict(extra='allow')

    length: list[int]
    flagged: bool


class GeneratedGeneration(BaseModel):
    model_config = ConfigDict(extra='allow')

    batch: str
    seed: int
    writer_model: str
    spec: str
    draws: GeneratedDraws


class GeneratedEvalCase(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    persona: str
    use_case: str
    topic: str
    title: str
    available_data: dict
    flagged: bool
    batch: str
    generation: GeneratedGeneration
    turns: list[Annotated[GeneratedUserTurn | GeneratedAgentTurn, Field(discriminator='role')]]


class FullRevoiceValidationTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    part_count: int
    faithful_to_plan: bool
    label_preserved: bool
    reason: str = ''


class FullRevoiceValidation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    turns: list[FullRevoiceValidationTurn]


class RetentionSelectionTurn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    turn_count: int
    retained_indices: list[int]
    valid: bool
    reason: str = ''


class RetentionSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')

    convo_id: str
    turns: list[RetentionSelectionTurn]


def load_cases(path: Path = TRAIN) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_cases(path: Path, cases: list[dict]):
    path.write_text(''.join(json.dumps(case, ensure_ascii=False) + '\n' for case in cases))


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')


def merge_values(target: dict, updates: dict):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_values(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def feedback_map() -> dict:
    feedback_dir = SUITE_DIR / 'review_app' / 'feedback'
    return {path.stem: json.loads(path.read_text()) for path in feedback_dir.glob('*.json')}


def following_agent(case: dict, user_index: int) -> dict:
    if user_index + 1 < len(case['turns']) and case['turns'][user_index + 1]['role'] == 'agent':
        return case['turns'][user_index + 1]
    return {}


def canonical_post(post) -> bool:
    return (isinstance(post, dict)
            and set(post) == {'post_id', 'title', 'status', 'sections'}
            and isinstance(post['sections'], dict)
            and all(isinstance(prose, str) and prose.strip() for prose in post['sections'].values()))


def normalized_clauses(utterance: str) -> list[str]:
    clauses = []
    for clause in re.split(r'[,.!?;]+', utterance.lower()):
        words = re.findall(r"[a-z0-9']+", clause)
        if len(words) >= 5:
            clauses.append(' '.join(words))
    return clauses


def comma_list(utterance: str) -> bool:
    if utterance.count(',') < 2:
        return False
    if ':' in utterance and utterance.split(':', 1)[1].count(',') >= 2:
        return True
    tail = utterance.split(':', 1)[-1]
    pieces = [piece.strip() for piece in tail.split(',')]
    return len(pieces) >= 3 and all(len(piece.split()) <= 10 for piece in pieces[1:]) and bool(
        re.search(r'\b(and|or|then)\b', pieces[-1], re.I))


def estimated_parts(utterance: str) -> int:
    boundaries = len(re.findall(r'[.!?;]+', utterance.rstrip('.!?;')))
    return 1 + boundaries


def case_facets(case: dict) -> dict:
    flows = []
    ambiguities = []
    planning = False
    for turn in case.get('turns', []):
        if turn.get('role') != 'user':
            continue
        stack = (turn.get('labels') or {}).get('stack', [])
        flows.extend(entry.get('flow') for entry in stack if entry.get('flow') in DOMAIN_FLOWS)
        planning |= len(stack) > 1 or (turn.get('labels') or {}).get('intent') == 'Plan'
        if turn.get('ambiguity'):
            ambiguities.append(turn['ambiguity'])
    return {'flows': sorted(set(flows)), 'topic': case.get('topic', ''),
            'ambiguities': sorted(set(ambiguities)), 'planning': planning}


def audit_case(case: dict, utterance_counts: Counter, clause_counts: Counter) -> list[dict]:
    issues = []
    turns = case.get('turns', [])
    if not turns or turns[0].get('role') != 'user':
        issues.append({'code': 'invalid_input', 'severity': 'hard', 'message': 'must start with user'})
    for index, turn in enumerate(turns):
        expected_role = 'user' if index % 2 == 0 else 'agent'
        if turn.get('role') != expected_role:
            issues.append({'code': 'invalid_input', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'turn alternation is broken'})
        utterance = turn.get('utterance')
        if utterance and utterance_counts[utterance] > 1:
            issues.append({'code': 'duplicate', 'severity': 'review',
                           'turn': turn.get('turn_count'), 'message': 'exact duplicate utterance'})
        if utterance and BANNED.search(utterance):
            issues.append({'code': 'voice', 'severity': 'review',
                           'turn': turn.get('turn_count'), 'message': 'contains a banned AI tell'})
        if turn.get('role') == 'user' and utterance:
            parts = estimated_parts(utterance)
            if parts >= 4:
                issues.append({'code': 'too_many_parts',
                               'severity': 'hard' if parts > 4 else 'review',
                               'turn': turn.get('turn_count'),
                               'message': f'estimated {parts} parts; 4 is a warning and 5+ is invalid'})
            if utterance.count(',') >= 3 and not comma_list(utterance):
                issues.append({'code': 'comma_fragmentation', 'severity': 'review',
                               'turn': turn.get('turn_count'),
                               'message': 'three or more non-list commas; merge the parts'})
            repeated = [clause for clause in normalized_clauses(utterance)
                        if clause_counts[clause] > 1]
            if repeated:
                issues.append({'code': 'repeated_phrase', 'severity': 'review',
                               'turn': turn.get('turn_count'),
                               'message': f'repeated corpus phrase: {repeated[0]!r}'})
        if turn.get('role') == 'agent' and utterance and PROACTIVE.search(utterance):
            prior = turns[index - 1] if index else {}
            prior_labels = prior.get('labels') or {}
            genuine_question = prior.get('ambiguity') or prior_labels.get('intent') == 'Plan'
            if not genuine_question:
                issues.append({'code': 'agent_voice', 'severity': 'review',
                               'turn': turn.get('turn_count'), 'message': 'unsolicited proactive offer'})
        if turn.get('role') != 'user':
            continue
        labels = turn.get('labels') or {}
        stack = labels.get('stack')
        ambiguity = turn.get('ambiguity')
        agent = following_agent(case, index)
        if not isinstance(stack, list):
            issues.append({'code': 'invalid_input', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'labels.stack must be a list'})
            continue
        if not stack and (ambiguity != 'general' or labels.get('intent') is not None):
            issues.append({'code': 'invalid_input', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'empty stack requires general ambiguity'})
        if len(stack) > 1 and labels.get('intent') != 'Plan':
            issues.append({'code': 'invalid_input', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'multi-flow stack requires Plan intent'})
        if ambiguity not in AMBIGUITY_LEVELS | {None}:
            issues.append({'code': 'invalid_input', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'unknown ambiguity level'})
        if ambiguity and agent.get('actions'):
            issues.append({'code': 'scope_mismatch', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'ambiguous turn calls a domain tool'})
        if len(stack) > 1 and agent.get('actions'):
            issues.append({'code': 'scope_mismatch', 'severity': 'hard',
                           'turn': turn.get('turn_count'), 'message': 'approval-gated plan calls a domain tool'})
        for entry in stack:
            flow = entry.get('flow')
            if flow == 'browse':
                issues.append({'code': 'obsolete_flow', 'severity': 'fix',
                               'turn': turn.get('turn_count'), 'message': 'replace browse with find'})
                continue
            if flow not in DOMAIN_FLOWS:
                issues.append({'code': 'invalid_input', 'severity': 'hard',
                               'turn': turn.get('turn_count'), 'message': f'invalid stack flow {flow!r}'})
                continue
            ontology = FLOW_ONTOLOGY[flow]
            if entry.get('dax') != ontology['dax']:
                issues.append({'code': 'invalid_input', 'severity': 'hard',
                               'turn': turn.get('turn_count'), 'message': f'wrong dax for {flow}'})
            if len(stack) == 1 and labels.get('intent') != ontology['intent']:
                issues.append({'code': 'invalid_input', 'severity': 'hard',
                               'turn': turn.get('turn_count'), 'message': f'wrong intent for {flow}'})
            if not ambiguity and len(stack) == 1 and agent:
                expected = ACTION_MAP[flow]
                if agent.get('actions') != expected:
                    issues.append({'code': 'trajectory', 'severity': 'review',
                                   'turn': turn.get('turn_count'),
                                   'message': f"expected actions {expected}, got {agent.get('actions')}"})
    for post in case.get('available_data', {}).get('posts', []):
        if not canonical_post(post):
            issues.append({'code': 'legacy_fixture', 'severity': 'fix',
                           'message': 'retained case needs a canonical seeded post'})
    lengths = (((case.get('generation') or {}).get('draws') or {}).get('length') or [])
    if any(parts >= 4 for parts in lengths):
        maximum = max(lengths)
        issues.append({'code': 'too_many_parts',
                       'severity': 'hard' if maximum > 4 else 'review',
                       'message': 'generation length vector contains a four-plus-part turn'})
    return issues


def audit_corpus(cases: list[dict]) -> dict:
    utterances = Counter(turn['utterance'] for case in cases for turn in case.get('turns', [])
                         if turn.get('utterance'))
    clauses = Counter(clause for case in cases for turn in case.get('turns', [])
                      if turn.get('role') == 'user' and turn.get('utterance')
                      for clause in normalized_clauses(turn['utterance']))
    case_reports = []
    for case in cases:
        issues = audit_case(case, utterances, clauses)
        batch_match = re.match(r'B(\d+)', case.get('batch', case['convo_id']))
        original = bool(batch_match and int(batch_match.group(1)) <= 6)
        case_reports.append({'convo_id': case['convo_id'], 'cohort': 'original' if original else 'new',
                             'facets': case_facets(case), 'issues': issues})
    counts = Counter(issue['severity'] for report in case_reports for issue in report['issues'])
    return {'created_at': datetime.now().isoformat(), 'case_count': len(cases),
            'issue_counts': dict(counts), 'cases': case_reports}


def run_audit(args):
    report = audit_corpus(load_cases())
    write_json(AUDIT_PATH, report)
    log.info('audited %d cases: %s', report['case_count'], report['issue_counts'])
    if args.strict and report['issue_counts'].get('hard'):
        raise SystemExit(1)


def load_scores() -> dict:
    if not SCORES_PATH.exists():
        return {}
    scores = {}
    for item in (json.loads(line) for line in SCORES_PATH.read_text().splitlines() if line.strip()):
        item['confidence'] = normalize_confidence(item['confidence'])
        scores[item['convo_id']] = item
    return scores


def normalize_confidence(value: float) -> float:
    if value > 5:
        value /= 100
    elif value > 1:
        value /= 5
    return max(0, min(1, value))


def judge_prompt(case: dict, audit: dict, feedback: dict, generalized_feedback: list) -> str:
    catalog = {flow: {'dax': FLOW_ONTOLOGY[flow]['dax'],
                      'intent': FLOW_ONTOLOGY[flow]['intent'],
                      'description': FLOW_ONTOLOGY[flow]['description']}
               for flow in sorted(DOMAIN_FLOWS)}
    return f"""Review one Hugo evaluation conversation. Quality priority is:
1. Every user turn has the correct flow, dax, intent, ambiguity level, and following actions.
2. The conversation makes sense as a sequence of blog-writing tasks.
3. User utterances sound human. Reject repetitive short punchy AI copy, but preserve natural terse speech.
4. Secondarily, agent replies report and stop rather than offering unsolicited next steps.

Return one finding for each USER turn only. Confidence MUST be a decimal from 0.0 to 1.0,
where 0.5 means uncertain and 1.0 means fully certain. Never use a 1-5 or percentage scale.
Keep every reason under 20 words and the generalized pattern under 30 words.

Plans use a multi-flow stack with Plan intent. General ambiguity uses an empty stack and null intent.
Neither plan nor clarify is a stack flow. Be conservative: do not invent defects merely because wording varies.

FLOW CATALOG:
{json.dumps(catalog, ensure_ascii=False)}

EXPECTED ACTIONS:
{json.dumps(ACTION_MAP)}

DETERMINISTIC AUDIT:
{json.dumps(audit, ensure_ascii=False)}

EXISTING HUMAN FEEDBACK (evidence, not binding):
{json.dumps(feedback, ensure_ascii=False)}

GENERALIZED HUMAN FEEDBACK (binding rubric updates):
{json.dumps(generalized_feedback, ensure_ascii=False)}

CASE:
{json.dumps(case, ensure_ascii=False)}
"""


def run_judge(args):
    from backend.components import prompt_engineer

    if args.model and not args.family:
        raise SystemExit('--model requires --family')
    if args.model:
        tiers = list(prompt_engineer.FAMILY_TIERS[args.family])
        tiers[prompt_engineer._TIER_IDX[args.tier]] = args.model
        prompt_engineer.FAMILY_TIERS[args.family] = tuple(tiers)
    PromptEngineer = prompt_engineer.PromptEngineer

    cases = load_cases()
    audit = load_json(AUDIT_PATH, audit_corpus(cases))
    audits = {item['convo_id']: item for item in audit['cases']}
    feedback = feedback_map()
    generalized_feedback = load_ledger().get('generalized_feedback', [])
    current_round = load_json(CURRENT_ROUND, {})
    if current_round.get('generalized_feedback'):
        generalized_feedback.append({'round': current_round.get('round'),
                                     'text': current_round['generalized_feedback']})
    ids = set(args.ids.split(',')) if args.ids else None
    if args.problematic:
        ids = {item['convo_id'] for item in audit['cases']
               if any(issue['severity'] == 'review' for issue in item['issues'])}
        ids |= {convo_id for convo_id, payload in feedback.items()
                if payload.get('verdict') == 'needs'}
    scores = load_scores() if args.resume else {}
    engineer = PromptEngineer(load_config())
    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        convo_id = case['convo_id']
        if ids is not None and convo_id not in ids:
            continue
        if args.resume and convo_id in scores:
            continue
        judgment = None
        for attempt in range(2):
            try:
                judgment = engineer(judge_prompt(case, audits[convo_id], feedback.get(convo_id, {}),
                                                 generalized_feedback),
                                    task='skill', tier=args.tier, family=args.family,
                                    max_tokens=args.max_tokens, schema=CaseJudgment)
                break
            except (ValueError, json.JSONDecodeError) as error:
                log.warning('judgment attempt %d failed for %s: %s', attempt + 1, convo_id, error)
        if judgment is None:
            with ERRORS_PATH.open('a') as error_file:
                error_file.write(json.dumps({'convo_id': convo_id,
                                             'error': 'two unparseable responses'}) + '\n')
            continue
        judgment.confidence = normalize_confidence(judgment.confidence)
        with SCORES_PATH.open('a') as score_file:
            score_file.write(judgment.model_dump_json() + '\n')
        log.info('judged %s: %s %.2f', convo_id, judgment.recommendation, judgment.confidence)


def quality_score(report: dict, judgment: dict | None, feedback: dict | None) -> float:
    penalty = {'hard': 40, 'fix': 10, 'review': 6}
    score = 100 - sum(penalty[issue['severity']] for issue in report['issues'])
    if report['cohort'] == 'original':
        score += 2
    if feedback:
        score += {'approve': 5, 'minor': 1, 'needs': -4}.get(feedback.get('verdict'), 0)
    if judgment:
        score += {'keep': 12, 'fix': 0, 'delete': -20}[judgment['recommendation']]
        score += (judgment['confidence'] - 0.5) * 8
    return score


def load_ledger() -> dict:
    return load_json(LEDGER_PATH, {'budget': HUMAN_BUDGET, 'events': [], 'rounds': [],
                                  'generalized_feedback': []})


def candidate_priority(report: dict, judgment: dict | None, score: float) -> tuple:
    severities = {issue['severity'] for issue in report['issues']}
    issue_rank = 0 if 'hard' in severities else 1 if 'review' in severities else 2 if 'fix' in severities else 3
    uncertain = judgment is None or judgment.get('confidence', 0) < 0.8
    coverage_value = len(report['facets']['flows']) + len(report['facets']['ambiguities'])
    return (issue_rank, not uncertain, -coverage_value, abs(score - 70), report['convo_id'])


def review_patterns(report: dict, judgment: dict | None, feedback: dict | None) -> set[str]:
    patterns = {issue['code'] for issue in report['issues']}
    if judgment:
        findings = judgment.get('findings', [])
        if any(not finding.get('label_correct', True) for finding in findings):
            patterns.add('label_error')
        if any(not finding.get('human_voice', True) for finding in findings):
            patterns.add('user_voice')
        if any(not finding.get('coherent', True) for finding in findings):
            patterns.add('coherence')
        if not judgment.get('agent_quality', True):
            patterns.add('agent_voice')
        patterns.add(f"judge_{judgment['recommendation']}")
        if feedback and feedback.get('verdict') == 'needs' and judgment['recommendation'] == 'keep':
            patterns.add('feedback_conflict')
    elif feedback and feedback.get('verdict') == 'needs':
        patterns.add('prior_needs')
    return patterns


def run_round(args):
    cases = load_cases()
    audit = load_json(AUDIT_PATH, audit_corpus(cases))
    scores = load_scores()
    feedback = feedback_map()
    ledger = load_ledger()
    requested_ids = set(args.ids.split(',')) if args.ids else None
    append_manifest = None
    if args.append_open:
        append_manifest = load_json(CURRENT_ROUND, {})
        if append_manifest.get('status') != 'open' or append_manifest.get('round') != args.round:
            raise SystemExit(f'round {args.round} is not the current open round')
        existing_ids = {item['convo_id'] for item in append_manifest['cases']}
        requested_ids = (requested_ids or set()) - existing_ids
        if not requested_ids:
            raise SystemExit('append-open requires at least one new --ids case')
    if args.replace_open:
        current = load_json(CURRENT_ROUND, {})
        if current.get('status') != 'open':
            raise SystemExit('there is no open round to replace')
        current_round_number = current.get('round')
        completed = sum(1 for event in ledger['events'] if event.get('round') == current_round_number)
        if completed:
            raise SystemExit('cannot replace an open round after a review event has been saved')
        current['status'] = 'superseded'
        current['superseded_at'] = datetime.now().isoformat()
        current['superseded_reason'] = 'replaced before review because stale pre-rewrite signals affected sampling'
        for round_item in ledger['rounds']:
            if round_item['round'] == current_round_number and round_item['status'] == 'open':
                round_item['status'] = 'superseded'
        write_json(REPORT / f'curation_round_{current_round_number}_superseded.json', current)
    if not args.append_open and any(entry['round'] == args.round for entry in ledger['rounds']):
        raise SystemExit(f'round {args.round} already exists')
    used = len(ledger['events'])
    reviewed_ids = {event['convo_id'] for event in ledger['events']}
    limit = min(args.limit, ledger['budget'] - used)
    if limit <= 0:
        raise SystemExit('human review budget is exhausted')
    reports = []
    case_map = {case['convo_id']: case for case in cases}
    for report in audit['cases']:
        if requested_ids is not None and report['convo_id'] not in requested_ids:
            continue
        if report['convo_id'] in reviewed_ids and not args.allow_rereview:
            continue
        judgment = None if args.calibration else scores.get(report['convo_id'])
        prior = None if args.calibration else feedback.get(report['convo_id'])
        score = quality_score(report, judgment, prior)
        reviewable_issues = any(issue['severity'] in {'hard', 'review'} or issue['code'] == 'obsolete_flow'
                                for issue in report['issues'])
        if requested_ids is not None or args.calibration or reviewable_issues or (judgment and judgment.get('recommendation') != 'keep') or (
                prior and prior.get('verdict') == 'needs'):
            case = case_map[report['convo_id']]
            user_turns = [turn for turn in case['turns'] if turn.get('role') == 'user']
            part_counts = [estimated_parts(turn['utterance']) for turn in user_turns]
            patterns = review_patterns(report, judgment, prior)
            if args.calibration:
                patterns |= {f"flow:{flow}" for flow in report['facets']['flows']}
                patterns |= {f"ambiguity:{level}" for level in report['facets']['ambiguities']}
                patterns |= {f"parts:{parts}" for parts in set(part_counts)}
                patterns |= {f"turns:{len(user_turns)}", f"cohort:{report['cohort']}"}
                patterns.add(f"planning:{report['facets']['planning']}")
            reports.append({'report': report, 'judgment': judgment, 'score': score,
                            'patterns': patterns})
    corpus_flows = {flow for report in audit['cases'] for flow in report['facets']['flows']}
    missing_flows = DOMAIN_FLOWS - corpus_flows
    for missing_flow in sorted(missing_flows):
        if requested_ids is not None:
            break
        source_flow = 'release' if missing_flow == 'schedule' else None
        source_candidates = [report for report in audit['cases']
                             if source_flow in report['facets']['flows']]
        source_report = max(
            source_candidates,
            key=lambda report: quality_score(report, scores.get(report['convo_id']),
                                             feedback.get(report['convo_id'])),
            default=None,
        )
        candidate = next((item for item in reports
                          if source_report and item['report']['convo_id'] == source_report['convo_id']), None)
        if source_report and candidate is None:
            candidate = {'report': source_report, 'judgment': scores.get(source_report['convo_id']),
                         'score': quality_score(source_report, scores.get(source_report['convo_id']),
                                                feedback.get(source_report['convo_id'])),
                         'patterns': set()}
            reports.append(candidate)
        if candidate:
            candidate['report'] = copy.deepcopy(candidate['report'])
            candidate['report']['issues'].append(
                {'code': 'coverage_gap', 'severity': 'review',
                 'message': f'consider a reviewed repair to represent missing flow {missing_flow}'})
            candidate['patterns'].add(f'coverage_{missing_flow}')
    chosen = []
    seen_patterns = set()
    seen_topics = set()
    cohort_counts = Counter()
    while reports and len(chosen) < limit:
        def information_gain(item):
            report = item['report']
            judgment = item['judgment'] or {}
            new_patterns = len(item['patterns'] - seen_patterns)
            new_topic = report['facets']['topic'] not in seen_topics
            cohort_balance = -cohort_counts[report['cohort']]
            uncertainty = 1 - judgment.get('confidence', 0.5)
            issue_penalty = -len(report['issues'])
            calibration_quality = item['score'] if args.calibration else -abs(item['score'] - 70)
            return (new_patterns, bool(judgment), new_topic, cohort_balance, issue_penalty, uncertainty,
                    len(report['facets']['flows']), calibration_quality)
        best = max(reports, key=information_gain)
        reports.remove(best)
        chosen.append(best)
        seen_patterns |= best['patterns']
        seen_topics.add(best['report']['facets']['topic'])
        cohort_counts[best['report']['cohort']] += 1
    manifest = append_manifest or {
        'round': args.round, 'status': 'open', 'created_at': datetime.now().isoformat(),
        'budget': {'used_before': used, 'allocated': 0,
                   'remaining_after_allocation': ledger['budget'] - used},
        'generalized_feedback': '', 'cases': []}
    revoiced = load_revoice_results()
    trim_plan = load_json(REVOICE_PLAN_PATH, {})
    planned_turns = {(case['convo_id'], turn['turn_count']): turn
                     for case in trim_plan.get('cases', []) for turn in case['turns']}
    for chosen_item in chosen:
        report = chosen_item['report']
        judgment = chosen_item['judgment']
        score = chosen_item['score']
        convo_id = report['convo_id']
        edited_case = None
        correction = ''
        if convo_id in revoiced:
            edited_case = copy.deepcopy(case_map[convo_id])
            notes = []
            for rewritten in revoiced[convo_id]['turns']:
                next(turn for turn in edited_case['turns']
                     if turn.get('turn_count') == rewritten['turn_count'])['utterance'] = rewritten['utterance']
                planned_turn = planned_turns[(convo_id, rewritten['turn_count'])]
                notes.append(f"T{rewritten['turn_count']} {planned_turn['current']}->{planned_turn['target_parts']} "
                             f"parts; retained {planned_turn['retained_parts']}; removed {planned_turn['removed_parts']}")
            correction = 'Random retention plus natural reconstruction. ' + ' '.join(notes)
        manifest['cases'].append({'convo_id': convo_id, 'score': score, 'audit': report,
                                  'judgment': judgment,
                                  'existing_feedback': None if args.calibration else feedback.get(convo_id),
                                  'review_patterns': sorted(chosen_item['patterns']),
                                  'decision': None, 'correction': correction, 'edited_case': edited_case,
                                  'case': case_map[convo_id]})
    manifest['budget']['allocated'] += len(chosen)
    manifest['budget']['remaining_after_allocation'] -= len(chosen)
    if args.append_open:
        round_entry = next(entry for entry in ledger['rounds'] if entry['round'] == args.round)
        round_entry['allocated'] += len(chosen)
    else:
        ledger['rounds'].append({'round': args.round, 'status': 'open', 'allocated': len(chosen),
                                 'completed': 0})
    if args.dry_run:
        write_json(REPORT / 'curation_round_preview.json', manifest)
    else:
        write_json(CURRENT_ROUND, manifest)
        write_json(LEDGER_PATH, ledger)
    log.info('created round %s with %d cases; %d completed review events remain',
             args.round, len(chosen), ledger['budget'] - len(ledger['events']))


def normalize_post(post, title: str) -> dict:
    if isinstance(post, str):
        post = {'title': post}
    post_title = post['title']
    post_id = post.get('post_id') or post.get('id') or re.sub(r'[^a-z0-9]+', '-', post_title.lower()).strip('-')
    sections = post.get('sections') or {}
    if isinstance(sections, list):
        sections = {name: f'{name} is part of the working draft for {post_title}.' for name in sections}
    if not sections:
        sections = {'Draft': f'This working draft develops the central argument of {post_title}.'}
    return {'post_id': post_id, 'title': post_title, 'status': post.get('status', 'draft'),
            'sections': sections}


def mechanical_repairs(case: dict, normalize_fixtures: bool = False) -> dict:
    repaired = copy.deepcopy(case)
    for index, turn in enumerate(repaired.get('turns', [])):
        if turn.get('role') != 'user':
            continue
        for entry in (turn.get('labels') or {}).get('stack', []):
            if entry.get('flow') == 'browse':
                entry.update({'flow': 'find', 'dax': FLOW_ONTOLOGY['find']['dax']})
                turn['labels']['intent'] = FLOW_ONTOLOGY['find']['intent']
                agent = following_agent(repaired, index)
                if agent.get('actions') == ['search_notes']:
                    agent['actions'] = ['find_posts']
        generation = repaired.get('generation') or {}
        text_fields = [repaired.get('use_case', ''), generation.get('spec', '')]
        repaired['use_case'] = re.sub(r'\bbrowse\b', 'find', text_fields[0])
        if generation.get('spec'):
            generation['spec'] = re.sub(r'\bbrowse\b', 'find', text_fields[1])
        draws = generation.get('draws') or {}
        sequence = (draws.get('use_case') or {}).get('sequence')
        if sequence:
            draws['use_case']['sequence'] = ['find' if flow == 'browse' else flow for flow in sequence]
    available = repaired.get('available_data') or {}
    if normalize_fixtures and available.get('posts'):
        available['posts'] = [normalize_post(post, repaired['title']) for post in available['posts']]
    return repaired


def backup_corpus(label: str) -> Path:
    REPORT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = REPORT / f'train_before_{label}_{stamp}.jsonl'
    shutil.copy2(TRAIN, path)
    return path


def run_apply_round(args):
    manifest = load_json(CURRENT_ROUND, None)
    if not manifest or manifest.get('status') != 'open':
        raise SystemExit('no open curation round')
    unresolved = [item['convo_id'] for item in manifest['cases'] if item.get('decision') not in {'keep', 'fix', 'delete'}]
    if unresolved:
        raise SystemExit(f'round has unresolved decisions: {unresolved}')
    for item in manifest['cases']:
        if item['decision'] == 'fix' and not item.get('edited_case'):
            raise SystemExit(f"{item['convo_id']} is fix without edited_case")
    cases = load_cases()
    decisions = {item['convo_id']: item for item in manifest['cases']}
    staged_rewrites = load_revoice_results()
    automatic_deletions = set(manifest.get('automatic_deletions', []))
    output = []
    for case in cases:
        item = decisions.get(case['convo_id'])
        if case['convo_id'] in automatic_deletions or (item and item['decision'] == 'delete'):
            continue
        if item and item['decision'] == 'fix':
            original = case
            case = copy.deepcopy(item['edited_case'])
            if case['convo_id'] in staged_rewrites:
                for rewritten in staged_rewrites[case['convo_id']]['turns']:
                    original_text = next(turn for turn in original['turns']
                                         if turn.get('turn_count') == rewritten['turn_count'])['utterance']
                    edited_turn = next(turn for turn in case['turns']
                                       if turn.get('turn_count') == rewritten['turn_count'])
                    if edited_turn['utterance'] == original_text:
                        edited_turn['utterance'] = rewritten['utterance']
        elif item and item['decision'] == 'keep' and case['convo_id'] in staged_rewrites:
            case = copy.deepcopy(case)
            for rewritten in staged_rewrites[case['convo_id']]['turns']:
                next(turn for turn in case['turns']
                     if turn.get('turn_count') == rewritten['turn_count'])['utterance'] = rewritten['utterance']
        output.append(mechanical_repairs(case))
    candidate_audit = audit_corpus(output)
    if candidate_audit['issue_counts'].get('hard'):
        raise SystemExit('applied round would leave hard audit failures')
    if not args.dry_run:
        backup_corpus(f"round_{manifest['round']}")
        write_cases(TRAIN, output)
        manifest['status'] = 'applied'
        manifest['applied_at'] = datetime.now().isoformat()
        write_json(CURRENT_ROUND, manifest)
        ledger = load_ledger()
        for round_entry in ledger['rounds']:
            if round_entry['round'] == manifest['round']:
                round_entry['status'] = 'applied'
        if manifest.get('generalized_feedback'):
            ledger['generalized_feedback'].append({'round': manifest['round'],
                                                   'text': manifest['generalized_feedback']})
        write_json(LEDGER_PATH, ledger)
    log.info('%s round %s: %d cases remain', 'checked' if args.dry_run else 'applied',
             manifest['round'], len(output))


def run_close_round(args):
    manifest = load_json(CURRENT_ROUND, None)
    ledger = load_ledger()
    if not manifest or manifest.get('status') != 'open':
        raise SystemExit('no open curation round')
    resolved = [item for item in manifest['cases']
                if item.get('decision') in {'keep', 'fix', 'delete'}]
    unresolved = [item for item in manifest['cases'] if item not in resolved]
    if unresolved and not args.discard_unreviewed:
        raise SystemExit(f"round has {len(unresolved)} unresolved cases; pass --discard-unreviewed")
    if not resolved:
        raise SystemExit('cannot close a round with no completed reviews')
    manifest['cases'] = resolved
    manifest['generalized_feedback'] = args.generalized_feedback
    manifest['closed_early_at'] = datetime.now().isoformat()
    manifest['discarded_unreviewed_ids'] = [item['convo_id'] for item in unresolved]
    for round_entry in ledger['rounds']:
        if round_entry['round'] == manifest['round']:
            round_entry['allocated'] = len(resolved)
            round_entry['completed'] = len(resolved)
    write_json(CURRENT_ROUND, manifest)
    write_json(LEDGER_PATH, ledger)
    log.info('closed round %s queue at %d completed reviews; discarded %d unreviewed cases',
             manifest['round'], len(resolved), len(unresolved))


def coverage_satisfied(cases: list[dict]) -> bool:
    facets = [case_facets(case) for case in cases]
    flows = {flow for item in facets for flow in item['flows']}
    topics = {item['topic'] for item in facets if item['topic']}
    ambiguity = {level for item in facets for level in item['ambiguities']}
    return (DOMAIN_FLOWS - {'schedule'}).issubset(flows) and len(topics) >= 16 and (
        AMBIGUITY_LEVELS.issubset(ambiguity)) and any(item['planning'] for item in facets)


def deletion_pressure(report: dict) -> float:
    weights = {'too_many_parts': 8, 'comma_fragmentation': 6, 'repeated_phrase': 5,
               'agent_voice': 2, 'trajectory': 4, 'legacy_fixture': 1,
               'obsolete_flow': 0}
    pressure = sum(weights.get(issue['code'], 3) for issue in report['issues'])
    if report['cohort'] == 'new':
        pressure += 2
    return pressure


def run_propose_deletions(args):
    cases = load_cases()
    reports = {item['convo_id']: item for item in audit_corpus(cases)['cases']}
    manifest = load_json(CURRENT_ROUND, None)
    if not manifest or manifest.get('status') != 'open':
        raise SystemExit('no open curation round')
    decisions = {item['convo_id']: item.get('decision') for item in manifest['cases']}
    forced = {convo_id for convo_id, decision in decisions.items() if decision == 'delete'}
    protected = {convo_id for convo_id, decision in decisions.items() if decision in {'keep', 'fix'}}
    ranked = sorted((case for case in cases if case['convo_id'] not in protected | forced),
                    key=lambda case: (deletion_pressure(reports[case['convo_id']]),
                                      reports[case['convo_id']]['cohort'] == 'new'), reverse=True)
    deleted = set(forced)
    for candidate in ranked:
        if len(deleted) >= args.count:
            break
        proposed = deleted | {candidate['convo_id']}
        remaining = [case for case in cases if case['convo_id'] not in proposed]
        if coverage_satisfied(remaining):
            deleted.add(candidate['convo_id'])
    if len(deleted) < args.count:
        raise SystemExit(f'could select only {len(deleted)} coverage-safe deletions')
    manifest['automatic_deletions'] = sorted(deleted - forced)
    manifest['deletion_summary'] = {
        'total': len(deleted), 'human': sorted(forced),
        'automatic': [{'convo_id': convo_id,
                       'pressure': deletion_pressure(reports[convo_id]),
                       'issues': [issue['code'] for issue in reports[convo_id]['issues']]}
                      for convo_id in sorted(deleted - forced)],
    }
    write_json(CURRENT_ROUND if not args.dry_run else REPORT / 'curation_deletion_preview.json', manifest)
    log.info('%s %d deletions (%d human, %d automatic)',
             'proposed' if args.dry_run else 'saved', len(deleted), len(forced), len(deleted - forced))


def run_import_decisions(args):
    payload = json.loads(Path(args.file).read_text())
    manifest = load_json(CURRENT_ROUND, None)
    ledger = load_ledger()
    cases = {case['convo_id']: case for case in load_cases()}
    if not manifest or manifest.get('status') != 'open':
        raise SystemExit('no open curation round')
    items = {item['convo_id']: item for item in manifest['cases']}
    for decision in payload['decisions']:
        convo_id = decision['convo_id']
        if convo_id not in items:
            raise SystemExit(f'{convo_id} is not in the open round')
        item = items[convo_id]
        choice = decision['decision']
        if choice not in {'keep', 'fix', 'delete'}:
            raise SystemExit(f'{convo_id} has invalid decision {choice!r}')
        item['decision'] = choice
        item['correction'] = decision.get('correction', '')
        if choice == 'fix':
            edited = copy.deepcopy(cases[convo_id])
            merge_values(edited, decision.get('case_edits', {}))
            turns = {turn['turn_count']: turn for turn in edited['turns']}
            for turn_edit in decision.get('turn_edits', []):
                merge_values(turns[turn_edit['turn_count']], turn_edit['fields'])
            item['edited_case'] = edited
        else:
            item['edited_case'] = None
        if not any(event['round'] == manifest['round'] and event['convo_id'] == convo_id
                   for event in ledger['events']):
            if len(ledger['events']) >= ledger['budget']:
                raise SystemExit('human review budget is exhausted')
            ledger['events'].append({'round': manifest['round'], 'convo_id': convo_id,
                                     'reviewed_at': datetime.now().isoformat()})
    completed = sum(item.get('decision') in {'keep', 'fix', 'delete'} for item in manifest['cases'])
    for round_entry in ledger['rounds']:
        if round_entry['round'] == manifest['round']:
            round_entry['completed'] = completed
    write_json(CURRENT_ROUND, manifest)
    write_json(LEDGER_PATH, ledger)
    log.info('imported %d decisions; %d review events remain', len(payload['decisions']),
             ledger['budget'] - len(ledger['events']))


def coverage_keys(report: dict) -> set[tuple]:
    facets = report['facets']
    keys = {('flow', flow) for flow in facets['flows']}
    keys.add(('topic', facets['topic']))
    keys.update(('ambiguity', level) for level in facets['ambiguities'])
    if facets['planning']:
        keys.add(('planning', True))
    return keys


def run_select(args):
    cases = load_cases()
    audit = audit_corpus(cases)
    reports = {item['convo_id']: item for item in audit['cases']}
    scores = load_scores()
    feedback = feedback_map()
    ranked = sorted(cases, key=lambda case: quality_score(reports[case['convo_id']],
                                                          scores.get(case['convo_id']),
                                                          feedback.get(case['convo_id'])), reverse=True)
    required = {('flow', flow) for flow in DOMAIN_FLOWS}
    required |= {('ambiguity', level) for level in AMBIGUITY_LEVELS}
    required.add(('planning', True))
    selected = []
    covered = set()
    for key in sorted(required, key=str):
        candidate = next((case for case in ranked if key in coverage_keys(reports[case['convo_id']])
                          and case not in selected), None)
        if candidate:
            selected.append(candidate)
            covered |= coverage_keys(reports[candidate['convo_id']])
    represented_topics = {case.get('topic', '') for case in selected}
    for case in ranked:
        topic = case.get('topic', '')
        if len(represented_topics) >= 16:
            break
        if topic and topic not in represented_topics and case not in selected:
            selected.append(case)
            represented_topics.add(topic)
    for case in ranked:
        if case not in selected and len(selected) < args.target:
            selected.append(case)
    payload = {'target': args.target, 'selected_ids': [case['convo_id'] for case in selected[:args.target]],
               'deleted_ids': [case['convo_id'] for case in cases if case not in selected[:args.target]],
               'missing_coverage': [list(key) for key in sorted(required - covered, key=str)]}
    write_json(SELECTION_PATH, payload)
    log.info('selected %d; proposed %d deletions; missing coverage=%d', len(payload['selected_ids']),
             len(payload['deleted_ids']), len(payload['missing_coverage']))


def exact_part_targets(turn_count: int) -> list[int]:
    raw = [turn_count * ratio for ratio in TARGET_PART_RATIOS]
    counts = [int(value) for value in raw]
    for index in sorted(range(4), key=lambda item: raw[item] - counts[item], reverse=True)[:turn_count-sum(counts)]:
        counts[index] += 1
    return counts


def run_prepare_revoice(args):
    cases = load_cases()
    present = {case['convo_id'] for case in cases}
    missing = sorted(CURATED_DELETIONS - present)
    if missing:
        raise SystemExit(f'curated deletion ids are missing: {missing}')
    retained = [case for case in cases if case['convo_id'] not in CURATED_DELETIONS]
    if len(retained) != TARGET_SIZE:
        raise SystemExit(f'expected {TARGET_SIZE} retained cases, found {len(retained)}')
    if not coverage_satisfied(retained):
        raise SystemExit('curated deletion set fails flow/topic/plan/ambiguity coverage')
    turns = []
    for case in retained:
        for turn in case.get('turns', []):
            if turn.get('role') == 'user':
                turns.append({'convo_id': case['convo_id'], 'turn_count': turn['turn_count'],
                              'utterance': turn['utterance'], 'current_parts': estimated_parts(turn['utterance']),
                              'tokens': len(re.findall(r"[A-Za-z0-9']+", turn['utterance']))})
    counts = exact_part_targets(len(turns))
    # Preserve the natural complexity ordering: the simplest turns are merged to one move,
    # while the few warning-level turns are reserved for genuinely verbose requests.
    ordered = sorted(turns, key=lambda item: (item['current_parts'], item['tokens'],
                                              item['convo_id'], item['turn_count']))
    targets = [part for part, count in enumerate(counts, 1) for _ in range(count)]
    for item, target in zip(ordered, targets):
        item['target_parts'] = target
    by_key = {(item['convo_id'], item['turn_count']): item for item in ordered}
    plan_cases = []
    for case in retained:
        planned = [by_key[(case['convo_id'], turn['turn_count'])]
                   for turn in case['turns'] if turn.get('role') == 'user']
        plan_cases.append({'convo_id': case['convo_id'], 'turns': planned})
    manifest = load_json(CURRENT_ROUND, {})
    if manifest.get('status') == 'open':
        manifest['status'] = 'superseded'
        manifest['superseded_at'] = datetime.now().isoformat()
        manifest['superseded_reason'] = 'corpus-wide fragmentation pass replaced the preliminary queue'
        write_json(CURRENT_ROUND, manifest)
        ledger = load_ledger()
        for round_item in ledger['rounds']:
            if round_item['round'] == manifest.get('round') and round_item['status'] == 'open':
                round_item['status'] = 'superseded'
                round_item['completed'] = 0
        write_json(LEDGER_PATH, ledger)
    write_json(SELECTION_PATH, {'target': TARGET_SIZE,
                                'selected_ids': [case['convo_id'] for case in retained],
                                'deleted_ids': sorted(CURATED_DELETIONS), 'missing_coverage': []})
    write_json(REVOICE_PLAN_PATH, {'created_at': datetime.now().isoformat(),
                                   'target_counts': dict(zip(['1', '2', '3', '4'], counts)),
                                   'case_count': len(retained), 'turn_count': len(turns),
                                   'cases': plan_cases})
    if REVOICE_RESULTS_PATH.exists():
        case_map = {case['convo_id']: case for case in retained}
        plan_map = {case['convo_id']: case for case in plan_cases}
        compatible = []
        for result in load_revoice_results().values():
            convo_id = result['convo_id']
            if convo_id not in case_map:
                continue
            parsed = RevoicedCase.model_validate(result)
            if not validate_revoice(case_map[convo_id], plan_map[convo_id], parsed):
                compatible.append(result)
        REVOICE_RESULTS_PATH.write_text(''.join(json.dumps(result, ensure_ascii=False) + '\n'
                                                for result in compatible))
        log.info('retained %d compatible prior rewrites', len(compatible))
    log.info('prepared %d retained cases and %d turns with targets %s', len(retained), len(turns), counts)


def revoice_prompt(case: dict, planned: dict, prior_error: str = '') -> str:
    targets = [{'turn_count': turn['turn_count'], 'target_parts': turn['target_parts']}
               for turn in planned['turns']]
    return f"""Rewrite every USER utterance in this Hugo evaluation conversation.

The rewrite must preserve the exact request, referents, slots, flow, ambiguity, persona, and conversation
continuity. Do not alter agent turns or structured labels. Minimize short punchy fragments by merging and
extending existing ideas into natural connected sentences. Every utterance should normally contain at least
11 word tokens. Do not pad with generic claims, stock transitions, or repeated phrases.

A part is an independent conversational move. For this controlled pass, realize each part as exactly one
complete developed sentence and use no commas, semicolons, colons, dashes, parentheses, or abbreviations with
periods. Therefore a one-part turn is one sentence with at least 11 words and no internal punctuation while a
three-part turn is exactly three complete sentences with at least 11 words total. Four parts is reserved for
the few deliberately verbose turns. Never produce five parts. Connect ideas within sentences using words such
as "because" or "while" or "and" without inserting a comma. Do not use clipped fragments.

Return every user turn exactly once and keep each original turn_count.
TARGETS: {json.dumps(targets)}
PRIOR VALIDATION ERROR: {prior_error or 'none'}
CASE: {json.dumps(case, ensure_ascii=False)}
"""


def load_revoice_results() -> dict:
    if not REVOICE_RESULTS_PATH.exists():
        return {}
    return {item['convo_id']: item for item in
            (json.loads(line) for line in REVOICE_RESULTS_PATH.read_text().splitlines() if line.strip())}


def validate_revoice(case: dict, planned: dict, result: RevoicedCase) -> str:
    expected = {turn['turn_count']: turn['target_parts'] for turn in planned['turns']}
    received = {turn.turn_count: turn.utterance.strip() for turn in result.turns}
    if set(received) != set(expected):
        return 'turn counts do not match the requested user turns'
    for turn_count, target in expected.items():
        utterance = received[turn_count]
        actual = estimated_parts(utterance)
        words = len(re.findall(r"[A-Za-z0-9']+", utterance))
        if actual != target:
            return f'turn {turn_count} has {actual} mechanically counted parts, target {target}'
        if actual >= 5:
            return f'turn {turn_count} has a forbidden five-plus parts'
        if words < 8:
            return f'turn {turn_count} has only {words} word tokens; extend it naturally to at least 8'
        if utterance.count(',') >= 3 and not comma_list(utterance):
            return f'turn {turn_count} has too many non-list commas'
    return ''


def revoice_turn_prompt(case: dict, planned_turn: dict, prior_error: str = '') -> str:
    turn_count = planned_turn['turn_count']
    index = next(index for index, turn in enumerate(case['turns']) if turn.get('turn_count') == turn_count)
    context = case['turns'][max(0, index - 2):min(len(case['turns']), index + 3)]
    target = planned_turn['target_parts']
    if planned_turn.get('retained_parts'):
        return f"""Rewrite one USER utterance after randomly selected conversational acts were removed.

Express every RETAINED ACT and none of the REMOVED ACTS. Preserve the retained request, referents, slots,
flow, ambiguity, persona, and continuity. Reconstruct the survivors as one natural user response with normal
connectors, contractions, punctuation, and light grammatical repair. Do not mechanically concatenate the
standalone split strings and do not turn them into clipped individual sentences. Maintain or increase natural
utterance length when possible, but never pad with generic claims, repeated constraints, or stock transitions.

Example A:
Original: "Yeah, that's exactly what I want, so go ahead and publish it."
Retain: ["Yeah", "That's exactly what I want", "Publish it"]
Good: "Yeah, that's exactly what I want, publish it."
Bad: "Yeah. That's exactly what I want. Publish it."

Example B:
Original: "Yeah, that's exactly what I want, so go ahead and publish it."
Retain: ["That's exactly what I want", "Go ahead"]
Good: "That's exactly what I want to go ahead with!"
Bad: "That's exactly what I want. Go ahead."

The result must contain exactly {target} conversational part{'s' if target != 1 else ''}. Never use fewer than
7 word tokens. Keep 7-10 token turns as a natural minority rather than extending them with padding. Return only the natural rewritten
utterance in the requested JSON field.

ORIGINAL: {json.dumps(case['turns'][index]['utterance'], ensure_ascii=False)}
RETAINED ACTS: {json.dumps(planned_turn['retained_parts'], ensure_ascii=False)}
REMOVED ACTS: {json.dumps(planned_turn['removed_parts'], ensure_ascii=False)}
NEIGHBORING CONTEXT: {json.dumps(context, ensure_ascii=False)}
PRIOR VALIDATION ERROR: {prior_error or 'none'}
"""
    return f"""Rewrite one USER utterance from a Hugo evaluation conversation.

Preserve its exact request, referents, slots, flow, ambiguity, persona, and continuity. Merge clipped ideas
and extend them naturally without generic padding or stock phrases. Aim above 10 word tokens and never use
fewer than 8. Return only the rewritten utterance in the requested JSON field.

The utterance must contain EXACTLY {target} complete sentence{'s' if target != 1 else ''}. Each sentence is
one substantive conversational move. Use no semicolons or em dashes and use fewer than three commas unless
they form a genuine list. Do not add or remove a move merely because the original has a different count.

TARGET TURN: {json.dumps(case['turns'][index], ensure_ascii=False)}
NEIGHBORING CONTEXT: {json.dumps(context, ensure_ascii=False)}
PRIOR VALIDATION ERROR: {prior_error or 'none'}
"""


def run_revoice_turns(args):
    from backend.components import prompt_engineer

    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    cases = {case['convo_id']: case for case in load_cases()}
    plan = load_json(REVOICE_PLAN_PATH, {})
    completed = load_revoice_results()
    failed_ids = {item['convo_id'] for item in
                  (json.loads(line) for line in REVOICE_ERRORS_PATH.read_text().splitlines())
                  if item.get('action') == 'replace_case'} \
        if REVOICE_ERRORS_PATH.exists() else set()
    requested_ids = set(args.ids.split(',')) if args.ids else None
    requested_keys = set(args.turn_keys.split(',')) if args.turn_keys else None
    for planned in plan.get('cases', []):
        convo_id = planned['convo_id']
        if convo_id in failed_ids:
            continue
        if requested_ids is not None and convo_id not in requested_ids:
            continue
        rewritten = [RevoicedTurn.model_validate(turn)
                     for turn in completed.get(convo_id, {}).get('turns', [])]
        completed_turns = {turn.turn_count for turn in rewritten}
        failed = ''
        for planned_turn in planned['turns']:
            key = f"{convo_id}:{planned_turn['turn_count']}"
            if planned_turn['turn_count'] in completed_turns or (
                    requested_keys is not None and key not in requested_keys):
                continue
            prior_error = ''
            accepted = None
            for attempt in range(3):
                candidate = engineer(revoice_turn_prompt(cases[convo_id], planned_turn, prior_error),
                                     task='skill', tier='high', family='together',
                                     max_tokens=512, schema=RevoicedUtterance)
                probe = RevoicedCase(convo_id=convo_id,
                                     turns=[RevoicedTurn(turn_count=planned_turn['turn_count'],
                                                        utterance=candidate.utterance)])
                one_plan = {'turns': [planned_turn]}
                if planned_turn.get('retained_parts'):
                    utterance = candidate.utterance.strip()
                    words = len(semantic_tokens(utterance))
                    prior_error = ''
                    if words < 7:
                        prior_error = f'only {words} word tokens; reconstruct a natural utterance with at least 7'
                    elif utterance == planned_turn.get('source_utterance'):
                        prior_error = 'the removed acts are still present because the original was returned unchanged'
                    elif BANNED.search(utterance):
                        prior_error = 'the rewrite contains a banned corpus phrase'
                    elif '\u2014' in utterance:
                        prior_error = 'the rewrite contains a forbidden em dash'
                    else:
                        edited = copy.deepcopy(cases[convo_id])
                        edited_turn = next(turn for turn in edited['turns']
                                           if turn.get('turn_count') == planned_turn['turn_count'])
                        edited_turn['utterance'] = utterance
                        try:
                            split = engineer(semantic_turn_prompt(edited, edited_turn), task='skill',
                                             tier='high', family='together', max_tokens=512,
                                             schema=SemanticTurnParts)
                        except (ValueError, json.JSONDecodeError):
                            prior_error = 'the semantic validation split was unparseable'
                        else:
                            if (not split.parts or not all(part.strip() for part in split.parts)
                                    or not semantic_split_faithful(utterance, split.parts)):
                                prior_error = 'the semantic validation split was not source-faithful'
                            elif len(split.parts) != planned_turn['target_parts']:
                                prior_error = (f'the reconstruction has {len(split.parts)} conversational parts; '
                                               f"target {planned_turn['target_parts']}")
                else:
                    prior_error = validate_revoice(cases[convo_id], one_plan, probe)
                if not prior_error:
                    accepted = probe.turns[0]
                    break
                log.warning('%s T%s attempt %d: %s', convo_id, planned_turn['turn_count'],
                            attempt + 1, prior_error)
            if accepted is None:
                failed = f"T{planned_turn['turn_count']}: {prior_error}"
                break
            rewritten.append(accepted)
        if failed:
            if convo_id not in failed_ids:
                with REVOICE_ERRORS_PATH.open('a') as error_file:
                    error_file.write(json.dumps({'convo_id': convo_id, 'error': failed,
                                                 'action': 'replace_case'}) + '\n')
                failed_ids.add(convo_id)
            continue
        if not rewritten or set(turn.turn_count for turn in rewritten) == completed_turns:
            continue
        result = RevoicedCase(convo_id=convo_id, turns=rewritten)
        completed[convo_id] = result.model_dump()
        REVOICE_RESULTS_PATH.write_text(''.join(json.dumps(completed[key], ensure_ascii=False) + '\n'
                                                for key in sorted(completed)))
        log.info('revoiced %s turn by turn', convo_id)


def run_repair_user_voice(args):
    from backend.components import prompt_engineer

    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    cases = load_cases()
    plan = load_json(REVOICE_PLAN_PATH, {})
    plan_map = {case['convo_id']: {turn['turn_count']: turn for turn in case['turns']}
                for case in plan['cases']}
    results = load_revoice_results()
    clauses = {}
    for case_index, case in enumerate(cases):
        for turn in case['turns']:
            if turn.get('role') != 'user':
                continue
            for clause in normalized_clauses(turn['utterance']):
                clauses.setdefault(clause, []).append((case_index, case['convo_id'], turn['turn_count']))
    repair_keys = set()
    forbidden_by_key = {}
    for clause, locations in clauses.items():
        if len(locations) < 2:
            continue
        for _, convo_id, turn_count in locations[1:]:
            key = (convo_id, turn_count)
            repair_keys.add(key)
            forbidden_by_key.setdefault(key, []).append(clause)
    for case in cases:
        for turn in case['turns']:
            if turn.get('role') == 'user' and BANNED.search(turn.get('utterance', '')):
                repair_keys.add((case['convo_id'], turn['turn_count']))
    case_map = {case['convo_id']: case for case in cases}
    for convo_id, turn_count in sorted(repair_keys):
        case = case_map[convo_id]
        planned_turn = plan_map[convo_id][turn_count]
        prior_error = ''
        accepted = None
        forbidden = forbidden_by_key.get((convo_id, turn_count), [])
        for attempt in range(3):
            extra = (f"\nDo not reuse these corpus phrases or close paraphrases: {json.dumps(forbidden)}. "
                     f"Do not use any of these banned words: load-bearing, byte-identical, delve, "
                     f"genuinely, absolutely, tighten. {prior_error}")
            candidate = engineer(revoice_turn_prompt(case, planned_turn, extra), task='skill',
                                 tier='high', family='together', max_tokens=512,
                                 schema=RevoicedUtterance)
            probe = RevoicedCase(convo_id=convo_id,
                                 turns=[RevoicedTurn(turn_count=turn_count,
                                                    utterance=candidate.utterance)])
            prior_error = validate_revoice(case, {'turns': [planned_turn]}, probe)
            if not prior_error and not BANNED.search(candidate.utterance) and not any(
                    phrase in normalized_clauses(candidate.utterance) for phrase in forbidden):
                accepted = candidate.utterance.strip()
                break
        if accepted is None:
            raise SystemExit(f'could not repair {convo_id} T{turn_count}: {prior_error}')
        result = results[convo_id]
        next(turn for turn in result['turns'] if turn['turn_count'] == turn_count)['utterance'] = accepted
        next(turn for turn in case['turns'] if turn.get('turn_count') == turn_count)['utterance'] = accepted
        log.info('repaired user voice %s T%s', convo_id, turn_count)
    REVOICE_RESULTS_PATH.write_text(''.join(json.dumps(result, ensure_ascii=False) + '\n'
                                            for result in results.values()))


def semantic_parts_prompt(case: dict) -> str:
    user_turns = [turn for turn in case['turns'] if turn.get('role') == 'user']
    return f"""Split every user utterance into conversational parts using the human rubric below.

A part is a conversational act that could serve as its own complete response. Count acts inside a sentence,
not punctuation. Acknowledgement, approval, permission, requested action, preamble, reason, repeated
constraint, and each coordinated question or command can be separate parts. A noun list remains one part.
A top-level request with a content list, chronology, style specification, purpose clause, or modifiers remains
ONE part. Split coordinated clauses only when they are independently omittable conversational moves, not when
they are participial modifiers or items in a content list. Coordinated finite commands remain separate even
when they support the same broader task. A `to` infinitive that states purpose or result stays with its
governing action. Two alternative questions joined by `or` are separate parts. A joining word such as `so`,
`and`, `but`, or `or` is NEVER a part by itself; discard the connector at the boundary. Never duplicate an
operation in two parts. A fronted dependent frame such as `Given what you summarized` is not a part because it
cannot stand alone. When both sides of `and` can be issued as complete imperatives, you MUST split them even
when they contribute to the same broader task; a shared objective does not merge two independently omittable
commands.

{SEMANTIC_PART_EXAMPLES}

Return each part as standalone wording taken from the utterance. You may remove only a joining word such as
"and", "so", or "but" and restore capitalization or terminal punctuation. Do not paraphrase, add content,
merge acts, or omit acts. part_count must equal the length of parts. Return every user turn exactly once.

CASE ID: {case['convo_id']}
USER TURNS: {json.dumps(user_turns, ensure_ascii=False)}
"""


def load_semantic_parts() -> dict:
    if not SEMANTIC_AUDIT_PATH.exists():
        return {}
    return {item['convo_id']: item for item in
            (json.loads(line) for line in SEMANTIC_AUDIT_PATH.read_text().splitlines() if line.strip())}


def semantic_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower().replace('\u2019', "'"))


def semantic_split_faithful(utterance: str, parts: list[str]) -> bool:
    source = semantic_tokens(utterance)
    split = [token for part in parts for token in semantic_tokens(part)]
    removable = {'and', 'so', 'but', 'or', 'since', 'because', 'though', 'although', 'yet'}
    source_index = 0
    for token in split:
        while source_index < len(source) and source[source_index] in removable and source[source_index] != token:
            source_index += 1
        if source_index >= len(source) or source[source_index] != token:
            return False
        source_index += 1
    return all(token in removable for token in source[source_index:])


def semantic_case_current(case: dict, split_case: dict) -> bool:
    split_turns = {turn['turn_count']: turn for turn in split_case.get('turns', [])}
    user_turns = [turn for turn in case['turns'] if turn.get('role') == 'user']
    if set(split_turns) != {turn['turn_count'] for turn in user_turns}:
        return False
    return all(split_turns[turn['turn_count']].get('source_utterance') == turn['utterance']
               and semantic_split_faithful(turn['utterance'], split_turns[turn['turn_count']]['parts'])
               for turn in user_turns)


def run_semantic_parts(args):
    from backend.components import prompt_engineer

    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    completed = load_semantic_parts() if args.resume else {}
    if not args.resume:
        SEMANTIC_AUDIT_PATH.unlink(missing_ok=True)
    for case in load_cases():
        if case['convo_id'] in completed:
            continue
        expected = {turn['turn_count'] for turn in case['turns'] if turn.get('role') == 'user'}
        accepted = None
        for attempt in range(3):
            candidate = engineer(semantic_parts_prompt(case), task='skill', tier='high',
                                 family='together', max_tokens=2048, schema=SemanticCaseParts)
            received = {turn.turn_count for turn in candidate.turns}
            valid = (candidate.convo_id == case['convo_id'] and received == expected
                     and all(turn.part_count == len(turn.parts) and turn.part_count >= 1
                             and all(part.strip() for part in turn.parts) for turn in candidate.turns))
            if valid:
                accepted = candidate
                break
            log.warning('semantic split attempt %d invalid for %s', attempt + 1, case['convo_id'])
        if accepted is None:
            raise SystemExit(f'could not split {case["convo_id"]}')
        with SEMANTIC_AUDIT_PATH.open('a') as output:
            output.write(accepted.model_dump_json() + '\n')
        log.info('split semantic parts for %s', case['convo_id'])


def semantic_turn_prompt(case: dict, turn: dict) -> str:
    index = case['turns'].index(turn)
    context = case['turns'][max(0, index - 2):min(len(case['turns']), index + 3)]
    return f"""Split one user utterance into conversational parts.

A part is a conversational act that could serve as its own complete response. Count acts inside sentences:
acknowledgement, approval, permission, requested action, preamble, reason, repeated constraint, and each
coordinated question or command can be separate parts. A noun list remains one part.
A top-level request with a content list, chronology, style specification, purpose clause, or modifiers remains
ONE part. Split coordinated clauses only when they are independently omittable conversational moves, not when
they are participial modifiers or items in a content list. Coordinated finite commands remain separate even
when they support the same broader task. A `to` infinitive that states purpose or result stays with its
governing action. Two alternative questions joined by `or` are separate parts. A joining word such as `so`,
`and`, `but`, or `or` is NEVER a part by itself; discard the connector at the boundary. Never duplicate an
operation in two parts. A fronted dependent frame such as `Given what you summarized` is not a part because it
cannot stand alone. When both sides of `and` can be issued as complete imperatives, you MUST split them even
when they contribute to the same broader task; a shared objective does not merge two independently omittable
commands.

{SEMANTIC_PART_EXAMPLES}

Return standalone wording taken from the utterance. You may remove only joining words and restore capitalization
or terminal punctuation. Every other source word must appear exactly once, in its original order, across the
parts. Keep dependent frames, modifiers, reasons, and purpose phrases attached to their governing act; never
drop them merely because they cannot stand alone. Do not paraphrase, duplicate, merge, omit, or add wording.
part_count must equal len(parts). Leave source_utterance as an empty string; the caller records it exactly.

TURN: {json.dumps(turn, ensure_ascii=False)}
LOCAL CONTEXT: {json.dumps(context, ensure_ascii=False)}
"""


def run_semantic_parts_turns(args):
    from backend.components import prompt_engineer

    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    if args.restart:
        SEMANTIC_AUDIT_PATH.unlink(missing_ok=True)
        SEMANTIC_FAILURES_PATH.unlink(missing_ok=True)
    completed = load_semantic_parts()
    failures = {item['convo_id']: item for item in
                (json.loads(line) for line in SEMANTIC_FAILURES_PATH.read_text().splitlines())} \
        if SEMANTIC_FAILURES_PATH.exists() else {}
    for case in load_cases():
        if case['convo_id'] in completed and semantic_case_current(case, completed[case['convo_id']]):
            continue
        if case['convo_id'] in failures:
            continue
        splits = []
        case_failed = False
        for turn in case['turns']:
            if turn.get('role') != 'user':
                continue
            accepted = None
            for attempt in range(3):
                try:
                    candidate = engineer(semantic_turn_prompt(case, turn), task='skill', tier='high',
                                         family='together', max_tokens=512, schema=SemanticTurnParts)
                except (ValueError, json.JSONDecodeError) as error:
                    log.warning('%s T%s semantic attempt %d unparseable: %s', case['convo_id'],
                                turn['turn_count'], attempt + 1, error)
                    continue
                if (candidate.parts and all(part.strip() for part in candidate.parts)
                        and semantic_split_faithful(turn['utterance'], candidate.parts)):
                    candidate.turn_count = turn['turn_count']
                    candidate.part_count = len(candidate.parts)
                    candidate.source_utterance = turn['utterance']
                    accepted = candidate
                    break
                log.warning('%s T%s semantic attempt %d invalid: %s', case['convo_id'],
                            turn['turn_count'], attempt + 1, candidate.parts)
            if accepted is None:
                failure = {'convo_id': case['convo_id'], 'turn_count': turn['turn_count'],
                           'utterance': turn['utterance'], 'attempts': 3, 'action': 'replace_case'}
                with SEMANTIC_FAILURES_PATH.open('a') as output:
                    output.write(json.dumps(failure, ensure_ascii=False) + '\n')
                failures[case['convo_id']] = failure
                log.error('marked %s for replacement after three failed splits at T%s',
                          case['convo_id'], turn['turn_count'])
                case_failed = True
                break
            splits.append(accepted)
        if case_failed:
            continue
        result = SemanticCaseParts(convo_id=case['convo_id'], turns=splits)
        completed[case['convo_id']] = result.model_dump()
        SEMANTIC_AUDIT_PATH.write_text(''.join(json.dumps(completed[convo_id], ensure_ascii=False) + '\n'
                                               for convo_id in sorted(completed)))
        log.info('split semantic parts turn by turn for %s', case['convo_id'])


def run_calibrate_semantic_parts(args):
    from backend.components import prompt_engineer

    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    tests = [
        ("I'm happy with that outline, so go ahead and turn it into a full draft now.", 3),
        ("Yeah, that's exactly what I want, so go ahead and publish it.", 4),
        ("What have I already written about overnight trains? Pull the closest pieces, since the ending should earn its conclusion.", 3),
        ("Before we go any further, how long is the overnight trains draft and how many sections does it have?", 2),
        ("Compare that draft against A Field Note on Overnight Trains and tell me where their structures diverge. The reader should reach the central claim early. That pacing constraint should carry through.", 4),
        ("The thread runs through fares, sleep quality, and city-center arrivals. Let the section order follow that logic. The ending should tie those threads together. Carry that constraint through every section.", 4),
        ("Reading through the full draft now, does the whole thing hold together as one voice, or does the loopholes section drift away from the rest?", 3),
        ("Pull the closest pieces that I have already written about tool-call traces.", 1),
        ("Draft an outline based on the playbook note.", 1),
        ("Draft the post beginning with gaslight-era houses, moving through Edison's grids and household wiring, and ending with what changed for families.", 1),
        ("That plan works. Pull the inventor sources as quickly as you can.", 2),
        ("Much better, but please clean up the duplicated content throughout the post.", 2),
        ("Do a full voice pass across the piece and match the register I use in my other energy posts.", 2),
        ("Summarize the Edison note on Menlo Park and pull out the key points worth using.", 2),
        ("Given what you summarized about Edison, how do his note and Swan's note disagree on who deserves credit?", 1),
    ]
    failures = []
    for index, (utterance, expected) in enumerate(tests, 1):
        turn = {'turn_count': index, 'role': 'user', 'utterance': utterance}
        case = {'turns': [turn]}
        candidate = None
        for attempt in range(3):
            try:
                proposed = engineer(semantic_turn_prompt(case, turn), task='skill', tier='high',
                                    family='together', max_tokens=512, schema=SemanticTurnParts)
            except (ValueError, json.JSONDecodeError) as error:
                log.warning('calibration %02d attempt %d unparseable: %s', index, attempt + 1, error)
                continue
            if (proposed.parts and all(part.strip() for part in proposed.parts)
                    and semantic_split_faithful(utterance, proposed.parts)):
                candidate = proposed
                break
            log.warning('calibration %02d attempt %d failed fidelity', index, attempt + 1)
        if candidate is None:
            raise SystemExit(f'calibration {index} returned no faithful split')
        actual = len(candidate.parts)
        log.info('calibration %02d expected=%d actual=%d %s', index, expected, actual, utterance)
        if actual != expected:
            failures.append({'index': index, 'utterance': utterance, 'expected': expected,
                             'actual': actual, 'parts': candidate.parts})
    if failures:
        print(json.dumps({'passed': len(tests) - len(failures), 'total': len(tests),
                          'failures': failures}, indent=2, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps({'passed': len(tests), 'total': len(tests)}, indent=2))


def run_trim_parts(args):
    import random
    from itertools import combinations

    cases = load_cases()
    semantic = load_semantic_parts()
    failures = {item['convo_id'] for item in
                (json.loads(line) for line in SEMANTIC_FAILURES_PATH.read_text().splitlines())} \
        if SEMANTIC_FAILURES_PATH.exists() else set()
    missing = sorted({case['convo_id'] for case in cases} - set(semantic) - failures)
    if missing:
        raise SystemExit(f'semantic part audit is incomplete: {missing[:8]}')
    current_round = load_json(CURRENT_ROUND, {})
    protected_keys = set()
    if current_round.get('status') == 'applied':
        round_ids = {item['convo_id'] for item in current_round.get('cases', [])}
        for convo_id, result in load_revoice_results().items():
            if convo_id in round_ids:
                protected_keys |= {(convo_id, turn['turn_count']) for turn in result['turns']}
        for item in current_round.get('cases', []):
            if not item.get('edited_case'):
                continue
            original = {turn['turn_count']: turn for turn in item['case']['turns']}
            for turn in item['edited_case']['turns']:
                if turn.get('role') == 'user' and turn['utterance'] != original[turn['turn_count']]['utterance']:
                    protected_keys.add((item['convo_id'], turn['turn_count']))
    flow_words = {
        'find': ('find', 'search', 'pull', 'surface', 'retrieve', 'look for'),
        'inspect': ('inspect', 'read', 'check', 'how long', 'how many', 'tell me'),
        'summarize': ('summarize', 'condense', 'boil', 'recap'),
        'compare': ('compare', 'side by side', 'differ', 'diverge', 'against'),
        'outline': ('outline', 'structure', 'sections', 'map', 'organize', 'shape'),
        'compose': ('draft', 'prose', 'write the post', 'first draft'),
        'refine': ('move', 'reorder', 'outline', 'section', 'change'),
        'brainstorm': ('brainstorm', 'angles', 'ideas', 'directions'),
        'rework': ('rebuild', 'rework', 'revise', 'fix', 'change'),
        'write': ('write', 'replace', 'add', 'remove', 'cut', 'split', 'fill', 'loosen', 'soften'),
        'audit': ('audit', 'review', 'read through', 'sound', 'voice', 'consistent', 'flag'),
        'propose': ('propose', 'options', 'ways', 'alternatives', 'fill', 'bridge'),
        'release': ('publish', 'release', 'push live'),
        'schedule': ('schedule', 'publish', 'release'),
        'cite': ('cite', 'source', 'back up', 'evidence'),
    }
    entries = []
    for case in cases:
        if case['convo_id'] in failures:
            continue
        turns = {turn['turn_count']: turn for turn in semantic[case['convo_id']]['turns']}
        for turn in case['turns']:
            if turn.get('role') == 'user':
                split = turns[turn['turn_count']]
                flows = [item['flow'] for item in (turn.get('labels') or {}).get('stack', [])]
                entries.append({'convo_id': case['convo_id'], 'turn_count': turn['turn_count'],
                                'source_utterance': turn['utterance'], 'parts': split['parts'],
                                'current': split['part_count'], 'flows': flows})
    rng = random.Random(args.seed)
    probabilities = {2: 0.52, 3: 0.70, 4: 0.30}
    choices = {3: ([1, 2], [0.70, 0.30]),
               4: ([1, 2, 3], [0.60, 0.30, 0.10]),
               5: ([1, 2, 3, 4], [0.60, 0.30, 0.09, 0.01])}
    current = Counter(entry['current'] for entry in entries)
    observed = Counter()
    planned = []
    rng.shuffle(entries)
    for entry in entries:
        count = entry['current']
        target = count
        if (entry['convo_id'], entry['turn_count']) in protected_keys:
            pass
        elif count >= 5:
            target = rng.choices(*choices[5], k=1)[0]
        elif count in probabilities and rng.random() < probabilities[count]:
            target = 1 if count == 2 else rng.choices(*choices[count], k=1)[0]
        if target < count:
            feasible = []
            while target < count and not feasible:
                feasible = [indices for indices in combinations(range(count), target)
                            if sum(len(semantic_tokens(entry['parts'][index])) for index in indices) >= 7]
                matching = [index for index, part in enumerate(entry['parts'])
                            if any(word in part.lower() for flow in entry['flows']
                                   for word in flow_words.get(flow, ()))]
                if matching:
                    feasible = [indices for indices in feasible if any(index in indices for index in matching)]
                elif feasible:
                    longest = max(range(count), key=lambda index: len(semantic_tokens(entry['parts'][index])))
                    feasible = [indices for indices in feasible if longest in indices]
                if not feasible:
                    target += 1
            if target == count:
                feasible = []
        entry['target_parts'] = target
        observed[target] += 1
        if target < count:
            retained = list(rng.choice(feasible))
            entry['retained_indices'] = retained
            entry['retained_parts'] = [entry['parts'][index] for index in retained]
            entry['removed_parts'] = [part for index, part in enumerate(entry['parts'])
                                      if index not in retained]
            planned.append(entry)
    total = len(entries)
    shares = {parts: observed[parts] / total for parts in range(1, 5)}
    bands = {1: (0.55, 0.65), 2: (0.25, 0.35), 3: (0.04, 0.14), 4: (0.00, 0.06)}
    if observed.get(5, 0) or any(not low <= shares[parts] <= high
                                 for parts, (low, high) in bands.items()):
        raise SystemExit(f'seed {args.seed} missed broad distribution bands: {dict(observed)}')
    cadence = {}
    for entry in entries:
        cadence.setdefault(entry['convo_id'], []).append(entry['target_parts'])
    dense_cases = sorted(convo_id for convo_id, targets in cadence.items() if min(targets) >= 3)
    if dense_cases:
        raise SystemExit(f'seed {args.seed} leaves every turn at three-plus parts in {dense_cases}')
    plan_cases = []
    for convo_id in sorted({entry['convo_id'] for entry in planned}):
        plan_cases.append({'convo_id': convo_id,
                           'turns': [entry for entry in planned if entry['convo_id'] == convo_id]})
    preview = {'created_at': datetime.now().isoformat(), 'seed': args.seed,
               'source_counts': dict(sorted(current.items())),
               'proposed_counts': dict(sorted(observed.items())),
               'changed_turns': len(planned), 'replacement_ids': sorted(failures),
               'cases': plan_cases}
    if args.dry_run:
        write_json(REPORT / 'curation_trim_preview.json', preview)
    else:
        write_json(REVOICE_PLAN_PATH, preview)
        REVOICE_RESULTS_PATH.unlink(missing_ok=True)
        REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    log.info('%s random trim plan for %d turns; changed %d; distribution %s',
             'checked' if args.dry_run else 'wrote', total, len(planned), dict(sorted(observed.items())))


def run_sanitize_revoice_plan(args):
    """Remove reviewed, replacement-bound, and context-unsafe turns from an existing trim plan."""
    plan = load_json(REVOICE_PLAN_PATH, None)
    if not plan:
        raise SystemExit('run trim-parts first')
    kept_cases = []
    removed = []
    for planned_case in plan.get('cases', []):
        convo_id = planned_case['convo_id']
        kept_turns = []
        for planned_turn in planned_case.get('turns', []):
            key = (convo_id, planned_turn['turn_count'])
            if (convo_id in PROTECTED_REVIEWED_IDS or convo_id in REPLACEMENT_DELETIONS
                    or key in UNSAFE_TRIM_KEYS):
                removed.append({'convo_id': convo_id, 'turn_count': planned_turn['turn_count']})
            else:
                kept_turns.append(planned_turn)
        if kept_turns:
            kept_cases.append({'convo_id': convo_id, 'turns': kept_turns})
    sanitized = copy.deepcopy(plan)
    sanitized['cases'] = kept_cases
    sanitized['changed_turns'] = sum(len(case['turns']) for case in kept_cases)
    sanitized['replacement_ids'] = sorted(REPLACEMENT_DELETIONS)
    sanitized['sanitized_at'] = datetime.now().isoformat()
    sanitized['removed_from_plan'] = removed
    write_json(REVOICE_PLAN_PATH, sanitized)
    REVOICE_RESULTS_PATH.unlink(missing_ok=True)
    REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    log.info('sanitized revoice plan: %d safe changes, %d removed, %d replacements',
             sanitized['changed_turns'], len(removed), len(REPLACEMENT_DELETIONS))


def run_prepare_replacements(args):
    import random

    rng = random.Random(args.seed)
    failed_revoices = {item['convo_id'] for item in
                       (json.loads(line) for line in REVOICE_ERRORS_PATH.read_text().splitlines())
                       if item.get('action') == 'replace_case'} \
        if REVOICE_ERRORS_PATH.exists() else set()
    delete_ids = set(REPLACEMENT_DELETIONS) | failed_revoices
    extra_count = len(delete_ids) - len(REPLACEMENT_SPECS)
    if extra_count > len(EXTRA_REPLACEMENT_SPECS):
        raise SystemExit(f'{extra_count} extra replacements exceed the prepared spec bank')
    replacement_specs = REPLACEMENT_SPECS + EXTRA_REPLACEMENT_SPECS[:max(0, extra_count)]
    plan_stacks = {
        13: ['outline', 'refine', 'compose'],
        14: ['rework', 'write', 'audit'],
    }
    total_turns = sum(len(spec[2]) + (index in plan_stacks)
                      for index, spec in enumerate(replacement_specs, 1))
    part_counts = ([1] * round(total_turns * 0.60)
                   + [2] * round(total_turns * 0.30))
    part_counts += [3] * (total_turns - len(part_counts))
    rng.shuffle(part_counts)
    personas = [
        'casual/neutral/plain', 'neutral/neutral/plain', 'formal/neutral/hedged',
        'neutral/skeptical/plain', 'casual/positive/blunt', 'neutral/pressured/plain',
        'formal/neutral/plain', 'casual/frustrated/blunt',
    ]
    flagged_by_batch = {}
    for batch_offset in range((len(replacement_specs) + 15) // 16):
        start = batch_offset * 16
        stop = min(start + 16, len(replacement_specs))
        flagged_by_batch[batch_offset] = rng.randrange(start, stop)
    cursor = 0
    specs = []
    for index, (topic, title, sequence, focus) in enumerate(replacement_specs, 1):
        user_turns = len(sequence) + (index in plan_stacks)
        lengths = part_counts[cursor:cursor + user_turns]
        cursor += user_turns
        batch_offset = (index - 1) // 16
        batch = f'B{13 + batch_offset:02d}'
        case_number = (index - 1) % 16 + 1
        specs.append({
            'convo_id': f'{batch}.C{case_number:02d}', 'batch': batch, 'seed': args.seed,
            'topic': topic, 'title': title, 'sequence': sequence,
            'plan_stack': plan_stacks.get(index), 'focus': focus,
            'persona': personas[(index - 1) % len(personas)],
            'target_parts': lengths, 'flagged': index - 1 == flagged_by_batch[batch_offset],
        })
    manifest = {
        'created_at': datetime.now().isoformat(), 'seed': args.seed,
        'delete_ids': sorted(delete_ids), 'specs': specs,
        'target_part_counts': dict(sorted(Counter(part_counts).items())),
    }
    write_json(REPLACEMENT_MANIFEST_PATH, manifest)
    REPLACEMENT_RESULTS_PATH.unlink(missing_ok=True)
    REPLACEMENT_ERRORS_PATH.unlink(missing_ok=True)
    log.info('prepared %d replacements with part targets %s', len(specs),
             manifest['target_part_counts'])


def replacement_prompt(spec: dict, prior_error: str = '') -> str:
    expected = []
    if spec.get('plan_stack'):
        expected.append({'kind': 'plan', 'stack': spec['plan_stack']})
    expected.extend({'kind': 'flow', 'flow': flow} for flow in spec['sequence'])
    catalog = {flow: {'intent': FLOW_ONTOLOGY[flow]['intent'],
                      'dax': FLOW_ONTOLOGY[flow]['dax'],
                      'actions': ACTION_MAP[flow]}
               for flow in set(spec['sequence']) | set(spec.get('plan_stack') or [])}
    return f"""Write one hand-quality Hugo evaluation conversation from this compiled replacement spec.

This corpus is testing realistic blog-writing work. The main structural goal is repeated independent work:
each consecutive refine turn makes a DIFFERENT outline change, and each consecutive write or rework turn fixes
a DIFFERENT passage or structural problem. Never collapse those turns or merely repeat a request.

For propose, the normal use case is in-filling. Offer 2-3 short options for a one- or two-word blank already
present as `<fill>` or `<fill in>`, then let a later write turn insert the selected option. When the focus says
frontend-grounded, at least one user request should naturally be as simple as "Can you fill in the blanks?"
because its turn slots carry the selected snippet and blank context as JSON. Do not turn propose into writing a
whole paragraph.

Human voice rules:
- Every user turn must be natural and at least 7 word tokens. Avoid short punchy fragments and stock phrases.
- Realize the requested semantic-part vector exactly. A part is an independently omittable conversational act,
  not a comma, modifier, reason, content list, chronology, or dependent frame. Never exceed 3 parts.
- Most turns should be one connected, average-length request. Commas and connectors are welcome.
- Do not repeat sentence templates or phrases. No em dashes, ellipses, AI padding, or banned words:
  load-bearing, byte-identical, delve, genuinely, absolutely, tighten.
- Imply the flow naturally rather than naming internal commands. Use the title once at most, then anaphora.
- Agent replies are complete natural sentences that report what happened and stop. No unsolicited next-step
  offers, and no telegraphic "Done" or "Drafted" replies.

Data rules:
- Alternate user and agent, starting with user. Include a closing agent turn after the final user; it may omit
  utterance but must contain actions.
- Every normal user turn has labels {{intent, stack:[{{flow,dax}}]}}, slots, and ambiguity:null. Intent and dax
  must come from the catalog. The following agent actions must exactly equal that flow's actions.
- A plan opener has intent Plan and the exact multi-flow stack from EXPECTED TURNS. Its following actions are
  [], its agent reply proposes the ordered plan and waits, and the next user turn naturally approves while also
  making the first concrete request in the specified sequence.
- available_data posts must use canonical objects: post_id, title, status, sections mapping headings to prose.
  Provide an existing draft when the sequence begins in Revise or find; new-draft sequences may begin with {{}}.
- generation.draws.length must exactly equal TARGET PARTS; record the given sequence, persona, and flags.
- flagged must match the spec. No verify field is needed.

SPEC: {json.dumps(spec, ensure_ascii=False)}
EXPECTED TURNS: {json.dumps(expected, ensure_ascii=False)}
FLOW CATALOG: {json.dumps(catalog, ensure_ascii=False)}
TARGET PARTS: {json.dumps(spec['target_parts'])}
PRIOR VALIDATION ERROR: {prior_error or 'none'}
"""


def validate_replacement(spec: dict, generated: GeneratedEvalCase,
                         existing_utterances: set[str]) -> str:
    case = generated.model_dump()
    if case['convo_id'] != spec['convo_id'] or case['batch'] != spec['batch']:
        return 'case identity or batch does not match the spec'
    if case['topic'] != spec['topic'] or case['title'] != spec['title']:
        return 'topic or title does not match the spec'
    if case['flagged'] != spec['flagged']:
        return 'flagged value does not match the spec'
    expected_flows = list(spec['sequence'])
    expected_users = len(expected_flows) + bool(spec.get('plan_stack'))
    if len(case['turns']) != expected_users * 2:
        return f'expected {expected_users * 2} alternating turns'
    if any(turn.get('role') != ('user' if index % 2 == 0 else 'agent')
           for index, turn in enumerate(case['turns'])):
        return 'turn roles do not alternate user and agent'
    user_index = 0
    flow_index = 0
    for index in range(0, len(case['turns']), 2):
        user = case['turns'][index]
        agent = case['turns'][index + 1]
        utterance = user.get('utterance', '').strip()
        if len(semantic_tokens(utterance)) < 7:
            return f"T{user.get('turn_count')} has fewer than 7 word tokens"
        if utterance in existing_utterances or BANNED.search(utterance) or '\u2014' in utterance:
            return f"T{user.get('turn_count')} duplicates or violates the voice rules"
        stack = (user.get('labels') or {}).get('stack', [])
        if spec.get('plan_stack') and user_index == 0:
            if (user['labels'].get('intent') != 'Plan'
                    or [item.get('flow') for item in stack] != spec['plan_stack']
                    or agent.get('actions') != []):
                return 'plan opener labels, stack, or actions are incorrect'
        else:
            flow = expected_flows[flow_index]
            flow_index += 1
            if (user.get('labels') or {}).get('intent') != FLOW_ONTOLOGY[flow]['intent']:
                return f'T{user.get("turn_count")} has the wrong intent for {flow}'
            if stack != [{'flow': flow, 'dax': FLOW_ONTOLOGY[flow]['dax']}]:
                return f'T{user.get("turn_count")} has the wrong stack for {flow}'
            if agent.get('actions') != ACTION_MAP[flow]:
                return f'T{user.get("turn_count")} has the wrong following actions for {flow}'
        if user.get('ambiguity') is not None:
            return f'T{user.get("turn_count")} has an unrequested ambiguity label'
        user_index += 1
    draws = ((case.get('generation') or {}).get('draws') or {})
    if draws.get('length') != spec['target_parts']:
        return 'generation.draws.length does not match the target parts'
    posts = (case.get('available_data') or {}).get('posts', [])
    if posts and not all(canonical_post(post) for post in posts):
        return 'available_data contains a noncanonical post fixture'
    if 'propose' in expected_flows:
        propose_turns = [case['turns'][index] for index in range(0, len(case['turns']), 2)
                         if ((case['turns'][index].get('labels') or {}).get('stack') or [{}])[0].get('flow')
                         == 'propose']
        if any(not turn.get('slots', {}).get('context') or not turn.get('slots', {}).get('source')
               for turn in propose_turns):
            return 'a propose turn is missing source or blank context grounding'
    return ''


def run_generate_replacements(args):
    from backend.components import prompt_engineer

    manifest = load_json(REPLACEMENT_MANIFEST_PATH, None)
    if not manifest:
        raise SystemExit('run prepare-replacements first')
    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    completed = {item['convo_id']: item for item in
                 (json.loads(line) for line in REPLACEMENT_RESULTS_PATH.read_text().splitlines())} \
        if args.resume and REPLACEMENT_RESULTS_PATH.exists() else {}
    existing_utterances = {turn['utterance'] for case in load_cases() for turn in case['turns']
                           if turn.get('utterance')}
    for spec in manifest['specs']:
        if spec['convo_id'] in completed:
            existing_utterances |= {turn['utterance'] for turn in completed[spec['convo_id']]['turns']
                                    if turn.get('utterance')}
            continue
        prior_error = ''
        accepted = None
        for attempt in range(3):
            try:
                candidate = engineer(replacement_prompt(spec, prior_error), task='skill', tier='high',
                                     family='together', max_tokens=args.max_tokens,
                                     schema=GeneratedEvalCase)
            except (ValueError, json.JSONDecodeError) as error:
                prior_error = f'unparseable JSON: {error}'
                continue
            normalized = candidate.model_dump()
            normalized.update({'convo_id': spec['convo_id'], 'batch': spec['batch'],
                               'topic': spec['topic'], 'title': spec['title'],
                               'persona': spec['persona'], 'flagged': spec['flagged'],
                               'use_case': ' -> '.join(spec['sequence'])})
            available = normalized.get('available_data') or {}
            if available.get('posts'):
                posts = []
                for post in available['posts']:
                    if isinstance(post, dict) and not post.get('title'):
                        post = {**post, 'title': spec['title']}
                    posts.append(normalize_post(post, spec['title']))
                available['posts'] = posts
            normalized['available_data'] = available
            normalized['generation'] = {
                'batch': spec['batch'], 'seed': spec['seed'], 'writer_model': args.model,
                'spec': (f"topic={spec['topic']} · persona={spec['persona']} · "
                         f"use_case={'->'.join(spec['sequence'])} · focus={spec['focus']}"),
                'draws': {'length': spec['target_parts'], 'flagged': spec['flagged'],
                          'sequence': spec['sequence'], 'persona': spec['persona']},
            }
            expected_user_count = len(spec['sequence']) + bool(spec.get('plan_stack'))
            if (len(normalized['turns']) == expected_user_count * 2
                    and all(turn.get('role') == ('user' if index % 2 == 0 else 'agent')
                            for index, turn in enumerate(normalized['turns']))):
                flow_index = 0
                for turn_index in range(0, len(normalized['turns']), 2):
                    user = normalized['turns'][turn_index]
                    agent = normalized['turns'][turn_index + 1]
                    user['turn_count'] = turn_index + 1
                    agent['turn_count'] = turn_index + 2
                    user['ambiguity'] = None
                    if spec.get('plan_stack') and turn_index == 0:
                        user['labels'] = {
                            'intent': 'Plan',
                            'stack': [{'flow': flow, 'dax': FLOW_ONTOLOGY[flow]['dax']}
                                      for flow in spec['plan_stack']],
                        }
                        agent['actions'] = []
                    else:
                        flow = spec['sequence'][flow_index]
                        flow_index += 1
                        user['labels'] = {
                            'intent': FLOW_ONTOLOGY[flow]['intent'],
                            'stack': [{'flow': flow, 'dax': FLOW_ONTOLOGY[flow]['dax']}],
                        }
                        agent['actions'] = ACTION_MAP[flow]
                        if flow == 'propose':
                            user.setdefault('slots', {})
                            user['slots'].setdefault('source', {
                                'post': spec['title'], 'sec': 'selected passage'})
                            user['slots'].setdefault(
                                'context', 'one- or two-word <fill> placeholder in the selected passage')
            candidate = GeneratedEvalCase.model_validate(normalized)
            prior_error = validate_replacement(spec, candidate, existing_utterances)
            if not prior_error:
                accepted = candidate.model_dump()
                break
            log.warning('%s attempt %d: %s', spec['convo_id'], attempt + 1, prior_error)
        if accepted is None:
            with REPLACEMENT_ERRORS_PATH.open('a') as output:
                output.write(json.dumps({'convo_id': spec['convo_id'], 'attempts': 3,
                                         'error': prior_error}) + '\n')
            continue
        completed[spec['convo_id']] = accepted
        existing_utterances |= {turn['utterance'] for turn in accepted['turns'] if turn.get('utterance')}
        REPLACEMENT_RESULTS_PATH.write_text(''.join(
            json.dumps(completed[convo_id], ensure_ascii=False) + '\n' for convo_id in sorted(completed)))
        log.info('generated replacement %s', spec['convo_id'])


def run_apply_replacements(args):
    manifest = load_json(REPLACEMENT_MANIFEST_PATH, None)
    if not manifest or not REPLACEMENT_RESULTS_PATH.exists():
        raise SystemExit('replacement manifest or results are missing')
    replacements = {item['convo_id']: item for item in
                    (json.loads(line) for line in REPLACEMENT_RESULTS_PATH.read_text().splitlines())}
    expected = {spec['convo_id'] for spec in manifest['specs']}
    if set(replacements) != expected:
        raise SystemExit(f'replacement results incomplete: {sorted(expected - set(replacements))}')
    output = [case for case in load_cases() if case['convo_id'] not in set(manifest['delete_ids'])]
    output.extend(replacements[convo_id] for convo_id in sorted(replacements))
    if len(output) != TARGET_SIZE or len({case['convo_id'] for case in output}) != TARGET_SIZE:
        raise SystemExit(f'replacement application would produce {len(output)} nonunique cases')
    if not args.dry_run:
        backup_corpus('replacements')
        write_cases(TRAIN, output)
    log.info('%s %d replacements; corpus size %d',
             'checked' if args.dry_run else 'applied', len(replacements), len(output))


def run_revoice(args):
    from backend.components import prompt_engineer

    if not REVOICE_PLAN_PATH.exists():
        raise SystemExit('run prepare-revoice first')
    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    cases = {case['convo_id']: case for case in load_cases()}
    plan = load_json(REVOICE_PLAN_PATH, {})
    completed = load_revoice_results() if args.resume else {}
    requested_ids = set(args.ids.split(',')) if args.ids else None
    REVOICE_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        REVOICE_RESULTS_PATH.unlink(missing_ok=True)
    for planned in plan['cases']:
        convo_id = planned['convo_id']
        if requested_ids is not None and convo_id not in requested_ids:
            continue
        if convo_id in completed:
            continue
        prior_error = ''
        result = None
        for attempt in range(3):
            try:
                candidate = engineer(revoice_prompt(cases[convo_id], planned, prior_error), task='skill',
                                     tier='high', family='together', max_tokens=args.max_tokens,
                                     schema=RevoicedCase)
                prior_error = validate_revoice(cases[convo_id], planned, candidate)
                if not prior_error:
                    result = candidate
                    break
                log.warning('%s attempt %d: %s', convo_id, attempt + 1, prior_error)
            except (ValueError, json.JSONDecodeError) as error:
                prior_error = str(error)
        if result is None:
            with REVOICE_ERRORS_PATH.open('a') as error_file:
                error_file.write(json.dumps({'convo_id': convo_id, 'error': prior_error}) + '\n')
            continue
        with REVOICE_RESULTS_PATH.open('a') as result_file:
            result_file.write(result.model_dump_json() + '\n')
        log.info('revoiced %s', convo_id)


def run_apply_revoice(args):
    plan = load_json(REVOICE_PLAN_PATH, {})
    results = load_revoice_results()
    planned = {case['convo_id']: case for case in plan.get('cases', [])}
    failed_revoices = {item['convo_id'] for item in
                       (json.loads(line) for line in REVOICE_ERRORS_PATH.read_text().splitlines())
                       if item.get('action') == 'replace_case'} \
        if REVOICE_ERRORS_PATH.exists() else set()
    replacement_ids = set(plan.get('replacement_ids', [])) | set(REPLACEMENT_DELETIONS) | failed_revoices
    missing = sorted(set(planned) - set(results) - replacement_ids)
    if missing:
        raise SystemExit(f'revoice results incomplete ({len(missing)} missing): {missing[:8]}')
    output = []
    for case in load_cases():
        if case['convo_id'] in CURATED_DELETIONS or case['convo_id'] in replacement_ids:
            continue
        rewritten = copy.deepcopy(case)
        if case['convo_id'] not in planned:
            for turn in rewritten['turns']:
                if turn.get('role') == 'user':
                    turn['utterance'] = MANUAL_UTTERANCE_REPAIRS.get(
                        (case['convo_id'], turn['turn_count']), turn['utterance'])
            output.append(rewritten)
            continue
        result = RevoicedCase.model_validate(results[case['convo_id']])
        expected_turns = {turn['turn_count'] for turn in planned[case['convo_id']]['turns']}
        if {turn.turn_count for turn in result.turns} != expected_turns:
            raise SystemExit(f"{case['convo_id']}: rewrite turn counts do not match the safe plan")
        if any(len(semantic_tokens(turn.utterance)) < 7 for turn in result.turns):
            raise SystemExit(f"{case['convo_id']}: a rewrite is below the seven-token floor")
        replacements = {turn.turn_count: turn.utterance.strip() for turn in result.turns}
        lengths = []
        for turn in rewritten['turns']:
            if turn.get('role') == 'user':
                turn['utterance'] = replacements.get(turn['turn_count'], turn['utterance'])
                turn['utterance'] = MANUAL_UTTERANCE_REPAIRS.get(
                    (case['convo_id'], turn['turn_count']), turn['utterance'])
                planned_turn = next((item for item in planned[case['convo_id']]['turns']
                                     if item['turn_count'] == turn['turn_count']), None)
                lengths.append(planned_turn['target_parts'] if planned_turn else
                               next((item['part_count'] for item in
                                     load_semantic_parts().get(case['convo_id'], {}).get('turns', [])
                                     if item['turn_count'] == turn['turn_count']),
                                    estimated_parts(turn['utterance'])))
        (((rewritten.get('generation') or {}).get('draws') or {}))['length'] = lengths
        output.append(rewritten)
    utterances = [turn['utterance'] for case in output for turn in case['turns'] if turn.get('role') == 'user']
    token_lengths = [len(re.findall(r"[A-Za-z0-9']+", utterance)) for utterance in utterances]
    if any(length < 7 for length in token_lengths):
        raise SystemExit('revoice left a user turn below the seven-token floor')
    duplicates = [text for text, count in Counter(utterances).items() if count > 1]
    if duplicates:
        raise SystemExit(f'revoice produced {len(duplicates)} duplicate utterances')
    if not args.dry_run:
        backup_corpus('revoice')
        write_cases(TRAIN, output)
    log.info('%s %d retained cases after applying safe rewrites',
             'checked' if args.dry_run else 'wrote', len(output))


def run_apply_trim_only(args):
    """Apply successful audited reductions without deleting or replacing any conversation."""
    plan = load_json(REVOICE_PLAN_PATH, {})
    planned = {case['convo_id']: case for case in plan.get('cases', [])}
    results = load_revoice_results()
    failed_ids = {item['convo_id'] for item in
                  (json.loads(line) for line in REVOICE_ERRORS_PATH.read_text().splitlines())
                  if item.get('action') == 'replace_case'} \
        if REVOICE_ERRORS_PATH.exists() else set()
    cases = load_cases()
    changed_cases = 0
    changed_turns = 0
    for case in cases:
        convo_id = case['convo_id']
        if convo_id not in planned or convo_id in failed_ids or convo_id not in results:
            continue
        planned_turns = {turn['turn_count']: turn for turn in planned[convo_id]['turns']}
        rewritten_turns = {turn['turn_count']: turn['utterance'].strip()
                           for turn in results[convo_id]['turns']}
        if set(rewritten_turns) != set(planned_turns):
            raise SystemExit(f'{convo_id}: rewrite results do not match the audited plan')
        case_turns = {turn['turn_count']: turn for turn in case['turns']
                      if turn.get('role') == 'user'}
        for turn_count, planned_turn in planned_turns.items():
            source = planned_turn.get('source_utterance')
            if source and case_turns[turn_count]['utterance'] != source:
                raise SystemExit(f'{convo_id} T{turn_count}: source changed since the audit')
            if len(semantic_tokens(rewritten_turns[turn_count])) < 7:
                raise SystemExit(f'{convo_id} T{turn_count}: rewrite is below seven tokens')
            case_turns[turn_count]['utterance'] = rewritten_turns[turn_count]
            changed_turns += 1
        lengths = (((case.get('generation') or {}).get('draws') or {}).get('length') or [])
        user_turns = [turn for turn in case['turns'] if turn.get('role') == 'user']
        if len(lengths) == len(user_turns):
            for index, turn in enumerate(user_turns):
                if turn['turn_count'] in planned_turns:
                    lengths[index] = planned_turns[turn['turn_count']]['target_parts']
        changed_cases += 1
    if len(cases) != TARGET_SIZE or len({case['convo_id'] for case in cases}) != TARGET_SIZE:
        raise SystemExit('trim-only application must preserve all 128 unique cases')
    utterances = [turn['utterance'] for case in cases for turn in case['turns']
                  if turn.get('role') == 'user']
    duplicates = [text for text, count in Counter(utterances).items() if count > 1]
    if duplicates:
        raise SystemExit(f'trim-only application would leave {len(duplicates)} duplicate user utterances')
    if not args.dry_run:
        backup_corpus('trim_only')
        write_cases(TRAIN, cases)
    log.info('%s %d audited turn reductions across %d cases; retained all %d cases',
             'checked' if args.dry_run else 'applied', changed_turns, changed_cases, len(cases))


def applied_trim_keys() -> set[tuple[str, int]]:
    plan = load_json(REVOICE_PLAN_PATH, {})
    planned = {case['convo_id']: case for case in plan.get('cases', [])}
    results = load_revoice_results()
    failed_ids = {item['convo_id'] for item in
                  (json.loads(line) for line in REVOICE_ERRORS_PATH.read_text().splitlines())
                  if item.get('action') == 'replace_case'} \
        if REVOICE_ERRORS_PATH.exists() else set()
    return {(convo_id, turn['turn_count']) for convo_id, result in results.items()
            if convo_id in planned and convo_id not in failed_ids for turn in result['turns']}


def run_prepare_full_revoice(args):
    import random
    from itertools import combinations

    rng = random.Random(args.seed)
    cases = load_cases()
    semantic = load_semantic_parts()
    applied = applied_trim_keys()
    prior_plan = load_json(REVOICE_PLAN_PATH, {})
    prior_targets = {(case['convo_id'], turn['turn_count']): turn['target_parts']
                     for case in prior_plan.get('cases', []) for turn in case['turns']}
    fixed = Counter(prior_targets[key] for key in applied)
    total_turns = sum(1 for case in cases for turn in case['turns'] if turn.get('role') == 'user')
    desired = Counter({1: round(total_turns * 0.60), 2: round(total_turns * 0.30)})
    desired[3] = total_turns - desired[1] - desired[2]
    remaining_quota = desired - fixed
    entries = []
    for case in cases:
        split_map = {turn['turn_count']: turn for turn in
                     semantic.get(case['convo_id'], {}).get('turns', [])}
        lengths = (((case.get('generation') or {}).get('draws') or {}).get('length') or [])
        user_index = 0
        for turn in case['turns']:
            if turn.get('role') != 'user':
                continue
            key = (case['convo_id'], turn['turn_count'])
            if key not in applied:
                split = split_map.get(turn['turn_count'])
                if split and split.get('source_utterance') == turn['utterance']:
                    source_parts = split['parts']
                    current_parts = split['part_count']
                else:
                    source_parts = []
                    current_parts = lengths[user_index] if user_index < len(lengths) else estimated_parts(
                        turn['utterance'])
                entries.append({
                    'convo_id': case['convo_id'], 'turn_count': turn['turn_count'],
                    'source_utterance': turn['utterance'], 'source_parts': source_parts,
                    'current_parts': max(1, current_parts), 'labels': turn.get('labels'),
                    'slots': turn.get('slots', {}), 'ambiguity': turn.get('ambiguity'),
                })
            user_index += 1
    if len(entries) != total_turns - len(applied):
        raise SystemExit('remaining utterance count does not match the applied first pass')

    def can_target(entry: dict, target: int) -> bool:
        if entry['current_parts'] < target:
            return False
        if not entry['source_parts']:
            return True
        return len(entry['source_parts']) >= target

    unassigned = list(entries)
    rng.shuffle(unassigned)
    target_three = [entry for entry in unassigned if can_target(entry, 3)]
    if len(target_three) < remaining_quota[3]:
        raise SystemExit('not enough three-part turns to meet the corpus target')
    chosen_three = set((entry['convo_id'], entry['turn_count'])
                       for entry in rng.sample(target_three, remaining_quota[3]))
    for entry in entries:
        if (entry['convo_id'], entry['turn_count']) in chosen_three:
            entry['target_parts'] = 3
    still_open = [entry for entry in entries if 'target_parts' not in entry]
    forced_one = [entry for entry in still_open if entry['current_parts'] == 1]
    if len(forced_one) > remaining_quota[1]:
        raise SystemExit('fixed one-part turns exceed the remaining one-part quota')
    for entry in forced_one:
        entry['target_parts'] = 1
    need_one = remaining_quota[1] - len(forced_one)
    eligible_one = [entry for entry in still_open
                    if 'target_parts' not in entry and can_target(entry, 1)]
    if len(eligible_one) < need_one:
        raise SystemExit('not enough reducible turns to meet the one-part target')
    for entry in rng.sample(eligible_one, need_one):
        entry['target_parts'] = 1
    for entry in entries:
        if 'target_parts' not in entry:
            if not can_target(entry, 2):
                raise SystemExit(f"{entry['convo_id']} T{entry['turn_count']} cannot realize two parts")
            entry['target_parts'] = 2
    observed = fixed + Counter(entry['target_parts'] for entry in entries)
    if observed != desired:
        raise SystemExit(f'full revoice target mismatch: {dict(observed)} != {dict(desired)}')
    for entry in entries:
        parts = entry['source_parts']
        target = entry['target_parts']
        if not parts:
            entry['retained_parts'] = []
            entry['removed_parts'] = []
            continue
        feasible = list(combinations(range(len(parts)), target))
        rng.shuffle(feasible)
        entry['candidate_subsets'] = [list(indices) for indices in feasible]
        retained = feasible[0]
        entry['retained_parts'] = [parts[index] for index in retained]
        entry['removed_parts'] = [part for index, part in enumerate(parts) if index not in retained]
    plan_cases = []
    for case in cases:
        turns = [entry for entry in entries if entry['convo_id'] == case['convo_id']]
        if turns:
            plan_cases.append({'convo_id': case['convo_id'], 'turns': turns})
    payload = {'created_at': datetime.now().isoformat(), 'seed': args.seed,
               'already_revised_turns': len(applied), 'remaining_turns': len(entries),
               'fixed_counts': dict(sorted(fixed.items())),
               'final_target_counts': dict(sorted(desired.items())),
               'retention_selected': False, 'cases': plan_cases}
    write_json(FULL_REVOICE_PLAN_PATH, payload)
    FULL_REVOICE_RESULTS_PATH.unlink(missing_ok=True)
    FULL_REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    log.info('prepared full revoice for %d remaining turns across %d cases; final targets %s',
             len(entries), len(plan_cases), dict(sorted(desired.items())))


def retention_selection_prompt(case: dict, planned: dict, prior_error: str = '') -> str:
    reductions = []
    for turn in planned['turns']:
        if not turn['source_parts'] or turn['target_parts'] >= turn['current_parts']:
            continue
        reductions.append({
            'turn_count': turn['turn_count'], 'source_utterance': turn['source_utterance'],
            'parts': list(enumerate(turn['source_parts'])), 'labels': turn['labels'],
            'slots': turn['slots'], 'ambiguity': turn['ambiguity'],
            'randomized_candidate_order': turn['candidate_subsets'],
        })
    return f"""Choose a safe randomly-prioritized subset of conversational parts for each Hugo user turn.

For each turn, inspect candidate subsets IN THE GIVEN RANDOMIZED ORDER and return the FIRST candidate that:
1. still expresses an unambiguous request matching the structured flow label;
2. retains enough grounding for the structured slots and local referents;
3. preserves authorization where the following agent performs an action;
4. does not leave only a distractor, reason, approval, negated action, or unsupported pronoun.

The retained request may be narrower than the original because independent acts are deliberately dropped.
Do not require removed secondary acts. For a multi-flow Plan label, the subset must still support the whole
decomposition. If no listed candidate is safe, set valid=false and return empty retained_indices. Use the
original zero-based indices exactly and keep reasons under 20 words.

LOCAL CASE: {json.dumps(case, ensure_ascii=False)}
REDUCTIONS: {json.dumps(reductions, ensure_ascii=False)}
PRIOR ERROR: {prior_error or 'none'}
"""


def run_select_retentions(args):
    from backend.components import prompt_engineer

    plan = load_json(FULL_REVOICE_PLAN_PATH, None)
    if not plan:
        raise SystemExit('run prepare-full-revoice first')
    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    cases = {case['convo_id']: case for case in load_cases()}
    requested_ids = set(args.ids.split(',')) if args.ids else None
    failures = []
    for planned in plan['cases']:
        convo_id = planned['convo_id']
        if requested_ids is not None and convo_id not in requested_ids:
            continue
        reductions = [turn for turn in planned['turns']
                      if turn['source_parts'] and turn['target_parts'] < turn['current_parts']]
        if not reductions:
            continue
        prior_error = ''
        accepted = None
        for attempt in range(3):
            try:
                candidate = engineer(retention_selection_prompt(cases[convo_id], planned, prior_error),
                                     task='skill', tier='high', family='together', max_tokens=2048,
                                     schema=RetentionSelection)
            except (ValueError, json.JSONDecodeError) as error:
                prior_error = f'unparseable selection: {error}'
                continue
            selected = {turn.turn_count: turn for turn in candidate.turns}
            if candidate.convo_id != convo_id or set(selected) != {turn['turn_count'] for turn in reductions}:
                prior_error = 'selection turn numbers do not match the reductions'
                continue
            invalid = []
            for turn in reductions:
                choice = selected[turn['turn_count']]
                candidates = turn['candidate_subsets']
                if not choice.valid or choice.retained_indices not in candidates:
                    invalid.append(f"T{turn['turn_count']}: {choice.reason or 'no safe subset'}")
            if invalid:
                prior_error = '; '.join(invalid[:3])
                continue
            accepted = selected
            break
        if accepted is None:
            failures.append({'convo_id': convo_id, 'error': prior_error})
            continue
        for turn in reductions:
            indices = accepted[turn['turn_count']].retained_indices
            turn['retained_parts'] = [turn['source_parts'][index] for index in indices]
            turn['removed_parts'] = [part for index, part in enumerate(turn['source_parts'])
                                     if index not in indices]
        write_json(FULL_REVOICE_PLAN_PATH, plan)
        log.info('selected safe random retentions for %s', convo_id)
    unresolved = []
    for failure in failures:
        planned = next(case for case in plan['cases'] if case['convo_id'] == failure['convo_id'])
        reductions = [turn for turn in planned['turns']
                      if turn['source_parts'] and turn['target_parts'] < turn['current_parts']]
        if any((planned['convo_id'], turn['turn_count']) not in RETENTION_OVERRIDES
               for turn in reductions):
            unresolved.append(failure)
            continue
        for turn in reductions:
            indices = RETENTION_OVERRIDES[(planned['convo_id'], turn['turn_count'])]
            turn['target_parts'] = len(indices)
            turn['retained_parts'] = [turn['source_parts'][index] for index in indices]
            turn['removed_parts'] = [part for index, part in enumerate(turn['source_parts'])
                                     if index not in indices]
        log.info('applied audited retention overrides for %s', planned['convo_id'])
    if unresolved:
        write_json(REPORT / 'curation_retention_failures.json', unresolved)
        raise SystemExit(f'{len(unresolved)} conversations have no validated retention selection')
    if requested_ids is None:
        plan['retention_selected'] = True
        final_counts = Counter(plan['fixed_counts'])
        final_counts.update(turn['target_parts'] for case in plan['cases'] for turn in case['turns'])
        plan['realized_target_counts'] = dict(sorted(final_counts.items()))
        write_json(FULL_REVOICE_PLAN_PATH, plan)
        FULL_REVOICE_RESULTS_PATH.unlink(missing_ok=True)
        FULL_REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    log.info('validated random retention subsets for %d conversations', len(plan['cases']))


def run_finalize_retentions(args):
    plan = load_json(FULL_REVOICE_PLAN_PATH, None)
    if not plan:
        raise SystemExit('run prepare-full-revoice first')
    for planned in plan['cases']:
        for turn in planned['turns']:
            key = (planned['convo_id'], turn['turn_count'])
            if key in RETENTION_OVERRIDES:
                indices = RETENTION_OVERRIDES[key]
                turn['target_parts'] = len(indices)
                turn['retained_parts'] = [turn['source_parts'][index] for index in indices]
                turn['removed_parts'] = [part for index, part in enumerate(turn['source_parts'])
                                         if index not in indices]
            if turn['source_parts'] and len(turn['retained_parts']) != turn['target_parts']:
                raise SystemExit(f"{planned['convo_id']} T{turn['turn_count']} has incomplete retention")
    final_counts = Counter({int(parts): count for parts, count in plan['fixed_counts'].items()})
    final_counts.update(turn['target_parts'] for case in plan['cases'] for turn in case['turns'])
    total = sum(final_counts.values())
    shares = {parts: final_counts[parts] / total for parts in (1, 2, 3)}
    if not (0.55 <= shares[1] <= 0.65 and 0.25 <= shares[2] <= 0.35
            and 0.05 <= shares[3] <= 0.15):
        raise SystemExit(f'retention overrides leave the target bands: {dict(final_counts)}')
    plan['retention_selected'] = True
    plan['realized_target_counts'] = dict(sorted(final_counts.items()))
    plan['retention_finalized_at'] = datetime.now().isoformat()
    write_json(FULL_REVOICE_PLAN_PATH, plan)
    FULL_REVOICE_RESULTS_PATH.unlink(missing_ok=True)
    FULL_REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    log.info('finalized safe retention plan with distribution %s', dict(sorted(final_counts.items())))


def full_revoice_prompt(case: dict, planned: dict, prior_error: str = '') -> str:
    return f"""Rewrite the remaining USER utterances in one Hugo evaluation conversation.

Return exactly the planned turn numbers and nothing else. Preserve the structured label, slots, ambiguity,
referents, persona, and conversation continuity. Agent turns and already-revised user turns are context only.
Every returned utterance must be freshly rephrased and differ from its source wording, even when its target
part count is unchanged. An exact copy of any source utterance fails the pass.

For a turn with RETAINED PARTS, express every retained act and none of the removed acts. The selection is
deliberately random. Reconstruct the survivors as a natural response with ordinary connectors, contractions,
and punctuation. Never mechanically concatenate clipped sentences. For a turn without source-part strings,
preserve its labeled request and grounded slots while realizing the target number of conversational acts.

A part is an independently omittable conversational act, not punctuation. Dependent frames, reasons, content
lists, chronology, modifiers, and purpose clauses stay attached. Each coordinated finite command or question
is separate when it could stand as its own response. Realize exactly target_parts and never exceed three.

Every rewritten utterance must contain at least 7 word tokens. Keep some 7-10 token turns natural, but usually
write connected responses longer than 10 tokens. Avoid short punchy fragments, generic padding, repeated
constraints, stock transitions, em dashes, ellipses, and these words: load-bearing, byte-identical, delve,
genuinely, absolutely, tighten. Do not repeat wording or rhetorical templates within the conversation.

Natural reconstruction examples:
- Retain approval + publish from "Yeah, that's exactly what I want, so go ahead and publish it."
  Good: "Yeah, that's exactly what I want, publish it."
  Bad: "Yeah. That's exactly what I want. Publish it."
- Retain only exact-fit approval from the same source:
  Good: "That's exactly what I want to go ahead with!"
  Bad: "That's exactly what I want. Go ahead."

CASE: {json.dumps(case, ensure_ascii=False)}
TURN PLAN: {json.dumps(planned['turns'], ensure_ascii=False)}
PRIOR VALIDATION ERROR: {prior_error or 'none'}
"""


def full_revoice_validation_prompt(case: dict, planned: dict, result: RevoicedCase) -> str:
    return f"""Validate rewritten Hugo user utterances against their source-retention plan.

Count conversational parts using this rubric: a part is an independently omittable conversational act, not
punctuation. Acknowledgements, approvals, permissions, requested actions, preambles, and coordinated finite
questions or commands can be separate. Dependent frames, reasons, purpose clauses, modifiers, content lists,
and chronology stay attached to their governing act. Joining words are never parts.

For each rewritten turn, decide whether it expresses every RETAINED PART and none of the REMOVED PARTS. Also
decide whether it still supports the structured flow label, slots, ambiguity, referents, and local continuity.
Be strict about lost authorization, missing comparison operands, missing metrics, unsupported referents, and
negated action words. Return one validation item per rewritten turn and keep reasons under 20 words.

CASE CONTEXT: {json.dumps(case, ensure_ascii=False)}
TURN PLAN: {json.dumps(planned['turns'], ensure_ascii=False)}
REWRITES: {result.model_dump_json()}
"""


def load_full_revoice_results() -> dict:
    if not FULL_REVOICE_RESULTS_PATH.exists():
        return {}
    return {item['convo_id']: item for item in
            (json.loads(line) for line in FULL_REVOICE_RESULTS_PATH.read_text().splitlines() if line.strip())}


def run_full_revoice(args):
    from backend.components import prompt_engineer

    plan = load_json(FULL_REVOICE_PLAN_PATH, None)
    if not plan:
        raise SystemExit('run prepare-full-revoice first')
    if not plan.get('retention_selected'):
        raise SystemExit('run select-retentions across the full plan first')
    tiers = list(prompt_engineer.FAMILY_TIERS['together'])
    tiers[prompt_engineer._TIER_IDX['high']] = args.model
    prompt_engineer.FAMILY_TIERS['together'] = tuple(tiers)
    engineer = prompt_engineer.PromptEngineer(load_config())
    cases = {case['convo_id']: case for case in load_cases()}
    completed = load_full_revoice_results() if args.resume else {}
    failed_ids = {item['convo_id'] for item in
                  (json.loads(line) for line in FULL_REVOICE_ERRORS_PATH.read_text().splitlines())} \
        if args.resume and FULL_REVOICE_ERRORS_PATH.exists() else set()
    if not args.resume:
        FULL_REVOICE_RESULTS_PATH.unlink(missing_ok=True)
        FULL_REVOICE_ERRORS_PATH.unlink(missing_ok=True)
    requested_ids = set(args.ids.split(',')) if args.ids else None
    for planned in plan['cases']:
        convo_id = planned['convo_id']
        if ((convo_id in completed and not args.force) or convo_id in failed_ids
                or requested_ids is not None and convo_id not in requested_ids):
            continue
        expected = {turn['turn_count']: turn for turn in planned['turns']}
        prior_error = ''
        accepted = None
        for attempt in range(3):
            try:
                candidate = engineer(full_revoice_prompt(cases[convo_id], planned, prior_error),
                                     task='skill', tier='high', family='together',
                                     max_tokens=args.max_tokens, schema=RevoicedCase)
            except (ValueError, json.JSONDecodeError) as error:
                prior_error = f'unparseable rewrite: {error}'
                continue
            received = {turn.turn_count: turn.utterance.strip() for turn in candidate.turns}
            if candidate.convo_id != convo_id or set(received) != set(expected):
                prior_error = 'rewrite turn numbers do not match the plan'
                continue
            local_error = next((f'T{turn_count} is below seven tokens'
                                for turn_count, utterance in received.items()
                                if len(semantic_tokens(utterance)) < 7), '')
            if not local_error:
                local_error = next((f'T{turn_count} was returned unchanged'
                                    for turn_count, utterance in received.items()
                                    if utterance == expected[turn_count]['source_utterance']), '')
            if not local_error:
                local_error = next((f'T{turn_count} violates the voice rules'
                                    for turn_count, utterance in received.items()
                                    if BANNED.search(utterance) or '\u2014' in utterance), '')
            if local_error:
                prior_error = local_error
                continue
            try:
                verdict = engineer(full_revoice_validation_prompt(cases[convo_id], planned, candidate),
                                   task='skill', tier='high', family='together', max_tokens=2048,
                                   schema=FullRevoiceValidation)
            except (ValueError, json.JSONDecodeError) as error:
                prior_error = f'unparseable validation: {error}'
                continue
            validations = {turn.turn_count: turn for turn in verdict.turns}
            if verdict.convo_id != convo_id or set(validations) != set(expected):
                prior_error = 'validation turn numbers do not match the plan'
                continue
            failures = [f"T{turn_count}: {validation.reason or 'semantic validation failed'}"
                        for turn_count, validation in validations.items()
                        if (validation.part_count != expected[turn_count]['target_parts']
                            or not validation.faithful_to_plan or not validation.label_preserved)]
            if failures:
                prior_error = '; '.join(failures[:3])
                log.warning('%s attempt %d: %s', convo_id, attempt + 1, prior_error)
                continue
            accepted = candidate.model_dump()
            break
        if accepted is None:
            with FULL_REVOICE_ERRORS_PATH.open('a') as output:
                output.write(json.dumps({'convo_id': convo_id, 'attempts': 3,
                                         'error': prior_error, 'action': 'replace_case'}) + '\n')
            failed_ids.add(convo_id)
            continue
        completed[convo_id] = accepted
        FULL_REVOICE_RESULTS_PATH.write_text(''.join(
            json.dumps(completed[key], ensure_ascii=False) + '\n' for key in sorted(completed)))
        log.info('fully revoiced remaining turns in %s', convo_id)


def run_apply_manual_revoice(args):
    """Apply checkpointed human-authored rewrites without requiring a complete corpus pass."""
    plan = load_json(FULL_REVOICE_PLAN_PATH, None)
    if not plan or not MANUAL_REVOICE_RESULTS_PATH.exists():
        raise SystemExit('full revoice plan or manual rewrite checkpoint is missing')
    planned = {case['convo_id']: case for case in plan['cases']}
    results = [json.loads(line) for line in MANUAL_REVOICE_RESULTS_PATH.read_text().splitlines()
               if line.strip()]
    if len({item['convo_id'] for item in results}) != len(results):
        raise SystemExit('manual rewrite checkpoint contains duplicate conversation ids')
    cases = load_cases()
    cases_by_id = {case['convo_id']: case for case in cases}
    changed_cases = 0
    changed_turns = 0
    for result in results:
        convo_id = result['convo_id']
        if convo_id not in planned or convo_id not in cases_by_id:
            raise SystemExit(f'{convo_id}: manual rewrite is not in the active corpus plan')
        expected = {turn['turn_count']: turn for turn in planned[convo_id]['turns']}
        received = {turn['turn_count']: turn['utterance'].strip() for turn in result['turns']}
        if set(received) != set(expected):
            raise SystemExit(f'{convo_id}: manual rewrite turn set does not match the plan')
        if any(len(semantic_tokens(utterance)) < 7 for utterance in received.values()):
            raise SystemExit(f'{convo_id}: manual rewrite contains a turn below seven tokens')
        user_turns = {turn['turn_count']: turn for turn in cases_by_id[convo_id]['turns']
                      if turn.get('role') == 'user'}
        case_changed = False
        for turn_count, utterance in received.items():
            current = user_turns[turn_count]['utterance']
            source = expected[turn_count]['source_utterance']
            if current == utterance:
                continue
            if current != source:
                raise SystemExit(f'{convo_id} T{turn_count}: corpus no longer matches source or checkpoint')
            user_turns[turn_count]['utterance'] = utterance
            changed_turns += 1
            case_changed = True
        if case_changed:
            changed_cases += 1
        lengths = (((cases_by_id[convo_id].get('generation') or {}).get('draws') or {}).get('length') or [])
        ordered_user_turns = [turn for turn in cases_by_id[convo_id]['turns'] if turn.get('role') == 'user']
        if len(lengths) == len(ordered_user_turns):
            for index, turn in enumerate(ordered_user_turns):
                if turn['turn_count'] in expected:
                    lengths[index] = expected[turn['turn_count']]['target_parts']
    utterances = [turn['utterance'] for case in cases for turn in case['turns']
                  if turn.get('role') == 'user']
    duplicates = [text for text, count in Counter(utterances).items() if count > 1]
    if duplicates:
        raise SystemExit(f'manual rewrites would leave {len(duplicates)} duplicate user utterances')
    if not args.dry_run and changed_turns:
        backup_corpus('manual_revoice')
        write_cases(TRAIN, cases)
    log.info('%s %d manual turn rewrites across %d cases; retained all %d cases',
             'checked' if args.dry_run else 'applied', changed_turns, changed_cases, len(cases))


def run_finalize(args):
    selection = load_json(SELECTION_PATH, None)
    if not selection:
        raise SystemExit('run select first')
    if selection['target'] != args.target or len(selection['selected_ids']) != args.target:
        raise SystemExit('selection does not match requested target')
    if selection.get('missing_coverage'):
        raise SystemExit(f"selection is missing required coverage: {selection['missing_coverage']}")
    manifest = load_json(CURRENT_ROUND, {})
    if manifest.get('status') == 'open':
        raise SystemExit('current review round is unresolved')
    selected = set(selection['selected_ids'])
    output = [mechanical_repairs(case, normalize_fixtures=True)
              for case in load_cases() if case['convo_id'] in selected]
    report = audit_corpus(output)
    if report['issue_counts'].get('hard') or len(output) != args.target:
        raise SystemExit('final corpus failed hard validation')
    observed = Counter(estimated_parts(turn['utterance']) for case in output for turn in case['turns']
                       if turn.get('role') == 'user' and turn.get('utterance'))
    expected = Counter({index: count for index, count in enumerate(exact_part_targets(sum(observed.values())), 1)})
    if observed != expected:
        raise SystemExit(f'final part distribution is {dict(observed)}, expected {dict(expected)}')
    if not args.dry_run:
        backup_corpus('finalize')
        batches = {}
        for case in output:
            batches.setdefault(case.get('batch', ''), []).append(case)
        for batch_cases in batches.values():
            for case in batch_cases:
                case['flagged'] = False
                draws = ((case.get('generation') or {}).get('draws') or {})
                if 'flagged' in draws:
                    draws['flagged'] = False
            batch_cases[0]['flagged'] = True
            draws = ((batch_cases[0].get('generation') or {}).get('draws') or {})
            if 'flagged' in draws:
                draws['flagged'] = True
        write_cases(TRAIN, output)
    write_json(SUMMARY_PATH, {'finalized_at': datetime.now().isoformat(), 'dry_run': args.dry_run,
                              'case_count': len(output), 'audit': report['issue_counts'],
                              'review_events_used': len(load_ledger()['events'])})
    log.info('%s final corpus with %d cases', 'checked' if args.dry_run else 'wrote', len(output))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    audit = subparsers.add_parser('audit')
    audit.add_argument('--strict', action='store_true')
    audit.set_defaults(func=run_audit)
    judge = subparsers.add_parser('judge')
    judge.add_argument('--tier', choices=['med', 'high'], default='high')
    judge.add_argument('--family', choices=['claude', 'gemini', 'gpt', 'together'], default='')
    judge.add_argument('--model', default='', help='concrete model override for this curation process')
    judge.add_argument('--ids', default='')
    judge.add_argument('--problematic', action='store_true')
    judge.add_argument('--resume', action='store_true')
    judge.add_argument('--max-tokens', type=int, default=8192)
    judge.set_defaults(func=run_judge)
    round_parser = subparsers.add_parser('round')
    round_parser.add_argument('--round', type=int, required=True)
    round_parser.add_argument('--limit', type=int, default=12)
    round_parser.add_argument('--ids', default='')
    round_parser.add_argument('--dry-run', action='store_true')
    round_parser.add_argument('--allow-rereview', action='store_true')
    round_parser.add_argument('--calibration', action='store_true',
                              help='sample the finalized corpus for maximum cross-axis information gain')
    round_parser.add_argument('--replace-open', action='store_true')
    round_parser.add_argument('--append-open', action='store_true')
    round_parser.set_defaults(func=run_round)
    apply_round = subparsers.add_parser('apply-round')
    apply_round.add_argument('--dry-run', action='store_true')
    apply_round.set_defaults(func=run_apply_round)
    close_round = subparsers.add_parser('close-round')
    close_round.add_argument('--discard-unreviewed', action='store_true')
    close_round.add_argument('--generalized-feedback', required=True)
    close_round.set_defaults(func=run_close_round)
    import_decisions = subparsers.add_parser('import-decisions')
    import_decisions.add_argument('file')
    import_decisions.set_defaults(func=run_import_decisions)
    propose_deletions = subparsers.add_parser('propose-deletions')
    propose_deletions.add_argument('--count', type=int, default=32)
    propose_deletions.add_argument('--dry-run', action='store_true')
    propose_deletions.set_defaults(func=run_propose_deletions)
    select = subparsers.add_parser('select')
    select.add_argument('--target', type=int, default=TARGET_SIZE)
    select.set_defaults(func=run_select)
    prepare_revoice = subparsers.add_parser('prepare-revoice')
    prepare_revoice.set_defaults(func=run_prepare_revoice)
    revoice = subparsers.add_parser('revoice')
    revoice.add_argument('--model', default='zai-org/GLM-5.2')
    revoice.add_argument('--resume', action='store_true')
    revoice.add_argument('--ids', default='')
    revoice.add_argument('--max-tokens', type=int, default=4096)
    revoice.set_defaults(func=run_revoice)
    apply_revoice = subparsers.add_parser('apply-revoice')
    apply_revoice.add_argument('--dry-run', action='store_true')
    apply_revoice.set_defaults(func=run_apply_revoice)
    apply_trim_only = subparsers.add_parser('apply-trim-only')
    apply_trim_only.add_argument('--dry-run', action='store_true')
    apply_trim_only.set_defaults(func=run_apply_trim_only)
    prepare_full_revoice = subparsers.add_parser('prepare-full-revoice')
    prepare_full_revoice.add_argument('--seed', type=int, default=20260714)
    prepare_full_revoice.set_defaults(func=run_prepare_full_revoice)
    select_retentions = subparsers.add_parser('select-retentions')
    select_retentions.add_argument('--model', default='zai-org/GLM-5.2')
    select_retentions.add_argument('--ids', default='')
    select_retentions.set_defaults(func=run_select_retentions)
    finalize_retentions = subparsers.add_parser('finalize-retentions')
    finalize_retentions.set_defaults(func=run_finalize_retentions)
    full_revoice = subparsers.add_parser('full-revoice')
    full_revoice.add_argument('--model', default='zai-org/GLM-5.2')
    full_revoice.add_argument('--max-tokens', type=int, default=4096)
    full_revoice.add_argument('--resume', action='store_true')
    full_revoice.add_argument('--ids', default='')
    full_revoice.add_argument('--force', action='store_true')
    full_revoice.set_defaults(func=run_full_revoice)
    apply_manual_revoice = subparsers.add_parser('apply-manual-revoice')
    apply_manual_revoice.add_argument('--dry-run', action='store_true')
    apply_manual_revoice.set_defaults(func=run_apply_manual_revoice)
    revoice_turns = subparsers.add_parser('revoice-turns')
    revoice_turns.add_argument('--model', default='zai-org/GLM-5.2')
    revoice_turns.add_argument('--ids', default='')
    revoice_turns.add_argument('--turn-keys', default='')
    revoice_turns.set_defaults(func=run_revoice_turns)
    repair_voice = subparsers.add_parser('repair-user-voice')
    repair_voice.add_argument('--model', default='zai-org/GLM-5.2')
    repair_voice.set_defaults(func=run_repair_user_voice)
    semantic_parts = subparsers.add_parser('semantic-parts')
    semantic_parts.add_argument('--model', default='zai-org/GLM-5.2')
    semantic_parts.add_argument('--resume', action='store_true')
    semantic_parts.set_defaults(func=run_semantic_parts)
    semantic_parts_turns = subparsers.add_parser('semantic-parts-turns')
    semantic_parts_turns.add_argument('--model', default='zai-org/GLM-5.2')
    semantic_parts_turns.add_argument('--restart', action='store_true')
    semantic_parts_turns.set_defaults(func=run_semantic_parts_turns)
    calibrate_parts = subparsers.add_parser('calibrate-semantic-parts')
    calibrate_parts.add_argument('--model', default='zai-org/GLM-5.2')
    calibrate_parts.set_defaults(func=run_calibrate_semantic_parts)
    trim_parts = subparsers.add_parser('trim-parts')
    trim_parts.add_argument('--seed', type=int, default=20260713)
    trim_parts.add_argument('--dry-run', action='store_true')
    trim_parts.set_defaults(func=run_trim_parts)
    sanitize_revoice = subparsers.add_parser('sanitize-revoice-plan')
    sanitize_revoice.set_defaults(func=run_sanitize_revoice_plan)
    prepare_replacements = subparsers.add_parser('prepare-replacements')
    prepare_replacements.add_argument('--seed', type=int, default=20260713)
    prepare_replacements.set_defaults(func=run_prepare_replacements)
    generate_replacements = subparsers.add_parser('generate-replacements')
    generate_replacements.add_argument('--model', default='zai-org/GLM-5.2')
    generate_replacements.add_argument('--max-tokens', type=int, default=8192)
    generate_replacements.add_argument('--resume', action='store_true')
    generate_replacements.set_defaults(func=run_generate_replacements)
    apply_replacements = subparsers.add_parser('apply-replacements')
    apply_replacements.add_argument('--dry-run', action='store_true')
    apply_replacements.set_defaults(func=run_apply_replacements)
    finalize = subparsers.add_parser('finalize')
    finalize.add_argument('--target', type=int, default=TARGET_SIZE)
    finalize.add_argument('--dry-run', action='store_true')
    finalize.set_defaults(func=run_finalize)
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    args = build_parser().parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
