"""Print an offline HTML report with an isolated browser and audit geometry."""
import html
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
source = BASE / 'BridgeTree_Audit_2026-09-15.html'
pdf = BASE / 'BridgeTree_Audit_2026-09-15.pdf'
qa = BASE / 'pdf_qa'
qa.mkdir(exist_ok=True)
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
start = time.time()
with tempfile.TemporaryDirectory(prefix='bridgetree-pdf-') as profile:
    cmd = [chrome, '--headless', '--disable-gpu', '--no-first-run',
        '--no-default-browser-check', '--disable-background-networking',
        '--disable-component-update', '--disable-sync', '--disable-extensions',
        '--disable-default-apps', '--disable-background-mode', '--no-service-autorun',
        '--metrics-recording-only', '--virtual-time-budget=1000',
        '--user-data-dir='+profile, '--no-pdf-header-footer', '--dump-dom',
        '--print-to-pdf='+str(pdf), source.as_uri()]
    with (qa/'browser_dom.html').open('w') as stdout, (qa/'browser_render.log').open('w') as stderr:
        process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        try:
            for _ in range(100):
                time.sleep(0.2)
                dom = (qa/'browser_dom.html').read_text()
                pdf_ready = pdf.exists() and pdf.stat().st_mtime >= start and pdf.stat().st_size > 1000
                if pdf_ready and '</html>' in dom:
                    time.sleep(0.5)
                    break
                if process.poll() is not None:
                    break
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    dom = (qa/'browser_dom.html').read_text()
    match = re.search(r'<pre id="layout-qa">(.*?)</pre>', dom, re.S)
    if not match:
        raise RuntimeError('Browser did not emit layout audit')
    layout = json.loads(html.unescape(match.group(1)))
    (qa/'layout_qa.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2))
    assert pdf.exists() and pdf.stat().st_mtime >= start, 'PDF was not regenerated'
    overflow = [p for p in layout if p['overflowPx'] > 1]
    print(json.dumps({'pdf':str(pdf),'bytes':pdf.stat().st_size,'pages':len(layout),'overflow':overflow},ensure_ascii=False,indent=2))
    if overflow:
        raise RuntimeError('Report content exceeds page body bounds')
