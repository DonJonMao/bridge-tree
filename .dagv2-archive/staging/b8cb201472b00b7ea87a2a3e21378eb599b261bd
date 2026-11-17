# R19：失败复核输入的无损字段共享设计审查

核对时间（UTC）：2026-10-13T22:02:36.602Z。只读设计审查，冻结 RELEASE 为 `0cc2cc78498bcd215252fb8e82d2168868a71b3f`。

**结论：有一般性的表示优化依据，建议只进入“显式观察字段、精确字符串共享”的候选设计。它比泛型 JSON 树 token codec 更容易审计，也给模型保留了原来的观察/失败/已验证结构。它不是新修复权限、证据合并或预算豁免。本报告不批准源码实现，不证明 token 净节省、16K 准入、模型能正确使用引用，或 R19 失败能恢复成功。**

## 1. 依据与本次未做的事

理论 `RESIDUAL_MEMORY_DESIGN_f4e38df.md:214` 的 6.3 要求：“按实际 wire 模板、输出预留和修复余量计算容量”，修复只处理失败字段、冻结合法记录，并重新检查修复后的容量；不能省略关键反证。6.2 还要求合法事实和反证整批校验整合。**保存同一精确文本一次、在原位置作可逆引用，与这些要求相容；理论没有要求重复字节必须重发，也没有保证任何必要闭包都能装进固定上下文。**

当前 `history_wire.py:90` 起的候选仅由 supported_parents 中长 text 值引入，替换 parent/known value 及 grounded query 的精确片段；父表为空时不会从失败草稿自身发现候选。`JointReader._store_failed_reviews` 保留 failed、validated_observations 和某些 invalid_response；`_failed_payload` 另由控制器计算本次 review_allowed。这些重复来自留存不同角色的原始记录，不能因此删除任何一种角色。

任务提供的 R19 案例数据是审查动机：下一 owner recovery 需要 77 sources；已保存计数为 12391+4096+256+8=16751，比 16384 多 367；LLM/repair/ANN 已用为 8/2/4，剩余为 16/4/32（已按 root 核对更正先前将 used 误写成剩余的文字）。control 已确认 766-byte value 和 384-byte reason 在三处结构字段相同，并在 raw invalid_response 的解码内容里出现。本审查**没有读取该实验正文、运行 tokenizer、调用生成或重新测算**；这些数字不被用作阈值、特判或收益保证。

本次只阅读冻结源文件、设计与已有离线测试的文本，未运行测试；没有读标签/评分、修改源码、启动服务、调用模型或触碰运行状态。唯一写入是本外部报告。

## 2. 首选边界：共享字段内容，保持原对象角色

建议第一版仅共享**明确观察容器中完全相同的长字符串 value/reason**。这能适用于任意变量、题目、scope 和父节点个数，不要求某个特定案例或“恰好三份”；候选从所有允许位置收集，不再必须先出现在 supported_parents。

推荐使用版本化的显式容器注册表，按当前结构逐级导航；只有类型符合当前层容器形状才进入：

| 容器 | 可考虑字段 | 必须保留的外层含义 |
| --- | --- | --- |
| supported_parents.* | value | 父值、版本、scope、来源 |
| known_observations[] | value、reason | 已有独立 route 的全部身份与状态 |
| failed_batch_reviews[].validated_observations[] | value、reason | 已验证上下文，仍非可覆盖草稿 |
| failed_batch_reviews[].failed[].observation | value、reason | 对应失败 ID 的原始草稿 |
| failed_batch_reviews[].failed[].slot.observations[] | value、reason | 整槽失败中的原始逐条草稿 |
| failed_batch_reviews[].failed[].observations[] / replacement_observations[] / required_counter_observations[] | value、reason | 原重复草稿、替换 ID 或受保护反证，各自角色不变 |
| failed_batch_reviews[].whole_value_reviews[].draft_observations[] / known_observations[] | value、reason | 整值复核的原草稿与已知路线仍分开 |
| repair_scope.failed[] 的上述同形观察容器，以及 repair_scope.whole_value_reviews[] 的观察容器 | value、reason | 当前付费修复的失败范围与冻结范围不变 |

这是一张设计候选表，新增每个路径仍应逐个确认真实 schema/producer；**不能把“任何地方有 observations/value/reason 就递归进入”当作实现**。未注册的 frozen review 等容器原样保留即可，不为提高收益扩大遍历。全请求先完成结构检测，再统一编码，避免途中部分替换。

