"""Transient dirty-source installer integration; never a formal release build."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import time

SOURCE=Path('/Users/mao/projects/dagv2-personamem-v4')
BASE=Path('/Users/mao/projects/dagv2-personamem-a48')
EVIDENCE=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
PYTHON='/Users/mao/projects/dagv2/.venv/bin/python'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def inventory():
    rows={}
    for directory,dirs,names in os.walk(BASE,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ('.git','__pycache__') and not d.startswith('.venv')]
        for name in names:
            path=Path(directory)/name
            if path.is_file() and not path.is_symlink():
                info=path.stat()
                rows[path.relative_to(BASE).as_posix()]=(file_sha(path),info.st_size,info.st_mtime_ns,stat.S_IMODE(info.st_mode))
    return rows


def private_literals():
    found=[]
    def walk(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key.lower() in ('api_key','authorization','access_token','secret') and isinstance(item,str) and item:
                    found.append(item.encode())
                walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    for directory in (SOURCE,BASE):
        for path in (directory/'configs').glob('*.local.json'):
            walk(json.loads(path.read_text()))
    tree=ast.parse((BASE/'dagbt/model_runtime.py').read_text())
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEFAULT_BT_LLM_API_KEY' for t in node.targets):
            value=ast.literal_eval(node.value)
            if isinstance(value,str) and value:found.append(value.encode())
    return found


def main():
    started=time.time(); before=inventory(); secrets=private_literals()
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=SOURCE).decode().split('\0')
    files={}
    for relative in sorted(set(names)-{''}):
        path=SOURCE/relative
        if path.is_symlink() or not path.is_file() or relative.endswith(('.local.json','.npy','.tar.gz','.tgz')):
            raise ValueError('Unsafe simulated release file: '+relative)
        data=path.read_bytes()
        if any(secret in data for secret in secrets):
            raise ValueError('Private literal found in release source: '+relative)
        files[relative]=data
    metadata={name:{'sha256':sha(data),'bytes':len(data)} for name,data in files.items()}
    snapshot=sha(json.dumps(metadata,sort_keys=True).encode())
    manifest={'release_name':'personamem-v4-INSTALLER-SIMULATION-NOT-RELEASE',
        'base_commit':'a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1',
        'source_commit':'uncommitted-working-tree-simulation',
        'files':metadata,'validation':{'release_ready':False,'scope':'installer integration only',
        'source_snapshot_sha256':snapshot}}
    files['DEPLOYMENT.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    evidence={'kind':'uncommitted installer integration simulation, not final release verification',
        'source_snapshot_sha256':snapshot,'package_files':len(files),'secrets_scanned':len(set(secrets)),
        'credential_literals_absent':True,'base_file_count':len(before)}
    try:
        with tempfile.TemporaryDirectory(prefix='personamem-v4-install-simulation-') as temporary:
            directory=Path(temporary); archive=directory/'simulation.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                for relative,data in files.items():
                    info=tarfile.TarInfo('dagv2/'+relative);info.size=len(data);info.mode=0o755 if relative.endswith('.sh') else 0o644
                    tar.addfile(info,io.BytesIO(data))
            evidence['archive_sha256']=file_sha(archive); evidence['archive_bytes']=archive.stat().st_size
            extracted=directory/'extracted';extracted.mkdir()
            with tarfile.open(archive,'r:gz') as tar:
                members=tar.getmembers()
                assert len(members)==len(files) and all(m.isfile() for m in members)
                for member in members:
                    assert tar.extractfile(member).read()==files[member.name[len('dagv2/'):]]
                tar.extractall(extracted,filter='data')
            target=extracted/'dagv2'
            evidence['tar_roundtrip_verified']=True
            environment={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
            # Prove local migration rather than depend on this shell's keys.
            for key in ('DAG_LLM_API_KEY','BRIDGETREE_CHAT_API_KEY','DAG_EMBED_API_KEY'):
                environment.pop(key,None)
            results=[]
            for attempt in range(2):
                completed=subprocess.run([PYTHON,str(target/'scripts/install_personamem_v4.py'),'--base',str(BASE)],
                    cwd=target,env=environment,capture_output=True,text=True)
                if any(secret.decode() in completed.stdout+completed.stderr for secret in secrets):
                    raise ValueError('Installer output contained private data')
                if completed.returncode:
                    evidence['installer_failure']={'attempt':attempt+1,'returncode':completed.returncode,
                        'stdout':completed.stdout,'stderr':completed.stderr}
                    raise ValueError('Real extracted installer failed; sanitized detail saved in evidence')
                result=json.loads(completed.stdout); result.pop('smoke_command',None)
                results.append(result)
            evidence['installer_runs']=results
            evidence['idempotent']=results[0]['ready'] and results[1]['ready'] and results[1]['reused_frozen_vectors']==0
            originals=json.loads((target/'original_manifest.json').read_text())['files']
            assert all((target/row['path']).stat().st_size==row['bytes'] and file_sha(target/row['path'])==row['sha256'] for row in originals)
            evidence['original_artifacts_verified']=len(originals)
            evidence['frozen_vectors']=[{'path':row['path'],'sha256':row['sha256'],'bytes':row['bytes'],
                'separate_from_base_inode':(target/row['path']).stat().st_ino!=(BASE/row['path']).stat().st_ino}
                for row in originals if row['path'].endswith('.npy')]
            credentials=target/'configs/credentials.local.json'
            private=json.loads(credentials.read_text())
            evidence['credentials']={'mode':oct(stat.S_IMODE(credentials.stat().st_mode)),
                'llm_nonempty':bool(private.get('llm',{}).get('api_key')),
                'embedding_auth_present':bool(private.get('embedding',{}).get('api_key')),
                'logged':False,'packaged':False}
            assert evidence['credentials']['mode']=='0o600' and evidence['credentials']['llm_nonempty']
            derived=target/'data/derived';assert derived.is_symlink()
            evidence['derived_cache_symlink_target']=str(derived.resolve())
            manifests=list(derived.rglob('personamem/manifest.json'));assert len(manifests)==1
            index=json.loads(manifests[0].read_text());vectors=manifests[0].parent/'passage_vectors.npy'
            assert file_sha(vectors)==index['vectors_sha256']
            evidence['derived_index']={k:index[k] for k in ('identity','embedding_model','embedding_endpoint','corpus_sha256','documents','dimensions','vectors_sha256')}
        evidence['temporary_archive_and_credentials_removed']=True
        evidence['passed']=True
    finally:
        evidence['base_files_unchanged']=inventory()==before
        evidence['elapsed_seconds']=round(time.time()-started,3)
        (EVIDENCE/'installer_integration_simulation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        (EVIDENCE/'installer_integration_simulation_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    assert evidence['base_files_unchanged']
    print(json.dumps({k:evidence[k] for k in ('passed','package_files','archive_bytes','idempotent','original_artifacts_verified','base_files_unchanged','credentials','elapsed_seconds')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
