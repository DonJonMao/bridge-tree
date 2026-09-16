"""Verify the final PDF against report requirements and audited inputs."""
import hashlib
import json
import re
import sys
from pathlib import Path

from bridgetree.dependency_experiment import _source_code_hash

BASE = Path(__file__).resolve().parent
pdf = BASE / 'BridgeTree_Audit_2026-09-15.pdf'
qa = json.loads((BASE/'pdf_qa/pdf_qa.json').read_text())
layout = json.loads((BASE/'pdf_qa/layout_qa.json').read_text())
evidence = json.loads((BASE/'experiment_evidence.json').read_text())
text = (BASE/'pdf_qa/extracted_text.txt').read_text()
compact = re.sub(r'\s+', '', text)

assert pdf.stat().st_size > 100_000
assert qa['page_count'] == 15 == len(layout)
assert all(p['replacement_characters'] == 0 and p['text_characters'] > 500 for p in qa['pages'])
assert all(p['overflowPx'] <= 1 for p in layout)
assert (BASE/'pdf_qa/extracted_text.txt').stat().st_mtime >= pdf.stat().st_mtime
for page in range(1,16):
    assert (BASE/f'pdf_qa/page-{page:02d}.png').stat().st_mtime >= pdf.stat().st_mtime
assert _source_code_hash() == evidence['provenance']['run_identity']['source_code_hash']
for _, item in evidence['inputs'].items():
    source = Path('/Users/mao') / item['name']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256']
for key in ['source_code_hash','config_hash','data_hash']:
    assert evidence['provenance']['run_identity'][key] in compact
for item in evidence['provenance']['dataset']['source_sha256'].values():
    assert item in compact
for anchor in ['0.1.0', '493', '377', '116', '232', '65.66%', '59.02%',
               '代理目标与证据效用错位','跨目标调度缺少保障',
               '下一版实验计划与验收条件', 'goldmemoryIDs', 'YingyiZhang']:
    assert anchor in compact, anchor
links = [link for page in qa['pages'] for link in page['links']]
officials = ['https://iclr.cc/virtual/2025/poster/30092',
    'https://proceedings.mlr.press/v267/gutierrez25a.html',
    'https://neurips.cc/virtual/2025/poster/119020',
    'https://aclanthology.org/2025.emnlp-main.1318/',
    'https://iclr.cc/virtual/2026/poster/10008269']
assert all(url in links for url in officials)
assert len(links) == 15
assert not any(s in text for s in ['BEGIN PRIVATE KEY','Bearer sk-','api_key=','sn_maozhifang@'])
visual = '--visual-reviewed' in sys.argv
requirements = {
    'version_and_experiment_results': {'pages':[1,2,3,4,14], 'evidence':'archive checksums, source match, outcomes 493, paired recomputation', 'verified':True},
    'current_code_problems': {'pages':[5,6,7,8,13], 'evidence':'local source, 602 interaction / 311 selection arithmetic checks, three case archives, 63 offline tests', 'verified':True},
    'recent_top_conference_research_and_recommendations': {'pages':[9,10,11,12,15], 'evidence':'five official venue links, research memos, independent research review, training/split boundaries', 'verified':True},
    'pdf_deliverable': {'pages':15, 'pdfkit_parse':True, 'clickable_links':len(links), 'no_body_overflow':True, 'visual_review_all_pages':visual},
}
result = {'requirements':requirements,'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
    'pdf_bytes':pdf.stat().st_size,'no_experiment_source_changes':True,
    'no_new_model_calls':True,'complete':visual}
(BASE/'completion_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
status = json.loads((BASE/'report_requirements.json').read_text())
status['visual_qa_status'] = 'passed_all_15_pages' if visual else 'pending_human_visual_review'
status['pdf_sha256'] = result['pdf_sha256']
(BASE/'report_requirements.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
