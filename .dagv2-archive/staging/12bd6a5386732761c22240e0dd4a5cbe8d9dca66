"""Bounded R20 canonical-row review; no labels, scoring, services or text export."""
import ast
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = ROOT / 'outputs/v4_validation_r20'
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r20_frontier_review.json')
COMMIT = '6c046374008ce2e45f817d6bc9876b3ab927ab18'
ARM = 'dagbt_residual_memory_v2'


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


# Load only frozen deterministic source-span code. Extracting the two pure
# document helpers avoids importing resource/model/tokenizer implementations.
spec = importlib.util.spec_from_file_location('r20_frozen_source_spans', ROOT / 'dagbt/evidence_spans.py')
span_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(span_module)
resource_tree = ast.parse((ROOT / 'dagbt/resources.py').read_text())
definitions = [node for node in resource_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
               and node.name in {'ProvenanceDocument', 'personamem_document'}]
helpers = {'dataclass': dataclass, 'field': field, 'Mapping': Mapping, 'deepcopy': deepcopy,
           'SourceSpanError': span_module.SourceSpanError,
           'document_source_metadata': span_module.document_source_metadata,
           'normalize_source_segments': span_module.normalize_source_segments}
exec(compile(ast.Module(body=definitions, type_ignores=[]), 'frozen_document_helpers', 'exec'), helpers)


def expand_source_spans(data):
    spans = data.get('source_spans', [])
    columns = data.get('source_span_columns')
    if columns:
        spans = [dict(zip(columns, row)) for row in spans]
    spans = deepcopy(spans)
    documents = data.get('source_documents', {})
    for span in spans:
        if span.get('doc_id') in documents:
            span.update(documents[span['doc_id']])
    return spans


manifest = load(RUN / 'manifest.json')
if not manifest:
    raise SystemExit('No R20 manifest; no review performed.')
ids = manifest['question_ids']['personamem']
index = {unit: position + 1 for position, unit in enumerate(ids)}
rows = []
for path in (RUN / 'personamem' / ARM / 'rows').glob('*.json'):
    row = load(path)
    if row:
        rows.append((path, row))
needed = {source['doc_id'] for _, row in rows
          for source in row.get('diagnostics', {}).get('joint_reading', {}).get('source_namespace', [])}
documents = {}
with (ROOT / 'data/personamem/corpus.jsonl').open() as handle:
    for line in handle:
        record = json.loads(line)
        if record['docid'] in needed:
            documents[record['docid']] = helpers['personamem_document'](record)
source_cache = {}


def authoritative_sources(doc_id, max_chars):
    key = doc_id, max_chars
    if key not in source_cache:
        source_cache[key] = {source['id']: source for source in
                            span_module.build_source_spans(doc_id, documents[doc_id], max_chars)}
    return source_cache[key]


