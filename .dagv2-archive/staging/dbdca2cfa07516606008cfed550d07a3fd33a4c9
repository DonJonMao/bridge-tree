import collections,gzip,hashlib,json,os,struct,tarfile,time
from pathlib import Path
from inventory_results import BASE,DEST,KEEP,archive_category,sha,walk

p=DEST/'results_inventory.json';d=json.loads(p.read_text());members=d['archive_result_members']
keys={(m['archive'],m['member']) for m in members}
for a in d['archives']:
    if not any(top=='dagv2' for top in a['top_level']):continue
    with tarfile.open(a['path'],'r|*') as t:
        for info in t:
            if not info.isfile() or (a['path'],info.name) in keys:continue
            parts=Path(info.name).parts
            if parts and parts[0]=='dagv2':parts=parts[1:]
            category=archive_category(parts)
            if category:
                h=hashlib.sha256();f=t.extractfile(info)
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
                members.append({'archive':a['path'],'member':info.name,'bytes':info.size,'sha256':h.hexdigest(),'category':category})
    print('REVISED_ARCHIVE',a['path'],sum(m['archive']==a['path'] for m in members),flush=True)

wanted_sizes={m['bytes'] for m in members};wanted_hashes={m['sha256'] for m in members}
gzip_matches=[];gzip_scanned=0
for root in (BASE/'dagv2_analysis',BASE/'output'):
    for f in walk(root):
        if not f.name.endswith('.json.gz'):continue
        with f.open('rb') as stream:
            stream.seek(-4,2);size=struct.unpack('<I',stream.read(4))[0]
        if size not in wanted_sizes:continue
        h=hashlib.sha256();actual=0
        with gzip.open(f,'rb') as stream:
            for b in iter(lambda:stream.read(8*1024*1024),b''):h.update(b);actual+=len(b)
        gzip_scanned+=1
        if h.hexdigest() in wanted_hashes:
            gzip_matches.append({'path':str(f),'bytes':f.stat().st_size,'uncompressed_bytes':actual,
                'sha256':sha(f),'payload_sha256':h.hexdigest()})
    print('GZIP_PAYLOADS',root.name,gzip_scanned,len(gzip_matches),flush=True)

locations=collections.defaultdict(list)
for r in d['files']:locations[r['sha256']].append({'kind':'file','path':r['path'],'root':r['root']})
for m in members:locations[m['sha256']].append({'kind':'archive_member','archive':m['archive'],'member':m['member']})
for r in d['protected_exact_matches']:locations[r['sha256']].append({'kind':'protected_file','path':r['path']})
for r in gzip_matches:locations[r['payload_sha256']].append({'kind':'protected_gzip_payload','path':r['path']})

for r in d['files']:
    locs=locations[r['sha256']]
    r['protected_exact_copies']=[x['path'] for x in locs if x['kind']=='protected_file']
    r['kept_root_exact_copies']=[x['path'] for x in locs if x['kind']=='file' and x['root'] in KEEP and x['path']!=r['path']]
    r['other_exact_copy_count']=sum(x['kind']!='protected_gzip_payload' for x in locs)-1

for a in d['archives']:
    am=[m for m in members if m['archive']==a['path']]
    a['result_members']=len(am);a['result_uncompressed_bytes']=sum(m['bytes'] for m in am)
    a['result_members_not_outside_archive']=sum(not any(x['kind'] in ('file','protected_file') for x in locations[m['sha256']]) for m in am)
    a['result_members_not_in_protected_or_kept_root']=sum(not any(x['kind']=='protected_file' or x['kind']=='file' and x['root'] in KEEP for x in locations[m['sha256']]) for m in am)
    a['result_members_not_in_protected_or_kept_content']=sum(not any(x['kind'] in ('protected_file','protected_gzip_payload') or x['kind']=='file' and x['root'] in KEEP for x in locations[m['sha256']]) for m in am)
    a['compressed_payload_match_members']=sum(any(x['kind']=='protected_gzip_payload' for x in locations[m['sha256']]) for m in am)
d['archive_result_members']=members;d['protected_gzip_payload_matches']=gzip_matches
d['exact_duplicate_groups']=[{'sha256':h,'locations':[x for x in ls if x['kind']!='protected_gzip_payload']} for h,ls in locations.items() if sum(x['kind']!='protected_gzip_payload' for x in ls)>1]
d['payload_equivalence_groups']=[{'payload_sha256':h,'locations':ls} for h,ls in locations.items() if any(x['kind']=='protected_gzip_payload' for x in ls)]
d['limitations'].append('Gzip payload equality additionally checked for .json.gz in protected areas; this is lossless content equivalence, not identical archive bytes.')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('REFINED',len(members),len(gzip_matches),flush=True)
