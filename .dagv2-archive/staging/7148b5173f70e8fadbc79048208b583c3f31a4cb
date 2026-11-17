from __future__ import annotations
import collections
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import zipfile

BASE = Path('/Users/mao/projects')
DEST = BASE / 'tmp/dagbt_cleanup_20261027'
KEEP = {'dagv2-personamem-v4', 'dagv2-prefeval-v4-fix3', 'dagv2-webwalker-v4'}
SKIP = {'.git','.venv','node_modules','__pycache__','.pytest_cache','site-packages'}
LIBRARY = {'data','configs','vendor','third_party','serving','package','dagbt','dagv2','dagresolve','tests','_webwalker_vendor','_webwalker_browser_vendor','_webwalker_browsers'}
EXT = ('.json','.jsonl','.csv','.tsv','.log','.txt','.md','.xml','.out','.err','.stdout','.stderr','.json.gz')
ARCH = ('.tar.gz','.tgz','.tar','.zip','.tar.zst','.7z')

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def result_category(parts):
    if not parts:return None
    low=[p.lower() for p in parts]
    name=low[-1]
    if any(name.endswith(ext) for ext in ARCH):return 'archive'
    if 'outputs' in low:return 'outputs'
    if 'results' in low:return 'results_summary'
    if 'results_analysis_20261008' in low:return 'analysis'
    if low[0]=='docs' and name.endswith(('.md','.json','.txt','.xml','.csv','.jsonl','.log')):return 'protocol_and_validation_docs'
    if low[0] in LIBRARY:return None
    if name.endswith(('.log','.out','.err','.stdout','.stderr','.xml')):return 'scattered_execution_evidence'
    if name.endswith(('.json','.jsonl','.csv','.tsv','.json.gz')):return 'scattered_structured_evidence'
    if name.endswith(('.md','.txt')) and not name.startswith(('requirements','license')):return 'scattered_report'
    return None

def archive_category(parts):
    # Archives may prepend arbitrary deployment/smoke run directory names.
    low=[p.lower() for p in parts]
    if not low:return None
    if any(p in {'outputs','results','attempts','rows','requests','index_build','diagnostics','preflight_calls'} for p in low):return 'archived_result'
    if any(p in LIBRARY for p in low[:-1]):return None
    if low[-1].endswith(EXT):return 'archived_report_or_diagnostic'
    return None

def walk(root):
    for dp,ds,fs in os.walk(root):
        ds[:]=[d for d in ds if d not in SKIP]
        for name in fs:
            if name=='.DS_Store':continue
            p=Path(dp)/name
            if p.is_symlink():continue
            try:
                if p.is_file():yield p
            except OSError:pass

