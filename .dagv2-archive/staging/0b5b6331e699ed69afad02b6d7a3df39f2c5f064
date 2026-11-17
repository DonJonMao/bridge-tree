# 基于 dagv2-origin 的改进方向：分歧触发的绑定条件检索

日期：2026-10-02。本文是研究设计，不是算法实施、效果报告或新颖性认证；未修改 dagv2、package、dagbt 或数据文件。

## 1. 建议敲定的主张

**不把“保留两个候选”作为贡献。最可测的研究问题是：当一个中间答案槽出现竞争实体时，在相同候选集合与真实成本内，检索“候选实体是否满足原问题的绑定关系及限定条件”，是否比继续回答两条下游分支、重搜原问题或通用核验，更能纠正错误绑定并减少跨跳传播？**

核心动作不是多问一次“陈海出生在哪里”，而是构造包含候选原文姓名、尚未核实的绑定关系、原问年份/身份/版本条件的查询，例如“陈海；导演；《归途》；1998 版”。对另一候选林舟做对称检索。候选被检索到许多生平事实不应增加其“1998版导演”资格；只有绑定关系证据可以改变该槽的采用状态。

多值槽、原文核验和局部回滚已有 BeamAggR、ReAgent、DVA 等先例，新版也已有支持失效和局部重求解。它们在本路线中属于必要基础设施。待验证的增量是**分歧触发何种查询、查询怎样回到原问绑定条件、未知证据怎样不被误剪**；即使这一组合有效，也仍需精读近作源码查等价机制。

最小版本应在判别完成前暂不放行依赖子节点，先验证检索动作本身；这样不需要先引入深链回滚、全局树搜索和复杂价值学习。下游重放可独立进入第二阶段。

## 2. origin 的确切改动入口

老版实际入口先由 `dagv2/experiment_v6.py:21–24` patch 冻结核心。关键代码文件此前已与 original_manifest 逐字节匹配。本设计另建研究入口/模块，不能覆盖冻结文件。

| 现有位置 | 老版语义 | 本路线最小变化 |
|---|---|---|
| package/core.py:61–77 schema/decode | 单 answer + panel长度的sources布尔数组 | 普通节点保留；仅一个合格桥节点调用候选输出协议，最多2项，每项原文出处独立验证 |
| core.py:80–87 node_state | 非空answer且勾来源即resolved；继承全部resolved父闭包 | 包装单候选/双候选状态；分别记录proposed、supported、contradicted、unknown、adopted；闭包属于具体假设，不属于两个答案的混合 |
| core.py:17–27 ground | 已解父的唯一answer替换slot；未解父以父问题代替值 | 每个接地请求引用明确候选ID；模糊父槽不自动用父问题继续生成派生证明 |
| v6 controller:34–80 | 单次拓扑遍历，每节点一次检索与一次作答 | 增加一个clarify动作及预算检查；完成判别后才执行依赖子节点；未决后代显式blocked |
| core.py:30–34 source_panel | 父直接引用优先，其后新hits，截20 | 对照判读面板保护候选锚定来源，同时保留对称的新检索份额；仍保留20篇上限 |
| core.py:90–114 select_sources | 等权完整闭包枚举 | 第一阶段沿用目标函数；只将采用假设作为一个resolved证明，不把互斥假设并成一个proof |
| v6 reader_input:87–101 | 所有resolved链，第一source_id，空span，链尾优先 | 采用链携带具体绑定证据；未决或拒绝候选不成为committed链。选集链门控作为共有安全接口或独立消融，不混称检索创新 |

原始 planner、archive、NV-Embed-v2、全语料top50并入池、普通节点top20/512 tokens、Reader1024 tokens可保留。原问已经出现在节点提示（core.py:37–58），原提示也提醒父答案可错；缺口不是再追加一句“注意父答案可能错”，而是可执行的绑定检索动作和候选状态。

## 3. 触发条件与应用范围

第一阶段只针对**有依赖后代的中间槽**，每题最多一次clarify。没有后代的直接问题不是错误传播研究的主场景。

触发需同时满足：

1. 面板原文出现两个不同、可定位的实体候选，且至少有一条关系/身份材料支持其作为当前绑定的提议。只采样出两个字符串不够。
2. 两候选与当前任务相关，但**当前拟采用候选**的至少一个必要绑定条件尚未被现有证据明确建立，或两侧出现相冲突的完整绑定支持。仅有一个旁支candidate未知，而拟采用项已获充分直接支持，不自动触发额外检索。
3. 能从**原问题文本**回连该条件；不能凭外部常识或gold新增“哪个更可能正确”的条件。
4. 至少存在一个区别于已请求原node/原问查询的新查询。候选原文名称必须进入查询，避免只重复原node问题、获得相同dense向量与top50。
5. 有足够的新增检索、判读、输出容量和最终Reader预留。否则记录not_triggered_budget，不启动半个分支。

