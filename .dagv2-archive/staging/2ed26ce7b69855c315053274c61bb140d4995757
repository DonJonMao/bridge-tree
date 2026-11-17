# dagbt 清理审查：Git 依赖与部署包去重

审查日期：2026-10-27。只读审查原项目、Git和部署包；没有删除、移动、改写项目文件，没有部署或调用模型。新增文件仅为本目录的审查报告/JSON清单。以下Git信息为清理前快照；root已决定将两个保留worktree改为独立Git仓库后移除旧主仓。

## 可执行结论

按root最新方案，保留 `dagv2-personamem-v4`、`dagv2-prefeval-v4-fix3`、`dagv2-webwalker-v4` 原路径；先解除Git与资产软链接依赖，再删除旧源码目录。部署侧保留全部15个原始tar.gz及同名.sha256、全部实验/验证记录、patch与manifest；可以删除本次列出的34个已解包source/payload/installed树，但必须先移出3个运行状态文件和1个本机凭据，并给未被原archive覆盖的源码快照做小型source-only备份。

**数据覆盖已逐文件核实：34个候选root内160条data文件路径，全部在保留的当前数据或已核验archive manifest中找到同相对路径、同SHA256内容；未覆盖的独有datafile为0。** 不要把这个结论推广到整个dagv2_deploy：`preparation/`、`real_smoke*`、`analysis/`、`output/`等兄弟目录不属于删除allowlist。

## Git 与保留任务线的依赖

清理前 `dagv2/.git` 是约32MiB的真实common git-dir；7个附属worktree的 `.git` 文件绝对指向其 `.git/worktrees/<name>`。各admin目录的 `commondir=../..`，gitdir又反向指回worktree。因此不能先rm旧主dagv2。

| 原目录 | 清理前HEAD | 状态/处理 |
|---|---|---|
| dagv2 | f4e38df23b5b621a4d0e759c018c60e1fe25dd9b | 主Git管理根；tracked干净但263个untracked，含研究文档/旧包/tmp。保存refs bundle及必要untracked/ignored内容后再移除 |
| dagv2-personamem-v4 | e6677081cdfb33c01db3aaa274a497168f314f78 | 保留；独立.git后验证，无tracked/untracked差异但有ignored输出/资产 |
| dagv2-webwalker-v4 | 8a491f36aa129d6a869a8df6906f788b03ca0e06 | 保留；11个tracked修改、92个untracked，含最新代码/tests/依赖；不能仅按HEAD还原 |
| dagv2-personamem-a48 | a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1 | 旧worktree；有被保留PM引用的数据及ignored outputs，先迁出 |
| dagv2-personamem-v4-reconcile | e6677081cdfb33c01db3aaa274a497168f314f78 | 同提交且无工作树差异；在记录保存后可移除 |
| dagv2-residual-f4 | a48dc8da586c8f2c9858548dadcebde14aa9d9ed | 旧worktree；outputs/residual_memory_v1是实验记录，先保留 |
| dagv2-support-review | 25bd3e99b1c99fcda869d37017d687b27fde451c | 旧worktree，源码历史通过bundle保存 |
| dagv2-webwalker | a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1 | 旧worktree，572个untracked，含保留WV4仍引用的浏览器运行依赖 |
| dagv2-prefeval-v4{,-fix,-fix2,-fix3} | 无.git | 普通拷贝，不受Git bundle保护；保留fix3的完整实际文件，旧版非Git源码需source-only快照/patch |

root拟采取的独立化方式合理：从共享旧仓clone临时独立仓（`--no-hardlinks --no-checkout --branch`），给PM/WV4换入独立.git并重建index，保持现有工作文件不变。**完成判据**：两保留目录`git rev-parse --git-common-dir`均解析到自己的.git；HEAD与清理前一致；`git diff --binary HEAD`内容/未跟踪清单一致；PM原本干净、WV4仍保留11个修改与所有新文件。不要执行会重置工作文件的checkout/reset --hard。

`git bundle create --all`能保存可达refs历史，但不保存未提交修改、未跟踪/ignored文件、reflog-only对象、凭据或worktree管理状态。建议旧仓所有refs bundle（并verify）+每worktree的binary diff/index状态+源码/未跟踪归档；若需要完整历史审计，再留一份约32MiB的旧.git元数据压缩备份。不要把“git status干净”当作输出和数据已备份。

### 必须先迁出的保留目录软链接

