# R16 本地精确 tokenizer 可行性核验

检查对象：运行源码 `b9e28a7faa8d419f9f1283574fa095399919c243`、本地 tokenizer 文件、已有计数事件与归档请求。全程无网络、无下载、无生成请求，未编辑源码/配置，未读评测标签。

## 结论

**当前没有找到可作为本次 DeepSeek 生成服务精确计数器的、已核验的本地 tokenizer 和服务端 chat template。** 因而不能离线精确计算新的 `shared_history_text` 请求的 token 收益。

本地可以精确复用**完全相同已归档 wire**的历史部署计数；这是按身份查验既有结果，不是本地重新分词。新输入编码或新增 SYSTEM 指令使 wire 改变，不能从旧 token 数或字节节约外推。

当前有证据支持的新 wire 精确计数路径是已有部署 `/tokenize`，按实际最终消息请求、`add_generation_prompt=true`、服务默认模板计数。本审查没有调用该接口。未来若取得与部署对应的 tokenizer、完整模板及参数，并用已有请求独立核验，可另行建立本地可信路径；不能假定同名模型或任意 DeepSeek tokenizer 等价。

## 1. 本地文件是什么

真实 R16 已存请求的 `payload.model` 为 **`deepseek-v4-flash`**。文件：第二题第12次请求 `f4d0aaa514888b4b04df17a057b357560dff5fdd0add9bfc11d84f2451814e22.json`。

仓库 `package/tokenizer` 是另一套 tokenizer：

| 文件或字段 | 已核验结果 |
| --- | --- |
| config.json model_type / architecture | `qwen3` / `Qwen3ForCausalLM` |
| tokenizer_config.json tokenizer_class | `Qwen2Tokenizer` |
| tokenizer.json model | BPE，vocab 151643，NFC normalizer |
| tokenizer.json SHA256 | `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4` |
| tokenizer_config.json SHA256 | `d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101` |
| 本地 chat_template | 4168字符，SHA256 `a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8` |

`dagbt/navigation_query.py:1` 明确限定其既有验证：对 Qwen3 embedding 服务，163个成功请求、3250条输入的本地裸文本 token 数加1与服务使用量相符。这是 **embedding 输入**的经验兼容性，不是 DeepSeek generator、chat wrapper 或服务器 tokenizer 文件身份的证明。

`dagbt/model_runtime.py:72` 的 `load_tokenizer()` 对 bridgetree 配置直接返回 `BTTokenAccounting`；该类仅返回 regex估算长度，不持有部署 vocabulary token IDs。源码明确写“not the deployed DeepSeek tokenizer”。非 bridgetree 分支才从 package/tokenizer 本地加载 AutoTokenizer，但该分支不适用于本次配置，也不能因此把 Qwen文件用于 DeepSeek。