触发协议会有漏判，需单独报告候选提出率、合法引用率、触发率与无效触发率。它不等于真实歧义检测器；不能把公开问题中有年份的比例直接当作路线的适用率。

候选生成和clarify需分成两级：在第一个“有后代且原问有可引用绑定条件”的节点做一次proposal（替代普通node调用，输出上限1024）；只有proposal满足上述证据分歧条件才花两次新查询和一次判读。每题最多一个proposal，没产生合格候选也不再逐节点重试；未触发时那次1024上限/实际usage仍记入方法成本。

“唯一答案”是本阶段的任务假设，而不是“who”一词或answer_type即可证明的事实。导演、作者等关系可以多值。若原文支持两个共同导演/多作者，不能把真实多值答案强行当成二选一冲突；退出该消歧机制，交给原问Reader，单独记录multi_value_supported。

## 4. 绑定条件与三值证据

### 4.1 条件从哪里来

候选调用复用原问与当前node文本，返回至多两个binding requirements，每个包含原问的精确span与当前绑定谓词。仅将原文可引用的年份、作品/机构身份、版本、职务、亲属或其他明确关系写入条件。程序核对span确实存在于原问题；语义关联是否正确仍须判读/人工审查，substring合法不等于关系正确。

第一版不额外调用LLM为所有题抽取条件，也不修改planner。将条件提取嵌入替代的候选节点调用，并在所有候选对照臂中共享。若原始plan丢了条件，以原问文本恢复；若无法把条件关联到当前槽，跳过clarify。候选输出及条件抽取同时改变prompt，因此exact origin与新方法的系统差值不能完全归因查询；主机制应在共享候选调用的实验臂间比较。

未核实条件选择采用预先固定规则：优先明确年份/版本，再显式身份/命名范围，再当前父槽与原问之间的关系绑定；同级按原问span顺序。不在测试期按gold或成功题调优。复杂效用学习不是首版必需。

### 4.2 状态针对完整绑定命题

设命题为 `P(h) = candidate h 满足 question 中该槽的全部必要绑定条件`。对照判读只允许：

- **supported**：原文直接建立相应实体—关系—范围，关键限定条件也被支持。
- **contradicted**：原文明示排除该实体/条件，或在有出处的互斥/唯一性条件下不相容。
- **unknown**：只提及候选、只给生平、只支持另一版本、缺少必要限定条件、没检索到充分资料，或证据冲突尚未澄清。

三个例子：

| 原文 | 对“陈海导演1998版《归途》”的地位 |
|---|---|
| 陈海出生武汉 | unknown；证明出生地，不证明影片导演绑定 |
| 陈海导演1986版《归途》 | unknown；另一版本不能单独排除他也导演1998版 |
| 1998版《归途》由林舟独立执导，并非陈海 | 可构成contradicted；须核对“独立/并非”确为原文 |

不把低dense分数、资料少、检索失败或另一侧来源更多当反证。原文支持一个候选、另一候选仍unknown时，可暂采用有直接支持的一侧继续答题，但必须标记`unexcluded_competitor=true`；这不叫已证明唯一。若两侧都supported但不具互斥事实、或两侧unknown，保持ambiguous，不硬剪枝。

### 4.3 查询的最小确定性模板

```text
query(h) = 候选在原文中的实体名称
           + 当前需要核实的绑定关系
           + 原问明确实体/作品/机构名称
           + 原问尚未核实的年份/版本/身份条件
```

查询文本由已验证的candidate/requirement字段确定性拼接，不额外用一次LLM自由写query。只有原文出现的别名可扩展，不能猜别名或加入外部事实。查询必须保留陈海/林舟等candidate原文实体token；若只重复“谁导演了1998版《归途》”，既不能区分检索动作，也可能精确命中已有请求缓存。

第一版为两候选各一次全语料dense检索，各top50并入原池。对照判读panel最多20篇：候选锚定来源最多4篇先保留，剩余位置对两侧新hits公平分配，重复篇只占一个位置，固定顺序补足。完整原文必须可见，不把摘要当新事实来源；如上下文容纳不下全部文档，按完整文档减配并记录，锚定文档也容不下则不启动该动作。

这是可复现的第一版策略，不宣称top50或拼接模板最优。直接generic-query与普通下游query都应作为强基线，不能只和随机噪声比。

## 5. 最小schema：提议、证据和依赖不要混在一个bool

