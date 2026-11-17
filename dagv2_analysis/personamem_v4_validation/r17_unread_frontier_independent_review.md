# unread frontier 分离：独立设计审查（简版）

## 结论：有条件接受该设计方向

审查 control 已书面传达的边界：ordinary `document_windows` 完整处理一个实际模型 batch 后返回控制器；纯未尝试候选留在可恢复 frontier；已观察未解/失败/反证与 mandatory 共同前提继续阻塞相关发布。

**这个分离与原设计“当前证据更新后重新求解、按真正剩余需求继续访问”的目标相容。未发现必须把所有未发送候选一律设为 hard pending 的理论依据。** 旧 README 记录了保守实现，不是用户已授权修正的审批禁令。但“一条 support”“一批成功”“没有引用某 source”都不能单独授权删除待办；以下不变量是接受该设计的必要条件。

## 必须保留的八组不变量

| 不变量 | 最小反例与必要边界 |
|---|---|
| **1. 完整响应原子处理** | 同响应前半 support、后半 counter，不能第一条成功即 yield。必须处理所有请求槽位、返回草稿、同批反证及必要 repair 后再求解。漏槽、截断或失败不会把该槽位原文变回“未尝试”。后一个成功 batch 也不解除前一个失败记录。 |
| **2. 曝光 ≠ 引用 ≠ 无关** | wire 有 s1、s2，模型仅引用 s1；s2 不能因此回退 pure frontier 或标 irrelevant。Never-offered 必须核对完整实际 wire，包括邻接、旧父、failed-review 与 repair 原文，并带任务/变量/scope/版本，不能仅看窗口主 aliases 或 `read_states`。 |
| **3. 未发送不等于可选** | 已读 s1 指出“限制由附件 R 决定”，R 虽未发送，已观察的必要缺口仍 hard。选定 proof 的共同前提、累计 summary 来源、相关 counter 和明确定位待办也不能因未发而前沿化。`mandatory_closure` 不得拆成成功前缀。 |
| **4. owner 与版本不洗记录** | old query 已对 s2 报 unresolved，new query 将 s2 放队列，不能按新 identity 清旧 hard。实体 A 换 B、时间范围或实际父版本改变时，旧 read/support 不能伪复用；排除旧工作须依据真实范围/依赖变化。反过来，合法消去且不再被当前证书使用的 sibling 可以保留未解而不全局阻塞。 |
| **5. 失败恢复与成本不再生** | 一窗口一返回不能重置全题 ledger、请求修复限额、旧失败 seen-source/parent signatures 或 same-task/phase 恢复门槛。换队列/identity不是新证据。HTTP 已发但超时、repair 已计费后失败，不能按“无成功结果”假定从未尝试或返还预算。 |
| **6. 契约充分性仍独立成立** | “全部经历”“从未做过X”“最近一次/当前最终规则”不能因一个旧例子 support 就完成。集合、否定、最新、规则完整性仍需其原有充分依据；frontier 不绑定值、不赋 false、不证明无反例。PersonaMem summary 可非穷尽，但不得省去已经观察到的约束和时间变化。 |
| **7. 两类发布保证不混用** | Symbolic 仍条件于合法绑定 Γ、固定契约、规则完整性、非空世界及实际祖先无 hard obligation。Semantic 仍须真实 terminal、来源/父依赖和 audit，只报 `semantic_assessment`；历史 summary 不能直接变最终答案。终端出现新缺口时，保留候选/桥接前沿必须能恢复。 |
| **8. checkpoint 与进展诚实** | 老 snapshot 仅有 unread，缺乏曝光/尝试/必要性分类时，不能批量迁移为 frontier；没有新字段不是 never-offered 的证据。保留成本、旧失败和发布身份。仅 enqueue/dequeue/rename 不得制造“新观察”无限重试；未送模型候选始终不标 read/resolved/irrelevant。 |

## 模型漏判问题的明确边界

第 2 条不能反向变成“每条可见 source 必须逐一分类后才能 yield”，否则会重新引入全量 mapping。沿用现有整批协议时，可以诚实地说：完整输入已提供，所有请求槽位和实际返回记录完成既有校验，未观测到剩余未完成项。**这仍是有条件的语义解释，不证明模型没有漏读某条未引用反证。** 不能凭操作日志证明 s2 无关，也不必为未被观察到的假想错误虚构一条真实 counter。

已明确报告的 partial/unresolved、未完成 coverage、漏槽或失败草稿不属于上述成功状态。这些事项与 pure frontier 的区别必须由可核对状态支撑，不能只由本次 support 的存在支撑。

## 依据与审查界限

原设计 [4.2、5.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:147) 支持重新求解与可暂停访问；[6.2、6.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:208) 要求同批反证整合、未读状态分离与共同前提保留；[7.3](/Users/mao/projects/dagv2-personamem-v4-reconcile/docs/RESIDUAL_MEMORY_DESIGN_f4e38df.md:238) 按采用支持/相关反证审计。3.5 的条件性解释保证不因引入 frontier 而加强。

当前源码的关键保留边界：

- [真实 wire / repair 可见范围](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2028)，[原子提交](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:2393)。
- [付费恢复资格](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:413)，[mandatory owner 与共同范围](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/joint_reading.py:1904)。
- [实际依赖发布检查](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:211)，[checkpoint](/Users/mao/projects/dagv2-personamem-v4-reconcile/dagbt/residual_control.py:731)。

**最终判定：可以继续作为有边界的建模修正候选；若接口不能区分上述反例，就不能声称仅靠“一批成功”安全早停。** 本审查不证明任何实际 summary 足够、不验证迁移已实现、不预测 R17 恢复、成本或准确率。仅写本外部报告；RECONCILE `8dac32b`、RELEASE `bcbd16f`、源码/测试和 live R17 均未修改，未调用模型或服务、未读取标签/选项/预测。
