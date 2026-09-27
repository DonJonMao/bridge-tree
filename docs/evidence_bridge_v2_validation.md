# Evidence BridgeTree v2：可靠性修订与验证

日期：2026-09-27。本轮依据服务器 v1 终止错误统计修改引用协议、恢复粒度和选择输入预算；搜索调度、A 四项算术、retain/speculate/pivot 与 reader 任务未改。当前方法契约见 [implementation](evidence_bridge_implementation.md)，服务器操作见 [runbook](evidence_bridge_runbook.md)。

## 实际修改与方法影响

| 问题 | v2 实现 | 保留的边界 |
|---|---|---|
| 102 次引用不匹配、15 次引用超长 | 从权威来源分出 <=400 字符 span，模型返回 ID，代码提取精确 fragments；多片段仍是一项 assessment | 未知/不可见/跨 memory/空白引用拒绝；出处正确不证明语义支持 |
| 49 次 JSON 开头解析失败 | 严格完整对象解析，支持确定 BOM/完整围栏/唯一 prose 包装；真实响应元数据；每请求最多2次、每题最多6次修复 | 不补括号/字段，不接受重复键、NaN、溢出数字或竞争对象；49次的具体包装尚未从原响应核实 |
| 局部错误造成整题失败 | 有效 assessment/coverage 留存；失败单元局部恢复、明确截断拆批；映射留额度给最终选择 | 最多24次 evidence调用；服务故障仍走现有有限HTTP策略；无合法最终选择仍失败 |
| 28 次输入超限 | 选择 payload 按完整记录、必要需求及 memory 轮转裁至预算，相关候选成本同步 | 只确认其中3条为 select，其他25条不能据摘要归类；固定 query/需求超限仍失败；reader原文不在这里裁剪 |
| 13 次跨需求引用 | 同需求约束写入提示，按需求分组、短别名、具体错误定位和局部coverage修复 | 同源支持多个需求须各有映射；不把A需求的support直接复制到B；13个原例尚未逐条语义复核 |

引用协议与格式恢复主要改变接口可靠性。允许部分有效映射继续、对 ledger 作预算筛选会改变模型实际看到的证据，是方法的 v2 运行变体，不能称为完全不影响方法。模型选错来源、错误判断支持关系、遗漏有用映射仍可能影响答案。

片段可追溯到 `Memory.text[start:end]`、source_hash 和权威角色。保守前提计数合并同assessment、重叠出处和同一句强制分片，避免把一个句子切成两份就获得“两前提联合推断”的资格；这也可能少计同一较宽片段中的不同事实，不构成语义独立性证明。

## 预算、恢复与日志契约

- 所有 planning/map/select/repair/rebatch 计入24次逻辑调用，最终reader单计。每逻辑请求最多2次格式/字段修复、整题最多6次。明确截断的map直接拆小，拆出的请求也占总调用预算；没有通过重分批绕过总额度。
- 映射为最后选择与剩余reader集合修订留调用空间。必要的选择格式恢复可使用这份余额，避免为尚未产生的预算修订保留额度而阻止首个合法选择。
- 局部coverage修复冻结有效行与selected_ids；预算不可行的完整proposal另开整体修订，允许删换。没有伪造覆盖或回退dense。
- 选择输入按完整记录裁剪；实际request中保留的ID和alias映射被记录，不能引用省略项。缺口诊断携带 omitted_evidence_count 和 mapping_incomplete，不能把预算不可见冒充未检索到。
- evidence专用 token 估算取旧regex计数与UTF-8字节数/3向上取整的较大值，解决连续中文/长ID严重少算。schema overhead同计，审计标记 `regex_or_utf8_bytes_div3_v2`；这仍不是服务tokenizer上界。旧reader/embedding/reranker估算没有因此改变。
- 完整raw_response、finish_reason、refusal、usage、response ID与实际协议在任务artifact。仅明确 `finish_reason=length` 判输出截断；缺元数据保持unknown。请求hash包含输出协议/schema和输出上限。
- 成功题按 normal / truncated / partially_mapped / truncated_and_partially_mapped 分组统计答对数、准确率和成本，失败成本另列。旧日志无诊断记unknown。汇总只读当前权威outcomes，不能重复累计retry历史。