候选节点的研究输出可采用以下结构，限定字符串与数组长度，避免生成无限诊断文字：

```json
{
  "primary_answer": "陈海",
  "requirements": [{
    "id": "r1",
    "question_quote": "1998版《归途》的导演",
    "binding_relation": "director_of",
    "subject_quote": "《归途》",
    "scope_quotes": ["1998"]
  }],
  "candidates": [{
    "id": "h1",
    "answer": "陈海",
    "evidence": [{"panel_index": 2, "quote": "陈海执导了《归途》。"}]
  }, {
    "id": "h2",
    "answer": "林舟",
    "evidence": [{"panel_index": 5, "quote": "林舟执导了影片《归途》。"}]
  }]
}
```

这是虚构schema示例，不是本仓库真实题/模型输出。panel_index必须在实际面板内，quote须逐字存在于该文档；歧义匹配要保存实际offset与doc_id，程序生成稳定span ID。实体/关系蕴含仍是语义判读对象，不由引用存在自动推导。没有合格第二候选则退回primary单值路径，不强造二选一。

判读调用返回每候选的`requirement_id/status/evidence_refs`、采用项或ambiguous、以及`unexcluded_competitor`。contradicted必须引用排除证据；判读输出IDs只能来自实际可见候选/条件/文档。输出不合法时保留unknown，而不是转成语义反证。协议失败及重试成本另记。

普通origin节点的answer/sources输出可以暂时不扩成全局复杂schema。由controller包装为单候选状态，并记录该请求**实际接地采用的父假设ID及版本**：

```text
node_state:
  adopted_hypothesis_id
  candidates / criterion_status / unexcluded_competitor
  bound_parent_refs = [(slot, hypothesis_id, version), ...]
  source_doc_ids / exact_binding_evidence
  closure_doc_ids
```

此处bound_parent_refs指“控制器用哪些取值接地并展示给模型”，不是模型语义上确实使用了哪些父结论。首版可以保守继承全部bound父项的闭包，宁可过度失效，也不能冒称已证明actual-use；新版的实际used-parent AND/OR解析可作为后续组件。

闭包必须随具体采用假设形成：绑定关系原文 ∪ 本节点答案来源 ∪ 所接地父假设闭包。两候选的闭包不能取并集后伪称一个更完整证明。父候选ID改变时，引用旧ID/version的派生状态失效；未使用该假设的独立支路可保留。

## 6. 可执行的硬预算

### 6.1 推荐MVP：判别之后再放行孩子

第一版每题最多在一个桥节点触发一次；在该槽采用前不执行其依赖孩子，所以**没有任意深链重放需求**。

| 动作 | 逻辑LLM请求 | 新增dense embedding查询 | 输出上限 |
|---|---:|---:|---:|
| 合格桥节点候选生成（替代原node调用） | 不增加次数 | 0 | 1024，替代原512 |
| 两候选绑定查询 | 0 | 2 | 不适用 |
| 对称原文三值判读 | 1 | 0 | 1024 |
| 采用后继续原DAG普通节点 | 不额外分叉 | 原定额度 | 每次512 |
| 最终Reader | 原定1次 | 0 | 1024，必须预留 |

最坏n=6时：origin有planner1+node6+Reader1=8个逻辑LLM请求、archive最多7+node6=13个embedding请求。MVP上限是**LLM9、embedding15**。输出最大预算从origin的6144（2048+6×512+1024）增至7680：候选替代多512，加判读1024。查询去重、节点跳过或不触发可降低实际消耗，不能把上限冒充实际成本。

一个新调用不等于只有一单位成本：候选生成prompt/输出也变化，对照臂需报告全部actual usage。原始512不一定足够两个quote和条件；故明确设1024，不假装“零tokens增量”。不保证1024永远输出合法JSON：要求finish=stop、完整字段；失败按协议失败处理，不能悄悄扩大输出或补无额度的LLM。

上下文检查改为研究请求实际 `prompt_tokens + output_reserve + 8 <=16384`。老版v6:55/101传prepared(False,0,0)，没有输出预留；exact origin需保持原代码并披露差异，新的请求预算不能沿用这个不完整检查。

执行clarify前，预留两次embedding请求、一次1024输出判读、后续原定可执行节点和Reader。不具备完整reserve时不启动该动作。歧义判读耗尽仍unknown时，不展开第二条深链：后代标blocked，以候选池原文运行raw Reader兜底；最终回答按正常全任务F1/EM计分，Reader失败计零。ambiguous自身不能被排除出样本，也不必机械地把正确raw兜底答案计零。

