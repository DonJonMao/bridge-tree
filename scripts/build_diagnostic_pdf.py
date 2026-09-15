"""Build/print the Chinese PR1–PR4 diagnostic report from actual artifacts.

No model requests. HTML-to-PDF uses a local, isolated Chromium profile;
--render is explicit. PDF page images are inspected separately before delivery.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def esc(value):
    return html.escape(str(value))


def table(headers, rows):
    return "<table><thead><tr>" + "".join("<th>" + esc(v) + "</th>" for v in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join("<td>" + esc(v) + "</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table>"


def build_report(run_dir: Path, output: Path, acceptance: Path) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    report = json.loads((run_dir / "diagnostic_report.json").read_text())
    if report["manifest_id"] != manifest["manifest_id"]:
        raise ValueError("report/manifest identity mismatch")
    offline = report["sections"].get("offline_analysis")
    if not offline:
        raise ValueError("run diagnostic-analyze before building report")
    checks = []
    for path in sorted(acceptance.glob("*-isolated.xml")):
        tree = ET.parse(path)
        suites = tree.getroot().findall(".//testsuite")
        checks.append([path.stem, sum(int(s.get("tests", 0)) for s in suites),
                       sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)])
    log = subprocess.run(["git", "log", "-12", "--format=%h %s"], check=True, text=True, capture_output=True).stdout
    commits = [line for line in log.splitlines() if re.search(r"PR[1-4]:", line)]
    pages = []
    def page(title, body):
        pages.append((title, body))
    online = []
    for phase in ("score", "generation", "root"):
        summary = report["sections"].get(phase + "_summary")
        gate = report["sections"].get(phase + "_gate")
        status = (f"成功 {summary['success']} / 失败 {summary['failed']}" if summary else
                  "身份门禁阻断；未发送请求" if gate else "尚未执行")
        online.append([phase, status])
    page("BridgeTree：诊断改造与机制重设计方向", f"""
<p class="subtitle">讨论修订版 R2 · PR1–PR4 同轮交付 · PersonaMem-v1 32k</p>
<div class="lead">大方向已知，但具体机制尚未定稿：优先检验集合相关性是否代表证据价值，再决定是否重设计目标、选择路径或跨目标调度。</div>
<h2>本轮边界</h2><p>本轮实施的是可复现诊断与受控消融，不是 PR5。保持 legacy 集合评分、选择器和默认搜索行为；不训练，不加 dense 保护、新 Judge、新选择器、轮询或根预算保留。PR4 只增加默认关闭的零优先级根平局顺序消融。</p>
{table(['工作类别','PR','性质'], [['工程与可观测性','PR1','身份、缓存隔离、请求与失败审计'],['找问题与验证错因','PR2–PR3','历史回放、28格点评分、重复生成'],['诊断性机制扰动','PR4','只改变根之间无语义的平局顺序'],['主方法重设计','PR5','未实施，需依据诊断另行定义']])}
<h2>实际执行状态</h2>{table(['阶段','当前归档状态'], online)}
<p>离线实际归档已恢复 {offline['historical_score_count']}/{offline['subset_count']} 个小集合分数，保留 {offline['missing_score_count']} 个缺口。三个完整 archive 历史选择回放均匹配。假 HTTP 测试证明程序契约，不证明真实服务效果。</p>
<p class="small">运行身份：{esc(manifest['manifest_id'])}<br>源码快照：{esc(manifest['source_snapshot_hash'])}<br>当前模型调用结果以本报告关联归档为准；旧15页审计报告保留，不将其历史成绩当作本轮新测。</p>""")
    page("01　已经知道的大方向，与尚未确定的内容", """
