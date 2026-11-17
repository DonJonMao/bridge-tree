# R18 第 13 题：真实容量与必要来源范围独立审查

对象：`0d2259ae-1432-46a9-81e7-e3b3e3be5cc9`，冻结源码 `800c51763ea3a2bfcad459b4413d41c6432db52e`，R18 residual v2。仅使用保存的请求、状态、事件和源码；没有重新分词、调用模型或网络、读取 gold/评分、修改源码或运行。本文不导出原文、题目内容或选项。4/5/6 的冻结观测反馈契约由另一路审查；这里只使用这些阶段已留下的来源集合、未决状态和计数。

## 结论与可执行判断

1. **记录里的容量超限是真实的。** event238 的最小已检查下一窗口、以及 7/8/9/10 后的下游 compose 预检，都超过继承的 16384 完整请求容量。7/8/9/10 本身的实际模型请求则都能容纳；不能把它们称为 HTTP 上下文失败。
2. **未发现无关节点来源污染、整库强制展开或重复原文计数。** 终端 75 段闭包可以精确分解为 user_profile 的已有支持、两项未决义务及其失败批次，加上新 draft 的真实引用。集合按来源身份去重。但 75 段只是当前协议要求保留的保守范围，不能称为语义上最小必要的 75 段。
3. **本例 citation_capacity 的修复目标不准确。** 7/8/9 新 draft 的 13→12→12 个引用全被另一变量 user_profile 的 75-source 义务覆盖。要求它继续缩引用无法减小来源闭包；实测只少了 8 input token，仍超 1564。容量错误本身并非虚构，但将阻塞归因于该新 draft 的引用太宽、继续付费让它缩引用，不是有效的本地修复方向。
4. **建议单列 `downstream_blocked_by_existing_obligations`，不要把这个确定的跨变量容量阻塞继续作为同一 draft 的 citation repair。** 记录阻塞 owner、稳定来源集合身份、版本/义务身份、实际 count 与预算；保留该 draft、全部原文和未决/失败记录，交回控制器处理真正阻塞项。在现有规则下也可先保守暂存为 capacity-blocked 而不接纳；分类改变不能自动变成事实绑定或成功发布。
5. **“尚不可执行的 terminal 先否决另一独立支持”有现有工程规则依据，但不是原理论强制条件。** `_handoff_failures` 明确在 query=None 时仍检查当前 mandatory footprint；checklist 的 capacity_handoff 也写明整合前保护。原设计要求合法事实/反证一起整合、实际调用容量检查及发布前必要来源审计，没有要求所有未来下游能容纳才允许保存一个独立有效观察。可另行审议把事实有效性/暂存与下游可执行性分开，待父事实及义务状态稳定后再检查真正执行闭包；这属于控制策略修改，需要新测试和新运行，不能套用到 R18 或放宽当前 strict gate。

## 75 段底座的来源

初始 DAG 的 user_profile、past_experiences、recent_interests 都是无父输入的独立 retrieval；response compose 明确依赖三者。历史来源义务属于 user_profile，因此对 response 不是无关节点，但对正在独立读取的 past_experiences 并非它自己的上游来源。

| 保存对象 | 来源段数 | 与 75 段底座关系 |
| --- | ---: | --- |
| user_profile 当前 support route | 7 | 子集 |
| joint_read/3 后的未决义务 | 49 | 子集 |
| joint_read/4 后保留的另一未决义务 | 75 | 完全相同 |
| user_profile 失败批次保留范围 | 75 | 完全相同 |
| 整合事实里的 counter route | 0 | 无额外 counter 段 |

两项未决义务各有 2 条描述，描述集合完全相同；49 段集合严格包含于 75 段集合。`_update_evidence_obligations` 在 slot.unresolved 非空、没有每条问题的来源映射时，采用整个实际 visible wire 作为来源，所以第一次保留 49，后一次保留 75。该扩大有明确协议来源，并非纯未发送 discovery 被误标必要。两条 obligation 元数据都保留，但 `_payload` 对原文使用集合并集，不会发送 49+75=124 段原文。

