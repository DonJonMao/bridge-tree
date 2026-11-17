import json,pathlib
from lxml import etree,html
src=pathlib.Path('tmp/research/sources')
acl={}
for f in src.glob('*.xml'):
 try:r=etree.parse(str(f))
 except:continue
 for v in r.findall('volume'):
  for p in v.findall('paper'):
   if p.find('title')is None:continue
   conf=f.stem[:-4];yy=f.stem[-4:];ident=f'{yy}.{conf}-{v.get("id")}.{p.get("id")}'
   title=''.join(p.find('title').itertext())
   a=[' '.join(''.join(x.itertext()) for x in au if x.tag in ['first','last']) for au in p.findall('author')]
   ab=''.join(p.find('abstract').itertext())if p.find('abstract')is not None else ''
   acl[ident]={'title':title,'authors':a,'abstract':ab,'year':int(yy),'venue':conf.upper()+' '+yy+' ('+v.get('id')+')','url':f'https://aclanthology.org/{ident}/'}
notes={}
for f in src.glob('openreview_*.json'):
 try:d=json.load(open(f))
 except:continue
 for n in d.get('notes',[]):notes[n['id']]=n

def ov(i):
 c=notes[i]['content'];g=lambda k:c.get(k,{}).get('value')
 return {'title':g('title'),'authors':g('authors'),'abstract':g('abstract'),'year':2024,'venue':g('venue'),'url':f'https://openreview.net/forum?id={i}','venueid':g('venueid')}
def page(nm,year,venue,url):
 d=html.fromstring((src/(nm+'.html')).read_text());meta={}
 for m in d.xpath('//meta[@name]'):meta.setdefault(m.get('name'),[]).append(m.get('content'))
 abstract=' '.join(x.text_content().strip() for x in d.xpath('//*[contains(@class,"abstract")]'))
 return {'title':meta['citation_title'][0],'authors':meta['citation_author'],'abstract':abstract,'year':year,'venue':venue,'url':url}
# 编号供报告正文稳定引用。中文method是对官方摘要/方法的概括。
items=[
('hSyW5go0v8',ov('hSyW5go0v8'),'反思token联合控制检索必要性、证据相关性、支持性和答案质量；需训练。'),
('GN921JHCRw',ov('GN921JHCRw'),'递归聚类并摘要，建立多层树，在不同抽象粒度检索；摘要节点不能替代原文证据。'),
('mlJLVigNHp',ov('mlJLVigNHp'),'训练抽取/生成式上下文压缩器；证据无益时返回空摘要进行选择性增补。'),
('2024.naacl-long.389',acl['2024.naacl-long.389'],'小分类器按问题复杂度在无检索、一次检索、迭代检索之间路由。'),
('2024.acl-long.67',acl['2024.acl-long.67'],'问题树自底向上求解，原子问题保留候选答案，复合问题beam组合并概率聚合。'),
('2024.emnlp-main.199',acl['2024.emnlp-main.199'],'训练轻量labeler/filter迭代产生查询并过滤噪声，降低逐轮LLM调用。'),
('hipporag',page('hipporag',2024,'NeurIPS 2024 (main conference)','https://proceedings.neurips.cc/paper_files/paper/2024/hash/6ddc001d07ca4f319af96a3024f6dbd1-Abstract-Conference.html'),'开放知识图谱、稠密实体关联与Personalized PageRank联合检索，支持关联多跳记忆。'),
('hippo2',page('hippo2',2025,'ICML 2025 (PMLR 267)','https://proceedings.mlr.press/v267/gutierrez25a.html'),'HippoRAG 2增强段落与图的整合以及在线LLM使用，改善事实、关联和sense-making记忆。'),
('ragged',page('ragged',2025,'ICML 2025 (PMLR 267)','https://proceedings.mlr.press/v267/hsia25a.html'),'系统测量检索深度与reader噪声鲁棒性，说明更多证据不总带来更好答案。'),
('2025.acl-long.1175',acl['2025.acl-long.1175'],'证据句集合用树路径表示；训练阶段MCTS按reader正确答案似然评价，推理阶段早停beam。'),
('2025.acl-long.1352',acl['2025.acl-long.1352'],'过程奖励MCTS多路径检索推理及自训练，支持逐步评估和纠错。'),
('2025.emnlp-main.317',acl['2025.emnlp-main.317'],'保留上下文的proposition图，在线无需LLM的beam搜索命题路径。'),
('2025.emnlp-main.202',acl['2025.emnlp-main.202'],'多agent局部/全局rollback，在矛盾出现时回退有效状态后重新推理。'),
('2026.eacl-long.322',acl['2026.eacl-long.322'],'把子查询作为bandit臂，按文档相关性反馈分配检索预算并研究层次分解。'),
('2026.eacl-long.147',acl['2026.eacl-long.147'],'系统区分RAG错误类别并定位组件问题，为定向修正和诊断提供框架。'),
('2026.acl-long.216',acl['2026.acl-long.216'],'Reasoner维护顺序全局计划，Purifier筛选检索信息；检索失败后修订剩余计划；SFT+RL。'),
('2026.acl-long.1203',acl['2026.acl-long.1203'],'CIRAG历史条件整合候选三元组以保留多证据链，按拒答指示从三元组级联到句子/文档。'),
('2026.acl-long.1662',acl['2026.acl-long.1662'],'COSMOS连接与大小约束下优化KG证据边集的语义相关性/冗余，再聚合分离组件。'),
('2026.acl-long.1780',acl['2026.acl-long.1780'],'段落级提取推理事实claim，独立检索外部知识，以最小token修正当前推理单元并接续。'),
('2026.acl-long.1937',acl['2026.acl-long.1937'],'MFAI注意提示及位置因子实验，区分证据识别和综合失败，诊断最弱可见证据制约。')]
out=[]
for k,(sid,meta,method)in enumerate(items,1):
 meta.update({'id':f'L{k:02}','source_id':sid,'first_author':meta['authors'][0], 'one_line_method':method,'verified_status':'正式主会/长文；依据官方论文页或OpenReview venueid','verified_on':'2026-10-01'})
 out.append(meta)
p=pathlib.Path('tmp/research/literature_core.json');p.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(p,len(out))
for r in out:print(r['id'],r['title'],r['year'],r['venue'],r['first_author'])
