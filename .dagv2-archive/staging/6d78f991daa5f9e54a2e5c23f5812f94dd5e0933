# R15 第三题终端续窗容量审查

本地重建完整匹配已归档的首个 terminal 请求，以及续窗全部 101 个 prefix 的 202 个输入计数 wire hash。没有调用任何服务、读取标签、修改源码或干预 R15。

## 已证实的失败链

- 7 个 history 批次和首个 terminal 批次均通过；实际用了 11 次 LLM、2 次 JSON repair，audit 尚未开始。
- 首个 terminal 请求包含 46 个可见原文，输入计数 11782；随后全部 101 个续窗 prefix 均未通过容量准入。
- 最小 prefix 含 1 个 source group、3 个窗口源、39 个可见原文。基础输入 11867，加 4096 输出和 264 margin 为 16227；普通 repair envelope 输入为 12095，总量 **16455，比 16384 超 71**。拒绝源自现有 repair 预留规则，不是 LLM 次数耗尽。

## 原文闭包与整文档扩张

父证明实际选择的完整原文闭包为 **36 个 sources，来自 12 个 documents**。控制器先把这些 sources 转成 parent_docs，reader 再展开这些 documents 的全部 mapped spans，得到 **117 个 spans，额外 81 个**。117 个都已在 history 阶段读过，仍因新的 terminal query identity 建立了新的阅读任务。

首窗消耗 16 个 groups、读过 17 个 spans，留下 101 个 groups、100 个 unread markers。邻接窗口导致剩余 groups 包含 102 个独特 aliases，其中 2 个已在首个 terminal 窗口出现；这解释数量差异。

首窗完成后，必要原文闭包仍为 36，没有新增必要 source。新增的 terminal route 使 known_observations 从 7839 增至 9372 UTF-8 bytes。三个父 summary 同时出现在 grounded_subquestion、supported_parents 和 known_observations；这是可证实的表示重复。字节数不能当作 token 数，未做删字段后计数或效果推断。

## 结论边界

当前 39 行原文具有 39 个唯一 alias、原文 ID 和坐标，没有相互重叠；原文已采用列式与共享 document metadata 编码。没有发现重复插入原文、错误算术或漏查可行 prefix 的代码缺陷。

可确认的是：实现把父证明闭包扩张为整文档的终端重读义务，而终端状态增长后，最小续窗也超过既定预留容量。整文档重读是否符合预期算法，需要与方法约定核对；“历史阶段已读”本身不能代替终端作用域审查。不能据此直接删除来源、将未读标记清零或绕过 audit。

**0 个新增 group 的当前完整请求没有匹配的已保存精确计数，故不能断言 36-source 必要闭包本身可装下或已超限。** 现有 handoff 检查只承诺必要下一步 footprint，不能保证后续每个扩张窗口都可执行。

可重复的离线入口为 `review_r15_terminal_continuation.py --no-write` 和 `review_r15_terminal_expansion.py`；后者同时输出源文件、归档文件与 helper 的 SHA256。两个 JSON 审查报告保留原始计数与所有 prefix 的 wire hash。