失败批次包含 1 个失败 slot、2 条未决描述和 1 个已验证的 7-source 观察；whole-value-review 列表为空。其 75 段来源与较大 obligation 完全相同。当前证据不足以证明可安全删去任何未决描述或其原文；也不能用“保守契约有依据”反过来证明每段原文都是最小语义前提。

## event238：局部下一窗口无法入场

失败后剩余 31 个邻接候选组。冻结 `_fitting_prefix` 的顺序为先最大组，再二分，若都不适配则检查其余未试 prefix；保存记录中有 62 次计数记录，对应 31 对 initial/repair envelope 计数，不包含新生成。

最小 prefix1 的 3 个邻接 alias 中，1 段已在 75 段底座，只有 2 段新增，因此实际来源是 **77 段、9 个文档**；完整剩余 prefix 的 106 段不是被强制作为最小输入。按冻结前缀搜索顺序及已保存组可对上 event184/185：12678/12766 input tokens。门槛采用两者较大值，再加 4096 输出预留、256 输入余量及 8 安全余量：

`12766 + 4096 + 256 + 8 = 17126 > 16384`，超 **742**。

因此 event238 是保留当前义务/failed draft 后连最小新窗口也放不下的预检失败；不是 ANN/LLM 总调用额度耗尽，也不是一次模型生成失败。这里没有对删除义务后的反事实重新计数，不声称放松哪项就能完成。

## 7→8→9→10：实际读取成功，未来 compose 容量拒绝

下表预检总量仍为 `max(initial, repair-envelope input) + 4096 + 256 + 8`。

| 调用 | 实际可见来源 | 新 support 引用 | 引用在底座外 | 下游闭包 | 下游 initial/repair input | 下游总量 | 超额 |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| joint_read/7 | 49 | 13 | 0 | 75 | 13415 / 13596 | 17956 | 1572 |
| repair/8 | 49 | 12 | 0 | 75 | 13407 / 13588 | 17948 | 1564 |
| repair/9 | 49 | 12 | 0 | 75 | 13407 / 13588 | 17948 | 1564 |
| durable repair/10 | 102 | 26 | 12 | 87 | 14876 / 15057 | 19417 | 3033 |

7/8/9 的实际 input 分别 7374/7740/7739，加既定预留后均适配。各返回一个 support、无 unresolved、parent_versions 为空，拒绝点是 `_handoff_failures` 的未来 response 请求。缩短自身引用不能移除 user_profile 的义务或失败批次；8/9 预检 request hash 也完全相同。若要确认缩短完整 typed summary 等其他反事实能节省多少，必须另外验证，不能从“来源集合不变”推出所有序列化 token 恒定。

10 的实际请求保留了上一失败的完整 49 段，再加入 53 个新可见来源，共 102 段；其实际 input=11911，总量=16271，仅余 113。返回 draft 引用 26 段，其中 12 段在 user_profile 底座之外，所以下游恰为 75∪26=87；没有把全部 102 段 recovery window 都灌入假想终端。被声明解决的旧 failed batch 在 prospective handoff 中排除；随后 handoff 再失败，因此真实状态没有提前释放它，失败恢复记录保留了新实际范围。

作为范围交叉核对，后续 11 的 draft 引用 24 段，其中 8 段在底座外，预检事件显示 83 段，亦为精确并集。当前尚未绑定的其他兄弟并没有无条件作为所有来源灌入每次 probe；源范围是当次已知/假想有效父项的闭包，不能称为未来最终输入的完整固定下界。

## 事前保护规则与本例可修改的边界

现实现有明确意图：`joint_reading.py:2007` 的 handoff 文档要求新 proof 的 mandatory next use 能适配；`:2072` 附近 query=None 分支仍检查当前 footprint，避免新支持无法转交或审计。相关容量回归 `tests/test_v4_joint_reading.py:531` 的正例是新 draft 自己引用过宽，改为充分窄引用后下游能适配；它不等价于本例由另一变量未决义务支配的情形。

原设计 `docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md` §6.2/6.3/7.3 区分有效事实整合、实际调用容量与发布前审计。`RESIDUAL_FRONTIER_POLICY_V2.md` 继续要求真正 mandatory compose/audit 提供完整必要闭包，但没有要求一个尚不可执行的未来 terminal 的当前临时义务范围，必须先成为独立历史证据的有效性条件。

