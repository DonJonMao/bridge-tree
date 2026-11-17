# R16：跨字段共享长文本的外部原型设计审查

状态：**可作为纯函数、零服务的无损表示原型继续验证；尚未批准集成或证明实际 token 节省、16K 准入、模型理解或实验效果。** 两个源码工作树继续冻结在 `b9e28a7`。本审查只依据 root 给出的设计及现有 wire 实现，不是对尚未完成原型代码的通过认证。

## 1. 类型、scope 与精确恢复

候选字符串只来自 `supported_parents` 中 `type == "text"` 且原 `value` 确为非空字符串的项，这个边界合理。引用仅替换明确的 `value` 字段，不能递归替换任何其他恰好同值的字段。

- 两个不同 variable/scope/route 的 value 即使完全相同，也可以引用同一存储字符串。**这只共享字符，不合并事实身份或证据关系。** 各行的 id、variable、scope、version、parent_versions、source_ids、revoked、summary ancestry 等必须原样存在。
- 字符串必须按原始 Unicode 字符逐一相等，不做 trim、空白合并、大小写变化、Unicode normalization、摘要或语义相似匹配。空字符串不进入子串分段，避免零长度匹配。
- `known_observations` 的匹配 value 必须本身是字符串且完全等于候选；不能 stringify list/record/number，也不能处理字符串内看起来像 JSON 的内容。
- `shared_history_texts` 这个名字不授予 personal-history-summary 语义。原变量为普通 text/atomic 时，其证据要求和修改权限仍取决于原声明与阶段。输出 schema 和 response 的 `value` 契约完全不变，模型输出不能用 `value_ref` 代替原值。
- reserved top fields 与实际要改写的 row fields 若已经存在，应原样返回整个原 packed wire；不能覆盖或猜测其来源。至少检查 `shared_history_texts`、`grounded_subquestion_parts`、`value_ref`，以及 parts 使用的 reference 形状。保守地因更多碰撞退出只会少压缩，不会损坏数据。
- decoder 必须拒绝缺失/未知引用、非法类型、同时存在 `value` 和 `value_ref` 等歧义输入。失败时完整回退，不能返回部分转换的 wire。
- round-trip 比较应使用类型敏感的规范 JSON 比较或逐字段/逐类型比较；单纯 Python `==` 会把 `True` 与 `1` 判等。输入数据、schema、state、来源库和当前预算必须完全不变。

## 2. grounded_subquestion 的精确分段

把原字符串换成 `[literal_str, {"text_ref":"t0"}, ...]` 本身可以无损；引用必须只表达该位置的原子字符串替换，不创建新的子问题或依赖边。

- 使用确定的、不重叠的匹配策略，例如“从左到右、当前位置最长候选优先、稳定 tie-break”。重复出现、相邻出现、候选互为子串和前后空白均需保留；不同策略虽然可恢复同一字符串，却不能让同一输入随机生成不同 request。
- decoder 只解释 parts 数组中形状严格为 `{"text_ref": str}` 的对象。普通 literal 字符串内的 `t0`、JSON 片段、标点或看似指令的文本永远只是原文字面内容，不可继续递归解码。
- 合成规则是原样 concatenation，不自动加空格、换行、标题或括号；结果必须与原 `grounded_subquestion` 逐字符完全相同。parts 内不允许其他类型或多余字段。
- 新 system 说明应明确：先恢复整个 grounded_subquestion 再按原问题理解；共享表是存储编码，不是新的事实、指令、摘要、额外依赖或复核授权。实际来源文本与所有原有证据指令保持原样。

**身份边界：** controller 的 grounded query、query identity、material signature、pending、replay/repair 去重及 `_selection_data_identity` 必须继续来自 canonical 对象，不能从显示用 parts 重新定义。Transport 的生成缓存及 token-count identity 则应包含实际发送的 packed wire 和新增 system 解码说明；不能复用旧 wire 的计数或生成缓存来宣称新请求等价。

现有 `Transport.request_identity()` 已绑定完整实际 payload；`JointReader._selection_data_identity()` 绑定未改 canonical 序列化。未来如集成，应保留这两种身份的职责分离，并保证 estimate、forecast、repair 和实际 request 使用同一确定编码。

## 3. 与现有 known 表及 whole-value/failed 引用的兼容