检查了工作区副本、`~/.cache`、Downloads 的 tokenizer/model/template 文件名，以及标准 Hugging Face / ModelScope 路径。发现的 tokenizer 文件属于上述 package 副本；没有找到另一套已核验的 DeepSeek tokenizer/template。`HF_HOME`、`HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`TRANSFORMERS_CACHE`、`XDG_CACHE_HOME` 均未设置；`~/.cache/huggingface`、`~/Library/Caches/huggingface`、`~/.cache/modelscope` 不存在。这是已检查范围的结论，不声称穷尽整台机器任何可能的任意路径。

## 2. 当前精确计数边界

调用链：

1. `Reasoner._payload`（`dagbt/reasoning.py:68`）构造 system/user 消息。plain 模式的输出 schema 已经以指令追加在 **system.content** 内；joint 操作的 user JSON 使用紧凑分隔符。
2. `Transport.count_reasoning_tokens` 调用 `prepare_request`，得到最终 BridgeTree 生成 wire。公开归档 `requests/*.json` 中 `payload` 保存的是这个最终 wire。
3. `DeploymentTokenCounter._payload`（`dagbt/token_counting.py:153`）向服务提交 `{model, messages, add_generation_prompt: true}`。它不是对 HTTP 请求 JSON 的字符进行分词，也不是用本地 Qwen template 渲染。
4. 服务默认 chat template 包装 system/user 及 generation prompt；返回实际输入 count。调用完生成后，`Transport._verify_token_count` 又要求返回的 `usage.prompt_tokens` 与预先计数严格一致。

因此离线复用归档时，应直接使用完整 `payload.messages`，**不要再次附加 schema**。验证新编码必须同时包含：变换后的 user JSON、输入解码说明、原有 system/phase指令、原有输出 schema，以及同一服务模板生成提示。只数 userdata、原文 spans 或新的 shared table 都不是完整请求计数。

当前接口只接受纯文本消息及明确的普通采样字段；工具、多模态、自定义模板参数、未知 provider 字段会拒绝。`max_tokens` 等采样字段不参与 tokenization输入，但输出预留4096以及256+8的容量余量必须在输入计数之外原样加入。服务报告 max_model_len=120000不改变实验固定上限16384。

## 3. 本地缓存/存档能复用什么

`DeploymentTokenCounter` 的缓存是每个 Transport 实例内的 bounded `OrderedDict`（512项），不会持久化一个可用于任意新文本的分词模型。cache key绑定 endpoint、mode、model、messages和add_generation_prompt；计数事件另保存完整最终 wire 的 SHA256。

持久化的 `tokenization_events.jsonl` 包含 count、输入身份、backend、是否估算等；不包含可还原的 tokenizer vocab/template。其 `tokenizer_id` 为 null，并明确注明“model weights and tokenizer hash are not independently verified”。

已只读核验 R16 第二题这个已完成 residual attempt 的 **12个生成归档请求**：每个完整 payload 的 SHA256 都唯一对应一个 `token_count_is_estimate=false` 的历史计数，且与本归档 `tokenization_validation.expected_prompt_tokens/observed_prompt_tokens` 一致。这12项核验不调用服务，也不读取 raw模型输出。

可以使用以下最小离线查验方法。它遇到新 wire 或冲突时必须失败，不能降级猜算：

```python
import hashlib
import json
from pathlib import Path

def exact_archived_count(request_file, events_file):
    record = json.loads(Path(request_file).read_text())
    wire = record["payload"]
    encoded = json.dumps(wire, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    wire_hash = hashlib.sha256(encoded).hexdigest()
    counts = {
        event["count"]
        for line in Path(events_file).read_text().splitlines()
        if line.strip()
        for event in [json.loads(line)]
        if event.get("status") == "ok"
        and event.get("token_count_is_estimate") is False
        and event.get("tokenization_wire_sha256") == wire_hash
    }
    if len(counts) != 1:
        raise ValueError("No unique exact historical count for this complete wire")
    count = next(iter(counts))
    validation = record.get("tokenization_validation", {})
    if (validation.get("status") != "matched"
            or validation.get("expected_prompt_tokens") != count
            or validation.get("observed_prompt_tokens") != count):
        raise ValueError("Archived generation usage does not certify this count")
    return count
```

对于尚未执行生成的 handoff预测，可能只有历史计数事件和 wire hash；若能准确重建同一完整 wire，可查该hash既有count，但没有生成usage交叉验证。若连原wire都不能逐字节重建，仅邻接事件序号不能当作通用离线tokenizer。

## 4. 对 shared_history_text 下一步验证的影响

独立往返测试和字节审计已经可以证明表示的结构保真及候选字节节约。它们不能证明输入token节约。此次本地检查未发现可补足这一缺口的精确DeepSeek分词器。

若继续验证真实token收益，应对原始及候选**最终生成wire**使用同一部署计数边界，记录两个wire哈希、prototype SHA、system/schema构造方式和计数结果。只发 tokenize 计数不等于发生成请求；但它仍是网络操作，本任务未执行。容量判断应对原始初次、原始repair、编码初次、编码repair分别计算，不能把一次输入节约或平均节约直接写成16k gate通过。