<h2>第一优先：拆开相关性、互补性与停止判断</h2>
<p>当前 R 同时用于集合排序、四项交互差分和正边际停止。相关文本不一定补充回答所需的历史原因、约束或偏好更新。拟议方向是：让相关性负责候选发现，独立研究条件证据贡献和证据缺口；这不等于已经选定一个在线 Judge。</p>
<p>pointwise 描述批内评分契约，unit_interval 描述范围。两者都不证明概率校准或 cardinal 效用。现有 R 明确标记 legacy_query_relevance；utility_validation_id 为空，不包装成真实证据增益。</p>
<h2>第二优先：在目标值得优化时，再允许选择修正</h2>
<p>当前选择器只添加、不能删除替换，而且每一步必须严格正边际。可能需要有限联合添加、回退或替换，但如果补入关键历史降低 R，更强地优化 R 也可能更坚定地拒绝历史。读书会两条记忆的全部四个子集已知，当前 m73 是该局部范围的 R 最大值；是否补 m37 能稳定改善回答仍待生成诊断。</p>
<h2>第三优先：检验目标覆盖与深入搜索之间的分配</h2>
<p>现象更准确地描述为少数 target 周围预算集中，不一定是一条链无限加深。浅层分支也会消耗大量预算。只改变零优先级根的顺序，可以检验词典序敏感性；不能证明轮询有效，也不能解释已入候选的关键历史为什么被拒绝。</p>
<aside><strong>尚未确定</strong><p>如何可靠识别证据缺口；新效用是否需要新模型；是否存在正路径但 greedy 未找到；新增证据是否被生成器利用；服务是否截断或漂移。这些原因可以并存，不能只挑一个解释。</p></aside>
<p>固定 archive 和可行性时，严格单调变换不改变当前选择器轨迹；它却可能改变四项差分符号及跨状态边际优先级。因此 logit 不是现成修复，搜索阶段与最终选择阶段不能混为一谈。</p>""")
    page("02　PR1：部署、请求与失败必须可追踪", """
<h2>模型别名与实际身份分开</h2>
<p>新增模型/权重/部署 revision、量化、tokenizer、模板与服务版本字段；来源区分 unknown、operator_declared、server_reported、verified。verified 必须有核验依据。API 名和地址不等于权重身份，人工声明 INT8 不冒充验证。</p>
<h2>保留旧 context_hash，复用实际 payload 身份</h2>
<p>原 GenerationCache 已按真实请求建键；此次复用规范化函数，并补上部署 fingerprint。context_hash 继续保留来源与选择顺序含义；request_hash 描述实际 JSON；execution_hash 关联部署。embedding、reranker、generator 的缓存身份都纳入部署；未知身份限制在运行作用域，不读取身份不充分的历史共享缓存。</p>
<h2>先落盘，再发送</h2>
<p>请求日志记录 task/attempt/phase、逻辑调用、物理请求、拆批父子关系、原始文档 index、集合 IDs、文档 hash、token 估算与服务返回 usage。started 事件持久化后才发请求。没有真实 token 时为 null，不将 batch 总量分摊成虚假的单文档测量。</p>
<p>默认不记录凭据、私网地址或未经脱敏的正文。配置与显式 request_params 都递归拒绝凭据别名和嵌套 headers，保留合法工具/输出格式参数及旧同值 canonical 参数。</p>
<h2>预算与故障语义</h2>
<p>HTTP 重试和拆批共用物理上限，重启从已落盘 started 恢复额度。物理预算耗尽与审计写入错误必须作为诊断失败，不能被旧字符串识别误当正常集合预算停止。逻辑唯一集合额度和原算法规则不变，不填零，不提交未完成的四项测量或选择轮。</p>
<aside><strong>不夸大工程修复</strong><p>新增审计不等于已经修好旧 HTTP500 根因，也不证明服务没有内部热切换。部分成功子批缓存不在本轮必要交付中；未测到的结果不会被补造。</p></aside>""")
    rows = [[c['case_id'], len(c['universe_ids']), c['subset_count'], c['historical_score_count'],
             ' / '.join(','.join(i.rsplit(':',1)[-1] for i in ids) for ids in c['missing_ids']) or '无'] for c in offline['cases']]
    page("03　PR2：真实历史恢复与预算感知回放", f"""
