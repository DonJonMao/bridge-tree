"""Context identity and reader variability diagnostics; no model calls."""
import json
import tarfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median

BASE = Path(__file__).resolve().parent
rows = []
with tarfile.open('/Users/mao/chain-audit-full.tgz') as archive:
    for member in archive.getmembers():
        if '/outcomes/' in '/' + member.name and member.name.endswith('.json'):
            rows.append(json.load(archive.extractfile(member)))
methods = {}
for row in rows:
    if row['status'] == 'success':
        task = row['task']
        methods.setdefault(task['method_id'], {})[(task['persona_id'], task['question_id'])] = row
comparisons = []
for left, right in [('dense', 'dense_rerank'), ('activation','activation_fixed_pool'),
                    ('activation','context_marginal')]:
    common = methods[left].keys() & methods[right].keys()
    equal_sets = equal_hash = different_labels = equal_hash_different_correct = 0
    examples = []
    for key in sorted(common):
        a, b = methods[left][key], methods[right][key]
        equal_sets += set(a['selected_ids']) == set(b['selected_ids'])
        equal_hash += a['context_hash'] == b['context_hash']
        different_labels += a['predicted_label'] != b['predicted_label']
        if a['context_hash'] == b['context_hash'] and a['correct'] != b['correct']:
            equal_hash_different_correct += 1
            examples.append({'persona_id': key[0], 'question_id':key[1]})
    comparisons.append(dict(left=left,right=right,common=len(common),equal_selected_sets=equal_sets,
        equal_context_hashes=equal_hash,different_labels=different_labels,
        equal_hash_different_correct=equal_hash_different_correct,examples=examples))
tz = timezone(timedelta(hours=8))
result = {
    'latest_finished_at_shanghai': datetime.fromtimestamp(max(r['finished_at_epoch'] for r in rows),tz).isoformat(),
    'personas': sorted({r['task']['persona_id'] for r in rows}),
    'question_count': len({r['task']['question_id'] for r in rows}),
    'comparisons': comparisons,
    'selected_count_distribution': {m: dict(Counter(len(r['selected_ids']) for r in group.values())) for m,group in methods.items()},
    'median_generator_input_estimated_tokens': {m:median(r['costs']['generator_input_tokens_estimate'] for r in group.values()) for m,group in methods.items()},
}
(BASE/'context_evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