精确地说，`grounded()` 并非看到任意 pending 就返回 None：它仍可使用已绑定值。本例在 hypothetical past_experiences 加入后还缺 recent_interests，而 user_profile 的未决义务也仍存在；尚没有可执行的完整终端请求/最终支持。当前 handoff 保护采用这一中间状态预测未来。不能从中间时刻超限推出义务被合法解决后仍必然超限。

可执行的下一轮设计议题是：

- 当局部 schema/来源/范围/父版本合法且唯一拒绝点来自别的 owner 的保留闭包时，记录跨变量下游阻塞，保留独立观察和所有原文，不再次要求同一 draft 缩减已被底座覆盖的引用。
- 阻塞解除只能来自对应 owner 的实际有界复核、新来源或合法父版本变化；不能清空义务、把已发送原文降成 discovery、增加预算，或把日志变化算成进展。
- 如进一步允许独立证据入事实状态，必须显式分离“有效观察已保存”和“其下游当前可执行/已审计/可发布”，并重新验证整个响应的反证、失败义务、版本与源身份；不能直接将 R18 的 rejected draft 回填成功。
- 对新 draft 确实增加必要来源、冲突需要复核、或者真实终端/审计本身已经可执行而超限的情况，仍保留原事前容量保护或真实调用拒绝。不能泛化为取消所有 handoff 检查。

这里给出的诊断分类和设计判断有范围限制：确认的是保存轨迹中的支配关系与当前规则，未进行新模型反事实、修复后验证或正确率评测。

## 证据身份

保存目录：`outputs/v4_validation_r18/personamem/dagbt_residual_memory_v2/attempts/0c8614cf717159045ebc63ab7fa331fafab193ce3462161de262ce7fd70230ab/attempt-001`。

### 文件 SHA256

- `fusion_snapshot.json`：`4ac387a5593a7d8505302a9a7e21862746f15c9863fc2ae5c7048c7b2b764f63`
- `fusion_events.jsonl`：`5e3dc84ab0c81f34a74d58621cf0faec873e4c9429989261be87cc042de400d5`
- `tokenization_events.jsonl`：`7fcb95277d3abc5339c6b75fad12dd85e3bd65067935e3b96395926e13fae53a`
- `dagbt/joint_reading.py`：`f5568ea4ad837dc32f8ebfb94afae4516efb5bb20f83dccdb2e0904eb94710eb`
- `dagbt/residual_control.py`：`b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211`
- `dagbt/fact_state.py`：`e55b9535d2c55ea87be3de59f4c5e1123e0eac06dc7e672827ba466e9c94c91e`

### 稳定来源集合 SHA256

集合哈希使用排序后的稳定 source_id 列表之紧凑 JSON（separators 为逗号/冒号）。

- user_profile obligation 49 段：`176c64b5a370a38a20e53b82c9ca7254197f4c9eea7de5c589301dfe7e257482`
- user_profile obligation 75 段：`d9abafb2b8ae370dd8e62c306fa28ee8b284eca6c83e9610837be27480ba840a`
- call 7 draft 引用 13 段：`31ec25755c88a677b353dfd6059795ae3d2d580d0b037530a7fae54f800daddf`；假想闭包 75 段：`d9abafb2b8ae370dd8e62c306fa28ee8b284eca6c83e9610837be27480ba840a`
- call 8 draft 引用 12 段：`a4b2e28e60a550edcbccb8dce29ffba0c50b24087cd8b3ae05fb9d0c10fe1d15`；假想闭包 75 段：`d9abafb2b8ae370dd8e62c306fa28ee8b284eca6c83e9610837be27480ba840a`
- call 9 draft 引用 12 段：`a4b2e28e60a550edcbccb8dce29ffba0c50b24087cd8b3ae05fb9d0c10fe1d15`；假想闭包 75 段：`d9abafb2b8ae370dd8e62c306fa28ee8b284eca6c83e9610837be27480ba840a`
- call 10 draft 引用 26 段：`b35fe9fb04be750e246ae92df4faaa313b95c8530ddf1dd24ea34b5810a4514b`；假想闭包 87 段：`44c0d829ed3a2e674188f5e2c9edbfd38136d27791ed956650eaf9aaa3a9b5a4`

