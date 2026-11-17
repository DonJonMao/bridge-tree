# R16 共享文本外部原型：实际实现只读复核

**结论：在当前外部纯函数原型范围内，实际实现符合既定的无损表示边界；未发现新的已证实阻断点。仅确认 prototype，不批准生产集成、新实验或任何 token/容量/模型效果结论。**

审查源码：`prototype_shared_history_text.py`，SHA256：
`5f3bdb9266dfcdd417750cb463d8625b4e36753ea4578f8732dfe2c0a4a6a825`。

本次实际逐段读取实现及独立 oracle 测试，核对既有 `shared_text_prototype_38_receipt.json` 和日志末行 **38 passed in 0.12s**；没有重新运行测试、调用 prototype、访问网络/模型或读取运行问题/标签/凭据。

## 已核实的实际行为

| 边界 | 实现核对 |
| --- | --- |
| 输入不变 | `pack`、旧表 normalize、`unpack` 均先 `deepcopy`；没有把外部对象写回 canonical payload/schema/state。回退也返回独立副本。 |
| 候选类型 | 候选只从 `supported_parents` 的 `type == 'text'`、严格 `str` value 取得，至少 256 UTF-8 bytes，且 rows/query 内至少出现两次。无 stringify、strip、Unicode normalization 或语义合并。 |
| 替换位置 | 只扫描直接 parent rows 和顶层 known rows 的 `value`，只替换与候选完全相同的字符串。source 文本、counter、scope、version、父依赖、ancestry、failed/frozen 草稿及嵌套应用对象不遍历改写。 |
| 跨类型/跨scope共享 | 候选来自 text；实际替换目标可以是其他 parent 的同值字符串，且其原 `type`/scope 元数据保持原样。这里共享的是字符串存储，不授予摘要语义、不把 entity/atomic 变成 text，也不合并 rows。 |
| 新字段碰撞 | 已有 `shared_history_texts`/`grounded_subquestion_parts` 时整包原样回退；解开旧表后任一目标 row 已有 `value_ref` 也整包回退。嵌套字面 `{value_ref:...}` 等不会被递归解释。 |
| 旧 known 表 | 列必须是唯一字符串列表；values 必须列表；rows 必须明确存在且是列表，行必须与列等长。缺 rows 已在当前 SHA 修复为拒绝；不会 `zip` 截断。 |
| 旧 shared cell | 只识别形状恰好为 `{'shared':N}` 的 cell；N 必须 `type is int`、非负且未越界，拒绝 bool/float/字符串。取出旧 pooled value 后直接深复制，不再次递归解释其内的字面 reference。 |
| grounded 分段 | `_parts` 选择最左匹配，再选该位置最长候选，稳定生成 parts；literal 片段不变，不添加空白。`unpack` 严格检查 parts 类型及 `{'text_ref':ref}` 唯一字段形状，最终 `''.join` 恢复原字符串。 |
| decoder 拒绝 | 未知 ref、非字符串 ref、value/ref 并存、query/parts 并存、无表 parts、非法表结构或 part 均拒绝，不返回部分解码结果。 |
| 精确往返 | 选择候选前，将 unpack(candidate) 与 normalize(original) 做 `allow_nan=False` 的 canonical JSON 比较，区分 bool/number/string。失败以 AssertionError 关闭，不返回不一致 candidate。 |
| 收益门槛 | `byte_size(candidate) + len(INSTRUCTION.encode('utf-8'))` 必须严格小于原 packed wire；当前 instruction 为 **676 UTF-8 bytes**。旧表更小、无收益时完整回退原表示。 |

`normalize_known_table` 在存在 columns 但没有 values 字段时使用空池；只要有 pooled reference 就因越界拒绝。无 shared cell 的纯 literal 表可以解开，不会生成或丢弃 cell 内容；现有生产 old-table encoder 总会输出 values 字段，这个宽度没有造成当前归档输入或 round-trip 的已证实问题。

## 引用、提示与请求身份

- 新 instruction 明确 input-only；要求模型继续按原 response schema 返回完整 typed values，禁止输出 `value_ref`/`text_ref`。它也明确共享表不是新观察、citation、review permission 或 agreement 证据。
- 原型不改动 `repair_scope.whole_value_reviews[].known_observation_ids`，不会新建或替换 whole-value ID。恢复 top known row 的 value 后，原有完整行引用仍指向相同 id、scope、来源、parent versions、counter 和 ancestry。
- 原型不处理 `failed_batch_reviews`、`repair_scope.failed` 或 frozen review 内的草稿文本。这些保留结构原样存在，未获得新恢复权限，也没有任何逐 record 释放操作。
- 实际 imports 只有 `copy.deepcopy` 与 `json`；没有文件/网络/服务调用，没有导入 Engine/reader/Transport，没有读写 query identity、cache、ledger、状态或运行配置。它返回一种候选 wire 表示，尚未接入 `_wire_data`、`_system`、estimate 或 request。
- 因此当前实现没有把 parts 表示误用为 controller/算法身份。将来是否能让 canonical identity 保持原样、同时令实际 packed payload 和新提示共同绑定 tokenizer/生成缓存，需要在明确批准集成后验证；当前纯函数测试不能替代该验证。

一个**未来集成注意项**：若输入已经有 reserved 顶层字段，`pack` 会原样回退。调用方不能仅以“返回结果含 `shared_history_texts`”判断本次真的进行了编码，并据此对原有不认识的字段追加解码指令。当前原型没有 system 组装调用，此问题尚未发生，不构成此次纯函数实现阻断。

## 证据与结论范围

- 已有独立 oracle 覆盖 metadata/scope、Unicode/overlap、literal reference-shaped 值、新旧 reference 畸形、碰撞回退和收益不足；root 增补的旧表形状检查与 missing-rows 修复已绑定上述 SHA。
- 既有测试 receipt：exit 0、文件未变、services_called 0、production_sources_modified false。测试文件 SHA256 为 `8ccde041edb3085d191c2b31c9209b1a0572868f839a3482223c300aa6c302e3`；日志 SHA256 为 `f657c77aa5bcb72b55f91333cac16a801dab85f893cc5a0a90f6d849f9652e3e`。
- 本次没有复用早期 528-byte instruction 版本的收益数，也不把 root 另行收集的归档往返结果冒充本次新测结果。676-byte 当前提示的字节门槛仅是压缩选择条件，不能证明 token 更少、16K 可用或模型遵循协议。
- 两源树与 R16 继续冻结。唯一新增项是本外部只读实现审查报告；生产集成、部署计数和新一轮实验均不在本次结论范围。
