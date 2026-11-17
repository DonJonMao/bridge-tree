"""Preserve DAGBT records and dependencies; deletion is a separate explicit stage."""
from pathlib import Path
import os, sys, json, hashlib, tarfile, shutil, time, subprocess

B=Path('/Users/mao/projects')
W=B/'tmp/dagbt_cleanup_20261027'
A=B/'dagv2_analysis/cleanup_20261027'
BEFORE=json.loads((A/'manifests/before.json').read_text())
KEEP=BEFORE['keep']; OLD=BEFORE['remove_old_code']
DEPLOY=[Path(x) for x in (W/'deploy_source_roots.txt').read_text().splitlines() if x]
STATE=A/'manifests/migration.json'
S=json.loads(STATE.read_text()) if STATE.exists() else {'created':time.time(),'moves':[], 'data':[], 'snapshots':[], 'links':[], 'free_bytes_before':shutil.disk_usage(B).free}
CACHE={}

def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def save(): dump(STATE,S)
def sha(p):
    st=p.stat(); key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
    if key not in CACHE:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
        CACHE[key]=h.hexdigest()
    return CACHE[key]
def sha_stream(f):
    h=hashlib.sha256()
    for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def files(root, skip=()):
    for base,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=[x for x in dirs if x not in skip]
        for n in names:
            p=Path(base)/n
            if p.is_file() and not p.is_symlink():yield p
def move(src,dst,kind):
    if not src.exists() and not src.is_symlink():
        assert any(r['source']==str(src) and r['destination']==str(dst) for r in S['moves']),str(src)
        return
    assert not dst.exists() and not dst.is_symlink(),str(dst)
    dst.parent.mkdir(parents=True,exist_ok=True)
    os.rename(src,dst)
    S['moves'].append({'source':str(src),'destination':str(dst),'kind':kind});save()
def translated(p):
    text=str(p)
    matches=[r for r in S['moves'] if text==r['source'] or text.startswith(r['source']+'/')]
    if matches:
        r=max(matches,key=lambda r:len(r['source']))
        return Path(r['destination']+text[len(r['source']):])
    return p
def under(p,roots):return any(p==r or p.is_relative_to(r) for r in roots)

if '--delete' in sys.argv:
    assert S.get('preserved_verified'), 'Preservation verification must finish first'
    assert not S.get('deleted'), 'Already deleted'
    # Fixed allowlists only: never traverse symlink roots for recursive removal.
    already_removed=set(S.get('deleted_roots',[]))
    for p in [B/n for n in OLD]+DEPLOY:
        if str(p) in already_removed:
            assert not p.exists() and not p.is_symlink(),str(p)
            continue
        assert p.is_dir() and not p.is_symlink(),str(p)
        assert p.parent==B or p.is_relative_to(B/'dagv2_deploy')
        assert not under(p,[B/n for n in KEEP]+[A])
    S.setdefault('free_bytes_before_delete',shutil.disk_usage(B).free);save()
    for p in DEPLOY+[B/n for n in OLD]:
        if str(p) in already_removed:continue
        shutil.rmtree(p)
        S.setdefault('deleted_roots',[]).append(str(p));save()
        print('Removed obsolete code:',p.relative_to(B),flush=True)
    S['deleted']=True;S['free_bytes_after_delete']=shutil.disk_usage(B).free;save()
    sys.exit(0)

assert not S.get('preserved_verified'), 'Migration already complete'

# Replace six links by their actual dependency contents without copying large files.
deps=[(B/'dagv2-personamem-a48/data/derived',B/'dagv2-personamem-v4/data/derived'),
      (B/'dagv2-webwalker/_webwalker_browser_vendor',B/'dagv2-webwalker-v4/_webwalker_browser_vendor'),
      (B/'dagv2-webwalker/_webwalker_browsers',B/'dagv2-webwalker-v4/_webwalker_browsers')]
for dataset in ('2wikimultihopqa','hotpotqa','musique'):
    deps.append((B/f'dagv2/data/{dataset}/index/passage_vectors.npy',B/f'dagv2-webwalker-v4/data/{dataset}/index/passage_vectors.npy'))
for src,dst in deps:
    if dst.is_symlink():
        assert dst.resolve()==src.resolve(),str(dst)
        original=os.readlink(dst);dst.unlink()
        move(src,dst,'materialized_final_dependency')
        S['links'].append({'path':str(dst),'old_target':original,'action':'materialized'});save()
    else:assert dst.exists(),str(dst)
print('Final runtime dependencies materialized',flush=True)

# Preserve each unique old dataset/index/cache file once, with exact canonical mapping.
canonical={}
for name in KEEP:
    for p in files(B/name/'data'):canonical.setdefault(sha(p),str(p))
known={r['source'] for r in S['data']}
for name in OLD:
    for p in list(files(B/name/'data')):
        if str(p) in known:continue
        digest=sha(p);size=p.stat().st_size
        if digest not in canonical:
            dst=A/'assets/old_data'/name/p.relative_to(B/name/'data')
            move(p,dst,'unique_old_dataset');canonical[digest]=str(dst)
        S['data'].append({'source':str(p),'canonical':canonical[digest],'sha256':digest,'bytes':size})
    save()
print('All old data files covered:',len(S['data']),flush=True)

# Preserve full output/result trees and research temp; no raw run records are dropped.
for name in OLD:
    for part in ('outputs','results'):
        src=B/name/part
        if src.exists() or any(r['source']==str(src) for r in S['moves']):
            move(src,A/'results'/name/part,'historical_experiment_tree')
move(B/'dagv2/tmp',A/'research/dagv2_tmp','historical_research')

