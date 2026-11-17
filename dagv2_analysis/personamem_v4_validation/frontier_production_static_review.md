# Discovery frontier：本次生产 diff 独立静态审查

## 范围与判定

审查 RECONCILE `/Users/mao/projects/dagv2-personamem-v4-reconcile` 相对
`8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8` 的 `dagbt/joint_reading.py`、
`dagbt/residual_control.py` 生产变更；只沿必要调用链读取现有 payload、reader、
reasoner、checkpoint、budget 恢复代码。没有修改源码或测试、没有导入生产模块、
没有运行测试、模型、服务或实验，也未读取标签和准确率。

**本次静态审查未确认仍未修复的生产缺陷。** 这不是完整验收结论：独立离线测试、
新身份运行由主代理分别确认。control 已宣布下列生产文件冻结，我已重新读取末次增量、
独立核对 SHA-256，且 `git diff --check` 通过。本报告只适用于下列版本，后续变更需要
定点复核。

```text
dagbt/joint_reading.py
0de601762d03daa8c4d59c6204c2413c31095b8bdca147a1a5916f8d372b3a3c
dagbt/residual_control.py
2ac20adf4cc24f473542915b2d8b8207c24607c962430c8943ca22f114f797aa
```

## 已确认的保留边界

| 核查点 | 静态依据与判断 |
| --- | --- |
| 明确 discovery 来源 | `read/_read` 默认 `discovery_doc_ids=None`；不存在来源参数时保留原整池 hard 策略。显式参数须属于本次 `doc_ids`，且只能用于普通 `document_windows`、不能用于 audit。controller 只在两条非 compose 检索路径传本地候选池或本次发现。变量类型没有成为豁免依据。 |
| 必要来源不能伪装候选 | 注册前以空新增窗口的 `_payload` 求当前 required sources；已知事实/父/规则输出、带源义务、failed reviews、clues 的来源先转为 hard。已存在 same-owner unread 也不能被 frontier 覆盖。`_require_frontier_source` 保留原 provenance 到 promotion 记录。 |
| 完整请求曝光 | `_request_with_exposure` 在进入 reasoner 前，从完整 canonical `source_spans` 记录来源，覆盖邻接、父来源、原失败材料与 scoped repair；不是只用主窗口 `batch` 或响应 citations。初始请求、普通修复和 terminal-only repair 都接入 wrapper。可逆 wire 编码未在本次改动中裁剪来源。 |
| 曝光后不能回退 never-offered | 曝光会移除同 query/source 的 frontier，为新工作登记 hard unread，并保留已有 owner marker；请求异常时补全实际请求变量的 hard 记录。未引用来源仍有曝光记录。批次完成仅按本 owner、该 alias 实际参与的变量集合结算，不清其他 owner 或未评估变量。普通 discovery 的未引用来源不会被标为 irrelevant。 |
| 整批原子处理后 yield | `if failures or discovery: break` 位于完整槽位/草稿/反证/whole-value/义务校验、有限修复、事实与 counter 整合、失败落盘和 terminal 检查之后。没有第一条 support 后提前返回的分支。失败、partial、unresolved 与已知反证依然进入原 hard 机制。 |
| mandatory 保持完整闭包 | 显式 discovery 与 `mandatory_closure` 的组合直接拒绝；controller compose 不传 discovery，audit 沿原 mandatory 路径。mandatory 仍以全部闭包形成一个 batch，保留 same/foreign owner unread 守卫和完整容量检查；新 break 条件不能给它成功前缀豁免。 |
| 中断不隐藏硬状态 | 新的公开 `read` 包裹 `_read`，在 `BaseException` 逃逸时将 reader hard variables 同步到 `state.pending`。请求内部不立即将临时 in-flight markers 填入 semantic pending，避免一次正常 mandatory 请求把自己的临时状态误认成旧语义缺口并扩张 proof projection。正常整合路径仍统一同步 pending。 |
| 不制造进展或预算 | frontier、discovery contexts、promotion、exposure ledger 从 `material_signature` 排除；真实 read states、事实、失败与义务仍参与。controller 的 `read_attempts/read_effects` 和全题 ledger 不重置，失败恢复仍要求同 task/phase、真实新来源或实际父变化及剩余修复预算。仅改查询名、排队或记日志不提供付费恢复资格。 |
| 旧快照继续 hard | 无 frontier version 的旧 snapshot 保留其 unread/failed/evidence 原意；带新状态却缺 version 或未知 version 则拒绝。新 frontier 验证原始 source identity、owner、scope/version 元数据及所属 discovery context，并拒绝与同 owner 的 hard unread、实际曝光或 read state 重叠。变量与 scope 须匹配归档 program；同 discovery identity 不允许换范围或版本。 |
| 恢复原顺序与成本 | frontier 为有序记录；同 identity 的仍未尝试候选排在新增候选前。snapshot 保留 frontier、exposure/promotion、local pools、read attempts/effects 和旧失败记录。`ResidualControl.restore` 沿现有 `BridgeSession.restore` 恢复累计 ledger、bridge 搜索状态与已消费位置；本次没有重做 dense/planner 或预算归零分支。 |

