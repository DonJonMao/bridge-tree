"""Pinned PrefEval MCQ data port for the frozen PersonaMem v4 algorithms.

Public runtime loaders never open the official raw rows or evaluation labels.
Only prepare_dataset and explicit evaluation may access those artifacts.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from .personamem import format_question, parse_choice, memory_title
from vendor.bridgetree.personamem import messages_to_memories, file_sha256

ROOT = Path(__file__).resolve().parents[1]
REVISION = '50795054b5ff5f418d2b768a331d71e480f93331'
REPOSITORY = 'https://github.com/amazon-science/PrefEval'
SCHEMA = 'prefeval_mcq_personamem_v4_port_v1'
FORMS = ('explicit', 'implicit_choice', 'implicit_persona')
TURNS = (0, 10, 70, 300)
PUBLIC_FILES = ('questions.jsonl', 'questions.json', 'corpus.jsonl', 'corpus.json', 'scopes.json')
FIELDS = {'id', 'question_id', 'question', 'user_question', 'options', 'persona_id',
          'shared_context_id', 'end_index', 'scope_id', 'question_type', 'topic',
          'inter_turns', 'preference_messages', 'source_index'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def directory(root):
    return Path(root) / 'data/prefeval'


def scope_id(context, turns):
    return 'prefeval:scope:' + digest([context, turns])


def read_questions(root):
    return [json.loads(line) for line in (directory(root) / 'questions.jsonl').read_text().splitlines() if line.strip()]


def load_questions(root=ROOT, limit=None):
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError('limit must be a nonnegative integer')
    rows = read_questions(root)
    seen = set()
    for q in rows:
        if set(q) != FIELDS or q['id'] in seen or q['id'] != q['question_id']:
            raise ValueError('PrefEval public whitelist/unique identity mismatch')
        if q['question_type'] not in FORMS or q['inter_turns'] not in TURNS:
            raise ValueError('Unknown PrefEval form or distractor condition')
        if (type(q['source_index']) is not int or q['source_index'] < 0
                or type(q['preference_messages']) is not int or q['preference_messages'] < 1
                or q['end_index'] != q['preference_messages'] + 2 * q['inter_turns']):
            raise ValueError('PrefEval chronological history boundary mismatch')
        if q['scope_id'] != scope_id(q['shared_context_id'], q['inter_turns']):
            raise ValueError('PrefEval scope identity mismatch')
        if q['question'] != format_question(q['user_question'], q['options']):
            raise ValueError('PrefEval public MCQ text/options mismatch')
        for key in ('id', 'topic', 'persona_id', 'shared_context_id'):
            if not isinstance(q[key], str) or not q[key]:
                raise ValueError('Invalid PrefEval public identity')
        seen.add(q['id'])
    if not rows:
        raise ValueError('Empty PrefEval dataset')
    return rows if limit is None else rows[:limit]


def load_scopes(root=ROOT):
    scopes = load(directory(root) / 'scopes.json')
    if not isinstance(scopes, dict) or not scopes:
        raise ValueError('PrefEval needs question-local retrieval scopes')
    return scopes


def validate_dataset(root=ROOT, include_labels=False):
    base = directory(root)
    manifest = load(base / 'manifest.json')
    if (manifest.get('schema') != SCHEMA or manifest.get('revision') != REVISION
            or manifest.get('repository') != REPOSITORY):
        raise ValueError('Unrecognized PrefEval dataset provenance')
    if set(manifest.get('public_sha256', {})) != set(PUBLIC_FILES):
        raise ValueError('Incomplete public PrefEval checksums')
    for name in PUBLIC_FILES:
        if file_sha256(base / name) != manifest['public_sha256'][name]:
            raise ValueError('PrefEval public artifact changed: ' + name)
    qs = load_questions(root)
    if load(base / 'questions.json') != qs:
        raise ValueError('PrefEval question copies differ')
    records = [json.loads(line) for line in (base / 'corpus.jsonl').read_text().splitlines() if line.strip()]
    docs = {}
    from .resources import personamem_document
    for d in records:
        personamem_document(d)  # Same authoritative role/offset validator as PersonaMem.
        expected = 'prefeval:memory:' + digest([d['shared_context_id'], d['source_message_indices'], d['text']])
        if d['docid'] != expected or expected in docs or d['title'] != memory_title(d['source_message_indices']):
            raise ValueError('PrefEval memory identity/title mismatch')
        docs[expected] = d
    if load(base / 'corpus.json') != [{'doc_id': d['docid'], 'title': d['title'], 'text': d['text']} for d in records]:
        raise ValueError('PrefEval corpus copies differ')
    scopes = load_scopes(root)
    if set(scopes) != {q['scope_id'] for q in qs}:
        raise ValueError('PrefEval question/scope sets differ')
    covered = set()
    for q in qs:
        ids = scopes[q['scope_id']]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('Empty or duplicate PrefEval scope documents')
        messages = []
        for ident in ids:
            d = docs.get(ident)
            if d is None:
                raise ValueError('Missing PrefEval scope document')
            if d['shared_context_id'] not in {q['shared_context_id'], 'prefeval:interturns:offset:' + str(q['preference_messages'])}:
                raise ValueError('Cross-question preference leakage')
            indices = d['source_message_indices']
            if max(indices) >= q['end_index']:
                raise ValueError('Out-of-scope future distractor messages')
            if d['shared_context_id'] == q['shared_context_id']:
                if max(indices) >= q['preference_messages']:
                    raise ValueError('Preference history boundary mismatch')
            elif min(indices) < q['preference_messages']:
                raise ValueError('Distractor order mismatch')
            messages.extend(indices)
            covered.add(ident)
        if sorted(messages) != list(range(q['end_index'])):
            raise ValueError('PrefEval history has missing/duplicate messages')
    if covered != set(docs):
        raise ValueError('Orphan PrefEval corpus documents')
    counts = {'questions': len(qs), 'documents': len(docs), 'scopes': len(scopes),
              'topics': len({q['topic'] for q in qs}), 'by_form': dict(Counter(q['question_type'] for q in qs)),
              'by_turns': dict(Counter(str(q['inter_turns']) for q in qs))}
    if any(manifest.get(k) != v for k, v in counts.items()):
        raise ValueError('PrefEval manifest counts mismatch')
    if include_labels:
        if file_sha256(base / 'evaluation_only.json') != manifest['evaluation_sha256']:
            raise ValueError('PrefEval evaluation artifact changed')
        labels = load(base / 'evaluation_only.json')
        if len(labels) != len(qs) or {r['id'] for r in labels} != {q['id'] for q in qs}:
            raise ValueError('PrefEval evaluation IDs differ')
        if any(set(r) != {'id', 'correct_answer'} or parse_choice(r['correct_answer'], ['a','b','c','d']) is None for r in labels):
            raise ValueError('PrefEval malformed evaluation labels')
    return {**counts, 'revision': REVISION, 'labels_read': include_labels}


def preference_messages(row, form):
    if form == 'explicit':
        # Deliberately no generated acknowledgment; both arms see this same fixed history.
        return [{'role': 'user', 'content': row['preference']}]
    conversation = row['conversation']
    if form == 'implicit_choice':
        keys = ('query', 'assistant_options', 'user_selection', 'assistant_acknowledgment')
        return [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': conversation[k]} for i, k in enumerate(keys)]
    if form != 'implicit_persona':
        raise ValueError('Unknown preference form')
    # The official extractor iterates the stored conversation order; persona annotations
    # and the row's explicit preference/explanation are never injected into this history.
    return [{'role': role, 'content': turn[role]} for turn in conversation.values() for role in ('user', 'assistant')]


def memories(messages, context, offset=0):
    result = []
    for memory in messages_to_memories(messages, context, memory_granularity='user_assistant_pair'):
        metadata = deepcopy(memory.metadata)
        indices = [i + offset for i in metadata['source_message_indices']]
        segments = metadata['source_segments']
        for segment in segments:
            segment['source_message_indices'] = [i + offset for i in segment['source_message_indices']]
        time = metadata['time']
        for key in ('observed_start', 'observed_end'):
            if time.get(key) is not None:
                time[key] += offset
        result.append({'docid': 'prefeval:memory:' + digest([context, indices, memory.text]),
                       'title': memory_title(indices), 'text': memory.text, 'shared_context_id': context,
                       'source_message_indices': indices, 'source_segments': segments,
                       'roles': metadata['roles'], 'time': time})
    return result


def prepare_dataset(raw, root=ROOT):
    raw, root = Path(raw), Path(root)
    source = raw / 'benchmark_dataset'
    official_manifest = load(raw / 'SOURCE_MANIFEST.json')
    if official_manifest['revision'] != REVISION:
        raise ValueError('Unpinned PrefEval source')
    for name, expected in official_manifest['files'].items():
        if file_sha256(raw / name) != expected:
            raise ValueError('Official PrefEval source changed: ' + name)
    distractors = [dict(role=m['role'], content=m['content'])
                   for row in load(source / 'filtered_inter_turns.json') for m in row['conversation']]
    if len(distractors) < 2 * max(TURNS):
        raise ValueError('Insufficient official distractor messages')
    for i, m in enumerate(distractors[:2 * max(TURNS)]):
        if m['role'] != ('user' if i % 2 == 0 else 'assistant') or not m['content']:
            raise ValueError('Official distractors do not form user/assistant pairs')
    qs, labels, docs, scopes = [], [], {}, {}
    noise_cache = {}
    topics = sorted(p.stem for p in (source / 'explicit_preference').glob('*.json'))
    for topic in topics:
        mcq = load(source / 'mcq_options' / (topic + '.json'))
        # Upstream classification loads explicit preferences from mcq_options,
        # whose wording differs slightly from the generation dataset in 30 rows.
        forms = {'explicit': mcq,
                 'implicit_choice': load(source / 'implicit_preference/choice-based' / (topic + '.json')),
                 'implicit_persona': load(source / 'implicit_preference/persona-driven' / (topic + '.json'))}
        if any(len(v) != len(mcq) for v in forms.values()):
            raise ValueError('Official form/MCQ row counts disagree: ' + topic)
        rng = random.Random(41)  # Matches the official per-topic seed and random.sample permutation.
        for index, item in enumerate(mcq):
            options = item['classification_task_options']
            if len(options) != 4 or len(set(options)) != 4:
                raise ValueError('PrefEval requires four distinct MCQ options')
            permutation = rng.sample(range(4), 4)
            shuffled = [options[i] for i in permutation]
            correct = chr(97 + permutation.index(0))
            for form in FORMS:
                row = forms[form][index]
                if any(row[k] != item[k] for k in ('question', 'preference')):
                    raise ValueError('Official row alignment mismatch: ' + topic + '/' + str(index))
                context = 'prefeval:history:' + topic + ':' + str(index) + ':' + form
                history = preference_messages(row, form)
                pref_docs = memories(history, context)
                noise_context = 'prefeval:interturns:offset:' + str(len(history))
                if len(history) not in noise_cache:
                    noise_cache[len(history)] = memories(distractors[:2 * max(TURNS)], noise_context, len(history))
                noise_docs = noise_cache[len(history)]
                for d in pref_docs + noise_docs:
                    if d['docid'] in docs and docs[d['docid']] != d:
                        raise ValueError('Memory identity collision')
                    docs[d['docid']] = d
                for turns in TURNS:
                    ident = f'prefeval-{topic}-{index:04d}-{form}-t{turns:03d}'
                    sid = scope_id(context, turns)
                    qs.append(dict(id=ident, question_id=ident, user_question=item['question'],
                        question=format_question(item['question'], shuffled), options=shuffled,
                        persona_id=context, shared_context_id=context, end_index=len(history) + 2 * turns,
                        scope_id=sid, question_type=form, topic=topic, inter_turns=turns,
                        preference_messages=len(history), source_index=index))
                    labels.append({'id': ident, 'correct_answer': correct})
                    scopes[sid] = [d['docid'] for d in pref_docs + noise_docs[:turns]]
    base = directory(root)
    if base.exists():
        raise ValueError('Refusing to overwrite prepared PrefEval data; use a new deployment')
    base.mkdir(parents=True)
    def write(name, value):
        (base / name).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    def jsonl(name, values):
        with (base / name).open('w') as f:
            for value in values:
                f.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    corpus = list(docs.values())
    write('questions.json', qs); jsonl('questions.jsonl', qs)
    write('corpus.json', [{'doc_id': d['docid'], 'title': d['title'], 'text': d['text']} for d in corpus])
    jsonl('corpus.jsonl', corpus); write('scopes.json', scopes); write('evaluation_only.json', labels)
    manifest = {'schema': SCHEMA, 'revision': REVISION, 'repository': REPOSITORY,
                'questions': len(qs), 'documents': len(docs), 'scopes': len(scopes), 'topics': len(topics),
                'by_form': dict(Counter(q['question_type'] for q in qs)),
                'by_turns': dict(Counter(str(q['inter_turns']) for q in qs)),
                'source_manifest_sha256': file_sha256(raw / 'SOURCE_MANIFEST.json'),
                'public_sha256': {name: file_sha256(base / name) for name in PUBLIC_FILES},
                'evaluation_sha256': file_sha256(base / 'evaluation_only.json'),
                'protocol': {'task': 'official MCQ questions/options/first-option gold; exact-match on selected label',
                    'selection': 'all 20 official topics and all 1000 rows per form; no training',
                    'forms': list(FORMS), 'inter_turn_conditions': list(TURNS), 'default_inter_turns': 10,
                    'options': 'Random(41) reset per topic, random.sample permutation shared across forms/conditions',
                    'implicit': 'only official conversation, never explicit preference/persona/explanation/aligned_op fields',
                    'explicit': 'user preference only; no model-generated acknowledgment',
                    'distractors': 'first 2*N flattened official messages, identical to upstream order',
                    'memory': 'role-preserving user/assistant pairs; source-order indices, no calendar inference',
                    'retrieval': 'both algorithms restricted to the exact per-question scope',
                    'output_adapter': 'PersonaMem single-label output, not upstream <choice> XML',
                    'comparison_limit': 'algorithm port, not a reproduction of the official full-history/top-5 baseline'}}
    write('manifest.json', manifest)
    return validate_dataset(root, include_labels=True)


def grouped_scores(questions, scores, arms):
    groups = defaultdict(list)
    for q in questions:
        groups[f"{q['question_type']}/t{q['inter_turns']:03d}"].append(q['id'])
    return {key: {'n': len(ids), 'arms': {arm: {
        'correct': sum(scores[arm][u]['accuracy'] for u in ids),
        'valid': sum(scores[arm][u]['valid'] for u in ids),
        'accuracy_percent': 100 * sum(scores[arm][u]['accuracy'] for u in ids) / len(ids)} for arm in arms}}
        for key, ids in sorted(groups.items())}