## 验证证据与范围

本轮本地验证使用实际源码路径与受控网络/模型替身，覆盖：

1. 多语种、emoji、换行、权威角色与结构间隙、长句和尾部覆盖；原文ID可追溯，重叠/重复来源不制造独立推理前提。
2. JSON完整性、包装、重复键、非有限数、长嵌套、empty/refusal/length元数据；plain/json_object/json_schema与reader隔离，本地HTTP拒绝不自动切协议。
3. 有效映射保留、失败单元耗尽恢复后的部分资格、最终选择调用预留、每请求/全局修复额度；同需求alias局部修复与不可见引用拒绝。
4. 超限ledger按完整记录裁剪，合法序列化请求不超本地预算，来源全部留在artifact；固定中文query不可裁剪时在发请求前失败。
5. 正式executor、reader、outcome和summary贯通；真实detached monitor/worker的start/stop/resume；无Git解包与Git源码身份一致，新protocol/spans模块都参与身份。
6. 日志导出包含原始证据请求响应和逐文件校验值，排除项目私有配置、环境变量及软链接；v2与v1状态隔离。

最终测试、lint、编译、数据预检与压缩包逐成员核对记录保存在本地 `outputs/evidence_v2_validation/`。最终全套回归为 **879 passed in 26.30s**；补充来源状态/运维边界测试72项通过。新增证据模块、脚本及相关测试Ruff通过；compileall、bash语法及git diff检查通过。固定数据预检确认589题、3方法/1767任务，预检本身0模型调用。压缩包成员/源码一致性和解包数据预检见同目录package_check.json及unpacked_preflight.json。历史v1的641项测试不作为v2证据。

本地尚未取得9月27日新失败的完整server artifacts，只有用户粘贴的计数与错误摘要。9月22日归档属于旧方法，不能充当v1 evidence失败的回放fixture。本轮测试包含报错类别重现，但不声称已重放全部230个真实失败。后续使用 `bash scripts/run_evidence_bridge.sh export` 导出新原始响应，逐条检查剩余语义失败。

本地测试通过不能证明真实模型准确率提高或230次失败全部消失。本轮额外尝试了实际配置服务的 plain planner 协议探测：1次逻辑调用、4次有限HTTP重试，约23.54秒后以 `HTTPTransportError` 终止，未取得HTTP状态或模型响应。没有继续执行真实map/select/json_object/reader，也没有将网络失败解释为格式不支持。实际记录为 `live_service_summary.json`、`live_service_plain_probe.json`，不含凭据/私有端点。

启动脚本会在用户服务器对当前部署执行一次无修复的真实planner协议预检；它只证明该次请求可用，失败不会启动全量实验。此次没有在用户服务器启动/停止实验，也未执行完整589题评测。

## 交付与版本隔离

- Git分支：`codex/conditional-activation`。
- 新包：`dist/evidence-bridge-v2-server/bridge-tree-evidence-v2.tar.gz`，附SHA256与成员清单。
- 旧包：`dist/evidence-bridge-server/bridge-tree-evidence.tar.gz` 保持原文件及SHA256 `684398b5c5db9f23890e18febad83234fb62d08cc85b17c1bcb165ca2f7360aa`。
- v2启动：`bash scripts/start_evidence_bridge_linux.sh`；默认独立 `outputs/background-evidence-bridge-v2` / `outputs/evidence-bridge-v2`，关闭SSH后仍运行，日志自动持久化。
- v1机制PDF保留为历史背景，未重写历史实验记录；当前v2以本记录和实现契约为准。
