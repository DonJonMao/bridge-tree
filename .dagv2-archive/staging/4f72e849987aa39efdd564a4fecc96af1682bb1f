#!/usr/bin/env python3
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, subprocess, tarfile

STAGE = Path(__file__).resolve().parent
OLD = STAGE / 'release_v2/dagbt_benchmarks_v4_experiment'
REPO = Path('/Users/mao/projects/dagv2-webwalker-v4')
NAME = 'dagbt_webwalker_v4_v2_experiment'
BASELINE = 'e6677081cdfb33c01db3aaa274a497168f314f78'

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--extract', type=Path)
    args=parser.parse_args()
    old=json.loads((OLD/'bundle_manifest.json').read_text())
    def keep(path):
        return ('browsecomp' not in path.lower() and 'benchmark' not in path.lower())
    expected={path:digest for path,digest in old['payload_sha256'].items() if keep(path)}
    require(len(expected)==155, 'Unexpected WebWalker subset size')
    seen={}
    manifest=None
    with tarfile.open(args.archive, 'r:gz') as archive:
        for member in archive.getmembers():
            path=PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and path.parts[0]==NAME,
                    'Unsafe member path')
            if member.isdir():
                continue
            require(member.isfile() and not member.issym() and not member.islnk(), 'Special member')
            relative=str(path.relative_to(NAME))
            require(relative not in seen, 'Duplicate archive member')
            require(not any(part in ('credentials.local.json','__pycache__','.git','outputs')
                            for part in path.parts), 'Private/cache/old output member')
            require('browsecomp' not in relative.lower() and 'benchmark' not in relative.lower(),
                    'Excluded benchmark payload remains')
            raw=archive.extractfile(member).read()
            seen[relative]=hashlib.sha256(raw).hexdigest()
            if relative=='bundle_manifest.json':
                manifest=json.loads(raw)
        require(isinstance(manifest,dict), 'Missing manifest')
        actual={path[len('payload/'):]:digest for path,digest in seen.items() if path.startswith('payload/')}
        require(actual==expected and manifest['payload_sha256']==expected,
                'Archive or manifest differs from exact v2 subset')
        for path,digest in expected.items():
            require(sha(OLD/'payload'/path)==digest, 'Retained old v2 payload changed')
        core={}
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE],cwd=REPO,text=True).splitlines()
        for path in paths:
            if path.endswith('.py') and path.split('/')[0] in ('dagbt','dagv2','dagresolve','package','vendor'):
                core[path]=hashlib.sha256(subprocess.check_output(['git','show',BASELINE+':'+path],cwd=REPO)).hexdigest()
        require(len(core)==107 and manifest['baseline_source_sha256']==core, 'Core baseline differs')
        require(all(actual.get(path)==digest for path,digest in core.items()), 'Public core changed')
        require(seen['install_webwalker.py']==sha(OLD/'install_webwalker.py'), 'Installer changed')
        wheel=old['pdf_wheel']
        require(manifest['pdf_wheel']==wheel and seen[wheel]==old['pdf_wheel_sha256'], 'PDF wheel differs')
        allowed={'payload/'+path for path in expected}|{'bundle_manifest.json','install_webwalker.py',
                 'README.md','validation.json','install_and_run.sh','install_and_offline.sh',wheel}
        require(set(seen)==allowed, 'Unexpected/missing top-level members')
        if args.extract:
            require(not args.extract.exists(), 'Extraction destination must be new')
            args.extract.mkdir(parents=True)
            archive.extractall(args.extract, filter='data')
    report={'verified':True,'archive':str(args.archive.resolve()),'archive_sha256':sha(args.archive),
            'bytes':args.archive.stat().st_size,'payload_files':len(expected),'regular_files':len(seen),
            'unchanged_public_core_python_files':len(core),'all_retained_payload_bytes_equal_v2':True,
            'browsecomp_or_dual_suite_payload_files':0,'private_credentials_or_old_outputs':False,
            'extracted_to':str(args.extract.resolve()) if args.extract else None}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
