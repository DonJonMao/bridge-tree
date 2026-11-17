"""Run the offline suite and bind its result to unchanged source bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


root = Path(sys.argv[1]).resolve()
prefix = Path(sys.argv[2]).resolve()
log = prefix.with_suffix('.txt')
receipt_path = prefix.with_name(prefix.name + '_receipt.json')
if log.exists() or receipt_path.exists():
    raise SystemExit('Refusing to replace an earlier test receipt')


def snapshot():
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root)
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in sorted(set(names.decode().split('\0')) - {''})
            if (root / name).is_file()}


before = snapshot()
base_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
started = time.time()
command = [sys.executable, '-m', 'pytest', '-q', 'tests']
with log.open('w') as output:
    result = subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.STDOUT)
after = snapshot()
receipt = {
    'root': str(root), 'base_commit': base_commit, 'command': command,
    'started_unix': started, 'finished_unix': time.time(),
    'exit_code': result.returncode, 'source_unchanged': before == after,
    'source_before': before, 'source_after': after,
    'log': str(log), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
}
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({key: value for key, value in receipt.items()
                  if key not in ('source_before', 'source_after')}, indent=2))
print('Tested source files:', len(before))
print('\n'.join(log.read_text().splitlines()[-4:]))
raise SystemExit(result.returncode or (0 if before == after else 2))