def inspect(path, row):
    errors, reviews = [], []
    result = {'question_index': index.get(row.get('unit_id')), 'unit_id': row.get('unit_id'),
              'status': row.get('answer', {}).get('status'), 'row_file': str(path.relative_to(RUN))}

    def check(condition, code, **details):
        if not condition:
            errors.append({'code': code, **details})

    check(row.get('unit_id') in index, 'row_outside_manifest')
    runner = row.get('runner', {})
    check(runner.get('dataset') == 'personamem' and runner.get('arm') == ARM, 'canonical_arm_identity')
    diag = row.get('diagnostics', {})
    joint = diag.get('joint_reading')
    if joint is None:
        check(result['status'] != 'ok', 'successful_row_missing_reader')
        return {**result, 'reader_reached': False, 'confirmed_failures': errors, 'requires_review': reviews}
    result['reader_reached'] = True
    check(joint.get('frontier_policy_version') == 1, 'frontier_policy_version')
    required_fields = {'source_namespace', 'discovery_frontier', 'discovery_contexts',
                       'source_exposures', 'discovery_promotions', 'read_states',
                       'unread_obligations', 'failed_obligations', 'evidence_obligations', 'failed_batch_reviews'}
    check(required_fields <= set(joint), 'missing_reader_fields')
    namespace = joint.get('source_namespace', [])
    by_alias = {source['source_alias']: source for source in namespace}
    by_id = {source['source_id']: source for source in namespace}
    check(len(by_alias) == len(namespace) == len(by_id), 'ambiguous_source_namespace')
    span_by_id = {}
    for source in namespace:
        stable = source['source_id']
        try:
            original = authoritative_sources(source['doc_id'], min(400, diag['settings']['max_quote_chars']))[stable]
        except (KeyError, ValueError):
            check(False, 'namespace_original_unavailable', source_hash=digest(stable))
            continue
        check(source['source_identity'] == digest({**{key: value for key, value in original.items() if key != 'id'},
                                                 'source_id': stable}),
              'source_content_identity_mismatch', source_hash=digest(stable))
        span_by_id[stable] = original

    def source_identity(source):
        stable = source.get('source_id')
        current = by_id.get(stable)
        check(current is not None, 'source_outside_namespace', source_hash=digest(stable))
        if current:
            check(all(source.get(key) == current[key] for key in ('source_id', 'doc_id', 'source_identity')),
                  'source_provenance_disagrees', source_hash=digest(stable))
            if 'current_source_alias' in source:
                check(source['current_source_alias'] == current['source_alias'], 'current_alias_disagrees')
        return stable

    contexts = {context['query_identity']: context for context in joint.get('discovery_contexts', [])}
    check(len(contexts) == len(joint.get('discovery_contexts', [])), 'duplicate_discovery_context')
    frontier = set()
    for identity, alias, item in joint.get('discovery_frontier', []):
        source = item.get('source', {})
        stable = source_identity(source)
        check(item.get('status') == 'unoffered' and item.get('provenance') == 'explicit_discovery',
              'invalid_frontier_state')
        check(source.get('source_alias') == alias and by_alias.get(alias, {}).get('source_id') == stable,
              'frontier_current_alias')
        check({key: value for key, value in item.items() if key not in {'source', 'provenance', 'status'}}
              == contexts.get(identity), 'frontier_context_mismatch')
        check((identity, stable) not in frontier, 'duplicate_frontier_source')
        frontier.add((identity, stable))

    # Inspect the authoritative attempt only. Old attempts are not outcomes.
    attempt = RUN / 'personamem' / ARM / 'attempts' / path.stem / f"attempt-{runner.get('attempt', 0):03d}"
    requests = {}
    for request_path in (attempt / 'requests').glob('*.json'):
        request = load(request_path)
        if not request:
            continue
        stage = request.get('stage', [])
        if len(stage) != 2 or stage[0] not in {
            'joint_read', 'joint_read_repair', 'semantic_compose', 'semantic_compose_repair', 'audit_joint', 'audit_joint_repair'}:
            continue
        try:
            data = json.loads(request['payload']['messages'][1]['content'])
            requests.setdefault((stage[0], int(stage[1])), []).append(data)
        except (KeyError, ValueError, TypeError, IndexError):
            reviews.append({'code': 'request_decode_unavailable', 'request_file': request_path.name})

    exposure_pairs, traced = set(), 0
    exposures = joint.get('source_exposures', [])
    for exposure in exposures:
        identity = exposure['query_identity']
        sources = exposure.get('sources', [])
        for source in sources:
            stable = source_identity(source)
            exposure_pairs.add((identity, stable))
            if source.get('discovery_origin'):
                source_identity(source['discovery_origin']['source'])
        if exposure.get('request_status') == 'not_sent':
            continue
        key = exposure.get('operation'), exposure.get('logical_call_index')
        actuals = requests.get(key, [])
        if not actuals:
            reviews.append({'code': 'exposure_request_unavailable', 'operation': key[0], 'logical_call_index': key[1]})
            continue
        for data in actuals:
            actual = expand_source_spans(data)
            check({source['source_alias'] for source in sources} == {source['id'] for source in actual},
                  'exposure_wire_source_set', logical_call_index=key[1])
            check(set(exposure['variables']) == set(data.get('variables', {})), 'exposure_wire_variables',
                  logical_call_index=key[1])
            check(exposure['scopes'] == data.get('requested_scopes'), 'exposure_wire_scopes', logical_call_index=key[1])
            current = {source['source_alias']: source for source in sources}
            for source in actual:
                original = span_by_id.get(current.get(source['id'], {}).get('source_id'))
                if original:
                    check(all(source.get(field) == original.get(field) for field in
                              ('doc_id', 'start', 'end', 'text', 'source_role', 'source_message_indices', 'time_metadata')),
                          'wire_original_fields_mismatch', logical_call_index=key[1], source_hash=digest(original['id']))
        traced += 1
    read_pairs = {(record['query_identity'], by_alias.get(record['source_alias'], {}).get('source_id'))
                  for record in joint.get('read_states', [])}
    hard_pairs = {(identity, by_alias.get(alias, {}).get('source_id'))
                  for identity, alias, _ in joint.get('unread_obligations', [])}
    check(not frontier & exposure_pairs, 'frontier_exposure_overlap')
    check(not frontier & read_pairs, 'frontier_read_overlap')
    check(not frontier & hard_pairs, 'frontier_hard_overlap')
    for promotion in joint.get('discovery_promotions', []):
        check(promotion.get('status') == 'required_evidence', 'promotion_status')
        source_identity(promotion['origin']['source'])

    successful = result['status'] == 'ok'
    if successful:
        answer, facts, terminal = row['answer'], diag['fact_state'], diag.get('terminal_input') or {}
        dependencies = terminal.get('binding_dependencies', {})
        check(answer.get('completion_kind') == 'semantic_assessment' and answer.get('certificate') is None,
              'personal_terminal_completion_kind')
        check(diag.get('audit_complete') is True and terminal.get('validation_complete') is True,
              'successful_terminal_audit_flags')
        check(bool(dependencies), 'missing_terminal_dependencies')
        for variable, binding in dependencies.items():
            check(binding.get('version') == facts.get('versions', {}).get(variable)
                  and binding.get('identity') == digest(facts.get('facts', {}).get(variable)), 'terminal_binding_stale')
        hard = set(facts.get('pending_variables', []))
        for name in ('unread_obligations', 'failed_obligations'):
            for _, _, variables in joint.get(name, []):
                hard.update(variables)
        hard.update(item['variable'] for name in ('evidence_obligations', 'failed_batch_reviews')
                    for item in joint.get(name, []))
        check(not set(dependencies) & hard, 'successful_dependency_has_hard_work')
        terminal_index = terminal.get('logical_call_index')
        check(any(item.get('logical_call_index') == terminal_index and item.get('request_status') == 'returned'
                  for item in exposures), 'terminal_request_untraced')
        audits = [item for item in exposures if item['operation'].startswith('audit_joint')]
        batches = [item for item in joint.get('batches', []) if item.get('operation') == 'audit_joint']
        check(bool(audits and batches), 'successful_audit_missing')
        if audits and batches:
            audit, batch = audits[-1], batches[-1]
            check(audit.get('request_status') == 'returned' and audit.get('status') == 'batch_assessed'
                  and isinstance(terminal_index, int) and audit.get('logical_call_index', -1) > terminal_index,
                  'audit_not_after_current_terminal')
            check(batch.get('audit_complete') is True and batch.get('audit_verdict') == 'supported'
                  and batch.get('complete') is True, 'latest_audit_not_complete_supported')
            check(all(facts.get('versions', {}).get(variable) == version
                      for variable, version in audit.get('parent_versions', {}).items()), 'audit_parent_version_stale')
    result.update({'source_namespace_checked': len(namespace), 'source_content_rebuilt': len(span_by_id),
                   'frontier_entries': len(frontier), 'discovery_contexts': len(contexts),
                   'exposure_records': len(exposures), 'exposures_traced_to_wire': traced,
                   'exposure_status_counts': dict(Counter(item.get('status') for item in exposures)),
                   'promotions': len(joint.get('discovery_promotions', [])),
                   'cross_query_frontier_exposure_same_source': sum(
                       any(old != owner and source == stable for old, source in exposure_pairs)
                       for owner, stable in frontier),
                   'historical_retention_scope': 'stored origins and per-query records checked; no proof of every unrecorded historical transition',
                   'successful_terminal_dependencies_checked': successful,
                   'confirmed_failures': errors, 'requires_review': reviews})
    return result