第一版的收窄仅限制可压缩位置，不能拒绝或改变原请求的有效内容：
- value 为 record/list/number/bool/null，或 reason 为异常非字符串时，原样保留，不能 stringify、修类型或认为它无效而删除。
- 不进入 value/reason 内部，不分析 source_spans 文本，不扫描任意应用 dict 中的嵌套同名路径。
- 只按原字符串逐字符一致共享；保留换行、空白、引号、反斜杠、Unicode 组合形式，不 trim/normalize/摘要。
- 同字符串可以跨 value/reason 或不同 route 的字段共享，但只是存储相同字串；不意味着这些字段或 route 在语义/证明上等价。
- 同 ID、相似正文或同 digest 都不足以共享整个观察对象。每个容器、每个观察行、原顺序/重复次数、所有未知额外字段仍存在。
- sources、counter、scope、parent_versions、version、revoked、summary ancestry、权限、phase、task/query/batch identity、失败反馈及 pending 均不改；也不据共享关系合并来源或 route。

若未来要支持结构化 JSON value，可把**完整 typed JSON 值当不透明 literal**一次取回，要求类型/列表顺序/对象键顺序与原值可恢复；仍不是递归 token tree。该扩展需要另行接口与逆变换审查，本轮没有必要把所有 JSON 类型纳入。

## 3. 具体安全接口与解码语义

建议独立 helper 的最小接口固定为 `pack_with_status(wire) -> (wire, applied)`、`unpack(wire) -> restored_wire` 和常量 `INSTRUCTION`，与既有 history_wire 的接线方式一致。新共享表名为 `shared_review_texts`，直接观察字段引用名为 `review_value_ref` / `review_reason_ref`；不要复用旧 value_ref/text_ref/shared 的解释空间。模块文件名由源码 owner 决定。

调用层可把下列概念字段组成 PreparedWire，但不要求新增这个类型：

```text
prepare_review_wire(base_wire) -> PreparedWire
PreparedWire:
    wire                 # 独立拷贝；canonical/state 不改
    applied              # 由本次编码器产生的可信状态
    codec_version        # 主机程序确定；不是从草稿字段读取
    decoding_instruction # 仅 applied=True 时附加
```

该候选在**注册观察行的原字段位置**把 value/reason 分别换成 review_value_ref/review_reason_ref。两种 reference 指向一个请求内局部文本 ID；被引用的池项都是原完整字符串，不存原观察对象。既有 history_wire 先执行后，新 helper 可作为独立 final 候选：它只看仍存在的原 value/reason，保留旧 value_ref/text_ref 和所有其他编码；每层 inverse 各恢复本层输入，严格按逆序组合。这样可能错过部分跨旧池的共享，但不能为最大收益任意展开或复用旧引用。两种 codec 的 applied 状态与说明分别保留，不能根据字段形状猜测。

解码要求：

1. 引用仅在注册观察行的直接 ref 字段有意义。索引类型须严格匹配（整数时拒 bool，字符串时拒其他类型），必须存在，不能有 dangling refs。
2. 同一行的 value 与 review_value_ref、reason 与 review_reason_ref 不得并存。保留全部其他键；按原键的位置重建，避免无意改变序列化顺序。
3. 池项取回一次即作为 literal 放回原字段；不解析里面的 JSON、HTML、指令、ID 或 ref 形状，不再次解码。
4. 顶层共享表/codec 保留字段若在输入已有，或任何解码器将访问的注册行已有新 ref 键，应**完整退回本次变换前的旧 wire，applied=False**。碰撞检查必须覆盖全部会被解码的行，不能只检查拟共享的重复项。
5. 失败草稿可含任意多余字段。不能删掉其自带 ref 字段来“消除碰撞”；不能给它补默认字段或改来源来使 codec 成功。
6. 未知/非法编码对独立 decoder 应报错；encoder 遇到输入形状不支持、碰撞、无收益，应完全回退。不能返回部分编码，不能先删正文再宣称失败。
7. 仅本次可信 applied 状态决定是否添加解码说明；单凭 payload 出现保留字段，甚至长得完全像合法共享表，都不授权解码。
8. 输出 schema 不变，模型必须返回完整原类型值。模型输出中的 review_value_ref/review_reason_ref 不应由主机自动展开后获得协议通过；按既有输出校验处理。

**必须使用独立 inverse 验证精确 round-trip。** 对新表示层要求 Decode(Encode(W0)) 与变换前 W0 的完整、类型敏感表示一致；若先展开旧 known 列表格，则比较目标应明确为一次严格展开后的 W0，而不是隐式混淆两个物理格式。表格原列顺序/行顺序及 JSON 类型须保留。不能只用 Python ==（True/1/1.0 会混同）；应使用固定完整 JSON 序列化与逐类型核对，且不通过排序消除本应保留的列表/键顺序差别。