def run():
    start=time.time()
    roots=[p for p in sorted(BASE.glob('dagv2*')) if p.is_dir() and p.name!='dagv2_analysis']
    records=[];rootstats={};archives=[]
    for root in roots:
        counts=collections.Counter();sizes=collections.Counter()
        for p in walk(root):
            rel=p.relative_to(root);size=p.stat().st_size
            top=rel.parts[0] if len(rel.parts)>1 else '<root>'
            counts[top]+=1;sizes[top]+=size
            # In deploy trees, library directories occur after release/install prefixes.
            category=result_category(rel.parts)
            if root.name=='dagv2_deploy' and category!='archive':
                if any(x.lower() in LIBRARY for x in rel.parts[:-1]):
                    category='outputs' if 'outputs' in rel.parts else ('results_summary' if 'results' in rel.parts else None)
            if category:
                record={'path':str(p),'root':root.name,'relative_path':str(rel),'bytes':size,'category':category,
                        'root_action':'keep_in_place' if root.name in KEEP else 'preserve_before_removing_code',
                        'sha256':sha(p)}
                records.append(record)
                if category=='archive':archives.append(record)
        rootstats[root.name]={'files':sum(counts.values()),'bytes':sum(sizes.values()),
            'top_level':{k:{'files':counts[k],'bytes':sizes[k]} for k in sorted(counts)}}
        print('FILES_HASHED',root.name,sum(r['root']==root.name for r in records),flush=True)
    (DEST/'results_inventory.files.json').write_text(json.dumps({'roots':rootstats,'files':records},ensure_ascii=False,indent=2))
    members=[];archive_reports=[]
    for archive in archives:
        p=Path(archive['path']);report={'path':str(p),'sha256':archive['sha256'],'bytes':archive['bytes'],
                'member_files':0,'member_uncompressed_bytes':0,'result_members':0,'result_uncompressed_bytes':0,
                'top_level':{},'error':None}
        tops=collections.Counter()
        try:
            if p.name.endswith('.zip'):
                with zipfile.ZipFile(p) as z:
                    for info in z.infolist():
                        if info.is_dir():continue
                        report['member_files']+=1;report['member_uncompressed_bytes']+=info.file_size
                        tops[info.filename.split('/')[0]]+=1
                        category=archive_category(Path(info.filename).parts)
                        if category:
                            h=hashlib.sha256()
                            with z.open(info) as f:
                                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
                            members.append({'archive':str(p),'member':info.filename,'bytes':info.file_size,'sha256':h.hexdigest(),'category':category})
                            report['result_members']+=1;report['result_uncompressed_bytes']+=info.file_size
            else:
                with tarfile.open(p,'r|*') as t:
                    for info in t:
                        if not info.isfile():continue
                        report['member_files']+=1;report['member_uncompressed_bytes']+=info.size
                        tops[info.name.split('/')[0]]+=1
                        category=archive_category(Path(info.name).parts)
                        if category:
                            h=hashlib.sha256();f=t.extractfile(info)
                            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
                            members.append({'archive':str(p),'member':info.name,'bytes':info.size,'sha256':h.hexdigest(),'category':category})
                            report['result_members']+=1;report['result_uncompressed_bytes']+=info.size
        except Exception as exc:report['error']=repr(exc)
        report['top_level']=dict(tops);archive_reports.append(report)
        print('ARCHIVE_DONE',p.name,'result_members',report['result_members'],'result_bytes',report['result_uncompressed_bytes'],flush=True)
        (DEST/'results_inventory.archives.json').write_text(json.dumps({'archives':archive_reports,'result_members':members},ensure_ascii=False,indent=2))
    # Exact-byte comparison against immutable protected areas; read only matching sizes.
    candidate_sizes={r['bytes'] for r in records}|{m['bytes'] for m in members}
    wanted_hashes={r['sha256'] for r in records}|{m['sha256'] for m in members}
    protected=[]
    for area in ('dagv2_analysis','output'):
        for p in walk(BASE/area):
            if p.stat().st_size not in candidate_sizes:continue
            h=sha(p)
            if h in wanted_hashes:protected.append({'path':str(p),'bytes':p.stat().st_size,'sha256':h})
        print('PROTECTED_MATCH_DONE',area,len(protected),flush=True)
    locations=collections.defaultdict(list)
    for r in records:locations[r['sha256']].append({'kind':'file','path':r['path'],'root':r['root']})
    for m in members:locations[m['sha256']].append({'kind':'archive_member','archive':m['archive'],'member':m['member']})
    for r in protected:locations[r['sha256']].append({'kind':'protected_file','path':r['path']})
    groups=[{'sha256':h,'locations':locs} for h,locs in locations.items() if len(locs)>1]
    for r in records:
        locs=locations[r['sha256']]
        r['protected_exact_copies']=[x['path'] for x in locs if x['kind']=='protected_file']
        r['kept_root_exact_copies']=[x['path'] for x in locs if x['kind']=='file' and x['root'] in KEEP and x['path']!=r['path']]
        r['other_exact_copy_count']=len(locs)-1
    for a in archive_reports:
        am=[m for m in members if m['archive']==a['path']]
        a['result_members_not_outside_archive']=sum(not any(x['kind'] in ('file','protected_file') for x in locations[m['sha256']]) for m in am)
        a['result_members_not_in_protected_or_kept_root']=sum(not any(x['kind']=='protected_file' or x['kind']=='file' and x['root'] in KEEP for x in locations[m['sha256']]) for m in am)
    manifest={'created_local_date':'2026-10-27','scope':'read-only dagv2* result/diagnostic inventory; dagv2_analysis and output are immutable protected references',
        'kept_code_roots':sorted(KEEP),'excluded_runtime_dirs':sorted(SKIP),'roots':rootstats,'files':records,'archives':archive_reports,
        'archive_result_members':members,'protected_exact_matches':protected,'exact_duplicate_groups':groups,
        'limitations':['No semantic/JSON-normalized deduplication; equality is SHA256 of exact bytes.',
            'Compressed archive file hash and uncompressed member hash are separate identities.',
            'Library/config/data/test paths are excluded from scattered result detection except nested outputs/results.',
            'Root docs and reports retained conservatively; not every preserved artifact is a natural-language model experiment.',
            'All archives kept conservatively if any result member lacks an exact protected/kept-root copy; no files moved or deleted.'],
        'elapsed_seconds':time.time()-start}
    (DEST/'results_inventory.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('COMPLETE',len(records),'files',len(members),'archive result members',len(groups),'duplicate groups','seconds',time.time()-start,flush=True)

if __name__=='__main__':run()
