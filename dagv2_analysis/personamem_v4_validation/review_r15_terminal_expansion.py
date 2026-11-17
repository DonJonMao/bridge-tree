"""Repeatable offline parent-document expansion audit for R15 question three.

The existing JSON reports are immutable. This helper prints only structural
fields and exact hashes; redirect its output to a new file when desired.
"""
import contextlib
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

BASE = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
helper = BASE / 'review_r15_terminal_continuation.py'
spec = importlib.util.spec_from_file_location('r15_continuation_offline', helper)
m = importlib.util.module_from_spec(spec)
sys.argv = [str(helper), '--no-write']
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(m)


def stable(value):
    if isinstance(value, dict):
        return {key: [m.sources[alias]['source_id'] for alias in item] if key == 'source_ids'
                else deepcopy(item) if key in ('value', 'output') else stable(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return deepcopy(value)


state = m.FactState(m.snapshot['initial_program'], m.snapshot['contract'], m.plan['steps'], m.plan['final_node_id'])
state.program = deepcopy(m.snapshot['program'])
state.revision = m.data['program_revision']
state.routes = {row['id']: stable(row) for row in m.data['known_observations']}
for variable, parent in m.data['supported_parents'].items():
    state.versions[variable] = parent['version']
reader = m.JointReader(SimpleNamespace(**vars(m.engine)), state)
reader.current_identity = m.reader.current_identity
reader.current_terminal_output = True
initial = reader._payload(m.data['task'], m.data['grounded_subquestion'], list(m.data['variables']),
                          m.joint['batches'][-2]['source_aliases'], True)
assert m._digest(m.wire(initial)) == m._digest(m.request['payload'])
mandatory = reader._payload(m.data['task'], m.data['grounded_subquestion'], list(m.data['variables']), [], True)
parent_aliases = {alias for parent in m.data['supported_parents'].values() for alias in parent['source_ids']}
parent_docs = {m.sources[alias]['doc_id'] for alias in parent_aliases}
expanded = [alias for alias, source in m.sources.items() if source['doc_id'] in parent_docs]
mandatory_aliases = {source['id'] for source in mandatory['source_spans']}
history_ids = {batch['identity'] for batch in m.joint['batches'] if batch['operation'] == 'joint_read'}
historically_read = {row['source_alias'] for row in m.joint['read_states']
                     if row['query_identity'] in history_ids and row['state'] in ('read', 'irrelevant')}
terminal_read = set(m.joint['batches'][-2]['source_aliases'])
pending_aliases = {alias for group in m.pending for alias in group}
groups = []
for alias in expanded:
    source = m.sources[alias]
    adjacent = [m.source_aliases.get(source.get(key)) for key in ('previous_span_id', 'next_span_id')]
    groups.append(list(dict.fromkeys([alias, *[item for item in adjacent if item]])))
consumed = len(groups) - len(m.pending)
assert groups[consumed:] == m.pending
assert {alias for group in groups[:consumed] for alias in group} == terminal_read
zero_data = m.mandatory
zero_repair = {**zero_data, 'repair_scope': {
    'failed': [{'variable': variable, 'id': '*', 'feedback': 'x' * 240, 'observation': None}
               for variable in zero_data['variables']], 'attempt': 1, 'previous_response_identity': '0' * 64}}
zero_hashes = [m._digest(m.wire(zero_data)), m._digest(m.wire(zero_repair, 'semantic_compose_repair'))]
report = {
    'scope': 'Offline exact-wire and parent-document expansion recheck; no services, labels, raw text output, or experiment writes.',
    'preterminal_state_reproduces_archived_first_terminal_wire': True,
    'last_paid_terminal_wire_sha256': m._digest(m.request['payload']),
    'selected_parent_original_source_count': len(parent_aliases),
    'parent_document_count': len(parent_docs),
    'initial_mandatory_closure_source_count': len(mandatory_aliases),
    'mapped_spans_in_parent_documents': len(expanded),
    'expanded_sources_beyond_initial_mandatory_closure': len(set(expanded) - mandatory_aliases),
    'expanded_sources_already_read_in_history': len(set(expanded) & historically_read),
    'expanded_extra_sources_already_read_in_history': len((set(expanded) - mandatory_aliases) & historically_read),
    'initial_terminal_groups': len(groups), 'first_terminal_consumed_groups': consumed,
    'first_terminal_read_source_count': len(terminal_read),
    'continuation_pending_groups': len(m.pending), 'continuation_pending_unique_aliases': len(pending_aliases),
    'continuation_aliases_already_read_in_first_terminal': len(pending_aliases & terminal_read),
    'unread_markers': len(m.joint['unread_obligations']),
    'post_terminal_mandatory_closure_sources': len(m.mandatory['source_spans']),
    'new_mandatory_sources_after_first_terminal': len({source['id'] for source in m.mandatory['source_spans']} - mandatory_aliases),
    'zero_new_group_wire_sha256s': zero_hashes,
    'zero_new_group_exact_saved_counts_available': [identity in m.saved for identity in zero_hashes],
    'zero_new_group_tokens_if_exactly_recorded': [m.saved[identity]['count'] if identity in m.saved else None for identity in zero_hashes],
    'new_network_calls': 0, 'generation_calls': 0,
    'archive_sha256s': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in [m.ATTEMPT / 'result.json', m.ATTEMPT / 'fusion_events.jsonl', m.RUN / 'manifest.json']},
    'source_sha256s': {str(m.ROOT / relative): hashlib.sha256((m.ROOT / relative).read_bytes()).hexdigest()
                      for relative in ('dagbt/joint_reading.py', 'dagbt/residual_control.py', 'dagbt/fact_state.py',
                                       'dagbt/reasoning.py', 'dagbt/model_runtime.py')},
    'helper_sha256s': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (helper, Path(__file__))},
}
old = json.loads((BASE / 'r15_terminal_continuation_expansion.json').read_text())
for key in ('selected_parent_original_source_count', 'parent_document_count', 'initial_mandatory_closure_source_count',
            'mapped_spans_in_parent_documents', 'expanded_sources_beyond_initial_mandatory_closure',
            'expanded_sources_already_read_in_history', 'continuation_pending_groups', 'unread_markers',
            'post_terminal_mandatory_closure_sources', 'zero_new_group_exact_saved_counts_available'):
    assert report[key] == old[key], 'Repeatable expansion evidence differs'
report['matches_original_expansion_report'] = True
print(json.dumps(report, ensure_ascii=False, indent=2))
