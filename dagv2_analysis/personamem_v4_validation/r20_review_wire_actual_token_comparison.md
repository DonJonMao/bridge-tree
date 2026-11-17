# R20 review-wire 实际 token 对比

- 保存的 repair 7：输入 11229 → 11238 tokens；旧减新为 -9。
- 保存的 repair 8：输入 10911 → 10920 tokens；旧减新为 -9。

仅测 R19 已发送的两个 repair 请求；先确认旧 payload 精确重建及新层无损 inverse，再按当前部署 tokenizer 计数。只在独立诊断 counter 禁用重试，实验配置及其重试策略未改。未生成、未 embedding、未读取标签或评分、未改源码或运行记录。

不重建尚未发送的 77-source 请求，不由本结果推断已填补 367-token 缺口、案例成功或准确率改善。
