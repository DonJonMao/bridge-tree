# R16 共享历史文本：部署计数结果

本次只研究输入表示，未集成到运行源码，也没有生成请求或读取标签。

固定原型 SHA256：`5f3bdb9266dfcdd417750cb463d8625b4e36753ea4578f8732dfe2c0a4a6a825`。
源码为 R16 的 `b9e28a7faa8d419f9f1283574fa095399919c243`。独立测量脚本为
`measure_shared_history_text_archive.py`，完整证据为
`r16_shared_text_deployment_token_measurement.json`，包含脚本、原型及相关源码哈希。

## 已实际验证

- 扫描时有 121 个已归档 joint/compose/audit 及 repair 请求，其中 16 个适用新编码。
- 每个适用请求都做类型敏感的完整还原比较，输入保持不变。
- 原始 system 与当前 `_system` 精确匹配。候选重新构造对应表示的指令，加入完整的
  676-byte 解码说明，并原样保留实际发送的 schema、模型及生成参数。
- 每个原 wire 都重新经过同一部署 `/tokenize` 计数，16 个结果与归档计数一致。
- 候选 16 个也分别计数，输入净减少 **6–737 tokens**。最小收益对应一次普通
  semantic compose repair；最大收益对应第六题的 semantic compose。
- 实际发生 32 次 tokenizer HTTP，0 次生成。测量只在外部分析目录写 receipt，
  不改变实验的 ledger、请求、缓存、源码、配置或结果。

## 不能由此推出

这些是已经实际发送、原本就能容纳的请求。第二题失败的 39-source handoff 没有被
发送，因此不在这 16 个样本内。现有结果不能证明失败请求已适配 16K，也不能证明
模型能正确理解新编码、实验完成率或答案准确率提高。

本地包中的 Qwen tokenizer 不能用来估算这次 DeepSeek 生成服务的精确收益；独立审查
见 `r16_local_tokenizer_feasibility.md`。本次使用现有部署计数路径，包含服务默认
chat template 和 generation prompt。模型权重及 tokenizer 文件哈希仍未独立验证。

## 下一步依据

第二题须先完整重构被拒 handoff 的 base 与 repair 请求，并匹配已存 wire SHA256
与 12817/13046 历史计数；之后才对候选计数。不能从别题最大节约数推算它是否适配。
未来生产集成必须把实际编码是否发生显式传给 system 构造，保证计数、预测、修复及
生成使用同一表示，且 schema、输出 typed value、控制状态和证据义务保持原契约。

另外静态发现 terminal-only repair 的准入 `_schema` 与发送时额外修改 `required`
存在差异；当前 R16 已归档请求中没有 `terminal_repair`，不能将本轮失败归因于此。
后续应统一 schema 构造并针对实际两个入口验证，不能仅改测试预期。