<p>评分直接从 activation 的 P/Pe/PG/PGe 和 selection 的 base_score/combined_score 恢复，保留归档 SHA、成员、JSON位置、task 和重复观测。冲突、缺分、截断或身份错误都显式报告；不通过差分倒推或插值补分。</p>
{table(['案例','记忆数','子集数','已知','缺口'], rows)}
<p>三个问题分别包含自己的空集；集合身份必须包含 question_id。当前全部28项尚非完整历史评分表。若原部署不可证明一致，新测4项与旧24项混合只能是探索性表；本轮在线默认重新测全部28项并另存，不污染旧分。</p>
<h2>四个不同问题，分别回答</h2>
<ol><li>目标集合是否直接存在于真实 archive。</li><li>是否能由真实 bundle 的并集构造；B 跨出 U 时，不能擅自使用 B∩U。</li><li>是否存在每步严格正边际且输入可行的添加路径；缺分或可行性未知时保留 unknown。</li><li>原 deterministic greedy 是否找到；复用原比较、tie-break、整轮原子性及逻辑预算计数。</li></ol>
<h2>已完成的真实回放验收</h2>
<p>绘画、音乐、读书会的完整 archive 回放均匹配选中集合、停止原因、初末逻辑唯一集合计费、逐轮决策及完整比较域。受限 U 模拟单独命名，不代表全 archive 的任意反事实轨迹，也不能证明全库最优。</p>
<p class="small">detail archive SHA256：{esc(offline['source_sha256'])}<br>所有本页结果来自本地只读真实归档；network_calls=0。</p>""")
    b = manifest['budgets']
    page("04　PR3：冻结28格点与受控重复生成", f"""
<p>公开题目投影不携带正确选项。历史按原 prefix 和可见性规则重建；评分只接收 query 和真实记忆，全部选项仅进入 reader。反事实上下文统一用已有 build_context_plan 构造，在线严格恢复 ContextPlan，不重新拼提示、重排或截断。</p>
{table(['计划项','数量／上限'], [['完整小集合评分',manifest['counts']['score_logical_inputs']],['生成逻辑trial',manifest['counts']['generation_trials']],['每条件技术重复',manifest['repeats']],['评分物理尝试上限',b['score_transport_attempts']],['生成物理尝试上限',b['generation_transport_attempts']],['根消融物理尝试上限',b['root_transport_attempts']]])}
<p>默认条件为28个子集加3个历史dense上下文，共31个；每条件10次，合计310个trial。长度匹配且不含关键事实的补入对照需人工预先指定来源和理由，目前没有自动编造。若额外加入3个对照，需重新冻结为340个trial并调整预算。</p>
<h2>重复、缓存与续跑</h2>
<p>按 repeat block 预先打乱条件顺序。不同 repeat 绕过响应缓存，发送实际请求；同一 trial 续跑读自己的完成记录。响应已落盘而 outcome 尚未原子提交时可以精确恢复，不额外调用。不因答错、解析失败或暂时有利的结果增加样本或提前停止。</p>
<p>失败重试不是新 repeat；超时可能已在服务端执行，结果未知要留档。物理上限是传输尝试约束，不是账单 token。真实服务是否存在内部缓存或调度相关性，不能由客户端请求数单独证明。</p>
<aside><strong>评价边界</strong><p>gold 只在独立评价阶段读取。报告固定 trial 分母、成功输出分母、解析失败、标签分布及相对原选择的分块配对。三个事后案例重复10次仍是三个案例，不是正式 benchmark 准确率。</p></aside>""")
    page("05　PR4：仅根平局顺序消融，默认关闭", f"""
<p>默认 legacy_lexical，保持旧 heap 顺序。seeded_hash 只改变 priority=0 且 premise为空的初始根相对顺序；正信号后继仍优先于未访问零根，非根平局顺序不变。</p>
<h2>严格固定的内容</h2><p>不重命名 memory ID，不打乱初始候选测试序列，不改记忆文本、集合序列化、激活公式、pair rescue、ANN和逻辑集合预算。SHA排序不依赖 Python hash、全局 RNG 或进程种子。默认 trace/archive/selection 通过修改前 golden 对照。</p>
<h2>预先声明的执行矩阵</h2><p>三个案例分别执行 legacy 和 seeds {esc(manifest['root_seeds'])}，共 {manifest['counts']['root_runs']} 次搜索；全部种子都报告，不挑选最好种子。每次使用原始搜索和最终选择器，冻结完整 reader 输入但不调用生成器。</p>
<h2>实际追踪字段</h2><p>根排序和 pop 顺序、每个 target 的状态数与深度、首计 ANN/唯一集合成本、未访问根、archive和最终集合hash、外部候选进入多记忆bundle和最终上下文的比例；跨seed报告集合相等性与Jaccard。缺失选择结果保持null。</p>
<p>若搜索已完成而选择失败，保留完整搜索结果及已提交选择轮，不能把两阶段都改成失败。物理传输预算耗尽记录为外部执行失败，不宣称算法正常结束。</p>
<aside><strong>这不是新的调度机制</strong><p>没有轮询、根预算保留或覆盖保证。种子敏感说明有必要研究调度，不等于某个种子提高了方法质量；共享暖缓存下时延仍受方法执行顺序影响，逻辑预算才是受控维度。</p></aside>""")
    page("06　可执行交付与独立验收", f"""
