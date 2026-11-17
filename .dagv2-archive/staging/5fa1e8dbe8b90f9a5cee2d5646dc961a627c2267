"""Read saved tokenization attempts for both arms; no endpoint or answer access."""
from pathlib import Path
from collections import Counter
import json
RUN=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r19')
OUT=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r19_tokenization_review.json')
def load(p):
    try:return json.loads(p.read_text())
    except (OSError,ValueError):return {}
manifest=load(RUN/'manifest.json');ids=manifest.get('question_ids',{}).get('personamem',[])
report={'run':RUN.name,'scope':'Saved request metadata only; no labels/scores/endpoints/run mutations. Connection/timeouts are distinct from InputOverflow and protocol failures. Existing bounded identical-request retries remain unchanged.','arms':{}}
for arm in manifest.get('arms',[]):
    rows=[load(p) for p in (RUN/'personamem'/arm/'rows').glob('*.json')]
    by_path={p.stem:load(p).get('unit_id') for p in (RUN/'personamem'/arm/'rows').glob('*.json')}
    events=[]
    for p in (RUN/'personamem'/arm/'attempts').glob('*/attempt-*/tokenization_events.jsonl'):
        for line in p.read_text().splitlines():
            try:e=json.loads(line)
            except ValueError:continue
            if e.get('status')=='ok':continue
            category=e.get('error_category')
            if category not in {'connection_or_timeout','http_error','invalid_response','invalid_count','context_length'}:category='other_recorded_category'
            unit=by_path.get(p.parent.parent.name)
            events.append({'question_index':ids.index(unit)+1 if unit in ids else None,'attempt_file':str(p.relative_to(RUN)),
                'request_sha256':e.get('tokenization_request_sha256'),'error_category':category,'status':e.get('status'),
                'http_attempts':e.get('http_attempts',0),'http_retries':e.get('http_retries',0),'failed_http_attempts':e.get('failed_http_attempts',0),
                'successful_http_requests':e.get('successful_http_requests',0),'elapsed_seconds':e.get('seconds'),
                'attempts':[{k:a.get(k) for k in ('attempt','status','retryable','will_retry','http_status','seconds')} for a in e.get('attempts',[])]})
    report['arms'][arm]={'published_rows':len(rows),'status_counts':dict(Counter(r.get('answer',{}).get('status') for r in rows)),
        'failed_tokenization_requests':len(events),'error_category_counts':dict(Counter(e['error_category'] for e in events)),
        'failed_request_http_attempts':sum(e['http_attempts'] for e in events),'failed_request_http_retries':sum(e['http_retries'] for e in events),
        'failed_request_elapsed_seconds':sum(e['elapsed_seconds'] or 0 for e in events),
        'attempt_duration_seconds':sum(a['seconds'] or 0 for e in events for a in e['attempts']),
        'failed_requests':events}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({arm:{k:v for k,v in row.items() if k!='failed_requests'} for arm,row in report['arms'].items()},ensure_ascii=False))