HTTP层仍可允许每逻辑请求最多3个持久化相同payload尝试（package/run.py:82–131），必须分别报告逻辑请求、物理尝试、失败、缓存命中与usage_unknown。24个逻辑服务请求（9+15）不意味着24个物理尝试；最保守物理尝试上限72。超时后服务实际用量未知时不能声称精确总tokens。缓存命中不算新服务调用；相同query的重搜不得伪装等物理成本。

### 6.2 第二阶段才允许推测执行/回滚

若后续确需在父槽未决前先执行一个替代子节点，则另设独立硬上限，例如额外候选子节点1个、changed-parent后最多重放2节点。它在MVP之外最多增加3个LLM和3个embedding请求，512输出/节点；必须在动作启动前同时预留完整额度与Reader。

若受影响后代超过2个，不能宣称“2次额外调用重跑整个6节点DAG”。可选择不提前提交；或只重放已预留部分，其余状态保持invalidated/blocked，回到raw Reader。禁止使用旧已失效答案凑成完整链。此阶段的传播依赖和成本单独消融，不能把它的收益算成绑定查询本身。

## 7. 三类强对照：固定候选，比查询和裁决

所有主机制臂共享同一candidate提议、初始panel、primary答案、条件抽取、模型、top50、最终Reader模板和新增硬额度。新候选prompt可能改变primary答案，故exact origin仍单列系统基线，组件归因优先看以下共享前端的臂。

| 臂 | 两次新增检索用于什么 | 判读 | 能隔离的问题 |
|---|---|---|---|
| Binding | 候选姓名 + 未核实绑定关系 + 原问范围条件 | 相同三值对照器 | 主机制 |
| Downstream | 分别接地原计划的第一个必要child问题，如两人的出生地 | 相同三值对照器 | 是否查询目标本身比多分支展开更重要 |
| Generic verify | 候选姓名 + 完整原问或完整parent问题，不专门抽取未核实绑定条件 | 相同三值对照器 | 是否只是通用原文verification |
| Original re-search | 原问/原node原句 | 相同三值对照器 | 重搜原问的机制下限；相同payload很可能缓存命中，必须如实报实际零新调用 |
| Random useful query | 从已有plan可执行问题池随机选两个新query，不用gold；固定qid散列seed | 相同三值对照器 | 是否新增检索机会即可带来收益；不是随机语料噪声弱对照 |

随机query池只包含原问或已有plan可接地问题，候选取值只能来自已提出集合。若不足两个未请求query，按可用数量执行并记录；不得人为捏造无关文本凑满次数。硬额度相同不自动等于实际成本相同，应画F1对实际tokens/物理请求的前沿，并报告未用额度。

### 分开测试原文判别和候选聚合

固定候选与新检索文档后，再比较三值binding判读、普通单答案verify、BeamAggR式边际/beam聚合、self-consistency。没有真实每分支生成/logprob时，不能把一次LLM自报confidence叫做BeamAggR复现。真正BeamAggR/ReAgent/DVA的同模型适配应实现其机制并单列，固定总请求/tokens上限，报告实际消耗；首版只有1个额外判读LLM，无法公平装下任意beam的所有分支生成，需在更高预算档比较或用已缓存分支结果做明确标注的离线聚合对照。

三值判读同样来自模型，会误判；它不是事实gold。普通verify最好也可回答unknown，不能故意让基线把没证据判错再声称胜出。真正区别应是是否核验绑定条件、是否对称比较竞争实体以及取得什么新证据。

### 建议的必需消融

1. 保留同一候选，Binding → Downstream/Generic/Random，判读器不变，隔离query目的。
2. Binding查询不变，三值对照 → 普通verify/真实beam聚合，隔离判读规则。
3. Binding中删除candidate原文姓名token，但保留条件，确认不是原node重复检索。
4. 保留candidate姓名，删除未核实限定条件，确认是否只因实体名称改善dense匹配。
5. 候选反例不足时“unknown保留” → 已有相应基线政策，测误剪率；不能把故意错误的binary规则当唯一强对照。
6. 第二阶段才对依赖失效/局部重放做独立消融；第一阶段不把回滚列为检索贡献。

额外选择目标、链门控、学习型VOI均推迟，避免首轮同时改变多个主要机制。某些安全字段与候选前端是共同基础设施，所有组件对照共享它们，并单独列exact origin作为系统参照。

## 8. 主结果、证据结果与否证条件

主结果是所有测试题的F1/EM与实际成本；匹配成功共同子集只能作辅助。预先定义的triggerable子集单列，不能跑完后挑“最受益题”作为主表。

机制指标至少包括：