| 保留目录内链接 | 清理前目标 |
|---|---|
| PM/data/derived | dagv2-personamem-a48/data/derived |
| WV4/_webwalker_browser_vendor | dagv2-webwalker/_webwalker_browser_vendor |
| WV4/_webwalker_browsers | dagv2-webwalker/_webwalker_browsers |
| WV4/data/2wikimultihopqa/index/passage_vectors.npy | dagv2/data/2wikimultihopqa/index/passage_vectors.npy |
| WV4/data/hotpotqa/index/passage_vectors.npy | dagv2/data/hotpotqa/index/passage_vectors.npy |
| WV4/data/musique/index/passage_vectors.npy | dagv2/data/musique/index/passage_vectors.npy |

需要复制/迁移资产并改链，验证目标存在且哈希一致。部署解包树另有32条browser链接，本次只移除链接本身而不跟随删除目标；保留WV4依赖必须先独立化。

## 15个部署archive：完整成员清单与SHA256

全部15包已流式读取tar成员，并对原压缩文件实际计算SHA256；15/15与各自.sidecar相符。原始archive之间SHA256都不同，不是可按文件名判定的相同包。内容清单（每个member的name/type/size/链接目标）、源码文件hash、与当前三条任务线的比较在 [deploy_archive_inventory.json](./deploy_archive_inventory.json)。下表源码比较仅覆盖dagbt/dagv2/scripts/tests/configs/vendor中选择的代码/配置扩展名，**不是完整项目树等价证明**。

| archive（相对dagv2_deploy） | 字节 | 成员数 | SHA256 | 对应当前任务线：相同/不同/当前无此路径 |
|---|---:|---:|---|---|
| 20261014_personamem_v4_experiment/dagv2_personamem_v4_experiment.tar.gz | 21781499 | 321 | `88b72a8e64b64ba4e33e806fb8023c3d24da333a1a467eb831b2e1dd47f9e4fc` | personamem: 225/0/0 |
| 20261014_webwalker_v4_experiment/dagbt_webwalker_v4_experiment.tar.gz | 1323301 | 145 | `2996d6a4cac203f200d4b7f8730088ddd1185c98b8e2ef03eabb3172252cbee6` | webwalker: 102/8/0 |
| 20261015_webwalker_v4_access_experiment/dagbt_webwalker_v4_experiment.tar.gz | 1322751 | 146 | `6422bd701428dccc4f4f72491b99e716398cf279dee41f4cf71589c5fe6b05ad` | webwalker: 102/9/0 |
| 20261015_webwalker_v4_access_experiment/stopped_gate_release/dagbt_webwalker_v4_experiment.tar.gz | 1323443 | 146 | `a6832fcb9822b50d416e72a20bf2b151f18927e1fd8d602499bb462da578e3af` | webwalker: 103/8/0 |
| 20261015_webwalker_v4_access_v2_experiment/release/dagbt_webwalker_v4_experiment.tar.gz | 1348504 | 153 | `e6d8f06febcea0325415942333c0a80f32876a92948386841093341c41d7bf6a` | webwalker: 104/14/0 |
| 20261015_webwalker_v4_access_v3_experiment/release/dagbt_webwalker_v4_experiment.tar.gz | 1353436 | 153 | `1e8937b0922ae6e5afdfecdab8163985a1fec1b126c934a178f68b3f3fe447bf` | webwalker: 105/13/0 |
| 20261015_webwalker_v4_access_v4_experiment/release/dagbt_webwalker_v4_access_v4_experiment.tar.gz | 1360030 | 154 | `b5c7e409ecbcb87e20bbc90f3b27f8a2f04fe2eff68ee5498d08ca0009fc4427` | webwalker: 108/11/0 |
| 20261016_dual_benchmark_v4/release/dagbt_benchmarks_v4_experiment.tar.gz | 2126556868 | 197 | `3d49b209d4c195af9ca00a2219407cc7c72cdb61b965ee7b5120246e931c65bc` | webwalker: 146/9/0 |
| 20261016_dual_benchmark_v4/release_v2/dagbt_benchmarks_v4_experiment.tar.gz | 2126561323 | 198 | `da005793826ce981b7a1f89d045af19327c149d8656741d0f9a47d3a902dff30` | webwalker: 153/3/0 |
| 20261016_dual_benchmark_v4/release_v3/dagbt_benchmarks_v4_experiment.tar.gz | 2126555634 | 198 | `ef078368011d27bad49f5293d502f4853fd2490d1e6489171019f42938f68146` | webwalker: 156/0/0 |
| 20261016_dual_benchmark_v4/release_webwalker_v2/dagbt_webwalker_v4_v2_experiment.tar.gz | 1623561 | 176 | `51bf40a60518e0f84159580fc186579958e3e47ac1482a34ac8552a662f9b648` | webwalker: 139/2/0 |
| 20261016_webwalker_v4_access_v13_experiment/candidate/dagbt_webwalker_v4_access_v13_experiment.tar.gz | 1438902 | 167 | `6e5945c56827ea04260661faad04739c06022809c7247052fa90b3c09c3eeec0` | webwalker: 123/10/0 |
| 20261016_webwalker_v4_access_v13_experiment/release/dagbt_webwalker_v4_access_v13_experiment.tar.gz | 1445104 | 168 | `d7acd57be15abb1c3347f4554cf5c89255f1d21feb720155d294288dfce23001` | webwalker: 123/10/0 |
| 20261020_prefeval_v4_experiment/dagv2_prefeval_v4_experiment.tar.gz | 69566930 | 426 | `e54cf55bbbacf88d87af3ac21c5ea58e062d423f60e17664e8e32f1fd2a414e2` | prefeval: 223/8/0 |
| 20261021_prefeval_v4_fix1_experiment/dagv2_prefeval_v4_fix1.tar.gz | 69568895 | 427 | `e4a589fcfa6d5d87948f32c9445714b53529e99a90c177a0553eaa065f1a6bae` | prefeval: 227/5/0 |