### 已发送请求身份及文件 SHA256

- `joint_read/3` request/response_ref：`59ca42ba5eb04387111b0a6955d440651e156946b7e3ce80c075ae9db4ae2822`；文件 SHA256：`bc205c38ce3c73574166b0711fb19998ab31c000379c4230f405b81edf3824c6`。
- `joint_read/4` request/response_ref：`1cede76c87440eb66c0045963801f9e8fae51fb5da7eb1ccc97edac5bcc79f50`；文件 SHA256：`2252765dddaf78124d92934a9bd49e1c678adcf080099b6998d2e81c6d54b0b1`。
- `joint_read_repair/5` request/response_ref：`3ef82086d52e445e7984f55d85d88fc7025c9d18644a04d909df5032db46e8e8`；文件 SHA256：`1e9f8207a0e643228f7389114ec183c4ad9f3dc243f0dedb3af159cd0b419f8a`。
- `joint_read_repair/6` request/response_ref：`5b06d6bcdf8b4ac45faccdc958c9bbc1f4410381ea452abd94654bf167ebd3ae`；文件 SHA256：`65d1f7ad3291bb5e5365a721d5bfcdd8aa5831b67b42083644af1120d4069764`。
- `joint_read/7` request/response_ref：`0aae470efcd354fc3edd746a453ce1c083df05ee1b82fc268a4fbbe5e792afe7`；文件 SHA256：`90c593dc22e675f6e624dec933851f2345daef234dbcc8b2bb5e301d4bbbcf2f`。
- `joint_read_repair/8` request/response_ref：`5dbce488fb2ba5a72ae836e7ff44bf312467eb6e19ef19754cf06e7ef66d22ce`；文件 SHA256：`94709e8069a314e1bb42216073406c30845ea64988aff511a0bf59c0eb1ad53e`。
- `joint_read_repair/9` request/response_ref：`378de9c6a9449270b5947fdf8ae8b8ba973cba5844830e01369d9053c2925dc4`；文件 SHA256：`11c1a198bfc94a6d719f0e43a2fb9fdf91005f4472d314ced80d24e4cd80b342`。
- `joint_read_repair/10` request/response_ref：`eb73762fb13f17a7d4056105c43782020ed8d1dfdf620bc6be24602e15880f68`；文件 SHA256：`393b4b76082b5fae5a07a146d89e4f44976611dad11dc73c11e36c43b292efef`。

### 保存的关键预检 request SHA256

- event 184，count=12678：`1ffd5843886952c7b946f049db01b7ba85c3e8542e296481971dc926afd2b72c`。
- event 185，count=12766：`fe9e336d3e041d10f8de53bf5e4f768f1d7d2e97b0304abbb505a57d09258970`。
- event 298，count=13415：`917ba9943d58293839f8698da6ee9bf2e5b3a748a5a06709f788c210958c3c6d`。
- event 299，count=13596：`9e6e0b68e716189aac1a0386a1c0c4ee5802e12514e9bb35aab78f01665ef5bb`。
- event 312，count=13407：`0acf8b9a013c02996d597b241e6ac0aa02f17bfb1769ed1adba59145e6fb3127`。
- event 313，count=13588：`8acce74b04207bc6446465b920249e1aa71d7746b141f032ecf28dfbddf14548`。
- event 326，count=13407：`0acf8b9a013c02996d597b241e6ac0aa02f17bfb1769ed1adba59145e6fb3127`。
- event 327，count=13588：`8acce74b04207bc6446465b920249e1aa71d7746b141f032ecf28dfbddf14548`。
- event 354，count=14876：`2ab01ee2e2047d24bed7724a49c160019db37ffaa8d37b8e0a83913104e860c2`。
- event 355，count=15057：`4d0d0577a77408c6a779283e866a675b2f5f56544a42445e12a8793b609e83e3`。

所有上述预检事件均记 token_count_is_estimate=false；这里只复用保存计数，没有再次请求分词服务。

记录时间：2026-10-13T21:21:18.055945+00:00
