# PersonaMem v3.1：两版均有效作答时的答案质量诊断

分析对象为本目录上传结果的 `original` 与 `dagbt_residual_memory_v1`，不是其他 BridgeTree 实验。以下只讨论两臂均成功、可解析选项的配对题。读取方式为 `gzip.open/json.load`；未运行模型、未修改生产代码、未将完整压缩行解压到磁盘。

## 结论与证据强度

最强的已确认现象是：若计划把 PersonaMem 的“依据个人历史选择最佳回应”收缩成一个当前事件/实体的事实抽取，融合版可以正确找到、正确认证这个窄事实，却选择错误的公开选项。部分错误中，足以区分选项的个人证据**已经进入实际模型输入**，甚至被模型在理由里明确提及，因此不能统一解释为检索没找到。

根代理的完整配对统计：共同有效 238 题，original 正确 162，fusion 正确 144；harm 35，rescue 17。按 fusion 的实际完成类型分层，`certified_symbolic` 51 题中为 36 对 20，`semantic_assessment` 187 题中为 126 对 124。净差 18 题中的 16 题集中在前一组。完整分层见 `completion_cohort_metrics.json`。根代理另检查了 `features.jsonl` 中的 `program`：这 51 题的 `expression.op` 全为 `var`；48 题只有一个变量，另外 2 题有两个变量、1 题有三个变量。这些“认证”主要是单变量事实的输出，不是复杂多跳计算。

**不能据此宣称符号模式因果导致下降 31.37 个百分点**：分组不是随机的，题型和任务结构不同；也没有做更换终端或计划的反事实重跑。这里能定位的是已发生的任务目标错配，以及认证覆盖的范围。

补充定位出两类 semantic 模式错误：个人历史中的时间变化在压缩为 profile 时丢失，以及从已绑定的个人事实跨到更泛化、证据更弱的建议。正向样例又表明，窄 `semantic_answer` 并非必然失败，semantic 终端能从可见原文中选出符合个人偏好的答案。

## 复核方式与限制

`paired_cases.json` 保存每题的 question、options、gold、两臂预测和压缩行路径。`effective_answer_case_evidence.json` 是本次 10 个深入案例的紧凑摘录，保存两臂预测、融合版 answer/initial_program/facts、original 节点及 20 篇选中材料、准确的 event 数组下标、每次调用的输出、相关原文与 doc_id 映射。它不是完整行的解压副本。

下文 `E[n]` 表示融合行的 `diagnostics.events[n]`；`P[n]` 表示对 `E[n].messages[1].content` 做 JSON 解析；`O[n]` 表示解析 `E[n].raw_output`。当 `source_spans` 为列式数组，需按同一 payload 的 `source_span_columns` 还原对象；`source_documents[dN]` 给出真实 doc_id 与时间元数据。`sN/dN` 仅在对应调用内解释。

original 行可见 `ranking.nodes`、`budgets["20"].selected_doc_ids` 及最终 `answer.prediction`，但本次行中没有最终 Reader 的完整请求原文，不能把选中文档列表等同于逐字确认最终 wire。源码 `dagbt/runner.py:528` 与 `:570` 则确认其独立 Reader 会看到 MCQ，并被要求依据个人记忆和偏好变化选择最佳选项；两臂上游规划都使用去掉选项的用户请求。

没有 gold supporting documents，不能从这些案例计算或声称“检索 recall 下降”。“证据已读到”仅指实际 wire 已提供该文字；无法观察模型内部是否认真处理。下述因果判断均为有证据支撑的解释，而非已完成消融的因果结论。案例是有目的选取的，不用来估计各故障类型占比。

## A. 窄事实被认证，不等于最佳偏好回应被认证

### A1. DIY 茶几：证据写明 DIY，最终却选泛化回应

