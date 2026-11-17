# Discovery frontier：Full21 修复增量静态审查

## 范围、冻结身份与结论

本报告单独补充 Full21 发现的恢复与拒绝前状态回归，不修改也不替代原
`frontier_production_static_review.md` 的历史记录。旧静态审查没有发现缺陷，不等于
完整测试通过；Full21 的实际失败是本次修复和复核依据。

只读审查 RECONCILE 的 source namespace/alias 恢复、material signature、异常同步、
`ResidualControl.restore` 调用衔接以及 root 修改的一个日志断言测试。没有改 repo，
没有运行测试、模型、服务或实验，没有读取标签或评分。执行了只读 hash/diff 检查；
`git diff --check` 通过。control 已正式二次冻结：

```text
dagbt/joint_reading.py
f5568ea4ad837dc32f8ebfb94afae4516efb5bb20f83dccdb2e0904eb94710eb
dagbt/residual_control.py
b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211
```

**在此二次冻结增量中，未确认仍未修复的缺陷。** 初始增量中“alias 变化使防重放签名变化”
的机制疑点已经由稳定 source key 规范化处理。实际离线测试通过数字由 control/contracts/root
回执提供，不冒充本审查执行；完整验收仍等 root 的 Full22。

## 1. 恢复按稳定原文绑定，历史实际请求保持原样

`_bound_source_alias`（415）先用稳定 `source_id` 查找当前 mapper，要求唯一对应，再比较
doc ID 与完整 `source_identity`。`_source_identity` 对原 span 除临时 `id` 外所有字段取
digest，因此相同原文的 alias 置换允许，text、role、time、offset、邻接等更改不能借置换通过。

`obligation_snapshot` 保存 `source_namespace`；`_rebind_snapshot_sources`（429）先深拷贝
snapshot，用 namespace 构造一一映射，拒绝重复旧 alias、重复当前绑定和无保存绑定的工作。

- 可执行的 `unread_obligations`、`read_states`、`clues` 和 frontier key 按新 alias 绑定；
  frontier 仍按旧队列顺序恢复，保留 owner、variables、scope、program/parent versions，
  在 `source_alias_history` 中追加之前的 alias。
- exposure 的 `source_alias` 描述**当时真实 wire**，恢复时不改；仅另存
  `current_source_alias`。`request_identity`、query identity、operation、logical index、
  来源稳定 ID、status 及原 discovery origin 不重写。promotion 也保留历史 alias，另记当前绑定。
- `discovery_origin` 的稳定来源会被再次核对；同 query 的曝光/已读与 frontier 重叠检查使用
  解析后的当前 source 绑定，不能因 exposure 保留旧 alias 而漏检。
- 没有 namespace 的旧快照不猜 alias 对应，也不把旧 unread 变为可暂停 frontier。
  旧未知来源继续保守处理。

`ResidualControl.restore`（784）现在接收 `restore_obligations` 返回的归一化 reader snapshot，
随后从该对象恢复 read states/clues。它不再把旧 snapshot 中的 alias 索引重新覆盖回来。
历史 batch 日志保留原样，不能误当成当前 mapper 的别名表。

## 2. alias 变化不制造进展，也不使旧防重放记录失效

早期增量会重绑定 alias，但 `material_signature` 仍把 read/unread/clue 的临时 alias 放入哈希；
controller 的 `read_attempts/read_effects/compose_exhausted` 却是旧签名的 opaque hashes。
静态可确认这会破坏纯别名置换的签名不变性；**本审查没有据此宣称额外付费请求已经发生**。
该机制已同步给 root/control/contracts，最终版本修正如下。

`material_signature`（306）将：

- `read_windows` 的 source 键；
- `unread_obligations` 的 source 键；
- `clues` 的 source 键；

统一表示成 `['source', stable_source_id]`；确实不可解析的旧记录保留
`['unavailable_alias', original_alias]`，不伪造原文对应。frontier/context/promotion/exposure/
source_namespace 作为发现或日志数据仍排除在语义进展签名外。

恢复保留 source 工作顺序、query identity、变量和实际事实，稳定 key 因而给出相同 material
signature；`read_progress` 的 before/effect、compose exhaustion guards 不需要清空或重算。
`failed_obligations` 的 batch identity 及 paid failed-review IDs 保持原样：它们是历史工作身份，
不能当成 source alias 改名。付费恢复仍依据稳定原文 seen IDs、真实父变化和剩余预算。

只读查看新增 `test_alias_permutation_preserves_material_progress_and_hard_source_ownership`
及 contracts 的真实 controller 恢复用例：包含实际已读状态、hard owner、source permutation、
恢复前后严格 signature 相等、前沿顺序保留和已曝光 source 不重读断言。测试本身由其它代理执行。

## 3. 拒绝前状态保持不变；真实新硬工作仍在异常时可见

公开 `read`（2190）进入前深拷贝四类 hard 状态并记录 exposure 数量。异常退出后，只有：

1. unread/failed/evidence/failed-review 状态确实变化；或
2. 新增实际 request-attempt exposure 记录；

才将 reader hard variables 同步到 `state.pending`。

因此纯参数拒绝、mandatory owner/scope 守卫在计数前拒绝且没有生成新工作时，不会把原本
未同步的旧 marker 顺手写入 pending。原有完整 snapshot/no-call/no-budget 断言可以保持。
相反，容量路径已注册新 hard 工作、实际请求被中断或 transport/preflight 留下 exposure 时，
仍会同步必要阻塞状态，不会将失败工作藏到读者看不见的状态中。

临时 in-flight marker 不在正常原子请求中立即成为旧 semantic gap；本修复没有改变 mandatory
闭包选择、输出契约、原文集合或付费请求限额。exposure 仍区分 `not_sent` 与实际逻辑请求，
不能将“曝光登记”直接当作物理 HTTP 成功。

## 4. root 第五个日志断言测试没有放宽 hard 语义

只读核对 `tests/test_v4_reader_review.py` 中
`test_successful_empty_read_cannot_clear_another_querys_evidence_obligation` 的 diff：

- 仅将新增 `source_exposures` 从前后 `obligation_snapshot` 比较中单独取出；其余整个
  snapshot 仍完全相等，包括 namespace、frontier/context/promotion、旧 unread/failed/
  evidence 记录。
- 原有效 history 不变、state.pending 与 reader.pending_variables 仍包含 history 的
  三个核心断言未删除或改弱。
- 新增恰好一次请求、旧 exposure 前缀完全不变、新增恰好一条
  `unrelated-check / joint_read / returned / incomplete / history` 的严格断言。
- exposure 与实际 wire 都要求包含 fixture 的**全部 8 条原文**。这是正确的旧协议范围：
  slot-level unresolved 没有逐 issue citation，已有义务携带整个观察窗口；不能缩成
  prior support/partial 各自引用的两条来源。

该测试将新增审计日志与旧不可变义务分开比较，没有允许成功空响应解除别的 query 的问题。

## 5. 剩余验证边界

目前未留下需报为已确认缺陷的增量问题。最终 full suite、失败 fixture 的真实回归修复、
实际新身份运行和 wire/source 字段验收由主代理回执确认；本静态报告不代替它们。
旧 checkpoint 与新策略的跨版本迁移不由本次自动授权：签名算法变化之后，只有按同一最终
方法/源码身份产生与恢复的新 checkpoint 才能要求 opaque guard 原样续用；旧运行不得静默续写。

R18 尚未实测。本报告不证明 frontier 一定降低失败率、缩小所有必要闭包或提高答案准确率，
也不授权启动 R18 或全量实验。