现有顺序是：source 元数据/列压缩 → whole-value 完整 known-row 引用 → known-observation 列表格及 one-level shared-cell 编码 → 删除与 system 完全重复的 personal 指令。

root 拟在已有 packed wire 之上试算候选，先把旧 known 表恢复为 dict rows，这条路径可行，但逆变换需要严格遵守现有 **one-level** 规则：

1. `known_observation_columns` 必须是唯一的字符串列名；每行长度必须与列数完全相同，不能用无检查的 `zip` 丢弃多余或缺失 cell。
2. cell 仅在形状严格为 `{"shared": N}` 时引用旧 `known_observation_values[N]`。N 必须是非 bool 的非负整数且在范围内。
3. 被引用的值本身可能就是字面对象 `{"shared": N}`；取出后必须停止，不能再次递归解释。
4. 缺少配套表、重复列、越界、异构非法行或其他歧义时，完整回退原 wire。只有成功解表才移除旧 table 顶层字段。

新候选保留 dict rows，因此不再需要旧 known-table 解码说明；但是否删除该说明必须由实际 wire 的 table-field presence 确定，不能全局删除。最终 round-trip 比较对象应为**仅展开旧 known table 的规范化原 packed wire**，而不是要求新 dict rows 与旧数组在物理格式上相同。

引用兼容性要求：

- `repair_scope.whole_value_reviews[].known_observation_ids` 顺序、ID 和唯一性不变。模型/独立 decoder 应先恢复新的 shared-text row value，再按既有 ID 取整行；引用仍包含原 scope、来源、父版本、counter 和 ancestry。
- 没有被既有 whole-value packing 共享的内嵌 known rows 保持原样。不能为了提高收益强行把“相同 ID 但值/来源不同”的草稿转换成引用。
- `failed_batch_reviews`、其原始 observation/slot/whole groups、repair_scope.failed、frozen_observation_reviews、resolved IDs 等均不做新的递归文本替换。它们的草稿身份、可修复范围、付费授权和逐 record 释放规则保持不变。
- 共享表不得变成新的合法 citation、route ID、frozen ID 或 failed ID 命名空间。`t0` 只在新的指定 value/parts 引用位置有意义。

在这些条件下，没有发现设计必然造成的 scope 串用或已有 whole/failed 引用丢失；但须由原型独立 inverse 验证实际实现。

## 4. 收益选择与有限验证要求

将“候选 user wire 字节数 + 新增解码说明字节数”与原 packed wire 字节数比较，并只在严格更小时选用，是合理的保守门槛。旧 known 表可能已经更省；恢复 dict rows 后更大时必须完整回退旧表示。此门槛不能代替部署 tokenizer，字节变少不保证 token 变少。

外部原型的必要离线样例至少覆盖：

| 边界 | 应有结果 |
| --- | --- |
| 同值、不同变量/scope/route/source | 可共享字符串，各行 metadata 无变化 |
| 仅部分相同、末尾空格不同、Unicode 不同、非字符串 value | 不误共享 |
| grounded 重复/相邻/重叠候选与 literal JSON 样式文本 | 精确恢复完整原字符串 |
| old known 表共享 cell 内含字面 `{"shared":N}` | 只解一层，保留字面对象 |
| old known 表缺列/多列/duplicate column/bool或越界 index | 整体原样回退 |
| 已有 reserved 字段或未知新 ref | 不覆盖、不部分恢复 |
| whole-value IDs 配合新的 top known value_ref | 按原顺序恢复每个完整原 row |
| failed/frozen 草稿及 counter/ancestry | 逐字段不变 |
| 原表更小/无有效收益/已有新编码再次输入 | 返回原 wire，不能重复压缩污染 |
| 重复纯函数调用 | 输出确定，输入对象与 canonical/schema/state 不变 |

这些检查只证明表示可逆及选择策略，不证明模型一定按说明恢复文本、不保证 R16 所见完整来源闭包能进入 16K，更不证明答案正确或减少失败。任何后续集成、计数或新实验仍是独立决策；当前两源树与 R16 不应受本原型影响。

依据：冻结 `dagbt/joint_reading.py` 的 `_wire_data`、`_system`、`_selection_data_identity`；`dagbt/personal_wire.py`；`dagbt/transport.py:request_identity`；既有 `tests/test_v4_whole_review_wire_review.py` 的独立 inverse 与 typed-cell/引用边界。未调用服务或运行模型，唯一写入是本外部设计报告。