<h2>分开提交，不混入原有工作树改动</h2><p>{'<br>'.join(esc(c) for c in commits) or '提交清单尚未生成'}</p>
<p>测试不仅在当前工作树运行，也在各提交独立 detached worktree 运行，确认导入隔离源码，不依赖后续PR或用户未提交修改。历史skip-failed工作区改动保留。</p>
{table(['独立验收产物','测试数','失败/错误'], checks) if checks else '<p>独立提交验收尚未归档。</p>'}
<h2>执行入口</h2><pre>python -m bridgetree diagnostic-plan --config CONFIG --output-dir RUN
python -m bridgetree diagnostic-analyze --run-dir RUN
python -m bridgetree diagnostic-score --run-dir RUN --config CONFIG
python -m bridgetree diagnostic-generate --run-dir RUN --config CONFIG
python -m bridgetree diagnostic-roots --run-dir RUN --config CONFIG
python -m bridgetree diagnostic-evaluate --run-dir RUN --gold-source CSV
python -m bridgetree diagnostic-report --run-dir RUN</pre>
<p>三个在线入口默认只展示清单；只有显式 --execute 才调用，并且必须通过身份、源码与预算门禁。--resume 不重置额度。完整命令与独立测试见 docs/diagnostic_runbook.md。</p>
<p>统一 JSON 报告连接 manifest、历史/新评分、重复生成、根trace、评价和失败。PDF是该状态的可读汇总，不替代原始归档。</p>""")
    page("07　诊断后的决策门，与本轮未完成项", f"""
{table(['得到的证据','下一步应改什么'], [['补入历史稳定有益，却降低R','优先修改评分目标或撤销当前效用解释'],['更好组合R更高，但archive不可构造','单独研究组合提议'],['存在正路径，greedy却走错','单独研究联合添加、有限回退或替换'],['事实在可见库但未召回','检查query、检索域与目标覆盖'],['证据已充分但重复生成仍错','检查reader输入、任务指令和利用能力'],['请求漂移、截断或服务不稳定','先处理部署/服务一致性，勿据此调公式']])}
<p>不能同时更换目标、选择器、调度器再猜收益来源。下一版新效用必须定义清楚：提供序关系、充分性标签还是可比较的差值；不能把未校准Judge打分直接塞入四项公式。dense锚点只能作为另命名的对照，不能证明条件机制被修好。</p>
<h2>当前归档中的未完成事项</h2>{table(['在线阶段','状态'], online)}
<p>若身份门禁阻断，需要部署操作者提供真实revision与来源、确认服务可用并在实验期间冻结部署，再建立新manifest。代码和假HTTP回归已完成不等于真实模型评分与生成实验完成；本报告不伪造在线成功率或宣称PR5已实现。</p>
<p>旧24分、新测28分、技术重复和根种子消融分别归档。生成结果出来后，应更新fresh格点分析和分块配对，再更新统一报告/PDF，而不是回写历史归档。</p>
<p class="small">本报告关联：{esc(run_dir)}<br>完整要求：docs/diagnostic_implementation_requirements.md<br>结论范围：同一PersonaMem-v1 32k历史的事后机制诊断；不是全体589题的正式方法排名。</p>""")
    css = """@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0;color:#172334;font-family:'PingFang SC','Noto Sans CJK SC',Arial,sans-serif;font-size:10.4pt;line-height:1.52}.page{width:210mm;height:297mm;padding:15mm 18mm 14mm;position:relative;break-after:page;overflow:hidden}.page:last-child{break-after:auto}.content{height:255mm;overflow:visible}h1{font-size:20pt;line-height:1.24;margin:0 0 7mm;color:#123e59}h2{font-size:12.5pt;margin:5mm 0 2mm;color:#174e67}p{margin:2.7mm 0}.subtitle{color:#567083}.lead{padding:4mm 5mm;background:#eaf3f6;border-left:3px solid #247492;font-size:12pt;margin:5mm 0}table{width:100%;border-collapse:collapse;margin:4mm 0;font-size:9.8pt}th{background:#e8eff3;text-align:left}td,th{padding:2.1mm 2.6mm;border-bottom:1px solid #d4e0e6;overflow-wrap:anywhere}aside{background:#f4f6f7;padding:3mm 4mm;margin:4mm 0}aside p{margin:1.5mm 0}.small{font-size:8.6pt;color:#536578;overflow-wrap:anywhere}pre{font:8.2pt/1.55 'Menlo',monospace;background:#f1f4f6;padding:3mm;white-space:pre-wrap;overflow-wrap:anywhere}ol{padding-left:6mm}li{margin:2mm 0}.footer{position:absolute;bottom:9mm;left:18mm;right:18mm;font-size:8pt;color:#6a7f8b;border-top:1px solid #d9e1e6;padding-top:2mm;display:flex;justify-content:space-between}#layout-qa{display:none}"""
    body = "".join(f'<section class="page"><div class="content"><h1>{esc(title)}</h1>{content}</div><div class="footer"><span>BridgeTree · PR1–PR4 诊断改造 · R2</span><span>{i+1} / {len(pages)}</span></div></section>' for i, (title, content) in enumerate(pages))
    audit = """<pre id="layout-qa"></pre><script>window.addEventListener('load',()=>{document.getElementById('layout-qa').textContent=JSON.stringify(Array.from(document.querySelectorAll('.content')).map((p,i)=>({page:i+1,overflowPx:p.scrollHeight-p.clientHeight})));});</script>"""
    output.mkdir(parents=True, exist_ok=True)
    path = output / "BridgeTree_Diagnostic_R2.html"
    path.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>BridgeTree PR1–PR4 诊断改造 R2</title><style>' + css + '</style><body>' + body + audit + '</body></html>', encoding="utf-8")
    return {"html": str(path.resolve()), "pages": len(pages), "manifest_id": manifest["manifest_id"], "commits": commits, "acceptance": checks}


