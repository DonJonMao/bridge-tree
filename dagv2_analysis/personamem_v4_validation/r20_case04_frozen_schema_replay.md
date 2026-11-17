# R20 case04 保存请求的 F / R schema 离线回放

候选 joint_reading.py SHA-256：`263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a`。线上 RELEASE 仍为冻结 6c046374；未改源码、已发送请求或 canonical row，未调用服务、读 gold 或评分。

按实际 saved wire 解开 review/history 文本引用、known_observation 表和 source-document/columnar 原文元数据。新 _schema 在不注入 F 的情况下，Calls 9、10、11 都与各自实际保存的旧 schema 精确相等，相同原响应均仍满足旧 schema。

F 的来源是 canonical failed batch 内实际保留的 normalized validated response unknown 行：同实际 Call 9 ID，value=null，16 个来源。Call 9 是新批次，F 初始为空；不能把旧 known route ID 当成来自上一批的冻结授权。

| Call | 离线补入 F | 原响应通过新 schema | ID not 禁令错误 | 其他 leaf 错误 |
| ---: | --- | --- | ---: | ---: |
| 9 | 无，保持新批次边界 | 是 | 0 | 0 |
| 10 | 当前批已规范化 unknown ID | 否 | 1 | 0 |
| 11 | 当前批已规范化 unknown ID | 否 | 1 | 0 |

Calls 10/11 schema 的唯一结构变化位于 response 分支 observation.properties.id；未扩大 reviewed_observation_ids 权限。未知行被声明不可重述，并未因此变为可清偿义务的 settled review。

结论仅是：新增 F 能把实际已有 runtime 的同批冻结禁令表达在 repair schema 里，且不会把 Call 9 误作跨批冻结违规。这不是模型再运行，不证明模型会遵守，也不证明覆盖条件被解决、审计成功、准确率提升或本题可成功。

JSON SHA-256：`967dcb4be9a48cb0a0d34c7d57bae6b39ac49747544d6cf2c23c593a6800f813`。