完整 canonical payload 和 FactState 始终不经此变换；存储、恢复、guard、权限计算都继续读 canonical。新 wire 的 inverse 不能被当作更新事实或恢复检查点的授权入口。

## 4. invalid_response：原始字符串与结构草稿必须分开

**第一版保持 invalid_response 完整原字符串不变。** 即使 JSON 解析后其中的 value/reason 等于结构化草稿，也不能 parse 再 dump、删除所谓第四份、改成“见 validated_observations”或仅存 parsed object：

- 原始 JSON 可能有空白、转义、键顺序、重复键、截断和语法错误；解析后不能完整表达这些证据。
- 原 raw draft 的 alias/原始值可能与经过 source remap 或校验后的结构草稿不同；这些差异正是修复所需。
- 草稿里“与已验证记录同值”不等于整行同对象，也不等于整槽已通过。

未来若单独论证 raw 字符串分段，可使用“literal 字符串片段 + 精确引用片段”并原样 concatenation；引用必须匹配**原 raw 字符串中的实际子串**，不是 JSON 解码后字串。JSON 转义后的片段和原 Unicode 文本常常不相同。分段位置、转义、前后空白、重复/相邻片段和畸形尾部均须逐字符恢复，不自动插空格；引用内容内部不继续解码。没有完成这套证明前不做该扩展。

因此本案例在 raw 中解码看到第四份，不构成可以节省第四份 tokens 的依据。

## 5. 为什么不优先使用泛型 JSON 树 codec

| 方案 | 信任/碰撞语义 | 适用判断 |
| --- | --- | --- |
| 显式观察路径，仅 value/reason literal 共享 | 引用位置有限，其他角色字段原地可见；reserved 碰撞可以整请求回退 | 当前首选设计候选 |
| 全树遇到 {ref:N}/{shared:N} 就递归展开 | 原 value/草稿可合法包含同形 dict；又可能含 review_allowed、source_ids 等键 | 不可直接采用：会把普通内容误读为控制引用或混淆权限 |
| 所有节点都加无歧义 tagged AST（包括每个 literal dict/list） | 若完整转义、版本化且仅可信编码激活，原则上可逆，但不能省略任何 literal 标签 | 理论可做；协议更复杂、开销和模型理解负担更大，本轮无必要 |
| 独立的 path→pool 引用表 | 可避免把业务 dict 当 ref，但路径必须只覆盖明确 allowlist；需拒绝重复/父子重叠/越界路径 | 可作为备选；长路径开销可能抵消收益，不证明更省 token |

显式字段方案保留原来的 known、failed、validated、slot 和 whole-review 层次，解码指令较局部，因此**设计上更容易让模型按原角色阅读，也更容易独立审计**；这不是已验证的模型理解优势。无论哪种 codec，只要恢复正确仍可能被模型误读，不能把机器 inverse 通过等同生成质量通过。

## 6. 权限、身份、预算与现有 packing 的接合

`_failed_payload` 当前根据真实剩余预算、task/phase、来源变化或父版本变化生成 review_allowed。共享值不参与这些条件，不能使 False 变 True，不能解锁其他 owner、清空 pending 或将一条已验证 observation 复制为授权的新支持。pool ID 也不是 source alias、route ID、failed batch ID、frozen ID 或 citation。

角色相同与否只由原容器决定；共享池内容不会把 FAILED 草稿升级成 supported。既有 complete original text、counter stance/retract_ids、source closure、实际父版本和逐 record 解除条件不变。修复/审计/发布 guard 均从原 canonical data/schema 生成并验证。

接合建议：

