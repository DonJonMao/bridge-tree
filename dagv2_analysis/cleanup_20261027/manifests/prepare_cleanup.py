from pathlib import Path
import os, json, hashlib, subprocess, tarfile, shutil, time

BASE = Path('/Users/mao/projects')
WORK = BASE/'tmp/dagbt_cleanup_20261027'
ARCH = BASE/'dagv2_analysis/cleanup_20261027'
KEEP = ['dagv2-personamem-v4', 'dagv2-prefeval-v4-fix3', 'dagv2-webwalker-v4']
OLD = ['dagv2', 'dagv2-personamem-a48', 'dagv2-personamem-v4-reconcile',
       'dagv2-prefeval-v4', 'dagv2-prefeval-v4-fix', 'dagv2-prefeval-v4-fix2',
       'dagv2-residual-f4', 'dagv2-support-review', 'dagv2-webwalker']

def run(*args, cwd=None):
    r=subprocess.run(list(args),cwd=cwd,capture_output=True,text=True)
    if r.returncode:
        raise RuntimeError((args,r.returncode,r.stderr[-1600:]))
    return r.stdout

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def source_inventory(root):
    rows={}
    skip={'.git','.venv','.pytest_cache','__pycache__','data','outputs','results',
          '_webwalker_browser_vendor','_webwalker_browsers','_webwalker_vendor','tmp'}
    for base,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in skip]
        for n in files:
            p=Path(base)/n
            if n in ('.DS_Store','.git') or p.is_symlink():continue
            rows[str(p.relative_to(root))]={'sha256':sha(p),'size':p.stat().st_size}
    return rows

ARCH.mkdir(parents=True,exist_ok=True)
for n in ('history','source_snapshots','manifests','results','artifacts','research','assets'):
    (ARCH/n).mkdir(exist_ok=True)
assert not (ARCH/'manifests/prepared.json').exists(), 'Preparation already complete'

before_path=ARCH/'manifests/before.json'
if before_path.exists():
    before=json.loads(before_path.read_text())
    for files in before['retained_sources'].values():files.pop('.git',None)
else:
    before={'created':'2026-10-27','keep':KEEP,'remove_old_code':OLD,'git':{},'retained_sources':{}}
    for name in KEEP+OLD:
        p=BASE/name
        if (p/'.git').exists():
            before['git'][name]={
                'head':run('git','-C',str(p),'rev-parse','HEAD').strip(),
                'branch':run('git','-C',str(p),'branch','--show-current').strip(),
                'status':run('git','-C',str(p),'status','--porcelain=v1','--untracked-files=all').splitlines(),
                'tracked_diff_sha256':hashlib.sha256(run('git','-C',str(p),'diff','--binary','HEAD').encode()).hexdigest()}
            (ARCH/'history'/f'{name}.working-tree.patch').write_text(run('git','-C',str(p),'diff','--binary','HEAD'))
            if (p/'.git').is_file():
                (ARCH/'history'/f'{name}.old-git-pointer.txt').write_text((p/'.git').read_text())
    for name in KEEP:
        before['retained_sources'][name]=source_inventory(BASE/name)
dump(ARCH/'manifests/before.json',before)
print('Saved pre-cleanup identities and final-source hashes',flush=True)

bundle=ARCH/'history/dagv2_all_refs.bundle'
if not bundle.exists():run('git','-C',str(BASE/'dagv2'),'bundle','create',str(bundle),'--all')
verification=run('git','-C',str(BASE/'dagv2'),'bundle','verify',str(bundle))
(ARCH/'history/bundle_verification.txt').write_text(verification)
print('Saved and verified all Git branch history',bundle.stat().st_size,flush=True)

snapshots=[]
skip_top={'.git','.venv','.pytest_cache','__pycache__','data','outputs','results',
          '_webwalker_browser_vendor','_webwalker_browsers','_webwalker_vendor','tmp'}
def tar_filter(info):
    parts=Path(info.name).parts
    if any(p in {'__pycache__','.pytest_cache','.DS_Store'} for p in parts):return None
    if info.name.endswith(('.tar.gz','.zip','.tgz','.pyc')):return None
    return info
for name in OLD:
    root=BASE/name
    dest=ARCH/'source_snapshots'/f'{name}.source.tar.gz'
    if not dest.exists():
        with tarfile.open(dest,'w:gz',compresslevel=6,dereference=False) as out:
            for p in sorted(root.iterdir()):
                if p.name not in skip_top:out.add(p,arcname=f'{name}/{p.name}',filter=tar_filter)
    with tarfile.open(dest,'r:gz') as check:count=sum(1 for _ in check)
    snapshots.append({'source':str(root),'archive':str(dest),'sha256':sha(dest),'members':count})
    print('Saved source snapshot',name,count,flush=True)
dump(ARCH/'manifests/source_snapshots.json',snapshots)

for name in ('dagv2-personamem-v4','dagv2-webwalker-v4'):
    dest=BASE/name
    old_pointer=dest/'.git'
    if old_pointer.is_dir():continue
    assert old_pointer.is_file()
    clone=WORK/f'{name}.git-preparation'
    assert not clone.exists(),str(clone)
    branch=before['git'][name]['branch']
    run('git','clone','--no-hardlinks','--no-checkout','--branch',branch,
        str(BASE/'dagv2'),str(clone))
    run('git','-C',str(clone),'reset','--mixed','HEAD')
    run('git','-C',str(clone),'remote','set-url','origin',str(bundle))
    old_pointer.unlink()
    shutil.move(str(clone/'.git'),str(old_pointer))
    shutil.rmtree(clone)
    assert run('git','-C',str(dest),'rev-parse','HEAD').strip()==before['git'][name]['head']
    diff=hashlib.sha256(run('git','-C',str(dest),'diff','--binary','HEAD').encode()).hexdigest()
    assert diff==before['git'][name]['tracked_diff_sha256'],name
    assert source_inventory(dest)==before['retained_sources'][name],name
    print('Made final repository independent; source and tracked edits unchanged:',name,flush=True)

dump(ARCH/'manifests/prepared.json',{'ok':True,'time':time.time(),'bundle':str(bundle),
                                 'kept_repositories':KEEP,'source_snapshots':len(snapshots)})
print('Preparation complete; no old source directory removed',flush=True)