- `unit_id`: `f740d2d7-3cec-4568-824c-95164aff05f3`；`recall_user_shared_facts`；gold/original=`d`，fusion=`a`；`answer.completion_kind=certified_symbolic`。
- 用户说刚用旧木料做了咖啡桌。d 回忆用户对 DIY 家具的兴趣；a 只是称赞项目并询问还有什么爱好。
- `diagnostics.fact_state.initial_program.variables.project` 只要求 project；表达式为 `var(project)`；`facts.project`、`answer.semantic_answer`、`answer.certificate.output` 都是 `a coffee table from reclaimed wood`。
- **实际读到**：`E[227]` 为 joint_read/call 2，`P[227].source_spans` 共 100 段。s3/d1 原文为 “I recently completed a unique DIY furniture project where I created a coffee table from reclaimed wood”；s4/s5 继续描述规划、完成和满足感。`O[227].slots[0].observations[0]` 引用 s3/s4/s5，理由明确识别 DIY 项目，但 `final_prediction=a`。
- `E[256]` 为 audit_joint/call 3，只读 9 段，再次认可 project；`P[256]` 无 `public_options`、无 `terminal_expression`；`O[256].audit_verdict=supported`，`final_prediction=null`。
- original 的三个节点也只是 project/material/material_type，均绑定同一文档 `personamem:memory:3560aa3c01233b19c1ab95a841b57e1f7d31868bcad89a277faa0d798977d11a`，但最终选 d。

**确认**：不能说“没有找到任何 DIY 证据”；事实值正确且有证据，错的是最终回应选择。**解释**：任务目标过窄以及局部事实审计与选项判别不一致，是比“分解更差/检索更差”更直接的候选机制。不能仅凭这段断言原文存在独立的、早于该项目的“兴趣声明”。

### A2. 图书馆：原版两个节点都失败，独立 Reader 仍选对

- `unit_id`: `cffc32b7-fa14-457f-ac4f-9c060bf2aee1`；`recall_user_shared_facts`；gold/original=`b`，fusion=`d`；`certified_symbolic`。
- 用户说昨天下午又去了图书馆。b 回忆其喜欢去本地图书馆；d 只是一般回应并询问新书。
- 计划问 “What did the user do yesterday afternoon?”，`facts.activity`/`semantic_answer`/`certificate.output` 为 `spent time at the library`。
- `E[229]` joint_read/call 2 实际有 101 段：s3/d1 “I just spent a meaningful afternoon at a local library ... inviting and peaceful”；s4 描述 refreshing；s11/d2 描述在图书馆志愿活动很有收获；s21/d3 描述 regular volunteering schedule，期待每周连接他人。相关偏好证据均可见。
- `O[229]` 引用 s3/s4 支持 activity，却给 d。`E[256]` audit/call 3 的 8 段只复核 activity，不再输出选择。
- `original.ranking.nodes` 的 library_name、library_address 均 `resolved=false`、answer 为空；但 `original.answer.prediction=b`。

**确认**：original 此题成功不能归因于其拆解更贴合任务。**解释**：当前活动被抽取后，个性化偏好没有成为必须满足的终端输出条件。另有较小的时间推断问题：源文本的 “just” 被理由称为直接匹配 “yesterday afternoon”，但没有精确事件时间证据；不能证明这个时间推断导致本题选项错。

### A3. 文化节：决定性负面偏好已读，因不提供节庆名称被排除

- `unit_id`: `bd19b555-7c4a-401e-8033-36658ee6650a`；`recall_user_shared_facts`；gold/original=`a`，fusion=`b`；`certified_symbolic`。
- 用户说旅途中也参加了一些文化节。a 回忆在节庆中被拥挤人群压垮；b 泛化赞扬冒险精神。
- 计划/事实只输出 `festivals` 集合，`semantic_answer`/`certificate.output=["a small local festival focused on food and traditions"]`。
- `E[235]` joint_read/call 2 有 104 段。s20/d3（message 17）明确写 “I did explore some cultural festivals during that trip, but I felt overwhelmed by the crowds”；s21 说明想找安静咖啡馆，文化节可能不符合悠闲探索偏好。真实 doc_id 为 `personamem:memory:4575c7a12d4d90ab95247d721680b484cd79ccd088ca55c80bd50c4ab9fc6b48`。
- 同一输入的 s12/s13/d2（message 76）描述另一次愉快的地方食品/传统节庆。`O[235].slots[0].unresolved` **直接提到** d3 的 overwhelmed，但说它不能确认旅途中的具体节庆名称；于是只引用 s12/s13 支持 festivals，最终选 b。
- `E[262]` audit/call 3 只有 d2 的 8 段，继续确认该集合；未重新检查 a/b 的区分。original 的唯一 festivals 节点 unresolved，最终仍选 a。

