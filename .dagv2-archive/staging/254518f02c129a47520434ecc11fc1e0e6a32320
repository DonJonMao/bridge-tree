# R15 wildcard slot 修复提示独立审查

源码：`50d1ba0b2edb623384e51ac42ea12b36e5b69229`；reader SHA-256：`08200e2ee7f84579762fdd123a8535a5c46cb1b6a17689c0aa5207d986b1e662`。
审查时间：2026-10-13T16:11:03.925200+00:00。
范围：只读源码及既有 R15 结构报告；未改源码/测试，未重跑测试、读评价标签或调用任何模型/计量服务。
结构报告 SHA-256：`bb3d1454da72b0b6fea9c0cfb8ac852c15a901d00a7a7b518a115d27e0acc72e`。

**结论：代码允许 wildcard 失败槽新增 observation ID，但提示没有明确说明这一例外，存在可消除的提示歧义。不能据 R15 重复支持行证明该歧义是实际失败原因；也未发现代码拒绝合法新增 review ID 的缺陷。**

## 可核对的源码证据

- [SYSTEM:92](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:92) 写 `Repair returns only failed observations/slots, retaining IDs`；[99–100](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:99) 写 `Correct those drafts in place, preserving each requested ID` 及已验证行 `must not be restated or changed`。没有随文解释 slot 级 `id="*"` 与具体 observation ID 级修复的不同授权。
- [SYSTEM:105–117](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:105) 已明确要求 settled 来源并集覆盖全部 obligation 来源，并允许真正独立的 irrelevant/corrective review。这证明来源覆盖要求现在明确；但“独立 review 可以使用新 ID”仍只可推断。
- [OBLIGATION_REVIEW_INSTRUCTION:137–155](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:137) 说明差集、独立 review 和 `reviewed_observation_ids`，明确禁止重述冻结行；没有出现 wildcard 槽可新增唯一 review ID 的明确许可。
- [_system:1090–1094](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1090) 仅当 repair failed 项有差集或冻结 offer 时追加上述专用提示。初始调用不追加；一般 repair 或清除差集后的 repair 也不必追加。因此若只在这段新增 wildcard 澄清，部分 wildcard 修复仍收不到。
- [read:1982–1986](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:1982) 把修复限制在失败变量；[2034–2035](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2034) 的新增行拒绝条件为：`attempt and (variable,'*') not in failures and key not in failures and key not in replacement_keys`。存在 `(variable,'*')` 时这一拒绝不触发，新增行继续经过正常来源、值、scope、父版本、反证和后续容量校验。具体 observation 级修复仍保留 ID 限制。
- [OBSERVATION_SCHEMA:246–248](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:246) 的 observation ID 是 string，没有旧 ID enum；[reviewed_observation_ids:682–684](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:682) 则只允许当前 offer 的 ID。新增 review 行与冻结引用适用不同授权，前者不是后者的新增引用许可。
- [repair payload:2177–2193](/Users/mao/projects/dagv2-personamem-v4/dagbt/joint_reading.py:2177) 为 `id='*'` 附上失败原 slot；这是足够供人理解的结构，但当前文本没有解释 `*` 是槽级修复标记，不是要求每个新 observation 使用该字面 ID。

## 初始与 repair 的判断

初始读取正常允许新 observation；通用提示要求覆盖和独立 review，未发现初始代码授权矛盾。
repair 中“只修失败 observations/slots、保留 requested ID”可以被理解成允许重做失败槽，也可能被理解成只能修改原 observations。代码采用前一种含义，提示没有把这个范围差别说清。

最小澄清应覆盖所有 wildcard repair，而不只 pure-coverage feedback：当该变量的 failed 项 `id='*'` 时，允许在该失败槽中新增唯一 observation ID，逐项真实审查未覆盖原文；具体指定失败 ID 仍须保留，不能遗漏原草稿/反证；冻结行只通过当前 offered `reviewed_observation_ids` 明确复核，不得重述或改写。保持全部来源、scope、value、summary revision、预算和 handoff 约束，不自动补引用或把缺失来源统称 irrelevant。

## R15 证据能证明什么

既有 [第二题结构报告](/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r15_second_case_review.md) 记录：call11 覆盖 17/52、缺 35；repair12 收到准确 52/17/35 差集和一个冻结 offer，但仍引用并重述同一支持行；repair13 清除引用后又只覆盖 17。它证明模型没有提交新增缺失来源审查，也证明重述/引用 guard 和旧差集清除按契约工作。

即使接受重复引用，仍缺 35 个来源；放宽该 guard 不能解决覆盖缺口。现有记录无法区分提示歧义、模型未遵守说明、真实语义无法判断或其他原因。明确 wildcard 授权是合理的小范围提示修正候选；是否减少实际失败，仍须同等约束下的真实运行验证，不能据离线授权检查宣称准确率提升。