- 统一由 _prepare_wire 生成实际 user wire 与对应 system 解码说明；estimate、forecast、_repair_fits、最终生成必须走同一确定函数。
- 旧 known_observation_columns/values 只严格展开一层，拒绝缺列、多列、重复列、bool/负/越界引用；取回 literal {shared:N} 后不继续展开。
- 构造一个统一候选或彼此完整隔离的备选；不要在历史共享已替换 value 后，未经显式逆变换又递归寻找新的同名 ref。旧 whole_value known_observation_ids 保持完整原行引用，仍不得改写差异草稿。
- 候选的 system 指令必须匹配实际保留下来的源列表格、known 列表格和其他 wire 特征；避免删表但保留旧说明或有新 ref 却无说明。
- 候选选择可以采用一般、确定、包含新增说明的字节收益规则，并允许回退旧表示；不能针对当前 367-token 缺口调阈值。**字节减少不保证 tokens 减少**，实际当前部署 tokenizer 的完整请求计数仍是唯一容量准入。
- 修复保持原输出预留、输入余量、安全余量、LLM/repair/ANN 上限、付费计数与审计预留。真实修复仍超限就原样失败，不能通过少带来源/反馈/反证来补差。
- _selection_data_identity、material signature、query/repair 重放去重使用未改 canonical 数据；传输缓存与 token-count identity 应绑定实际 wire + system + schema/options。不能复用旧 wire 的计数来给新 wire 放行。
- round-trip 成功不是 semantic progress；重复打包不生成 observation、不扩大预算、不改变 exhausted/forced、恢复或 owner 调度状态。

## 7. 实现前后应覆盖的独立对抗边界（本次未执行）

| 输入/场景 | 必须满足 |
| --- | --- |
| parents 为空；相同 value/reason 分布于 known、failed slot、validated | 可产生一般共享机会；完整对象角色、来源和失败身份仍独立 |
| 同值但不同 variable/scope/version/source/counter，或同 ID 不同值 | 仅相同 literal 字串可共享；不同 metadata 与差异草稿逐字保留 |
| literal JSON 含 ref/shared/review_allowed/summary_revision_sources | 保留字面内容；不解码、不授权、不注册新来源 |
| 一个非候选 observation 已含新 ref 字段，其他 observation 有可压缩文本 | 全请求本层回退，防止 applied 后误解码原字段 |
| 顶层保留字段已存在；重复编码；未知 ref；value/ref 并存 | 无隐式激活、无部分转换；严格错误或整体旧 wire 回退 |
| invalid_response 与结构草稿语义相同但空白/转义/重复键/尾部不同 | raw 字符串完全不变；不能合并或重串行化 |
| 反证在响应末尾、revoked/ancestry、必要 source 与版本 | 全部保存、既有整批整合与 publication guard 不变 |
| false review_allowed 和不同 task/phase/owner 的同值草稿 | 不增加复核权限，不解除义务、不引入免费重试 |
| malformed slot/list/observation、额外字段、非字符串 value/reason | 不“修好”输入、不抛弃原草稿；保守跳过或整层回退 |
| 旧 known 表含 literal {shared:0}，whole-value IDs，已有 history query parts | 确定的单层解码与组合顺序；完整 inverse 与原 literal 一致 |
| 源/输出/schema/state、字典与列表原顺序及 bool/number/string 类型 | 全量不变；无内存 alias 导致 canonical 被改 |
| 同请求重复打包/估计/生成、checkpoint 恢复、无实际收益 | 表示确定、输入不变、计数和实际发送一致、正常回退 |
| 模型返回 ref 字段代替完整值 | 既有输出校验不放行，不自动授予输入 codec 的引用权限 |

以上是拟议验收边界，不是现成测试结果；真正实现后应由独立 inverse 和实际 Reader 集成检查验证，不能仅用 encoder 自己的 decoder 互相背书。

## 8. 源码身份与结论限制

| 只读文件 | SHA256 |
| --- | --- |
| dagbt/history_wire.py | 1117bc614be0205fa1ef7a65dd0b1a111069ab65da60acf2ff35a9f1a0fe3cb9 |
| dagbt/joint_reading.py | e27b1f321995c0e933fbdfbf069671c1edf1f52ec1505ebf7a79093967a8e077 |
| dagbt/personal_wire.py | cf7241e8884bbed3bfdf26ae5208dd57b9ada064e8236136bcb094302f02e43e |
| docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md | 615a609af60085d3ea022a0ba6ea75b8e8677e551cfb71e67f39d6c6baddb22f |
| docs/HANDOFF_EXECUTABILITY_POLICY.md | e07d3b7a65422f150ee6f7c9795c4d4ea02ac56348020a8ec37063b233b633e3 |
| tests/test_v4_history_wire_review.py（仅阅读） | ea5be5bec02f602fe893c817b186286e29d3c5ca43d06a17b73e60973f51f719 |

**建议的是可复核的表示层机会，不是弱化理论的例外。** 其成立依据是完整可逆、不同记录角色及所有约束不变，符合 6.3 对实际 wire 计数的要求；不是因为某题只差 367 tokens。仍需后续独立授权的实现与验证；本报告不声称新 wire 能省 367 tokens、进入 16K、使当前失败转成功，或提高答案准确率。
