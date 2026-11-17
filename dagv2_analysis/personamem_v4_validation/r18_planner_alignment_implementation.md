# R18 第 14 题通用规划协议对齐：实施回执

修改仅位于 `/Users/mao/projects/dagv2-personamem-v4-reconcile`，基底提交 `800c51763ea3a2bfcad459b4413d41c6432db52e`。没有修改 RELEASE、运行目录、全局 `reasoning.py` 或既有测试；没有提交、完整测试套件或新模型/tokenizer/network 调用。其他代理的第 13 题修改不属于本回执的审查范围。

## 实现

- `dagbt/local_terminal.py`：JSON schema 为 compose 增加非空显式父输入约束，与现有校验顺序一致；合法单节点 retrieval 仍允许。
- `dagbt/residual_plan.py`：仅 PersonaMem schema 收窄 semantic/text/semantic、至少两节点、终端 var 表达式并排除 rule_binding；历史变量类型、确定性中间绑定及非个人模式保留。动态终端 ID、依赖闭包、作用域等仍由既有本地校验负责。
- 同文件新增 `personal_repair_builder(reasoner)`。每次 planner 调用获得新闭包；仅接受当前最后一条已判 invalid 的 planner 记录，并核对逻辑调用顺序、错误、错误类别及修复序号。第一回从实际已发请求核对原输入，此后原输入不变。原样保留前次 `raw_output` 和从记录直接取得的有界累计错误；不将无法核验的异常类型作为事实写入。
- `dagbt/engine.py`：仅 personal planner 向现有 `Reasoner.json` 注入该 builder。错误草稿明确标为不可信诊断内容。原输入、原草稿与累计错误不为容量而裁剪；现有完整 wire 计数、输出预留、本地两次修复及共享预算保持原样，超限仍失败。
- `tests/test_v4_planner_contract_alignment.py`：新增 16 个合成案例，覆盖 schema 拒绝既有非法组合、合法历史类型/确定性中间节点、实际 Engine 两次修复、通用模式隔离、真实 preflight 溢出及原始无效 JSON 保留。没有硬编码 R18 的正确计划或答案。

plain 模式的 schema 仍是提示约束，不承诺服务端强制解码或真实模型一定成功。

## 定向验证

在隔离目录执行：

```bash
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q \
  tests/test_v4_planner_contract_alignment.py \
  tests/test_v4_personal_task.py \
  tests/test_v4_personal_semantics_review.py \
  tests/test_residual_planner_protocol.py \
  tests/test_local_terminal_integration.py \
  tests/test_reasoning_v2.py \
  tests/test_v4_contracts.py
```

结果：**204 passed in 3.23s**。自身新增文件先单跑为 16 passed in 1.29s；该 16 项已包含在 204 中，不能相加。

日志：`reader_planner_alignment_targeted.txt`，SHA256 `8b010ef739d1086313e01e69478e216202034e97632e5577628fda9883ee6693`。

## 当前冻结文件 SHA256

| 文件 | SHA256 |
| --- | --- |
| dagbt/local_terminal.py | f585a6a38dfdcdafe2dd5e458fdf333ff2f687ad2aa6bff2881cafed83c9bac4 |
| dagbt/residual_plan.py | f146da849bbbd207f2527ee4bd2b0a20c871e316c55d6d64bf81e7717359626b |
| dagbt/engine.py | 1cbdd158e676eacefcbc1036c97779ff9143f67df29d0c2a775e7719c417573d |
| tests/test_v4_planner_contract_alignment.py | 01fe46b3143fb454a9881f17528930b5bf58a85af44030b156ed13a9f5ef7579 |

独立代理的新增 42 项已报告通过，正式独立报告由该代理单独提供。发布仍需 root 核对合并范围、完成必要完整测试和新的冻结版本真实验证；R18 原失败记录保持不变。
