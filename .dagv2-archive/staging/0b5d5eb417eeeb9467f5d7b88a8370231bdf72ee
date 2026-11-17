# PersonaMem：23 个 unresolved_or_exhausted 的只读复现

结论：**12 个任务在事实已经确定后仍无法结束，其中 11 个是规划契约与程序根表达式不兼容，另 1 个缺少完成规则的路径。**其余 11 个仍有未解决输入，不能归为同一证书问题，也不能仅凭 `unresolved_or_exhausted` 认定预算耗尽。

分析使用生产树 `/Users/mao/projects/dagv2-personamem-a48`，HEAD `a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1`；开始时工作树干净。未修改生产代码，未调用模型，未读取 gold 标签。只读取 `failure_features.jsonl` 和其中列出的 23 个压缩结果行，调用当前生产校验、求值和证书函数。函数源文件 SHA256 随重放输出保存。这里统计的是失败条件，不是修复后可答对的题数。

## 重放结果

运行方式（脚本只向 stdout 输出；重定向写在分析目录）：

```bash
cd /Users/mao/projects/dagv2_analysis/personamem_v3_1_full_20261013
/Users/mao/projects/dagv2/.venv/bin/python repro_contract_deadends.py > contract_deadend_repro.json
```

脚本阻止 socket 网络连接，禁用 bytecode 写入，不创建 Engine。完整初始计划由 `dagbt.residual_plan.validate_plan` 和实际 `repair_planner.validate_plan` 验证；当前状态另外执行 `validate_program`、`validate_output_contract`、`validate_bindings`。最后用实际 `program/facts/contract/versions/sources/pending_variables` 重放 `possible_outputs` 与 `certify_output`。

- **23/23 完整初始计划及当前各组件均通过校验。**
- **23/23 求值状态与最后日志一致；23/23 符号证书为 None。**对 semantic 模式，符号证书为 None 是设计行为，必须另外满足 semantic ready 条件，因此不能将这 9 个都称为证书缺陷。
- 12 个 `determined`，且日志 `active_demands=[]`；11 个 `indeterminate`，且日志 active 非空。
- 契约：`one_reason` 11、`semantic` 9、`value` 2、`all_failures` 1。
- 结果类型：text 20、set 2、entity 1。

| 互斥的直接阻挡条件 | 数量 | 最终求值状态 |
| --- | ---: | --- |
| 静态规划的 mode 与根表达式不兼容 | 11 | determined，无 active |
| rules_complete=false，且无规则完成入口 | 1 | determined，无 active |
| 本地 sources/parents/counters 超出真实输入容量 | 8 | indeterminate |
| compose 的支持观察缺少原始来源 | 1 | indeterminate |
| secrecy_plan 组合任务没有得到所需支持 | 2 | indeterminate |

上述“compose 缺少原始来源”的 1 个任务还存在潜在 mode 不兼容。因此 **mode 不兼容总计 12 个，但本轮已确定事实并卡在该条件的为 11 个**；两者不能相加。

## 1. 规划器接受了证书函数必然拒绝的静态程序

`dagbt/residual_plan.py:98` 的 `validate_plan` 依次校验输出契约、表达式自身类型、DAG 绑定，但不比较 mode/result_type 与表达式根节点/返回类型。

`dagbt/residual.py:516` 的 `validate_output_contract` 只要求 `one_reason` 的 explanation 为 one、`all_failures` 为 all。另一方面，`validate_program` 的 `one_reason` 是对布尔条件生成 decision/reason **record** 的专用运算，`failures` 是汇总失败条件的 **set** 运算（`:208`）；并非一般自然语言“解释一个原因/列出若干原因”的别名。

`certify_output` 在 `dagbt/residual.py:481` 明确要求：

```python
one_reason -> expression.op == 'one_reason'
all_failures -> expression.op == 'failures'
```

本批 11 个已确定病例全部是 `expression.op='var'`、`rules_complete=True`、没有 rule_binding：10 个 one_reason/text，加 1 个 all_failures/set。事实已绑定，但证书函数在进入求值前就返回 None；增加检索预算无法改变静态契约不兼容。

代表：`5117e665-5204-44ae-9946-0c984965c04e`。contract 为 all_failures/set；program 只有开放集合变量 reasons，根节点 `{"op":"var","id":"reasons"}`。已有四条带来源的原因，pending 为空，重放 determined/nonempty_proven，最后 active 为空；花费 2 次 LLM 和 1 次 ANN，证书仍 None。日志有合法选项字母，但本分析未判断其答案正确性，也不建议直接接受它。

one_reason 代表：`cd8f66f9-1da2-47c0-8a26-4cfbd29fc593`，同样只用 2 次 LLM、1 次 ANN，reason 文本已确定，却因 one_reason/text/var 不能认证。将文本根节点机械改成 one_reason 也无效：它要求布尔 fields，并输出 record，结果类型也不匹配。

`repro_contract_deadends.py` 还包含两个最小合成例：分别用 one_reason/text/var 和 all_failures/set/var，完整计划校验均接受，绑定一个合成来源支持的值后都得到 determined/live=[]，证书均 None。合成例仅证明程序接口问题，不涉及真实答案。