# Archives excluded from source snapshots must survive as whole original files.
for name in OLD:
    for p in list(files(B/name,skip={'.git','.venv','__pycache__','.pytest_cache','data'})):
        if p.name.endswith(('.tar.gz','.tgz','.zip')):
            move(p,A/'artifacts'/name/p.relative_to(B/name),'historical_archive')

exceptions=json.loads((W/'deploy_removal_exceptions.json').read_text())
for category in ('runtime_records','local_secret_files'):
    for r in exceptions[category]:
        src=B/'dagv2_deploy'/r['root']/r['path']
        dst=A/('private' if category=='local_secret_files' else 'results/deployment')/r['root']/r['path']
        move(src,dst,category)
        if category=='local_secret_files':
            os.chmod(A/'private',0o700);os.chmod(dst,0o600)

# Snapshot source-only repair candidates and unpacked source roots, retaining all unique code.
skip={'.git','.venv','.pytest_cache','__pycache__','data','outputs','results',
      '_webwalker_browser_vendor','_webwalker_browsers','_webwalker_vendor'}
def tar_filter(info):
    if any(x in {'.DS_Store','__pycache__','.pytest_cache'} for x in Path(info.name).parts):return None
    if info.name.endswith('.pyc'):return None
    return info
for i,root in enumerate(DEPLOY,1):
    rel=root.relative_to(B/'dagv2_deploy')
    dest=A/'source_snapshots/deployment'/('__'.join(rel.parts)+'.source.tar.gz')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():
        with tarfile.open(dest,'w:gz',compresslevel=6,dereference=False) as tf:
            for p in sorted(root.iterdir()):
                if p.name not in skip:tf.add(p,arcname=str(p.relative_to(root)),filter=tar_filter)
    os.chmod(dest,0o600)
    row={'source':str(root),'archive':str(dest),'sha256':sha(dest)}
    if not any(r['source']==str(root) for r in S['snapshots']):S['snapshots'].append(row);save()
    print(f'Source snapshot {i}/{len(DEPLOY)} verified readable',flush=True)

# Build source snapshot member hash index and verify every surviving regular source file.
covered={}
old_snapshot_rows=json.loads((A/'manifests/source_snapshots.json').read_text())
for r in old_snapshot_rows+S['snapshots']:
    root=Path(r['source']);archive=Path(r['archive'])
    assert sha(archive)==r['sha256'],str(archive)
    os.chmod(archive,0o600)
    with tarfile.open(archive,'r:gz') as tf:
        for member in tf:
            if not member.isfile():continue
            rel=Path(member.name)
            if root.parent==B:rel=Path(*rel.parts[1:])
            p=root/rel
            digest=sha_stream(tf.extractfile(member))
            if p.exists():assert sha(p)==digest,str(p)
            covered[str(p)]={'archive':str(archive),'member':member.name,'sha256':digest}
    for p in files(root,skip=skip|({'tmp'} if root.parent==B else set())):
        if p.name=='.git' or p.name=='.DS_Store' or p.suffix=='.pyc':continue
        assert str(p) in covered, 'Unpreserved source file: '+str(p)
dump(A/'manifests/source_file_coverage.json',covered)
print('All old regular source files verified against snapshots',flush=True)

# Relocate absolute links inside moved experiment trees using the longest exact prefix.
# Data links may point to deduplicated canonical files.
data_map={r['source']:r['canonical'] for r in S['data']}
for base,dirs,names in os.walk(A,followlinks=False):
    for n in dirs+names:
        p=Path(base)/n
        if not p.is_symlink():continue
        original=os.readlink(p)
        if not os.path.isabs(original):continue
        target=Path(original);new=translated(target)
        if str(target) in data_map:new=Path(data_map[str(target)])
        if new!=target:
            p.unlink();p.symlink_to(new)
            S['links'].append({'path':str(p),'old_target':original,'new_target':str(new),'exists':p.exists(),'action':'rewritten'})
save()

# Verify every inventoried experiment/report file via migrated path or source snapshot.
inventory=json.loads((W/'results_inventory.json').read_text())
verified=[]
for row in inventory['files']:
    original=Path(row['path']);dest=translated(original)
    if dest==original and under(original,[B/n for n in OLD]+DEPLOY) and str(original) in covered:
        r=covered[str(original)];assert r['sha256']==row['sha256'],str(original)
        verified.append({'source':str(original),**r})
    elif dest.is_file():
        assert sha(dest)==row['sha256'],str(dest)
        verified.append({'source':str(original),'destination':str(dest),'sha256':row['sha256']})
    elif str(original) in covered:
        r=covered[str(original)];assert r['sha256']==row['sha256'],str(original)
        verified.append({'source':str(original),**r})
    else:raise AssertionError('Missing inventoried evidence: '+str(original))
dump(A/'manifests/experiment_file_coverage.json',verified)
for row in inventory['archives']:
    p=translated(Path(row['path']));assert p.is_file() and sha(p)==row['sha256'],str(p)
for row in S['data']:
    p=Path(row['canonical']);assert p.is_file() and sha(p)==row['sha256'],str(p)

# Keep all machine inventories and audit reports in the permanent archive.
for p in W.iterdir():
    if p.is_file() and p.suffix in {'.json','.md','.txt','.py'}:
        shutil.copy2(p,A/'manifests'/p.name)
S['preserved_verified']=True;S['verified_result_files']=len(verified);S['finished_preservation']=time.time();save()
print('PRESERVATION VERIFIED:',len(verified),'experiment/report files; no old source roots deleted yet',flush=True)
