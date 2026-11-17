# R12 首题结构诊断（已人工停止）

主代理因具体失败链停止运行并确认 live_writer=false。此记录不是自然算法终态；没有发布 row、attempt result 或 fusion snapshot。未读取标签，没有新增模型生成或 tokenizer 调用。

## 真实失败链

| 环节 | 实际证据 |
|---|---|
| Fresh 窗口选择 | event 512：event_history 最大 46 个 prefix groups；100 个可见源；cap 34，结构 floor 24 |
| 首次生成 call 9 | 实际 max_tokens=34；prompt=11210；completion=34；finish_reason=length |
| 第一次 repair call 10 | 原 100 个源的 wire 完全保留；max_tokens=4096；prompt=11338；completion=451；finish_reason=stop |
| 修复验证 | summary_revision 只保留旧 7 个引用中的 2 个，遗漏 5 个，另新增 1 个；被原引用继承约束拒绝 |
| 第二次 repair 容量检查 | event 535：input 12119 + output 4096 + margin 256 + fixed 8 = 16479，超出 95 |
| 后续历史动作 | event 581：event_history InputOverflow |

首次 repair 实际能够入场；容量溢出发生在修正引用缺失所需的第二次 repair。不能把这两次修复混写。

## 输入与 forecast 差额

已有历史摘要仅 277 个字符，值序列化 279 字节，完整 route 861 字节，继承引用 7 个。窗口另携带 1 个既存 evidence obligation，要求保留 53 个原源。大输入不能简单归因于摘要本身过长。

原 whole-review forecast 输入为 11990，给未知首次草稿保留 34，因此 11990 + 4096 + 34 + 256 + 8 = 16384。第二次实际 repair 输入变成 12119，比该 forecast 多 129；扣除首次草稿预留 34 后超出 95。预留一个首次草稿不保证后续所有修复草稿都能容纳。

## 停止时状态

最后预算 LLM 13/24、ANN 3、JSON repair 3。已完成历史 batch 中 7 个 complete=true，2 个 complete=false。最后 active_demands 为 event_history、interests、response；无最终 FactState，pending_variables 不可确定。terminal 和 audit 都尚未发起。

cap 的实际下发与严格截断处理符合实现。这个窗口暴露的是：以空 slots 骨架作为 floor、优先最大前缀，允许了缺乏有效提取空间的 34-token 首读；本例确实因此截断并消耗修复。不能据单例宣称所有 cap 或所有前缀必然失败。完整安全标量证据见同名 JSON。
