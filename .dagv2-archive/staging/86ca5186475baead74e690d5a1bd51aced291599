import gzip
import hashlib
import json
from pathlib import Path
import tarfile
import time

BASE = Path(__file__).resolve().parent
ARCHIVE = Path('/Users/mao/projects/dagv2/scripts/personamem_v3_1_diagnostics.tar.gz')
started = ARCHIVE.stat()
index = []
failure = None
try:
    with tarfile.open(ARCHIVE, 'r|gz') as tar:
        for entry in tar:
            rel = Path(entry.name)
            if rel.is_absolute() or '..' in rel.parts or not (entry.isfile() or entry.isdir()):
                raise ValueError('Unsafe archive entry: ' + entry.name)
            if not entry.isfile():
                continue
            raw = tar.extractfile(entry).read()
            if len(raw) != entry.size:
                raise ValueError('Short member: ' + entry.name)
            sha = hashlib.sha256(raw).hexdigest()
            if '/rows/' in entry.name:
                target = BASE / 'compressed_rows' / (entry.name + '.gz')
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix('.tmp')
                with gzip.open(temp, 'wb', compresslevel=1) as handle:
                    handle.write(raw)
                temp.replace(target)
                row = json.loads(raw)
                info = {'archive_path': entry.name, 'path': str(target.relative_to(BASE)),
                        'bytes': entry.size, 'sha256': sha, 'unit_id': row['unit_id'],
                        'arm': rel.parts[1], 'status': row['answer']['status']}
                index.append(info)
                with (BASE / 'row_index.jsonl').open('a') as handle:
                    handle.write(json.dumps(info) + '\n')
                if len(index) % 100 == 0:
                    print('Processed', len(index), 'rows', flush=True)
            else:
                target = BASE / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
except (EOFError, tarfile.ReadError) as exc:
    failure = repr(exc)
ended = ARCHIVE.stat()
report = {'archive': str(ARCHIVE), 'started_size': started.st_size, 'ended_size': ended.st_size,
          'started_mtime': started.st_mtime, 'ended_mtime': ended.st_mtime,
          'error': failure, 'complete_rows': len(index), 'rows': index, 'finished_unix': time.time()}
if failure is None:
    h = hashlib.sha256()
    with ARCHIVE.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    report['archive_sha256'] = h.hexdigest()
(BASE / 'extraction_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2), flush=True)
