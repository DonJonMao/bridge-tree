# RECONCILE shared history text：最终只读复核

日期：2026-10-14。基线为 `b9e28a7faa8d419f9f1283574fa095399919c243`，检查对象为 `/Users/mao/projects/dagv2-personamem-v4-reconcile` 当前未提交候选。RELEASE 不在本次修改范围。本文仅新增于外部验证目录；未修改源码/测试/README，未重跑测试，未请求服务。

**结论：未发现新的阻塞问题或 README 夸大声明。实际实现遵守已评审的输入层边界；显式 applied 状态正确控制新解码指令，规范状态、输出 schema、符号终端旁路与 assistant 输出结构 floor 没有被错误改写。以下结论是代码/离线协议复核，不是模型解码成功、完成率或准确率证明。**

## 1. 精确文件身份

| 文件（RECONCILE 相对路径） | SHA256 |
| --- | --- |
| `dagbt/history_wire.py` | `1117bc614be0205fa1ef7a65dd0b1a111069ab65da60acf2ff35a9f1a0fe3cb9` |
| `dagbt/joint_reading.py` | `41f84e8eccdaa527c753fb6ad7345e83131d00cac1bd1de29c81fd02362c0391` |
| `tests/test_v4_history_wire_integration.py` | `533b0b00dfb3ca1319bd9b3c72f581bd18b19fa1a9e346c9ff32582bf299d4a8` |
| `tests/test_v4_history_wire_review.py` | `ea5be5bec02f602fe893c817b186286e29d3c5ca43d06a17b73e60973f51f719` |
| `README_PERSONAMEM_V4.md` | `1ae46c00cb5d9f67648338e88cb96b93c351141834916470a59da0a49ac26d2c` |

## 2. 实现与调用边界

- `history_wire.pack_with_status` 保持已评审原型的候选选择、256 UTF-8 字节阈值、精确匹配、确定性别名/切分、完整 byte 收益比较和严格 roundtrip；只把返回值改为 `(wire, applied)`。`pack` 保留单独返回字典的纯变换接口。676 字节 INSTRUCTION 未改变。
- 每个回退都返回完整旧 wire 的独立副本与 False，包括保留字段碰撞、坏旧表、非适用输入及无收益；不把已存在的 shared_history_texts 当作应用成功。
- `_prepare_wire` 是唯一新增的生产准备层：先旧 `_wire_data`，再 `pack_with_status`，最后 `_system(wire)` 加上仅在 applied 为真时出现的新指令。没有跨请求缓存 applied 状态。
- `_estimate`、`read` 请求循环和 `_repair_terminal` 三入口均使用 `_prepare_wire`；schema 始终来自原始规范 payload。已有 forecast、actual repair、mandatory handoff 通过 `_estimate` 进入同一编码准备层。
- `_schema` 在存在 terminal_repair 时统一 required 为 slots、semantic_answer、final_prediction；发送入口的迟到覆写已移除。混合 history_evidence、response_audit 或 audit_instruction 明确抛 ProtocolError，普通 history/audit 契约保留。真实 request 的最终计数/容量门仍保留。
- 新解码函数不用于接收模型输出。`_observation` 仍要求完整 value，不接受 value_ref/text_ref 作为答案或证据捷径；scope、父版本、失败草稿、反证、来源及恢复权限没有迁移至共享表。

## 3. 明确没有接入新编码的路径

本次以 AST 提取函数源码段，对照 HEAD 精确检查：`_payload`、`_wire_data`、`_system`、`_selection_data_identity`、`_fresh_structure_response`、`_fresh_structure_floor`、`_handoff_failures`、`_observation` 均未改变。另逐文件确认 residual_control.py、reasoning.py、transport.py、token_counting.py 与 HEAD 相同。