关系结论：PM 20261014包的所比较225份源码与保留PM全同；WebWalker dual release_v3的156份发布源码与当前WV4全同，但当前根还有更多源码/tests；v13仍有10处旧代码，不能替代当前WV4工作树备份。PrefEval旧包和fix1分别有8/5处所比较文件与fix3不同，因此不能当作fix3备份。fix3的最终目录/补丁交付本身需保留。

## 可删除的34个解包root与条件

绝对路径一行一条见 [deploy_source_roots.txt](./deploy_source_roots.txt)。**只允许精确匹配清单中的root，不使用dagv2_deploy/*之类通配删除。** 这些root之间无父子重叠。

删除前统一条件：

1. 对应原archive及.sha256保留；本次哈希结果已记录。需要未来还原的独有候选源码先做小型source-only快照tar（保留configs/docs/tests/package/serving/dagresolve等必要源码与元数据，排除data、outputs/results和可重建runtime/cache；本机凭据另存）。不要只存Git bundle，因为候选source及普通PrefEval拷贝未必是Git提交。
2. 移出下面列出的运行记录/凭据，保留相对位置映射及文件哈希；所有root外验证、分析、运行、patch与manifests保持原样。
3. 数据覆盖以 [deploy_data_coverage.json](./deploy_data_coverage.json) 为准；34root内数据全部已覆盖。清理时不跟随symlink；确认无运行进程以这些root作cwd/打开文件（root主流程另做检查）。
4. 15个有bundle_manifest的payload本次已对**全部声明文件**实际校验：missing=0/different=0/extra=0，见 [deploy_manifest_validation.json](./deploy_manifest_validation.json)。installed/candidate source则按本报告的源码快照、data coverage及exceptions分别保留；不要将源码子集一致性当作整个installed树无独有文件。

| 候选root（相对dagv2_deploy） | data files | 数据未覆盖 | 额外处理 |
|---|---:|---:|---|
| 20261015_webwalker_v4_access_experiment/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261015_webwalker_v4_access_experiment/stopped_gate_release/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261015_webwalker_v4_access_v2_experiment/release/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261015_webwalker_v4_access_v2_experiment/verified_extracted/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261015_webwalker_v4_access_v2_experiment/verified_install | 4 | 0 | 先安全保留本机凭据 |
| 20261015_webwalker_v4_access_v3_experiment/release/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261015_webwalker_v4_access_v4_experiment/release/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/extracted_webwalker_only_v2/dagbt_webwalker_v4_v2_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/installed_validation | 8 | 0 | 先移出outputs状态文件 |
| 20261016_dual_benchmark_v4/installed_validation_v2 | 8 | 0 | 先移出outputs状态文件 |
| 20261016_dual_benchmark_v4/installed_validation_v3 | 8 | 0 | 先移出outputs状态文件 |
| 20261016_dual_benchmark_v4/installed_webwalker_only_v2 | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/release/dagbt_benchmarks_v4_experiment/payload | 8 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/release_v2/dagbt_benchmarks_v4_experiment/payload | 8 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/release_v3/dagbt_benchmarks_v4_experiment/payload | 8 | 0 | 按原archive/源码快照保留 |
| 20261016_dual_benchmark_v4/release_webwalker_v2/dagbt_webwalker_v4_v2_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/candidate/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/current_validation/candidate_install/extracted/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/current_validation/candidate_install/installed | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/current_validation/final_install/extracted/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/current_validation/final_install/installed | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_access_v13_experiment/release/dagbt_webwalker_v4_experiment/payload | 4 | 0 | 按原archive/源码快照保留 |
| 20261016_webwalker_v4_local_repair/candidate_branch_review_v2/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_exploration_identity_v4/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_exploration_identity_v4_retry/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_grounding_review_v5/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_group_body_v11/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_group_members_v9/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_group_probe_v7/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_occurrence_feedback/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_review_scope_v10/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_root_diversity_v6/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_scope_protocol_v3/source | 4 | 0 | 独有旧source做小型快照 |
| 20261016_webwalker_v4_local_repair/candidate_stance_review_v8/source | 4 | 0 | 独有旧source做小型快照 |

### 必须先移出的例外文件

完整例外与链接清单：[deploy_removal_exceptions.json](./deploy_removal_exceptions.json)。本次roots内识别到3条运行记录和1份本机凭据（只报告路径，不读取/输出密钥内容）：

- `20261016_dual_benchmark_v4/installed_validation/outputs/benchmarks_v4_full/current_child.json`，112 B。
- `20261016_dual_benchmark_v4/installed_validation_v2/outputs/benchmarks_v4_full/current_child.json`，112 B。
- `20261016_dual_benchmark_v4/installed_validation_v3/outputs/benchmarks_v4_full/current_child.json`，112 B。
- `20261015_webwalker_v4_access_v2_experiment/verified_install/configs/credentials.local.json`，105 B；另存为0600，不能打入公开源码备份。

这些状态文件虽然很小，仍属于实验记录。`real_smoke*`、`candidate*/output`、`validation_evidence`、`current_validation`中的root外记录、分析脚本与报告不在删除allowlist。不要删除其父部署目录。

## 最重路径与真实可回收空间

`dagv2_deploy/20261016_dual_benchmark_v4`逻辑约20.72GB，du约15GiB。六个BrowseComp SQLite路径均为2,292,801,536 B，实际SHA256均为 `d8e2222aac1cdebe85f14c10a7d4ad1ee1cc7c04746c3f26a54280ca18ff2c79`。

- `installed_validation/data/browsecomp_plus/corpus.sqlite3`、`installed_validation_v2/...`、`installed_validation_v3/...`：三份独立inode；删除这三份副本可回收约6.878GB（约6.41GiB）数据库空间，另有少量源码/依赖。先保留其outputs状态文件。
- `release/.../payload/data/browsecomp_plus/corpus.sqlite3`、`release_v2/...`、`release_v3/...`与**当前保留WV4的data/browsecomp_plus/corpus.sqlite3**是同一inode（nlink=4）。移除三个payload链接不会回收这份数据库本体；当前最终数据仍然存在。不能把六路径都计成可回收13.76GB。
- 三份原始大archive分别约2.1266GB；按root方案全部保留，因此其合计约6.38GB不计为回收。
- `20261016_webwalker_v4_local_repair`逻辑约494MB，但里面大量是需要保留的output/分析记录；只删除列出的candidate*/source，不删除整个local_repair。
- `preparation/`约292MB，含shard、pyarrow依赖和准备日志，不在本次34root覆盖内；如要进一步去重，应单独核对数据/准备记录，不能顺手删除。

## 核验文件索引

- [deploy_archive_inventory.json](./deploy_archive_inventory.json)：15包原文件SHA、完整tar member清单、所选源码hash与最终目录比较。
- [deploy_source_tree_inventory.json](./deploy_source_tree_inventory.json)：34源码root、所选源码树指纹与7组重复源码树、6条SQLite路径的实际hash/inode。
- [deploy_manifest_validation.json](./deploy_manifest_validation.json)：15份已解包payload的全部manifest文件校验，全部通过。
- [deploy_data_coverage.json](./deploy_data_coverage.json)：34root逐datafile的当前/原archive同path同hash覆盖证据，未覆盖为0。
- [deploy_source_roots.txt](./deploy_source_roots.txt)：34条绝对路径allowlist。
- [deploy_removal_exceptions.json](./deploy_removal_exceptions.json)：3运行记录、1本机凭据、32软链接的移出/依赖清单。

本报告给出可实施条件，不代表任何删除已执行。清理前原目录、archive、Git和实验记录均未被本代理修改。