**确认**：这不是候选检索没召回负面偏好，而是实际读取后按错误的“节庆名称”任务标准排除了它。**解释**：局部抽取目标和偏好回应目标错配，并伴随把另一次 local festival 绑定到 “during my trip” 的事件范围推断。不是说更晚证据必然无效，而是其原文没有像 s20 那样明确绑定该次旅途。

### A4. 财经术语：认证一般资源类别，输出具体书名/网站选项

- `unit_id`: `c0d8eb9c-0a8a-47a0-a2bc-2f6e5724d33a`；`suggest_new_ideas`；gold/original=`a`，fusion=`b`；`certified_symbolic`。
- a 提供能解释 depreciation/capital gains 的入门指南；b 推荐一本具名书、《Khan Academy》与 Investopedia。
- `initial_program` 只有 resources 集合，`semantic_answer`/`certificate.output` 列出 podcasts、videos、beginner-friendly articles/guides、webinars、books 等类别，还包含 premium financial analysis service、cryptocurrency certification 等用户提过的项目。
- `E[283]` joint_read/call 2 共有 128 段，s32/d4（message 17）准确写用户被 depreciation/capital gains 等术语困扰，s33 延续这个障碍；s38 是 assistant 建议 beginner-friendly guides/video tutorials。s9、s20、s82 也标为 assistant 建议。
- `O[283].slots[0].unresolved` 明确承认“没有具体资源名称，assistant 只提供一般类别”。仍给 `final_prediction=b`，并在 observation 中把多类资源统称为能简化术语的 beginner-friendly resources。
- `E[436]` audit/call 3 复核类别值，`final_prediction=null`。original 的 resources 节点 unresolved，但独立 Reader 选 a。

**确认**：已读到与 gold 选项直接对应的术语障碍；证书只覆盖资源类别，不覆盖 b 的具体书名/网站，更不覆盖 b 优于 a。**解释**：一般资源推导/选项映射替代了针对该用户困难的回应。这里“提出新资源”本来就是任务的一部分，不能仅以书名不在记忆里就判为禁止生成；问题是这个新推荐为何优于有明确个人依据的选项，没有被认证或审计。assistant 建议被标注和引用不等于发生说话人解析 bug，也不能自动当作用户偏好。

### 认证/终端设计的共同边界

上述四题 call 2 都有 `public_options`，所以不能称融合版“完全看不到选项”；真正 option-blind 的是上游计划。四题 `supported_parents={}` 是单变量计划的正常结果，不能称父依赖在传输中丢失。

源码 `dagbt/joint_reading.py:226` 附近只在 semantic/terminal output 时附加公开选项；`AUDIT_INSTRUCTION` 明确写 “This is paid semantic verification, not output selection.” `dagbt/residual_control.py:366` 附近会在已获得同步 semantic answer + label 时检查值是否等于证书输出、字母可解析，然后保留该 label，不再运行一个独立 Reader。证书本身也写 `conditional_on="validated semantic interpretation; not proof that all counterevidence was retrieved"`。

因此**本次确认的是认证对象与评测对象的覆盖落差**，而不是形式化证明器算错了：正确证明 `var(project)=coffee table` 并不蕴含“a 是四个回应里最佳选项”。也不能从 `certified_symbolic` 推导“该选择题已被形式证明正确”。

## B. semantic 模式：偏好变化被压缩，或建议跨出已绑定证据

### B1. 学习方法：把历史“不喜欢卡片”压成 now，忽略已读到的重新喜欢