1. **规范状态**：新函数对旧 wire 深拷贝后变换，不修改 canonical payload。grounded query 的规范字符串、字典顺序相关的 selection identity、source 坐标、所有作用域/版本/义务仍在原通道；schema 不读取输入引用。
2. **符号终端旁路**：`_handoff_failures` 中 terminal_format_request 的直接 estimate 和 `ResidualController.terminal_format` 的 `Reasoner.json('semantic_compose',...)` 仍使用独立格式化 envelope。没有在 Reasoner 内按 semantic_compose 名称全局编码。
3. **assistant 输出 floor**：`_fresh_structure_floor` 仍直接构造完整 typed assistant 模板并只计数，不调用 `_prepare_wire`。输入节省不会被错误折算成可以输出引用或降低完整输出结构要求。
4. **计数与缓存**：没有改动 Reasoner/Transport/token counter。实际新 system+user 消息进入既有计数与生成身份；生成 cache 仍含完整 payload，计数 cache 仍只以 tokenizer 实际 model/messages 请求为基础。max_tokens 改变只影响生成身份和最终总容量，不伪造新的输入 token 计数规则。

## 4. 两个新增测试的覆盖与限制

已阅读独立 `test_v4_history_wire_review.py`，其 oracle 没有调用生产 normalize/unpack；旧共享单元格只解码一层，literal 形状不会递归被解释。覆盖 Unicode、重叠/相邻 query 子串、类型敏感 roundtrip、来源/同值异 scope/父版本/反证/失败草稿、旧 table 与 whole IDs、坏引用/坏形状、收益回退、显式 applied 与 system 碰撞、不跨请求遗留 applied、输出引用拒绝、实际 read 估算/发送消息一致、canonical/schema 不变及 terminal mixed phase 拒绝。

`test_v4_history_wire_integration.py` 补充六种操作的完整计数/发送消息、真实 read→terminal-only 修复、schema 准入溢出时不先扣 json repair、forecast/actual repair 同编码和 assistant floor 完整值旁路。直接编解码测试与实际调用层测试分别验证了表示与接入，不仅仅断言实现返回值。

先前已完成的单文件结果分别为独立复核 **52 passed**、集成 **14 passed**；本次未重跑。报告完成时 root 已回报全套 tests 19：**1838 passed、69 warnings、106.30 s，exit 0，source_unchanged=true，301 tested files**；日志 SHA256 为 `601197544b1f875de34f4a103afafc2096a403e8d0c57249fd599b4588102df1`。这是 root 的独立运行回执，本次复核没有重复执行该套件。

独立复核文件的 reader_payload_fixture 使用 100000 容量，只用于长 Unicode 的协议/消息一致性测试；它不是本次实验 16384 容量通过证据，也没有更改生产配置。另一新集成文件保留 fixture 的 16384；真实容量证据仍应来自具体生产 wire 的部署 tokenizer 与实际生成验证，不能由上述离线 fixture 冒充。

## 5. README 文案复核

新增文案明确区分 PersonaMem-v1 的 32K 历史版本与单请求总容量 16384；该值包含完整输入、输出额度和余量，也没有被说成文献统一规定。这与先前上下文定义审查一致。

共享文本段落说明仅对完全相同的长历史值/grounded query 子串做输入表示变换，计入说明后 byte 更少才选用，真实容量仍按部署 tokenizer 检查，并要求模型输出完整类型值。文案没有承诺 token 必减、每题必能放下、模型必然正确解码、零失败、完成率或准确率提升；“来源、路线等保持原样”在上下文中指原始证据与规范状态保留，并未声称 wire 的 value 字段不发生已说明的引用变换。

## 6. 放行边界

本次只读复核支持继续完成现有离线验证和冻结候选，不替代 root 的完整测试结果、来源哈希门或后续真实模型验证。先前精确归档的两条 handoff wire hash 相等与部署计数节省属于独立、特定请求证据；不能推广成整题或整批通过。无需因本次复核修改冻结候选；没有请求扩大预算、减少证据或绕过已有失败状态。
