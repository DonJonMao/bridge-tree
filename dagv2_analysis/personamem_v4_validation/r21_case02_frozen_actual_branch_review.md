# R21 第 2 题：两次真实冻结修复分支窄查

unit `f546a74f-54de-40d0-9d88-8b0e30467d7b`，运行源码 e667。只读已保存 Call 6/7 及同批前驱 Call 5；未执行新测试，未读标签/评分，未调用服务，未改源码/测试/运行，不等待或评价本题终态。

**两次实际请求的 schema 禁止集合与 controller 的 F 一致，settled 引用许可与明确提供的 R 一致；模型返回没有普通冻结 ID 重述。未发现新矛盾。**

| 实际调用 | 同批冻结与明确引用集合 | 模型实际返回 |
| --- | --- | --- |
| Call 6，repair 1 | F = R = `{obs_getaway_prefs_001}`，来自 Call 5 的 support | 引用 001；新报 support 002，没有普通重述 001。 |
| Call 7，repair 2 | F = R = `{obs_getaway_prefs_001, obs_getaway_prefs_002}` | 引用 001、002；新报 support 003，没有普通重述前两项。 |

独立核对了保存请求中的实际 schema：普通 observation 的禁止枚举分别恰好为上述 F；`reviewed_observation_ids` 许可枚举分别恰好为上述 R。Call 6 的 001 通过失败 slot 中的完整原 observation 提供；Call 7 的 002 同样由 slot 提供，001 通过 explicit complete offer 提供。三处完整 observation 均与其同批前次响应完全一致，引用没有凭空授权或修改原 observation。

同批边界为 Call 5 新批次产生 001，随后 Call 6 新增 002，并形成上述两次最终 F。源码的 F 构建位于 summary、whole-value、handoff 可能移除草稿之后；本例两个转换均保留了已有合法 support，**没有实际触发 thaw 移除分支**。因此这份真实运行证据只覆盖 settled support 的同批累积、schema 表达与完整不变引用；F−R 均为空，不能声称真实验证了 unknown/partial 的“禁止重述但不允许引用”分支。

两次请求均正常结束且保存的 tokenization/usage matched，输入分别为 11302、11747 tokens。以上只说明这两次请求的结构契约一致与具体返回遵从，不证明整题成功、义务已解除、语义充分或准确率改善；无需据此新增修复或扩大验证范围。

结构收据：`r21_case02_frozen_actual_branch_review.json`，SHA-256 `0f14af6776c8da24ef0f93a34973810552c117826045fd2f12c88658c7928bb1`。