cases = []
for path, row in rows:
    try:
        cases.append(inspect(path, row))
    except Exception as exc:
        # Dynamic exceptions may contain source text; export only the class.
        cases.append({'question_index': index.get(row.get('unit_id')), 'unit_id': row.get('unit_id'),
                      'status': row.get('answer', {}).get('status'), 'inspection_error_type': type(exc).__name__,
                      'confirmed_failures': [], 'requires_review': [{'code': 'inspection_incomplete'}]})
cases.sort(key=lambda item: item.get('question_index') or 999)
progress = load(RUN / 'progress.json') or {}
report = {'run': RUN.name, 'source_commit': COMMIT, 'review_state': 'live_observation',
          'progress_state': progress.get('state'), 'planned_questions': len(ids), 'canonical_residual_rows': len(cases),
          'analysis_labels_read': False, 'analysis_scores_read': False, 'accuracy_scored': False,
          'source_or_answer_text_exported': False, 'services_called': False,
          'runner_may_auto_score_after_tasks_terminal': True,
          'scope': 'Canonical current rows, immutable public source identities, actual saved request scope and terminal structure only.',
          'cases': cases}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'rows': len(cases), 'planned': len(ids),
                  'confirmed_failures': sum(len(item['confirmed_failures']) for item in cases),
                  'requires_review': sum(len(item['requires_review']) for item in cases),
                  'frontier_entries': sum(item.get('frontier_entries', 0) for item in cases),
                  'exposures_traced': sum(item.get('exposures_traced_to_wire', 0) for item in cases),
                  'source_identities_rebuilt': sum(item.get('source_content_rebuilt', 0) for item in cases)}, ensure_ascii=False))