def print_pdf(source: Path, chrome: str) -> dict:
    pdf, qa = source.with_suffix(".pdf"), source.parent / "pdf_qa"
    qa.mkdir(exist_ok=True)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="bridgetree-diagnostic-pdf-") as profile:
        cmd = [chrome, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-background-networking", "--disable-component-update", "--disable-sync", "--disable-extensions",
               "--disable-default-apps", "--disable-background-mode", "--metrics-recording-only", "--virtual-time-budget=1000",
               "--user-data-dir=" + profile, "--no-pdf-header-footer", "--dump-dom", "--print-to-pdf=" + str(pdf), source.as_uri()]
        with (qa / "browser_dom.html").open("w") as out, (qa / "browser_render.log").open("w") as err:
            process = subprocess.Popen(cmd, stdout=out, stderr=err)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if pdf.exists() and pdf.stat().st_mtime >= started and '</html>' in (qa / "browser_dom.html").read_text():
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(.2)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    dom = (qa / "browser_dom.html").read_text()
    match = re.search(r'<pre id="layout-qa">(.*?)</pre>', dom, re.S)
    if not match or not pdf.exists() or pdf.stat().st_mtime < started:
        raise RuntimeError("PDF render or layout audit did not finish")
    layout = json.loads(html.unescape(match.group(1)))
    (qa / "layout_qa.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2))
    if any(p["overflowPx"] > 1 for p in layout):
        raise RuntimeError("PDF page content overflows: " + str(layout))
    return {"pdf": str(pdf), "bytes": pdf.stat().st_size, "pages": len(layout), "overflow": False,
            "visual_qa": "pending_page_image_inspection"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--acceptance-dir", type=Path, default=Path("outputs/diagnostics/acceptance"))
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--chrome", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    args = parser.parse_args()
    result = build_report(args.run_dir.resolve(), args.output_dir.resolve(), args.acceptance_dir)
    if args.render:
        result.update(print_pdf(Path(result["html"]), args.chrome))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