- `unit_id`: `f8edd318-d6b7-4943-a60c-c02e54f203d3`；`suggest_new_ideas`；gold/original=`d`（flashcards + spaced repetition），fusion=`c`（Pomodoro）；`semantic_assessment`。
- `initial_program` 有 user_study_profile(past) → recommendations(present)。`E[277]` joint_read/call 2 实际读取 125 段。
- s41–s43/d5（messages 54–55）说 flashcards 太简单；s62–s63/d7（76–77）说缺少深度。但 s3–s5/d1（209）明确说重新以创意方式融入 flashcards，enjoyable、effective for retention，并同时使用数字和实体卡片。s13–s14/d2（57–58）也明确说下载了 flashcards + spaced repetition app 且更有效。
- `O[277]` 虽引用上述各段，却把 profile 压为 “They find flashcards too simplistic now and prefer more complex methods ...”。记录保留了“用过 flashcards”，没有保留其重新转为正面的相对顺序。
- `E[516]` semantic_compose/call 3 及 `E[550]` call 4 都选 c；recommendations 的理由引用 s78/s80/s84/s85（早期 13–18 的时间管理材料），并以偏好更复杂方法为支撑。`E[805]`、`E[823]` audit 均 supported。

**确认**：正确方向的材料在实际输入和引用名单内；模型生成的 profile 仍把旧负面态度描述为 now。**解释**：时间演化压缩失真污染了后续建议，是较明确的阅读/状态归纳问题。message index 表示观察顺序，不是日历日期；这里仅比较同一对话中明确的态度变化先后，不臆造现实日期。

### B2. 本地生态：已找到 hiking club，合成输出却推荐未被证据具体支持的 cleanup

- `unit_id`: `c0c4fb2f-d06d-44f1-8d68-66153f057509`；`suggest_new_ideas`；gold/original=`c`（hiking club），fusion=`a`（environmental cleanup）；`semantic_assessment`。
- 计划 user_prefs(past)、local_activities(present) → recommendation(present)。`E[237]` joint_read/call 2 读到 s3/s4（message 64，local hiking group）、s11/s12（81，hiking club，enjoyment/camaraderie）、s29–s31（guided trail hike）。`E[469]` call 3 的 local_activities 明确只绑定 hiking group、hiking club、guided hike；其 unresolved 说没找到其他同时满足 community+nature 的 local ecosystem 活动。
- `E[674]` semantic_compose/call 4 和 `E[702]` call 5 却输出 a；理由把 hiking/group 偏好、NGO 志愿经历（s72–s74，message 13）、迷路经历（s38–s40，33）和受伤后转向城市活动（s56/s57，96）合成为 cleanup 是 structured guided format 且符合 available local activities。最后 `E[923]` audit supported。

**确认**：不是没有找到 hiking club；它已成为有来源绑定的 local_activities。cleanup 的“本地可用/有引导”属性不是这组来源明确建立的事实。**解释**：终端推导从个人经历泛化到合理但较弱的新建议，并把推导判断写成 supported。**限制**：较晚 injury 材料确实可以让避免 rigorous hiking 显得合理，因此不能把这个选项错简单称为完全无依据或唯一正确偏好被无视；这是严格 benchmark label 下的错误，也是值得单独复核的样例歧义。

## C. 正向案例：机制不是必然损害，也不能把选对等同完整推理被证实

### C1. 旧钱币：语义值仍很窄，但成功保留负面偏好

- `unit_id`: `0034a537-925f-448b-b275-eae07f3d9ae5`；`recall_user_shared_facts`；original=`a` 泛化谈古币，gold/fusion=`d` 回忆不喜欢收藏；`semantic_assessment`。
- 计划只问 old_items，`semantic_answer="antique coins"`。`E[251]` semantic_compose/call 2 引用 s22–s28；s22 明确有用户 “frustrated sorting through a collection of antique coins that held no value”；s27/s28 延续不值得花时间、无满足感。
- 同一输出选 d；`E[290]` audit supported。

**确认**：窄变量本身不必然丢失个性化判断；semantic 终端可从真实来源同时输出正确的偏好回应。**限制**：部分来源 chunk 含未显式标注说话人的长段，不能仅从系统 source_role 标为 user 就断言每一句都是原始用户表达；本例结论依赖带 `User:` 的明确负面句。

### C2. 独立书店：成功选择完整转变叙述，但证据引用仍有瑕疵

