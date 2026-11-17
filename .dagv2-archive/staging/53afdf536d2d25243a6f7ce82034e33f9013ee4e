# R7 首题摘要复核阻断

仅检查 c10c6da 的首题请求、事件和状态；未读标签或预测，未调用模型。本报告不包含记忆原文、完整提示或凭据。

- 历史摘要变量声明与 history 阶段输出契约正确。
- call3/4/5/6 重发相同 468 字摘要、相同 10 个原始来源及相同 scope/parents，均显式声明 summary_revision；理由明确没有新证据。
- 唯一阻断为 `Summary revision cannot create a new version from an identical whole value and proof`。恢复请求已经带正确失败批次 ID；不是遗漏 ID。
- 最终状态为 `unresolved_or_exhausted`；预算使用为 `{"ann": 4, "embedding_http": 4, "http_attempts": 18, "json_repairs": 6, "llm": 14}`；未出现 terminal 请求。

建议在完整版本、路径、来源及反证验证之后，将精确未变化的候选视为幂等复核，状态层跳过新增路径、退休和版本变更。保留已有路径与修订祖先，不能删除 revision 字段再转普通 support。真正反证、下游容量及显式付费义务解除门槛保持。

逐请求标识、文本/来源集合哈希、相等性检查与失败链见 `r7_noop_review.json`。
