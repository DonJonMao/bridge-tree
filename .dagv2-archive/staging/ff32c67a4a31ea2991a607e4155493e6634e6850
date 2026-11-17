#!/usr/bin/env python3
"""PrefEval original vs complete residual-v2: launch, resume, progress and scores."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dagbt import runner, prefeval
from dagbt.methods import RESIDUAL_V2

ARMS = ['original', RESIDUAL_V2]


def public_snapshot(output):
    output = Path(output).resolve()
    manifest = runner.load(output / 'manifest.json')
    if manifest.get('arms') != ARMS or set(manifest.get('question_ids', {})) != {'prefeval'}:
        raise ValueError('Not an original vs residual-v2 PrefEval run')
    if manifest.get('source_hashes') != runner.frozen_sources():
        raise ValueError('Source differs from this frozen experiment')
    if runner.file_hash(ROOT / 'data/prefeval/manifest.json') != manifest['dataset_manifests']['prefeval']:
        raise ValueError('PrefEval data differs from this experiment')
    qs = {q['id']: q for q in prefeval.load_questions(ROOT)}
    ids = manifest['question_ids']['prefeval']
    if not ids or len(set(ids)) != len(ids) or runner.digest([qs[u] for u in ids]) != manifest['questions_digest']['prefeval']:
        raise ValueError('Frozen PrefEval question selection changed')
    rows, malformed = {a: {} for a in ARMS}, {a: 0 for a in ARMS}
    for arm in ARMS:
        for unit in ids:
            p = runner.result_path(output, 'prefeval', arm, unit)
            if not p.exists():
                continue
            try:
                row = runner.validate_result(runner.load(p), unit)
                if row.get('runner', {}).get('arm') != arm or row.get('runner', {}).get('dataset') != 'prefeval':
                    raise ValueError('Result arm/dataset mismatch')
                if arm == RESIDUAL_V2 and (row.get('algorithm_version') != RESIDUAL_V2 or row.get('method') != RESIDUAL_V2):
                    raise ValueError('Wrong residual algorithm')
                rows[arm][unit] = row
            except (ValueError, TypeError, KeyError, OSError):
                malformed[arm] += 1
    return manifest, qs, ids, rows, malformed


def status(output):
    out = Path(output).resolve()
    info = runner.status(out)
    info['output'] = str(out)
    if (out / 'manifest.json').exists():
        _, _, ids, rows, bad = public_snapshot(out)
        info['completed_tasks'] = sum(len(v) for v in rows.values())
        info['total_tasks'] = len(ids) * len(ARMS)
        info['arms'] = {arm: {'completed': len(rows[arm]), 'malformed': bad[arm],
            'statuses': dict(Counter(r['answer']['status'] for r in rows[arm].values()))} for arm in ARMS}
    return info


def accuracy(output):
    manifest, qs, ids, rows, malformed = public_snapshot(output)
    if any(malformed.values()):
        raise ValueError('Malformed/mismatched result files found; refusing a misleading accuracy')
    prefeval.validate_dataset(ROOT, include_labels=True)
    labels = {r['id']: r['correct_answer'] for r in runner.load(ROOT / 'data/prefeval/evaluation_only.json')}
    scores, report = {}, {'planned_questions': len(ids), 'arms': {}, 'paired': {}, 'by_condition': {}}
    print(f'计划 {len(ids)} 题、{2 * len(ids)} 个任务；仅统计当前已发布结果，失败计错。')
    for arm in ARMS:
        scores[arm] = {}
        for unit, row in rows[arm].items():
            answer = row['answer']
            choice = prefeval.parse_choice(answer.get('prediction'), qs[unit]['options'])
            valid = answer['status'] == 'ok' and choice is not None
            scores[arm][unit] = {'accuracy': int(valid and choice == labels[unit]), 'valid': valid}
        count = len(scores[arm]); correct = sum(v['accuracy'] for v in scores[arm].values())
        valid = sum(v['valid'] for v in scores[arm].values())
        report['arms'][arm] = {'completed': count, 'valid': valid, 'correct': correct,
            'completed_accuracy_percent': 100 * correct / count if count else None,
            'valid_answer_accuracy_percent': 100 * correct / valid if valid else None}
        acc = f'{100 * correct / count:.2f}%' if count else '待确定'
        print(f'{arm}：完成 {count}/{len(ids)}；有效 {valid}；答对 {correct}；含失败准确率 {acc}')
    common = set(scores[ARMS[0]]) & set(scores[ARMS[1]])
    valid_common = {u for u in common if all(scores[a][u]['valid'] for a in ARMS)}
    for name, subset in [('同题含失败', common), ('同题双方有效', valid_common)]:
        entry = {'n': len(subset), 'correct': {a: sum(scores[a][u]['accuracy'] for u in subset) for a in ARMS}}
        entry['delta_percentage_points'] = (100 * (entry['correct'][ARMS[1]] - entry['correct'][ARMS[0]]) / len(subset)) if subset else None
        report['paired'][name] = entry
        print(name + '：' + str(len(subset)) + ' 题；' + '；'.join(f"{a} {entry['correct'][a]}/{len(subset)}" for a in ARMS)
              + (f"；差值 {entry['delta_percentage_points']:+.2f} 个百分点" if subset else ''))
    for form in prefeval.FORMS:
        for turns in prefeval.TURNS:
            subset = [u for u in ids if qs[u]['question_type'] == form and qs[u]['inter_turns'] == turns]
            if not subset:
                continue
            key = f'{form}/t{turns:03d}'
            report['by_condition'][key] = {}
            parts = []
            for arm in ARMS:
                done = [u for u in subset if u in scores[arm]]
                correct = sum(scores[arm][u]['accuracy'] for u in done)
                report['by_condition'][key][arm] = {'completed': len(done), 'planned': len(subset), 'correct': correct,
                    'completed_accuracy_percent': 100 * correct / len(done) if done else None}
                parts.append(f'{arm} {correct}/{len(done)}')
            print(key + '：' + '；'.join(parts))
    report['snapshot_note'] = 'Conditional valid-only and partial-completion subsets are not the full benchmark accuracy.'
    runner.save(Path(output) / 'interim_accuracy.json', report)
    return report


def diagnostics(output):
    """Published task failures and capacity deferrals; no labels or model calls."""
    _, _, _, rows, malformed = public_snapshot(output)
    report = {'output':str(Path(output).resolve()), 'labels_read':False,
              'malformed':malformed, 'arms':{}}
    for arm, tasks in rows.items():
        errors = Counter()
        capacity = []
        validation_failures = Counter()
        for row in tasks.values():
            diag = row.get('diagnostics', {})
            for error in diag.get('errors', []):
                errors[(error.get('type',''), error.get('error',''))] += 1
            if row['answer'].get('error'):
                errors[(row['answer'].get('error_type',''),row['answer']['error'])] += 1
            for event in diag.get('events', []):
                if event.get('event') in {'joint_capacity_deferred','joint_support_capacity_rejected',
                                         'joint_repair_input_unavailable'}:
                    capacity.append({key:event.get(key) for key in ('event','operation','node_id',
                        'next_operation','next_node_id','source_scope','source_spans','input_tokens',
                        'output_token_reserve','context_tokens')})
            for batch in diag.get('joint_reading',{}).get('batches',[]):
                for failure in batch.get('failed_slots',[]):
                    validation_failures[(batch.get('operation',''),failure.get('error',''))] += 1
        report['arms'][arm] = {
            'completed':len(tasks),
            'statuses':dict(Counter(row['answer']['status'] for row in tasks.values())),
            'top_errors':[{'count':n, 'type':kind, 'error':message}
                          for (kind,message),n in errors.most_common(12)],
            'top_validation_failures':[{'count':n,'operation':op,'error':message}
                                      for (op,message),n in validation_failures.most_common(12)],
            'capacity_deferrals':len(capacity), 'capacity_examples':capacity[:3]}
    return report


def selected_ids(turns, forms, smoke=False):
    qs = [q for q in prefeval.load_questions(ROOT) if q['inter_turns'] in turns and q['question_type'] in forms]
    if smoke:
        # One public question per form and selected distractor condition; no label-based selection.
        seen, selected = set(), []
        for q in qs:
            key = (q['question_type'], q['inter_turns'])
            if key not in seen:
                seen.add(key); selected.append(q)
        qs = selected
    return {'prefeval': [q['id'] for q in qs]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['full', 'smoke', 'run', 'status', 'accuracy', 'diagnostics', 'stop', 'prepare-index', 'validate'])
    parser.add_argument('--turns', nargs='+', type=int, choices=prefeval.TURNS, default=[10])
    parser.add_argument('--forms', nargs='+', choices=prefeval.FORMS, default=list(prefeval.FORMS))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/prefeval-v4.json')
    args = parser.parse_args()
    turns = sorted(set(args.turns)); forms = sorted(set(args.forms))
    condition = '_'.join('t' + str(n) for n in turns)
    if set(forms) != set(prefeval.FORMS):
        condition += '_' + '_'.join(forms)
    suffix = '_smoke' if args.action == 'smoke' else '_full'
    output = (args.output or ROOT / 'outputs' / ('prefeval_v4_' + condition + suffix)).resolve()
    if args.action == 'validate':
        print(json.dumps(prefeval.validate_dataset(ROOT), ensure_ascii=False, indent=2)); return
    if args.action in {'status', 'accuracy', 'diagnostics', 'stop'}:
        if args.action == 'accuracy': accuracy(output)
        else:
            action = {'status':status, 'diagnostics':diagnostics, 'stop':runner.stop}[args.action]
            print(json.dumps(action(output), ensure_ascii=False, indent=2))
        return
    config = runner.validate_config(runner.load(args.config))
    if args.action == 'prepare-index':
        from dagbt.resources import ensure_index
        print(json.dumps(ensure_index(config, 'prefeval', output), indent=2)); return
    selection = selected_ids(turns, forms, smoke=args.action == 'smoke')
    output.mkdir(parents=True, exist_ok=True)
    selection_path = output / 'selected_questions.json'
    if selection_path.exists() and runner.load(selection_path) != selection:
        raise ValueError('Different question selection; choose a new output directory')
    if not selection_path.exists():
        runner.save(selection_path, selection)
    run_args = SimpleNamespace(config=str(args.config.resolve()), datasets=['prefeval'], arms=ARMS,
        output=str(output), limit=None, question_ids_file=str(selection_path), retry_failed=False, offline_preflight=False)
    if args.action == 'run':
        runner.run_experiment(run_args)
    else:
        print(json.dumps(runner.launch(run_args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