- 候选包含正确绑定的比例、合格引用比例、trigger/unknown/multiple-supported比例。
- 新检索取得原问绑定条件证据的比例，进入实际判读面板的比例。
- 判读前后采用项变化；正确救回和新引入错误分开统计。
- contradicted误判率、unknown误剪率、采用unknown竞争项时的错误率。
- 受影响后代错误传播率、invalidated状态被继续使用率（应为0）。
- 拟合阈值/模型全部只用独立开发集；测试gold仅在全量生成后做答案评分或离线候选上界诊断。

“decision-changing evidence”不能由judge说“我改变主意”自证。应保存判读前后的原文与候选状态，由盲审者确认新增证据是否实际支持/排除原问绑定条件；再看该变化是否改善gold答案。若判读变化多而答案更差，说明动作没有达到目标。

关键否证：同候选、同成本下Binding不优于Generic或Downstream；新增材料只是生平或主题重叠；收益仅来自候选prompt或链门控；大量真多值任务被误当竞争；两个候选都错的题占多数；quote合法但原问条件提取漏失导致误判。出现这些结果，应缩小为检索/诊断组件，而不是扩大beam或继续宣称主创新。

## 9. 公开问题文本的离线分布（未读gold）

只读取三个 `data/<dataset>/questions.jsonl` 的 `id/question` 字段，按固定case-insensitive正则统计词面cue；没有读取evaluation_only、corpus支持标签或输出scores。下面各列可重叠，词面cue不是歧义发生率，不证明该题需要分叉。

| 公开词面类别（每集1000题） | HotpotQA | 2Wiki | MuSiQue |
|---|---:|---:|---:|
| 明确四位年份：1xxx或20xx | 189 (18.9%) | 66 (6.6%) | 56 (5.6%) |
| 时间/比较cue，包括when/year/before/first等 | 196 | 338 | 358 |
| 身份/角色/亲属关系词，如director/author/mother等 | 188 | 681 | 268 |
| 媒介/范围名词，如film/book/edition/season等 | 211 | 494 | 72 |
| 比较cue，如same/both/older/first等 | 212 | 481 | 110 |
| 年份与角色关系词同时出现 | 44 | 53 | 4 |
| 角色关系词或媒介名词出现（去重） | 333 | 771 | 318 |

三集仅311/3000题（10.37%）出现明确年份。因此路线不宜仅定义成“年份消歧”；更普遍的绑定关系/身份条件值得考察。但表中大量词只是最终问法或普通名词，例如when可能是答案目标而非限定条件，film不说明存在同名版本。真正eligible率必须在非gold的candidate/evidence触发日志中测。

统计正则：

```text
year: \b(?:1\d{3}|20\d{2})\b
time: \b(?:before|after|during|between|earlier|later|first|last|oldest|youngest|when|year|month|day|date)\b
identity: \b(?:directors?|writers?|authors?|composers?|performers?|singers?|actors?|actress(?:es)?|producers?|presidents?|prime ministers?|founders?|mothers?|fathers?|wives|wife|husbands?|sons?|daughters?|parents?|spouses?|brothers?|sisters?)\b
media: \b(?:versions?|editions?|remakes?|sequels?|series|seasons?|episodes?|albums?|films?|movies?|books?|novels?)\b
comparison: \b(?:older|younger|taller|larger|smaller|more|less|same|both|earlier|later|first|last|highest|lowest|longer|shorter|oldest|youngest)\b
```

读取文件SHA256：HotpotQA `1f03126ae012a531f7fdfcf24092b2e1392725316f7b4625a6985ea9fd372e13`；2Wiki `a480b140a33bd9af516287fd786c242dcca2f8bbdf776d1b963bc172580c687f`；MuSiQue `d88be698d8b7f61dc13f2bd4076af66acf27f75a904941a59b404353dd214a79`。均与original_manifest相应问题文件一致。这是固定本地1000题子集的统计，不外推官方全集。

## 10. 敲定后的第一轮实施清单（仍未实施）

1. 冻结研究问题、上面MVP硬预算和trigger规则；准备独立开发题，不能用当前全测试gold选择规则。
2. 保留exact origin完整运行身份；建立共享candidate前端的controlled实验臂。
3. 只做一处中间槽的候选提议与binding查询；判断前不放行后代。
4. 首先跑Binding/Downstream/Generic三臂，再补Random与原问重搜，保存所有实际query和引用。
5. 机制成立后才做beam/ReAgent/DVA强比较，以及依赖回滚、链门控或终端选择的配套实验。

可交付的新方向是**绑定条件检索策略的可复现实验**，不是“又一个多候选RAG”。若同预算普通verify已经同样有效，就应如实把结论改成对origin的低成本核验增强；不要为维持新颖性再叠模块。