定位：`joint_reading.py` 的 `material_signature`（306）、`restore_obligations`（351）、
`_validate_work_context`（410）、`_record_source_exposure`（461）、`_request_with_exposure`（490）、
`_mandatory_scope_payload`（2075）、`read/_read`（2100）、实际曝光结算（2635）及 yield（2692）；
`residual_control.py` 的 `read_progress`（535）、两条 discovery 入口（678、715）、
`snapshot/restore`（732、759）。行号对应上述哈希。

## 审查中已处理的疑点

早期 diff 的恢复校验只核对 source/query/provenance/status，未检查工作范围元数据
及与曝光/read state 的重复身份。我将它作为**损坏或歧义快照拒绝强度疑点**发给 control；
未发现正常生成快照已经触发的运行缺陷。

目前版本新增 `_validate_work_context`，检查 task、变量、scope、program revision/hash、
parent versions 的形状，并对归档 program 的变量和 scope 核验；恢复时还交叉拒绝同
query/source 已曝光或已读的 frontier。`discovery_contexts` 将每个身份绑定到一个完整
scope/version 上下文，新的 read 不能沿旧身份改变上下文。最终 `_source_identity`
对原 span 除临时 alias 外所有字段取 digest，覆盖 role、time、邻接等元数据。

这覆盖了提出的具体疑点。历史 scope/parent version 不应强制等于当前值，因为旧身份
前沿需要作为历史 provenance 保留；生产 controller 以包含实际版本的 query identity
发起新工作，而不把旧 read state 当作新范围已完成。归档 program 校验读取的
`FactState.instantiations[].program` 是现有生成与恢复代码明确维护的字段，未见结构冲突。

## 尚待验收，不能由本报告推出的结论

1. **没有剩余已确认缺陷；有动态覆盖待验收。** 本审查未执行邻接/父/修复 wire、
   中断、terminal-only repair、恢复与控制器端到端离线用例。contracts/control 已编写
   相关用例，但其通过数字不计为本报告亲自验证；应以主代理保存的最终测试回执为准。
2. **曝光记录不等于物理 HTTP 成功。** wrapper 在 reasoner preflight 前保守升级工作；
   `request_status=not_sent` / `failed` / `returned` 与 logical index 保留区别。
   下游统计不能把所有 exposure 条目算成已发送 HTTP 或模型已利用证据。物理成本仍由
   transport/ledger 负责，本次没有按 exposure 数量计费。
3. **新策略运行身份需要发布阶段核对。** 这两个文件的 diff 不能单独证明新 manifest、
   配置、运行目录与冻结源码身份已建立；不得把策略静默套在 R17 或旧结果上继续写。
4. **算法效果未验证。** 完整批次通过只表示现有协议下有条件接受；不证明模型没有漏掉
   未引用反证。暂停纯候选也不证明它们无关、未来不会改变答案，不能推导 R17 失败必定
   恢复、成本下降或准确率提高。

最终接受条件仍是：固定源码、独立测试通过、保留实际 hard 义务及 mandatory 完整性，
再按主代理授权以新身份开展结构验证。本报告不授权启动或发布实验。

## 补充：root 既有测试变更快速核对

按 root 后续要求，只读审阅 4 个已修改测试文件的 diff，未执行测试。

- `test_v4_adaptive_initial_cap_review.py` 的 4 个候选、
  `test_v4_prefix_admission_review.py` 的 1 个候选，以及
  `test_v4_headroom_review.py` 的 1 个候选，均显式保留 `discovery=False/True`
  双分支。共享 `read_all` 默认仍为 legacy，没有将所有旧测试默认迁移到新策略。
- adaptive fixture 的 `s1` 已支持 `OLD`，新无调用断言仍将它保留为 hard；只有
  无必要关系的未发送 `s2/s3` 进入 frontier。无模型调用、零 LLM/JSON 消耗、
  admission identity、原文保留与有效旧事实等断言继续存在。
- 后续容量用例在 discovery 分支只完成首个真实批次，实际已曝光但未引用的 `s2`
  明确为 read；只有未发送 `s3` 留前沿。legacy 分支仍要求后续溢出与 unread 阻塞。
- headroom 用例仍要求恰好 2 次请求、1 次 JSON repair；这两次是同批初始生成和
  whole-value repair，不能因为 frontier 而减少为一次。两次曝光范围均精确等于
  实际首批原文，未发送 suffix 不标已读，settings/source 全量不变。
- `test_v4_proof_projection_review.py` 的
  `test_audit_eliminated_pending_terminal_sibling_does_not_protect_parent_alternatives`
  仅从 `obligation_snapshot()` 比较中单独取出新增 `source_exposures` 日志。
  剩余 obligation/frontier/promotion 状态以及 `routes/versions/program` 仍逐项
  canonical 比较不变，pending 仍为无关 sibling，替代证明仍归档，certificate 不变。
  曝光日志旧前缀原样保留，新增恰好一条 `audit_joint/returned/batch_assessed`，
  精确要求变量 `{decisive, history}` 和来源 `{s1, s2}`，没有允许额外无关材料。

上述改动与先前测试策略审查一致；未发现为获取通过而取消硬义务、原文完整性或真实
请求/预算断言的变化。root 报告的通过数量仍以其独立回执为准。
