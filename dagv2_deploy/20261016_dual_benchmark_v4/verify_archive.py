"""Stream-check a generated benchmark archive without another full disk copy."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, importlib.util, json, subprocess, tarfile, time

parser=argparse.ArgumentParser()
parser.add_argument('archive')
parser.add_argument('--report',required=True)
args=parser.parse_args()
archive=Path(args.archive)
started=time.monotonic()
name='dagbt_benchmarks_v4_experiment'
root=name+'/'
seen={}
manifest=None
with tarfile.open(archive,'r|gz') as stream:
    for member in stream:
        path=PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or path.parts[0] != name:
            raise ValueError('Unsafe archive member')
        if member.isdir():
            continue
        if not member.isfile() or member.issym() or member.islnk():
            raise ValueError('Unexpected link or special archive member: '+member.name)
        relative=member.name[len(root):]
        if relative in seen or relative.startswith('outputs/') or '/outputs/' in relative:
            raise ValueError('Duplicate or old output archive member')
        if any(piece in ('credentials.local.json','__pycache__','.git') for piece in path.parts):
            raise ValueError('Private or cache archive member')
        source=stream.extractfile(member)
        digest=hashlib.sha256()
        if relative == 'bundle_manifest.json':
            data=source.read()
            digest.update(data)
            manifest=json.loads(data)
        else:
            for block in iter(lambda: source.read(1024*1024), b''):
                digest.update(block)
        seen[relative]=digest.hexdigest()
if manifest is None or manifest.get('credentials_in_bundle') is not False:
    raise ValueError('Missing or invalid bundle manifest')
baseline='e6677081cdfb33c01db3aaa274a497168f314f78'
repo=Path('/Users/mao/projects/dagv2-webwalker-v4')
core={}
for relative in subprocess.check_output(['git','ls-tree','-r','--name-only',baseline],cwd=repo,text=True).splitlines():
    if relative.endswith('.py') and relative.split('/')[0] in ('dagbt','dagv2','dagresolve','package','vendor'):
        original=subprocess.check_output(['git','show',baseline+':'+relative],cwd=repo)
        core[relative]=hashlib.sha256(original).hexdigest()
if len(core)!=107 or manifest.get('baseline_commit')!=baseline or manifest.get('baseline_source_sha256')!=core:
    raise ValueError('Archive baseline manifest differs from independently read fixed core107')
expected=manifest['payload_sha256']
actual={key[len('payload/'):]:value for key,value in seen.items() if key.startswith('payload/')}
if actual != expected:
    raise ValueError('Archive payload hashes differ')
spec=importlib.util.spec_from_file_location('local_packager',repo/'scripts/package_benchmarks.py')
packager=importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
if set(actual)!=set(packager.payload_paths(core)):
    raise ValueError('Archive payload list differs from the local authorized package recipe')
for key,value in manifest['baseline_source_sha256'].items():
    if actual.get(key)!=value:
        raise ValueError('Baseline source hash differs')
if seen[manifest['pdf_wheel']]!=manifest['pdf_wheel_sha256']:
    raise ValueError('PDF dependency hash differs')
fixed={key for key in actual if key.startswith('data/browsecomp_plus/')}
if fixed != {'data/browsecomp_plus/'+piece for piece in ('manifest.json','questions.jsonl','evaluation_only.json','corpus.sqlite3')}:
    raise ValueError('Expected exactly four BrowseComp runtime artifacts')
for launcher in ('install_and_run.sh','install_and_smoke.sh','install_webwalker.py','README.md','validation.json'):
    if launcher not in seen:
        raise ValueError('Missing bundle launcher/document: '+launcher)
allowed={'payload/'+key for key in expected}|{'bundle_manifest.json',manifest['pdf_wheel'],'install_and_run.sh','install_and_smoke.sh','install_webwalker.py','README.md','validation.json'}
if set(seen)!=allowed:
    raise ValueError('Unexpected top-level archive files: '+str(sorted(set(seen)^allowed)))
result={'verified':True,'archive':str(archive),'regular_files':len(seen),'payload_files':len(actual),'unchanged_public_python_files':len(manifest['baseline_source_sha256']),'dataset_questions':{key:value.get('questions',value.get('rows')) for key,value in manifest['datasets'].items()},'private_credentials_or_old_outputs':False,'seconds':round(time.monotonic()-started,3)}
Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
