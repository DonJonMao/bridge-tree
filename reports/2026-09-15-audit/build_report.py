"""Build the Chinese audit report as offline, print-ready HTML.

Only creates report artifacts; never alters experiment inputs or calls models.
"""
import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
E = json.loads((BASE / 'experiment_evidence.json').read_text())
C = json.loads((BASE / 'case_evidence.json').read_text())
X = json.loads((BASE / 'context_evidence.json').read_text())
P = E['provenance']
METHODS = ['dense', 'dense_rerank', 'activation', 'context_marginal', 'activation_fixed_pool']
LABEL = dict(zip(METHODS, ['dense', 'dense_rerank', 'activation', 'context_marginal', 'fixed_pool']))

def esc(x):
    return html.escape(str(x))

def pct(x):
    return f'{100*x:.2f}%'

def table(headers, rows, widths=None, cls=''):
    cols = '' if widths is None else '<colgroup>' + ''.join(f'<col style="width:{w}%">' for w in widths) + '</colgroup>'
    return '<table class="'+cls+'">'+cols+'<thead><tr>'+''.join('<th>'+str(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'

def note(text, label='证据边界'):
    return f'<aside><strong>{label}</strong><p>{text}</p></aside>'

def link(url, label):
    return f'<a href="{esc(url)}">{esc(label)}</a>'

pages = []
def page(title, content, kicker='研究与工程审计'):
    pages.append((title, content, kicker))

overall = E['snapshot']['overall']
expected = P['dataset']['questions'] * len(METHODS)

page('BridgeTree：当前问题与下一步方案', f'''
<p class="subtitle">PersonaMem-v1 32k · 版本与实验复核 · 2025–2026 顶会研究</p>
<p class="meta">报告版本：2026-09-15 / R1　｜　代码包版本：0.1.0<br>
结果截止：2026-09-15 17:30:19（北京时间，下载归档）<br>
审计性质：只读诊断与方案建议；不是新版本实现或新一轮实测</p>
<div class="lead">当前最需要解决的不是“搜索量不够”，而是三个独立问题：<br>
评分目标与历史证据充分性不一致；有限预算下跨目标搜索覆盖不足；reranker 服务失败及评测归因不清。</div>
<h2>实验现状</h2>
{table(['已处理任务', '成功执行', '执行失败', '成功输出答对'], [[493,377,116,232]], [25,25,25,25], 'numbers')}
<p>总计划为 589 题 × 5 方法＝2,945 个任务，目前处理 {pct(493/2945)}。任务执行成功不等于答对；当前仍有 2,452 个任务未进入最新 outcomes 快照。报告不声称这是服务器此刻的实时进度。</p>
<h2>核心结论</h2>
<ul>
<li><strong>质量：</strong>activation 与 dense 共同成功的 61 题中，分别答对 36 / 41 题；纠正 5 题、损害 10 题。点估计不利，但样本小且存在非随机失败，不能宣称总体显著劣于 dense。</li>
<li><strong>机制：</strong>三个详细反例中，关键历史都已进入候选库，却被负集合边际拒绝。602 条交互、311 次选择比较的算术复算正确。</li>
<li><strong>可靠性：</strong>三个搜索方法的 295 个已处理任务中，116 个最终失败，均未调用生成器；所有任务级重试均未恢复。</li>
</ul>
<h2>建议决策</h2>
<p>保留当前运行作基线。先补齐模型身份与失败请求日志；先做冻结候选库的选择器消融，再做同预算跨目标调度消融。外部对照首选 <strong>RF-Mem（ICLR 2026）启发式版本</strong>，其公开 32k 数据与本实验逐字节一致。</p>
<p class="small">阅读导航：版本 p.2；结果 p.3；失败成本 p.4；代码机制 p.5–8；论文 p.9；修改方案 p.10–12；日志与复现依据 p.13–15。</p>
''', '技术审计报告 / 2026-09-15')

page('01　当前版本与实验协议', f'''
<p>软件版本、Git 提交和运行内容身份需要分开记录。<code>pyproject.toml</code> 的发布版本是 <strong>0.1.0</strong>；本地 HEAD 为 <code>39efab3dd547</code>，工作树有既有未提交改动。重新计算的<strong>本地源码聚合哈希与归档运行完全相同</strong>，因此本报告所引用实现可对应这次运行。</p>
{table(['项目','归档／当前核验值'], [
['运行目录','outputs/chain-skip-failed/<br>dependency_20260914_124930_2365962'],
['代码身份','source hash：<code>3a55adcae46c…</code><br>包含 src/bridgetree、reference、configs、scripts、pyproject.toml；不是单一 Git commit'],
['数据','PersonaMem-v1 · 32k · 589 题<br>revision：<code>fd7c30f071d5…</code>'],
['可见历史','每题 messages[:end_index]；user_assistant_pair；include_system_persona=true'],
['方法','dense / dense_rerank / activation / context_marginal / activation_fixed_pool'],
['预算','初始 dense 12；初始扩展宽度 4；proposal 4；ANN 总上限 36；搜索与选择各 512 个唯一集合配额'],
['生成','deepseek-v4-flash；temperature=0；输出上限 512；完整输入估算上限 8192 tokens'],
['评分与编码','qwen3-embedding-8b；reranker 为 pointwise / unit_interval；batch_size=32，输入估算上限 8192'],
['训练与协议','optimizer_steps=0；weights_updated=false；protocol_role=all_data；protocol_hash=not_defined'],
], [22,78])}
{note('归档只证实生成器 API 配置名。用户所述 284B / INT8 及实际 checkpoint、服务版本、thinking 模式没有被归档字段证实；reranker 的 model 字段为空。下一版必须固定实际部署身份，不能从 API 别名推断模型能力。','优先补齐的复现信息')}
<p class="small">本报告不改动版本号或实验配置。完整 source/config/data hash、原始文件 SHA 与归档校验和见 p.14。文中的 fixed_pool 是 activation_fixed_pool 的表格简称。</p>
''')

method_rows = []
for method in METHODS:
    r = E['counts_by_method'][method]
    method_rows.append([LABEL[method],r['completed'],r['successful'],r['correct'],r['failed'],pct(r['successful_accuracy']),pct(r['correct_per_completed_including_failures'])])
pair_rows = []
for pair in E['paired_common_success']:
    if pair['left'] == 'dense':
        pair_rows.append([LABEL[pair['right']], pair['common_success_tasks'], f"{pair['left_correct']} / {pair['right_correct']}", f"{pair['right_rescues']} / {pair['right_harms']}", f"{100*pair['right_minus_left_accuracy']:+.2f}"])
page('02　实验结果：先看分母，再谈优劣', f'''
<p>优先采用 493 份逐任务 outcomes。归档中的 summary/current 都是 490 条，少了三条成功但答错的最新结果，属于非原子快照刷新差异；不是本次将重试重复计入成绩。</p>
{table(['方法','处理','成功','正确','失败','成功样本<br>正确率','已处理任务<br>正确率¹'],method_rows,[25,8,8,8,8,21,22], 'numbers')}
<p class="caption">¹ 正确数 / 已处理任务数，执行失败计入分母但不是“模型回答错误”。成功样本正确率＝正确数 / 成功执行数。未处理任务不在这两个分母中。</p>
<h2>与 dense 的同题共同成功配对</h2>
{table(['对比方法','共同题数','dense / 方法<br>答对数','纠正 / 损害','净差<br>百分点'],pair_rows,[27,13,23,21,16], 'numbers')}
<p class="caption">“纠正”＝dense 错而该方法对；“损害”反之。每行使用各自共同成功题，不可将不同行分母混在一起。</p>
<p>五种方法全都成功的共同集合仅 <strong>44 题</strong>：dense、dense_rerank 各对 30；activation 对 24；context_marginal 对 25；fixed_pool 对 24。说明当前差距不完全由 HTTP 失败造成，但不能排除共同成功筛选产生的偏差。</p>
{note('样本覆盖 99 个问题、4 个 persona（0、1、3、6），不是全体 589 题的随机样本。三个搜索方法相对 dense 的探索性精确 McNemar p 值约 0.302 / 0.344 / 0.263，未做多重校正及 persona 聚类处理；没有统计证据宣称稳定优劣。','统计解释')}
<p class="small">整体 successful_accuracy=232/377=61.54% 只是五方法执行汇总，不代表一个模型的独立测试分数。232/2945=7.88% 是未完成实验的固定分母准确率下界；不能拿它当最终 accuracy。</p>
''')

page('03　可靠性与成本：先定位 reranker', f'''
<div class="lead">116 / 295＝39.32% 的搜索方法任务最终失败。全部失败发生在生成之前，因此这些失败不能归因于 DeepSeek 答题能力或生成端 INT8 量化。</div>
{table(['失败类型／阶段','已核实数量'],[
['最终 HTTP 500 / TimeoutError','112 / 4'],
['dependency_search / selection','83 / 33'],
['任务级失败尝试','116 个任务 × 3 次＝348 条'],
['任务级重试恢复','0 个；232 次追加尝试均未恢复'],
['尚有 ANN 预算的最终失败','77 个；所有失败仍有集合评分预算'],
],[65,35])}
<p>116 个任务的三次尝试都停在相同 ANN / scored_sets 计数。后两次依赖缓存快速重走前缀，只剩一次 reranker 逻辑调用。这与“某个剩余请求稳定触发失败”相容，<strong>但未证明是同一个请求体、超长输入或 OOM</strong>。</p>
<p>HTTP500 已经拆分到单个 <em>集合文档</em> 仍失败；一个集合文档可能包含多条记忆。日志缺少失败集合 ID、真实 token 数、响应关联 ID 和服务端异常栈，不能把“单文档”误读成“单条短记忆”。</p>
<h2>成本必须累计所有尝试</h2>
{table(['方法','全部尝试小时','成功任务中位秒'],[
['dense','0.694','25.11'],['dense_rerank','0.257','9.61'],
['activation','9.765','369.40'],['context_marginal','4.531','140.52'],['fixed_pool','2.960','73.32'],
],[42,29,29], 'numbers')}
<p>去重后的 725 次 executor 调用合计 <strong>18.207 小时</strong>，其中失败消耗 7.608 小时（41.79%）。只加 outcomes 的最近一次成本，会漏掉约 6.66 小时。额外任务退避约 2.417 小时是按配置推算，不是等待事件实测。</p>
{note('dense 承担共享 memory embedding；后执行方法复用大量 persistent score cache。表中时延不是算法固有速度排名，也不是运行墙钟时间；不包含全部外层等待。逻辑 token 估算不是账单 token，也不是单请求长度。','成本口径')}
''')

page('04　代码问题一：代理目标与证据效用错位', '''
<div class="pipeline"><span>原始 query</span><b>→</b><span>记忆集合串联</span><b>→</b><span>相关性 R(q,S)</span><b>→</b><span>正边际添加</span></div>
<p>实现将完整记忆集合序列化成一个文档，与原始 query 一起送入 pointwise reranker。元信息与 user/assistant 原文保留，没有独立检查“这些历史是否足以完成个性化回答”。选项只在最终生成阶段出现。</p>
<div class="formula">Δ(B | S) = R(q, S ∪ B) − R(q, S)<br>只接受最大且严格为正的 Δ；否则 no_positive_marginal 停止。</div>
<h2>已证实的行为</h2>
<ul>
<li>三个案例的关键历史都已召回、归档且可放入预算；选择器仍因负边际拒绝它们。</li>
<li>末轮所有边际严格小于零，既不是阈值太高，也不是小数显示舍入成零。</li>
<li>0.999 只是服务返回的相关性值，不是 99.9% 答对概率。unit_interval 只校验取值范围，没有证据充分性校准。</li>
</ul>
<h2>机制缺口，不是已发现的减法 bug</h2>
<p>当前 query 的近似复述可能取得极高分，却没有提供 query 之外的历史事实。另一方面，过去的退出原因或使用习惯可能决定正确回答，却拉低集合分。将“更相关”直接用作“更有用”的唯一准则，存在清楚的失败反例。</p>
<p>此外，选择器只有添加，没有移除、替换或重新选择先前项。早期高分选择可能锁定后续轨迹；但在同一失配目标上增加搜索复杂度，也不保证找回有用证据。</p>
<h2>搜索同样受这一代理分数影响</h2>
<div class="formula">A(e,G | P) = R(P∪G∪&#123;e&#125;) − R(P∪G) − R(P∪&#123;e&#125;) + R(P)</div>
<p>正 activation 只说明评分上的条件交互；不保证集合边际为正，更不等于真实依赖或因果关系。读书会例中 38 个正 activation 有 2 个对应负 context_marginal。</p>
<p class="small">源码：dependency_scoring.py:576、799；dependency_experiment.py:1743；dependency_search.py:635、1244、1282。对固定候选库作严格单调 logit 变换，不改变选择边际的正负及本轮 argmax，不能单独修复此选择机制。[R1]</p>
''')

page('05　三个反例：事实已到达，最后被排除', '''
<p>这三个案例用于定位失败链路，不用于估计全数据发生率。记忆编号是各自 question_id 内的局部编号。完整 task / question 标识见 p.14；原文事实已按固定数据前缀重新构建核验。</p>
<h2>绘画：保留“想重新上课”，遗漏“过去为什么离开”</h2>
<p>m39 描述画室课程的僵化限制了自由实验；位于初始 dense 第 4 名。最终却保留 m11（曾报名）与 m81（当前重返课程的想法）。最终集合分 0.9997326174，补入 m39 后为 0.9988752425，Δ＝−0.0008573748。dense 答对，activation 答错。</p>
<h2>音乐：保留观看演出，遗漏“自己用软件制作音乐”</h2>
<p>m05 是家庭录音室制作习惯，m27 明确提到新软件与数字音频工作站，初始 dense 排名分别为 1、9。最终只选 m06+m08；加入两条事实中的任意一条都会降分。</p>
''' + table(['候选操作','原分','加入后','边际'],[
['音乐：补 m05','0.99287857','0.94580127','−0.04707730'],
['音乐：补 m27','0.99287857','0.97404264','−0.01883593'],
['读书会：补 m37','0.99924459','0.99629275','−0.00295185'],
],[31,23,23,23], 'numbers') + '''
<h2>读书会：当前重返想法压过过去退出原因</h2>
<p>m37 解释退出是因为讨论过于学术化、正式，削弱情感交流；初始 dense 排名第 3，进入过多个 bundle。最终只选 m73（当前想重新加入）。dense 答对，activation 答错；context_marginal 也只选 m73、哈希相同，却答对。</p>
''' + table(['核验项','绘画','音乐','读书会'],[
['交互记录 / 选择比较','192 / 117','250 / 83','160 / 111'],
['末轮负边际 / 比较总数','38 / 38','40 / 40','55 / 55'],
['最终估算输入 tokens','1100','971','716'],
['不可行比较 / 不完整轮','0 / 0','0 / 0','0 / 0'],
],[37,21,21,21], 'numbers') + '''
<p class="caption">所有比较都在容量内，生成输入上限均为 8192。少选不自动等于错误；这里的关键是有用历史被明确拒绝，且补回能否改善答案仍需控制生成波动的实验。</p>
''')

page('06　代码问题二：跨目标调度缺少保障', '''
<p>状态是 <strong>(固定 target，premise 集合)</strong>。扩展增加前提，不切换目标。所有初始根以 priority=0 入堆，平局按 memory_id 排序；任何正信号后继都优先于未访问根。有限预算下，其他目标可能长期没有机会。</p>
''' + table(['案例','初始根','已访问目标','24 条状态中的前提深度分布'],[
['绘画','15','1（m2）','0 层 1；1 层 10；2 层 13'],
['音乐','16','4','0 层 4；1 层 20'],
['读书会','19','1（m3）','0 层 1；1 层 16；2 层 6；3 层 1'],
],[17,13,23,47]) + '''
<p>三个案例均为初始阶段消耗 13 次 ANN，剩余 23 次条件 ANN；日志包含 23 个发生测量的状态与最后一次预算拒绝状态。<strong>24 条状态不是 24 次完整有效展开，更不是一条 24 层长链。</strong></p>
<h2>准确描述：局部有分叉，跨目标扩散不足</h2>
<div class="branch"><div>目标 e → 前提 {a} → 前提 {a,c} 或 {a,d}</div><div>目标 e → 前提 {b} → 其他组合</div><div class="muted">目标 f、g、h 仍在零优先级队列中等待</div></div>
<p>绘画根 m2 一次产生 10 个正后继；读书会根 m3 一次产生 17 个。音乐主要是几个根的一层星状分支，而不是深链。尚未作为 target 展开的记忆仍可作为 premise、初始 singleton 或最终候选出现，不能说它们完全没被看到。</p>
<h2>额外限制</h2>
<p>池外新候选只会归档为单例、参与已有目标的前提组合，不会自动成为新的独立根。新候选数、bundle 数或 visited_state_count 均不能替代“不同目标获得多少预算”的覆盖统计。</p>
<h2>待测修改</h2>
<p>在相同 ANN 与评分总配额下，测试跨目标轮询或根覆盖预留配额，目标内部仍按 signal 排序。首轮根可能测量整个初始池，因此不能只约束 ANN 而忽略评分预算。池外候选晋升为根是另一项改动，应单独消融。</p>
<p class="small">源码：dependency_search.py:271、302、710、786；tests/test_dependency_search.py:235 明确测试正后继优先。现象对应设计取舍，不是代码意外违背既定规则；广覆盖会牺牲局部深入，准确率收益尚未验证。</p>
''')

page('07　其他代码与实验控制问题', '''
<h2>dense_rerank 对照没有改变最终记忆集合</h2>
<p>99 / 99 共同题中，两者都保留相同的 12 条记忆。生成器构造输入前又统一按时间排序，因此当前设置下 rerank 的顺序改变不会保留到 reader。65 对与 66 对的差别不能直接解释成重排收益；7 个标签变化中只有 2 次纠正、1 次损害。</p>
<p>下一版应先记录真实请求哈希。如果需要有效的筛选型 rerank 基线，可预先定义更大的初始候选集，再选相同 k 条；这是一项新的基线配置，不应悄悄改写当前结果。</p>
<h2>context_hash 不等同于线上请求身份</h2>
<p>哈希包含 selected_ids 的原始顺序，而请求使用规范化时间顺序。不同 hash 不证明发给模型的 messages 不同；反之，搜索方法已有相同 hash 却一对一错的例子。temperature=0 不能保证远端部署完全确定。</p>
<h2>扩展后的有效差异很小，不能用过程计数代替收益</h2>
''' + table(['共同成功对比','共同题数','最终集合相同'],[
['activation / fixed_pool','55','49（89.1%）'],
['activation / context_marginal','46','36（78.3%）'],
],[54,18,28]) + '''
<p>activation 的 61 个成功任务中，42 个最终只保留 0–2 条记忆，完整输入中位数 1147 tokens；dense 为 4722。压缩可能有价值，也可能丢证据，需要按“证据是否被保留”与正确率共同评估，不能把 token 少本身视为失败。</p>
<h2>失败批次的可观测性与部分缓存</h2>
<p>reranker 拆分后的成功子批结果，若另一个子批失败，可能尚未返回 scorer 并写入持久缓存；完整评分事件也只在调用成功后追加。下一版可独立持久化已验证的 pointwise 单文档结果，并写 pre-call 事件，但不得提交不完整选择轮次或给失败伪造分数。</p>
''' + note('当前本地离线测试：search/scoring 42 passed，clients 21 passed。证明的是公式、缓存与控制流等被测行为；未运行新的模型调用，不证明服务稳定或代理目标正确。','验证范围') + '''
<p class="small">源码：clients.py:185、252、738；dependency_scoring.py:833、855。reranker 模型身份缺失与失败请求追踪缺失应列为工程 P0；目标错位与调度不足是独立的机制问题。</p>
''')

page('08　近两年顶会：严格区分可比性', '''
<p>检索截止 2026-09-15；“近两年”采用正式会议年份 <strong>2025–2026</strong>，以会议官网、PMLR、ACL Anthology 核实身份，并阅读论文和作者代码。以下是与当前问题最相关的候选集，不声称穷尽全部工作。</p>
''' + table(['论文／方法','正式会议','可借鉴内容','当前数据可比性'],[
['Sufficient Context [R1]','ICLR 2025','相关性、充分性、答对三者分开','不是 PersonaMem'],
['HippoRAG 2 [R2]','ICML 2025','原文 passage 与结构检索融合','不是 PersonaMem'],
['A-Mem [R3]','NeurIPS 2025','原文、事实描述、动态链接','原论文 LoCoMo / DialSim'],
['MemoryOS [R4]','EMNLP 2025 主会','近期交互、主题记忆、用户画像分层','原论文 GVD / LoCoMo'],
['RF-Mem [R5]','ICLR 2026','熟悉性与回忆路径自适应路由','32k 两文件 SHA 完全匹配'],
],[28,19,27,26]) + '''
<h2>最直接的机制依据：Sufficient Context</h2>
<p>论文将“上下文包含足够回答信息”与生成器是否答对分离。提示式 autorater 可不更新权重，但需要人工核验后才能迁移；其 selective generation 还包含 logistic regression，另有 LoRA 实验，<strong>不能把整篇论文都标成免训练</strong>。</p>
<h2>结构不是目的：HippoRAG 2</h2>
<p>正式题名为 <em>From RAG to Memory: Non-Parametric Continual Learning for Large Language Models</em>。它保留 passage 节点，将 dense 信息通路与图关联结合，并在过滤不到 triples 时回退 passage retrieval。这支持检验“基础事实通路是否被结构选择牺牲”，不直接证明根轮询适合 PersonaMem。</p>
<h2>记忆表示与时序管理：A-Mem / MemoryOS</h2>
<p>两者核心记忆写入、关联、总结可通过既有模型推理实现，无须针对本数据训练权重，但需要计入建库成本。A-Mem 链接不是因果证明；MemoryOS 的访问热度也不等于偏好生效时间。</p>
''' + note('除 RF-Mem 外，本次没有核实这些论文原实验使用与我们相同的 PersonaMem-v1 32k 文件。后续论文中的 PersonaMem 128k 重测不能冒充当前 32k 排行榜；LoCoMo F1 也不能与多选 accuracy 直接比较。') + '''
<p class="small">完整官方出处、论文和代码链接见 p.15。下文工程方案是受这些研究启发的待测假设，不是论文已在本项目验证的结论。</p>
''')

page('09　下一步机制修改：先隔离，再组合', '''
<h2>方向 A：增加独立的历史证据审计 [R1]</h2>
<p>对固定候选池和最终集合分别判断：是否有用户相关事实、是否提供 query 之外的新信息、是否包含过去原因或明确更新、能否回溯到原文。PersonaMem query 常是陈述句，不能照抄开放域 QA 充分性提示。</p>
<p>第一步只作离线人工小样本审计，再验证提示式评审器与人工的一致性。离线可查看答案判断所需事实；<strong>线上 query-only 检索与选择不得读取金标准</strong>。若要引入答案选项感知，必须另立统一协议，不能仅给新方法额外信息。</p>
<h2>方向 B：替换“唯一正边际”准入与停止机制 [R1, R2]</h2>
<p>冻结候选库，对比原选择器与“预声明 dense 锚点保留＋互补证据补充”。锚点数在独立开发集或预先规定，不按这三个反例逐题指定。另一条后续路线是覆盖约束：优先覆盖互补历史事实、避免把 query 复述当唯一证据；评分器仍可用于相关性排序，但不独自决定证据已足够。</p>
<p>先不加更复杂的大图、beam 或无限补文档。严格单调 logit 变换不会修复固定 archive 下的当前选择轨迹；放宽到负边际也不能在未验证的尺度上保证有意义。</p>
<h2>方向 C：同预算多目标调度</h2>
<p>保留部分预算访问不同根，或目标间轮询、目标内按 signal 排序。报告每个目标的 ANN、唯一评分集合和状态数。新候选晋升为根、改变 pair rescue 或替换 signal，各自单独开消融，避免无法归因。</p>
<h2>方向 D：在确认选择损失后，再改表示 [R3, R4]</h2>
<p>引入可追溯的个人事实字段、来源、观察时间、明确的更正／否定关系，同时保留原文。区分稳定画像与近期事件；不能把访问频率当有效性，也不能把消息索引当日历时间。任何 LLM 抽取字段都需要原文支持和错误监测。</p>
''' + note('人工补回 m39/m27/m37 只能作为诊断实验，不是可部署算法成绩。报告中所有方案均未实现、未调用模型验证，也未承诺提高准确率。','防止事后调参') + '''
<p class="small">优先顺序：工程可观测性 → 冻结候选的选择器 → 同预算调度 → 两者组合 → 表示层／完整记忆系统。三个已定位案例关键事实已召回，因此单纯增加检索量不是最直接修复。</p>
''')

page('10　首选复现：RF-Mem 的同数据对照', '''
<p><strong>Evoking User Memory: Personalizing LLM via Recollection-Familiarity Adaptive Retrieval</strong>，ICLR 2026。[R5] 官方仓库固定 commit <code>d6a2cb3416e8…</code> 下的两份 32k 文件，与本实验 question / context SHA 完全一致，共 589 题。</p>
''' + table(['论文 Table 1 · 32k','准确率','论文平均输入 tokens'],[
['Dense Retrieval','59.08%','3515.9'],
['Recollection','62.14%','3711.1'],
['RF-Mem','63.50%','3566.6'],
['Full Context','61.29%','24657.8'],
],[49,21,30], 'numbers') + '''
<p class="caption">这是论文内对照，不是我们的 DeepSeek 成绩。论文实现说明只称生成器为“advanced LLM”；代码默认 gpt-4.1-mini 不能反推发表表格的服务身份。论文毫秒级 retrieval time 也不是我们的端到端 HTTP 时延。</p>
<h2>为什么适合先复现</h2>
<p>主版本使用相似度统计／熵进行熟悉性与回忆策略路由，结合聚类与检索扩展，不需要额外训练权重，也没有 A-Mem 式 LLM 记忆重写成本。应排除附录的 learned gate，先移植主启发式及两个分支作为对照。</p>
<h2>不能直接运行当前公开 driver</h2>
<ul>
<li>读取了每题 end_index，但主入口未据此截断共享 history；公开数据 README 明确要求截断。复现必须修正此协议缺口，不能据此反推论文表格一定泄漏。</li>
<li>代码使用 cmd_args.rag，但 argparse 没有对应参数；run.sh 是 60 组参数扫描，不是冻结配置的单次运行。</li>
<li>上游预处理会跳过 system，并丢弃无后续 assistant 的尾部 user；我们的记忆政策不同，需要在统一 harness 中明示对齐。</li>
<li>上游默认 embedding 与 Qwen3 不同，路由阈值可能失配。只允许独立开发集／无标签统计校准，禁止在 589 题答案上扫参取最优。</li>
</ul>
<p><strong>第二批：</strong>A-Mem、MemoryOS 可作模型对齐迁移基线，而不是已验证同 32k 优胜者。MemoryOS 的 get_response 默认把测试问答写回记忆，迁移时须隔离；其错误字符串也必须分类为失败，不能正常入库。</p>
<p class="small">移植属于“同模型、同可见信息协议重测”，不等于精确复现论文数值。不要给本来没有 reranker 的基线额外添加 reranker；不同记忆大小不宜用强制同条数代替同 token 预算。</p>
''')

page('11　下一版实验计划与验收条件', '''
<p>以下是建议的新协议，不覆盖当前运行，也不把看过的错误题重新当未见测试题。先建立独立、最好按 persona 隔离的开发／保留评估划分；现有 99 题和三个深审案例标记为“已观察诊断集”。</p>
<h2>阶段一：冻结候选的选择器实验</h2>
<p>使用同一 query、历史前缀、候选 archive、规范化生成提示及模型服务，比较原选择器与预注册新选择器。人工补事实另作诊断分支，不进入正式成绩。先判断“候选有证据、最终丢证据”的比例是否下降。</p>
<h2>阶段二：同预算 2×2 消融</h2>
''' + table(['实验臂','搜索调度','选择器','回答的问题'],[
['A','原调度','原规则','复核旧行为与服务波动'],
['B','原调度','新规则','选择器单独贡献'],
['C','多目标调度','原规则','覆盖调度单独贡献'],
['D','多目标调度','新规则','二者组合及交互'],
],[12,23,23,42]) + '''
<p>固定 ANN 总上限 36、搜索唯一集合 512、选择追加 512，完整生成输入上限 8192；更换调度可以改变 archive，这是调度实验的真实作用，不能再称候选库完全相同。离线生成记忆与在线充分性评审若新增调用，应独立计费。</p>
<h2>阶段三：加入外部免训练基线</h2>
<p>先移植 RF-Mem familiarity / recollection / routed 三分支；完成源码与有效参数 golden tests 后重跑。再按工程预算考虑 A-Mem、MemoryOS；HippoRAG 2 可作为结构通路的后续对照，而不是先决条件。</p>
<h2>验收不只看一个 accuracy</h2>
<ul>
<li>运行身份可复查：实际 checkpoint、量化、thinking、embedding、reranker、提示与配置均固定。</li>
<li>报告全部预注册题的执行成功率、固定分母正确率、成功样本正确率和共同题配对 win/loss；失败单列，不用成功样本掩盖缺失。</li>
<li>按 persona / question_type 分层；预先约定重复生成与统计方案。同一实际请求可共享一次生成作控制实验，或重复多次估计波动，二者不能混用计费。</li>
<li>并列报告证据召回、最终保留、根覆盖、输入 token 与全部尝试成本；覆盖变广或分数变高本身不是成功标准。</li>
</ul>
''')

page('12　日志与代码修改清单（尚未实施）', '''
<h2>P0：让失败可定位、版本可追溯</h2>
<p>在实际服务调用之前记录 request_id、阶段、任务／尝试、集合 ID、文档哈希、估算及服务实际 token、batch 文档数；失败时保留 HTTP 状态、关联 ID 与脱敏错误类型。服务端记录 traceback / OOM / tokenizer 或 payload 校验结果。原始个人文本与凭据不应进入公开日志。</p>
<p>记录实际模型标识、部署版本、量化、thinking、解码参数和 tokenizer；为最终 HTTP payload 生成规范化 request_hash，排除仅供审计的 selected_ids 顺序与传输地址等元信息。</p>
<h2>P1：增加能判定模块贡献的统计</h2>
<p class="small">证据召回／入选率需要独立标注的诊断集。当前协议没有现成的官方 gold memory IDs，不能直接从现有过程日志计算正式 Recall；请区分人工事实审计指标与自动运行计数。</p>
''' + table(['模块','应新增／汇总的观测','判断目标'],[
['候选检索','证据所在层：可见库 / 初始池 / 扩展池','没召回，还是召回后丢失'],
['依赖搜索','不同根覆盖；每根 ANN / scored_sets；premise 深度；正信号分支','预算是否集中于少数目标'],
['归档选择','证据入选率；拒绝原因；前后集合分；query 重复项；互补事实覆盖','分数变化是否牺牲历史证据'],
['最终生成','真实 request_hash；同请求标签变化；证据充分性 × 正确性','生成波动，还是输入差异'],
['成本可靠性','按 task_id+attempt 去重；离线/在线/重试/等待；冷/热缓存','端到端代价与失败恢复'],
],[18,51,31]) + '''
<h2>建议涉及的实现位置</h2>
<p class="code-list">dependency_scoring.py:576 / 799　集合序列化与 pre-call 事件<br>
dependency_search.py:710 / 786　根与后继队列调度<br>
dependency_search.py:1244 / 1282　边际选择与停止<br>
clients.py:185 / 252　规范化生成请求与 hash<br>
clients.py:738　拆批失败与成功子批结果<br>
dependency_experiment.py:1743　评分器身份及运行记录</p>
''' + note('不得把失败请求的分数置零继续当正常测量；不得把不完整选择轮次提交为有效结果。若提出 dense 回退，应另命名为显式复合方法，记录 fallback，并与不回退的原方法分开汇报。','保持失败语义') + '''
<p class="small">不建议当前直接提高 ANN、score 或重试次数：关键事实已召回的案例不受益于更多召回，稳定失败的请求也未因任务级重试恢复。先取得失败请求与服务端证据，再决定工程修复。</p>
''')

idrows = [
['运行 source hash',P['run_identity']['source_code_hash']],
['运行 config hash',P['run_identity']['config_hash']],
['运行 data hash',P['run_identity']['data_hash']],
['数据 revision',P['dataset']['dataset_revision']],
['questions_32k.csv SHA256',P['dataset']['source_sha256']['questions_32k.csv']],
['shared_contexts_32k.jsonl SHA256',P['dataset']['source_sha256']['shared_contexts_32k.jsonl']],
['chain-audit-full.tgz SHA256',E['inputs']['full_archive']['sha256']],
['chain-audit-detail.tgz SHA256',E['inputs']['detail_archive']['sha256']],
]
caseblocks=''.join('<p class="case-id"><strong>'+esc(c['case'])+'</strong>　question：<code>'+esc(c['question_id'])+'</code><br>task：<code>'+esc(c['task_id'])+'</code></p>' for c in C)
page('附录 A　证据身份与可复算材料', '''
<p>本地原始数据与运行 manifest 的两文件 SHA 一致；本地源码聚合 hash 也与运行一致。以下长哈希为准确身份，不能仅凭文件名、日期或 API 模型名代替。</p>
''' + table(['身份项','完整值'],[[esc(k),'<code>'+esc(v)+'</code>'] for k,v in idrows],[31,69], 'hashes') + '''
<h2>详细案例索引</h2>
''' + caseblocks + '''
<h2>本报告的证据文件</h2>
<p class="small">experiment_evidence.json：逐方法、逐尝试和配对清单；case_evidence.json：三例原文事实与逐轮比较；context_evidence.json：最终集合与生成变化。对应复算脚本为 build_experiment_evidence.py、audit_cases.py、audit_contexts.py。研究核查详见 research_mechanisms.md、research_baselines.md；均保存在报告同目录。</p>
<p class="small">归档不含完整的所有题候选池／失败请求体；深审仅覆盖提供的三个案例。报告不推断其他题均有相同机制，也不证明当前服务器已完成或停止。未进行新的生成／评分服务调用。</p>
''', '审计附录 / 精确身份')

refs = [
('R1','Hailey Joren et al.','Sufficient Context: A New Lens on Retrieval Augmented Generation Systems','ICLR 2025',
 'https://iclr.cc/virtual/2025/poster/30092','https://arxiv.org/html/2411.06037v3','https://github.com/hljoren/sufficientcontext'),
('R2','Bernal Jiménez Gutiérrez et al.','From RAG to Memory: Non-Parametric Continual Learning for Large Language Models (HippoRAG 2)','ICML 2025 · PMLR 267:21497–21515',
 'https://proceedings.mlr.press/v267/gutierrez25a.html','https://arxiv.org/html/2502.14802v2','https://github.com/OSU-NLP-Group/HippoRAG'),
('R3','Wujiang Xu et al.','A-Mem: Agentic Memory for LLM Agents','NeurIPS 2025',
 'https://neurips.cc/virtual/2025/poster/119020','https://arxiv.org/html/2502.12110v11','https://github.com/WujiangXu/A-mem'),
('R4','Jiazheng Kang et al.','Memory OS of AI Agent','EMNLP 2025 主会 · 25961–25970',
 'https://aclanthology.org/2025.emnlp-main.1318/','https://aclanthology.org/2025.emnlp-main.1318.pdf','https://github.com/BAI-LAB/MemoryOS'),
('R5','Yingyi Zhang et al.','Evoking User Memory: Personalizing LLM via Recollection-Familiarity Adaptive Retrieval (RF-Mem)','ICLR 2026',
 'https://iclr.cc/virtual/2026/poster/10008269','https://arxiv.org/html/2603.09250','https://github.com/Applied-Machine-Learning-Lab/ICLR2026_RF-Mem'),
]
refhtml=''
for ref, authors, title, venue, official, paper, code in refs:
    refhtml += f'<div class="reference"><h2>[{ref}] {esc(title)}</h2><p>{esc(authors)} {esc(venue)}。</p><p>官方：{link(official,official)}<br>全文：{link(paper,paper)}<br>代码：{link(code,code)}</p></div>'
page('附录 B　参考文献与使用边界', '''
<p>以下链接可在 PDF 内点击。会议身份以官方页面为准；预印本版本用于阅读方法细节。检索日期：2026-09-15。RF-Mem 固定代码 commit 为 <code>d6a2cb3416e8320bcb1439921d319729aeccec8e</code>。</p>
''' + refhtml + '''
<p class="small">文献只为设计与复现提供依据。没有把跨数据集成绩混作 PersonaMem 32k 比较；没有宣称免训练意味着零推理成本；没有把公开 driver 的缺口直接归罪于发表表格。所有下一版方案仍需在统一模型、数据可见性与预算协议下验证。</p>
''', '参考文献 / 官方来源')

CSS = '''
@page { size: Letter; margin: 0; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; background:#eef1f4; color:#202733; }
body { font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",Arial,sans-serif; font-size:10.5pt; line-height:1.55; }
.page { width:8.5in; height:11in; padding:1in; position:relative; background:white; margin:14px auto; break-after:page; page-break-after:always; }
.page:last-of-type { break-after:auto; page-break-after:auto; }
main { height:9in; position:relative; }
.running { position:absolute; left:1in; right:1in; top:.45in; font-size:8pt; color:#647184; display:flex; justify-content:space-between; letter-spacing:.02em; }
footer { position:absolute; left:1in; right:1in; bottom:.43in; font-size:8pt; color:#647184; display:flex; justify-content:space-between; }
h1 { font-size:21pt; line-height:1.28; color:#183b5b; margin:0 0 15pt; font-weight:650; }
h2 { font-size:12.3pt; line-height:1.35; color:#2e74b5; margin:13pt 0 5pt; font-weight:650; break-after:avoid; }
p { margin:0 0 7pt; }
strong { font-weight:650; }
.subtitle { font-size:12pt; color:#445871; margin:0 0 11pt; }
.meta { font-size:9.4pt; color:#566275; margin:0 0 14pt; line-height:1.65; }
.lead { background:#edf3f8; border-left:3px solid #2e74b5; padding:10pt 12pt; margin:0 0 11pt; color:#193b5a; font-size:11.3pt; line-height:1.6; }
table { width:100%; border-collapse:collapse; table-layout:fixed; margin:8pt 0; font-size:9.1pt; line-height:1.45; }
th,td { border:1px solid #d8dfe7; padding:6pt 7pt; vertical-align:middle; overflow-wrap:anywhere; }
th { background:#f2f4f7; color:#34495e; text-align:left; font-weight:650; }
/* Named override: dense evidence tables keep body type size unchanged. */
.page[data-page="3"] th,.page[data-page="3"] td,
.page[data-page="4"] th,.page[data-page="4"] td,
.page[data-page="9"] th,.page[data-page="9"] td,
.page[data-page="13"] th,.page[data-page="13"] td { padding-top:4pt; padding-bottom:4pt; }
.page[data-page="4"] p,.page[data-page="9"] p { margin-bottom:6pt; }
.page[data-page="4"] th,.page[data-page="4"] td,
.page[data-page="9"] th,.page[data-page="9"] td { padding-top:3pt; padding-bottom:3pt; }
.page[data-page="9"] h2 { margin-top:11pt; }
.page[data-page="12"] li { margin-bottom:5pt; }
tr { break-inside:avoid; }
.numbers td:not(:first-child), .numbers th:not(:first-child) { text-align:center; }
ul { margin:5pt 0 8pt; padding-left:18pt; }
li { padding-left:2pt; margin:0 0 6pt; }
aside { background:#f4f6f9; padding:8pt 11pt; margin:10pt 0; font-size:9.5pt; border-radius:3pt; }
aside strong { color:#34526e; }
aside p { margin:3pt 0 0; }
.small,.caption { font-size:8.5pt; color:#627084; line-height:1.5; }
.caption { margin:4pt 0 8pt; }
code { font-family:Menlo,"SFMono-Regular",monospace; font-size:.87em; overflow-wrap:anywhere; color:#384b60; }
.formula { background:#f7f9fb; padding:10pt; font-family:Arial,"PingFang SC",sans-serif; font-size:11pt; color:#203e58; margin:9pt 0; }
.pipeline { display:flex; align-items:center; justify-content:space-between; gap:5pt; margin:0 0 12pt; font-size:9.1pt; color:#34526e; }
.pipeline span { background:#edf3f8; padding:8pt 6pt; text-align:center; border-radius:3pt; }
.branch { margin:10pt 0; padding:10pt 12pt; background:#f7f9fb; line-height:1.9; color:#2d4d67; }
.muted { color:#738092; }
.code-list { font-size:9pt; line-height:1.8; color:#425870; }
.hashes { font-size:8.2pt; }
.hashes td { padding:5pt 6pt; }
.hashes code { font-size:8pt; line-height:1.5; }
.case-id { font-size:8.5pt; margin-bottom:9pt; }
.reference { margin-bottom:11pt; }
.reference h2 { font-size:10.6pt; margin:9pt 0 3pt; }
.reference p { font-size:8.7pt; margin:0 0 3pt; line-height:1.5; }
a { color:#24699c; text-decoration:none; overflow-wrap:anywhere; }
#layout-qa { display:none; }
@media print { html,body { background:white; } .page { margin:0; } }
'''
html_pages=[]
for i,(title,content,kicker) in enumerate(pages,1):
    html_pages.append(f'<section class="page" data-page="{i}"><header class="running"><span>BRIDGETREE / PERSONAMEM AUDIT</span><span>{esc(kicker)}</span></header><main><h1>{esc(title)}</h1>{content}</main><footer><span>0.1.0 · source 3a55adcae46c · 2026-09-15</span><span>{i} / {len(pages)}</span></footer></section>')
script='''<script>
function auditLayout() {
 const rows=Array.from(document.querySelectorAll('.page')).map(p=>{
  const m=p.querySelector('main'), rect=m.getBoundingClientRect();
  const bottom=Math.max(...Array.from(m.children).map(c=>c.getBoundingClientRect().bottom));
  return {page:Number(p.dataset.page),height:m.clientHeight,scrollHeight:m.scrollHeight,
    overflowPx:Math.max(0,bottom-rect.bottom),title:m.querySelector('h1').innerText};
 });
 document.getElementById('layout-qa').textContent=JSON.stringify(rows);
}
document.fonts.ready.then(auditLayout); window.addEventListener('load',auditLayout);
</script>'''
result='<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>BridgeTree 当前问题与下一步修改建议 · 2026-09-15</title><style>'+CSS+'</style></head><body>'+''.join(html_pages)+'<pre id="layout-qa"></pre>'+script+'</body></html>'
destination=BASE/'BridgeTree_Audit_2026-09-15.html'
destination.write_text(result,encoding='utf-8')
(BASE/'report_requirements.json').write_text(json.dumps({
 'objective':['当前版本号和实验结果','当前分析出来的代码存在的问题','近两年顶会文章与下一步修改建议'],
 'report_pages':len(pages),'source_package_matches_run':P['local_source_matches_archived_run'],
 'tests':{'search_and_scoring_passed':42,'clients_passed':21},
 'research_window':'2025–2026, checked 2026-09-15',
 'no_experiment_code_or_configuration_changed':True,
 'no_new_model_calls':True,
 'visual_qa_status':'pending',
},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'html':str(destination),'pages':len(pages)},ensure_ascii=False))