控制器不是把已确定事实算错，而是没有终止兼容性检查：`dagbt/residual_control.py:213` 的 active 由 live variables、pending 与可用 rule_binding 产生；`:419` 的成功路径要求证书或 semantic ready；这些静态非 semantic 程序没有证书，也没有 active，最后落入 `:503` 的通用 unresolved 状态。**主要责任在规划验收缺少跨组件契约校验，控制器则缺少清楚的不可完成原因。**不应通过取消证书要求处理。

剩余 one_reason 例 `8823918d-36cc-4caa-87f7-075f846a0be5` 也具有相同潜在不兼容，但当前 reason 尚未绑定：联合读取因 `Supported/counter observation needs original sources` 拒绝 compose 观察，pending 包含 reason。修正契约本身不保证这例能完成。

## 2. rules_complete=false，但计划没有完成规则的入口

`63f0c40f-a1c8-4e5d-af0a-37bc2b317185`：value/entity，根节点 var recommendation，计划依次获取 past_activities、controlled_activities，再 compose recommendation。三个事实均已绑定，pending 为空；求值 determined，active 为空，LLM 4/ANN 2。但程序声明 `rules_complete=False`，没有 rule_binding。

`dagbt/residual.py:498` 在规则不完整时只允许特定否定见证短路；该普通 var 输出不属于例外。`dagbt/residual_control.py:203` 与 `:218` 只为初始 rule_binding 创建规则完成需求，这个计划没有入口，后续不会自动变为规则完整。

重放在**内存副本**上仅将 rules_complete 改为 True，证书即可生成，确认阻挡点。这个实验不证明规则完整，不能作为真实修补或自动放行。应在规划时明确此任务究竟是有完整规则的符号值输出，还是基于历史偏好的开放建议；当前请求是后者时，应在检索前建立正确 semantic 契约。

也不能一律拒绝所有 `rules_complete=False/no rule_binding`：现有契约允许 one_reason 或 and 的否定短路，在已知必要条件失败时无需补齐全部规则。较准确的早期校验应识别“当前输出永远不可能走合法短路，且无规则完成机制”的计划；至少本例普通 var/value 能静态识别。

## 3. 其余 11 个不是事实已确定后的证书死路

8 个容量病例的错误均为 `InputOverflow: Local sources/parents/counters exceed real wire capacity`，发生在 recommendation/suggestions/comparison/summary 的最终组合。它们为 7 semantic/text 加 1 value/set；LLM 仅 3–5 次，ANN 2–4 次，仍有预算。控制器捕获错误后耗尽的是当前执行 identity，并非 ANN/LLM 总预算。单位明细和原始行路径见重放 JSON，不应归为“预算太小”。

上述 `8823918d...` 是 1 个缺来源的 compose 失败。

另 2 个是 surprise event/trip 的 secrecy_plan 阻塞：

- `57154824-9041-47ce-ae17-27b93e7cd1ce`：semantic/text，preferences 与 event_ideas 已绑定；secrecy_plan、plan 未绑定。联合读取指出源文只说明需要保密，未给出具体保密策略；历史成功惊喜旅行也不包含实现保密的方法。batch 可完成、无协议失败，但仍没有相应支持。4 次 LLM、1 次 ANN。
- `112eeb1b-84d0-47b2-a983-4cb3a0b8287f`：相似的 semantic DAG，preferences/event_ideas 已绑定，secrecy_plan/final_plan 未绑定；还出现 `Unavailable/out-of-scope/stale actual parent`。6 次 LLM、1 次 ANN。

控制器对 compose 不执行新检索；读取无进展后将该 identity 标为 exhausted，再无可执行任务则 unresolved。这里需要区分“用户未来建议需要结合已有偏好产生建议”和“必须从历史找出用户已经使用过的具体保密策略”。现有计划/读取要求导致后者成为前置条件。不能根据这些日志直接宣称模型缺乏建议能力，或以放松来源验证作为修复。

## 4. 可以更早拒绝什么，边界在哪里

1. 静态无 rule_binding 计划：检索前验证 mode 与根表达式兼容，比较结果类型；one_reason 应对应 Boolean fields -> record，all_failures 应对应 failures -> set。一般解释性文本/列表不能因为题目出现“原因”就选择这些专用 mode。
2. 有来源规则实例化的计划：初始 var 可以是合法占位符，不能只看初始根节点一刀切拒绝。对 immutable contract 的结果类型约束应尽早校验；规则实例化后再次校验最终根表达式与 mode。必须保留先检索规则再产生条件表达式的设计。
3. 不完整规则：保留否定短路例外；对普通 value 输出且无规则完成入口的静态计划尽早报错并有界修正规划。不能运行后将 rules_complete 自动设 True。
4. 运行时对 determined、无 active、无证书的状态给出明确不兼容原因，避免把不可终止规划显示为笼统预算/检索失败。该诊断不能替代初始规划校验，也不能构造替代答案。
5. 提示词应解释专用 mode 的计算意义，而不只枚举名字；开放回复/建议的生成契约要在读取前确定。现有 `residual_plan.py:13–15,39–47` 对普通 value 与 semantic 有说明，但没有充分解释 one_reason/all_failures 的布尔运算含义。

修复优先针对契约验收、任务定义与无进展诊断；保持既有证书、来源和最终一致性要求。上述计数仅限这批 23 个 unresolved 结果，不外推到全部失败，也不代表任何准确率增益。