- `unit_id`: `7028667b-f2aa-4e22-a2e3-2bb97f3d9605`；`track_full_preference_evolution`；original=`a`，gold/fusion=`d`；`semantic_assessment`。
- d 正确描述 dislike → like → dislike again。`initial_program` 只有 preference(current)，`semantic_answer` 仅概括最新不喜欢过强社交义务。
- `E[241]` semantic_compose/call 2 的实际 107 段包含：s12–s15/d2（25–26）独立书店选择过多而焦虑；s24/s25/d3（49）被独特收藏/氛围吸引；当前 original_question 讲不再适合并希望更放松。于是它具备看到完整变化的材料，最终选择 d。
- **不能把正确字母包装成无瑕疵的引用链**：`O[241]` 理由称 s1 是 original_question，但 `P[241].source_spans[id=s1]` 实际是 “Conversation message indices 78–79 ...” 的标题，`source_role=unknown`。其最终 preference 仍可从 payload.original_question 读到，但这条 source_alias 解释本身错误。`E[268]` audit supported。

**确认**：当前语义值窄不阻止终端选择包含历史演化的正确回应；同时，选对不证明引用严格无误。这个案例不能用来宣称整条历史被 certificate 正式验证，因为它属于 semantic_assessment。

### C3. 电影社区：有用的多来源 synthesis，并在后续 terminal 调用更正选项

- `unit_id`: `aa359f37-2eb6-4604-a3e5-07a066de210d`；`suggest_new_ideas`；original=`d`（去电影节），gold/fusion=`c`（扩展已有博客）；`semantic_assessment`。
- `initial_program` 有 user_history(past)、suggestions(general,present) → recommendation(user,present)。`E[247]` joint_read/call 2 和 `E[487]` call 3 读到 s51/s52/d6（message 64）已开电影博客并连接同好，s25/s26 描述发布影评得到正向反馈，同时见到电影节、电影俱乐部、论坛等多种经历。
- `E[700]` semantic_compose/call 4 的 semantic_answer 同时包含扩展博客、参加活动、志愿服务和 podcast，先选 a。`E[748]` call 5 保留同一长 semantic_answer，但改选 c；后续 `E[975]`、`E[1009]` audit supported。

**确认**：最终融合结果在此优于 original，且有原文支撑“在既有博客基础上拓展”的个性化路径。**限制**：不能把两次终端调用之间的字母改变直接归因于 BT 找到了新的支撑：call 5 的来源集合、调用情境发生变化，但没有反事实实验；这个例子还说明同一长 semantic_answer 可兼容多个选项，选项判别是独立的质量环节。

### C4. 艺术合作：额外的窄语义正例

- `unit_id`: `221c8369-8ac4-447e-a13c-6088536f9abf`；`recalling_the_reasons_behind_previous_updates`；original=`a`，gold/fusion=`d`；`semantic_assessment`。
- `E[229]` semantic_compose/call 2 仅绑定 `partnership="partnership with local artists to create unique book-themed merchandise for upcoming events"`，引用 s3（message 162），却正确选到强调合作重燃兴趣的 d。`E[248]` audit/call 3 只有 4 段。

**确认**：再次证明窄 semantic_answer 不必然选错。**限制**：本次核对的实际读取材料没有明确找到 d 中“之前退一步管理压力”的独立历史支撑，不把此正例夸大成完整跨时原因链被证实。

## 下一步实验假设（未执行、未改代码）

1. 优先检验 PersonaMem 的最终任务契约：输出应当约束“最佳个性化回应”，不能仅约束当前事件/对象的投影。用相同证据比较原终端和具有明确偏好判别要求的终端，可区分计划/终端目标问题与检索问题。
2. 另评估终端选择与证书是否一致：单变量事实可以保留认证，但不能将该认证标识当作已认证选项；应独立记录事实支持与选择质量。A1–A4 是具体待复核样例。
3. 对 preference profile 保留带观察顺序的正/负转变及当前结论依据；B1 提供无需额外检索即可验证的回归案例。
4. 新建议要区分“用户历史事实”“可推导偏好”“新增推荐及假设”，避免把推荐的可用性、具体属性等新增内容都标成原文支持。B2 是候选检查用例，但必须保留 injury 带来的歧义。

这些是从当前日志提出的可检验机制，不构成“BT 必然无效/有效”或“加大检索就能修复”的结论。本次仅完成离线读日志与证据整理。
