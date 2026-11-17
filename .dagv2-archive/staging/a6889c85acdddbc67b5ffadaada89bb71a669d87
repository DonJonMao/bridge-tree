# R19 / 0cc2cc7 清理计划当前有效性核对

核对时间（UTC）：2026-10-13T21:55:35.175153+00:00

**结论：锁定清理范围仍与当前文件系统逐项一致；没有发现需要增加的旧部署包。未执行清理、移动或 metadata 保留复制，也未验证或替代当前正式发布的安装 gate。**

## 锁定身份与核对边界

- RELEASE HEAD（仅 git rev-parse）：`0cc2cc78498bcd215252fb8e82d2168868a71b3f`。
- cleanup_review.json SHA256：`f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84`，与指定锁定值一致。
- cleanup_plan.json SHA256：`88df5e5e4ac01850750ac4321514ef7eae00846bf587d0577778ce2025a2fa4e`，bytes 6,424，与 review 中记录完全一致；plan.completed=false。
- execute_reviewed_cleanup.py SHA256：`1dad740e4b3d756d785f30fb0758756ea35640b6c313e4c9b1680f3af05c2a4a`，与上次核对一致。只静态阅读，没有导入或运行，包括 dry run。
- 前一报告 cleanup_freshness_review_800c.md SHA256：`78899270863c9ac113ff34b391db6a119df24ece185d694cfa9ee099a3cc7d06`。前次核对时间为 2026-10-13T20:36:21.108378+00:00。
- 本次独立按固定 allowlist 对照 review 与 plan；14 文件和 3 staging 根的集合完全一致，不扩展原清理范围。
- 仅对授权旧归档、review 列明 staging 文件、外部重复验证记录及历史 Git blobs 读取字节以计算 SHA256；保护归档仅 stat，限定部署/scripts 搜索仅看文件名和元数据。没有解包 diagnostics，没有读取实验运行、标签或评分，没有运行测试、模型、网络或服务。

## 14 个归档及校验和

以下路径相对 /Users/mao/projects。所有文件的 regular-file 存在性、大小、SHA256、规范路径、无符号链接祖先与 hash 前后 stat 稳定性均通过。

| 文件 | 当前 bytes | 当前 SHA256 | 与锁定记录 |
| --- | ---: | --- | --- |
| `dagv2_deploy/20261011/dagv2_bt_deploy_20261011_personamem_v4.tar.gz` | 440,405,090 | `857dda2660999ea5e97ed97410c03adca79249d55e8e01303b745603df139e11` | 一致 |
| `dagv2_deploy/20261011/dagv2_bt_deploy_20261011_personamem_v4.tar.gz.sha256` | 112 | `129e389779243cd1b4dfe508dd3154dbb9abcea1e320b4df236b6c57d7f67e82` | 一致 |
| `dagv2_deploy/20261011_a48dc8d/dagv2_bt_deploy_20261011_personamem_a48.tar.gz` | 440,605,817 | `5ded0bbf92c1c0d63355ca3e5e226bb88913b20317136076fbfb23e67686efd4` | 一致 |
| `dagv2_deploy/20261011_a48dc8d/dagv2_bt_deploy_20261011_personamem_a48.tar.gz.sha256` | 113 | `5347fc42e08d3964a18e3006a54acd1d06d160373dd01bf0525c58622ca47ce0` | 一致 |
| `dagv2_deploy/20261011_a48dc8d_v2/dagv2_personamem_a48_v2_patch.tar.gz` | 60,256 | `7fb3ee7b1a05d8bfe6eaa3c3a6249a5d36c4b3f118bf97123f1d88be9daedb19` | 一致 |
| `dagv2_deploy/20261011_a48dc8d_v2/dagv2_personamem_a48_v2_patch.tar.gz.sha256` | 103 | `52b4137055493c4fc1f2c31d828bffbe541cb0114aae3e448aa345491d2ca80d` | 一致 |
| `dagv2_deploy/20261011_a48dc8d_v3/dagv2_personamem_a48_v3_patch.tar.gz` | 129,574 | `7e6b51f24bc9e5fd9ea15da55745ec88ba2d68044cd691c9ab4fb9577048e1e5` | 一致 |
| `dagv2_deploy/20261011_a48dc8d_v3/dagv2_personamem_a48_v3_patch.tar.gz.sha256` | 103 | `14a945b755684040014e3821c38f708012bd3804857e14c06fbfb9eb136f151d` | 一致 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/dagv2_personamem_a48_v3_1_patch.tar.gz.sha256` | 105 | `57fa4b71ca587db9e195cc37ad536a3461138cb469e7e8117f33f00cf32d04cb` | 一致 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/dagv2_personamem_a48_v3_1_patch.tar.gz` | 129,922 | `0df290ade5ec4044995690dc274fa880cbb69cee0ce39fe2c523fe055a340ac9` | 一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_patch.tar.gz` | 129,574 | `7e6b51f24bc9e5fd9ea15da55745ec88ba2d68044cd691c9ab4fb9577048e1e5` | 一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_1_patch.tar.gz.sha256` | 105 | `57fa4b71ca587db9e195cc37ad536a3461138cb469e7e8117f33f00cf32d04cb` | 一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_patch.tar.gz.sha256` | 103 | `14a945b755684040014e3821c38f708012bd3804857e14c06fbfb9eb136f151d` | 一致 |
| `dagv2/scripts/dagv2_personamem_a48_v3_1_patch.tar.gz` | 129,922 | `0df290ade5ec4044995690dc274fa880cbb69cee0ce39fe2c523fe055a340ac9` | 一致 |

合计 **14 文件 / 881,590,899 bytes**，无缺失、变化或范围新增。

## 3 个 staging 根、精确文件集合与可恢复性

| staging（相对 projects） | 实际/清单文件 | 当前/plan bytes | Git payload | 待保留 metadata | 其他已列明文件 |
| --- | ---: | ---: | ---: | ---: | --- |
| `dagv2_deploy/20261011_a48dc8d_v2/patch` | 9/9 | 200,013/200,013 | 5 | 4 | 外部重复验证 0；缓存 0 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | 24/24 | 457,658/457,658 | 17 | 5 | 外部重复验证 1；缓存 1 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | 18/18 | 553,763/553,763 | 11 | 5 | 外部重复验证 1；缓存 1 |

- 三个 staging 的精确文件集合均一致；所有目录与文件均为规范路径，无符号链接或未知对象。没有新增日志、遗漏文件或额外文件。
- 合计 51 个 staging 文件：33 个历史 Git payload、14 个必须先保留的 metadata/安装说明/安装器、2 个与外部相同的验证记录、2 个明确列入 review 的 CPython 缓存。
- 历史 Git 仓库为 /Users/mao/projects/dagv2-personamem-a48。以下三条 commit 均仍可访问；33 个 payload 均重新读取对应 git cat-file blob，当前 bytes/SHA256 与 review 和 staging 文件完全一致。
  - `54c3baefca943320b7a173f13dec381344d3feea`：5/5 个 payload 匹配。
  - `da64d56250733bc7a87942f6a5389b04a00176bd`：17/17 个 payload 匹配。
  - `a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1`：11/11 个 payload 匹配。

### 全部 staging 文件的当前字节身份

各分表路径相对该 staging 根；每个条目均与 review 的 bytes/SHA256 一致。Git payload 另经历史 blob 复核；其 SHA256 与同一文件表一致。

#### dagv2_deploy/20261011_a48dc8d_v2/patch

| 文件 | 当前 bytes | 当前 SHA256 | 类别 |
| --- | ---: | --- | --- |
| `patch.json` | 1,121 | `63cd24670ebe9196ba615a4ed3b2dd36cd7ab1442fffda122bc7193cd8eafa33` | 必须先保留 |
| `payload/DEPLOYMENT.json` | 38,056 | `9edb5b5abf27a8513ae51a82de5ece6dd9078769c77cebfd36d50dbce4b4c849` | 必须先保留 |
| `README.md` | 6,321 | `bd8bc99f49b0be4a12abffb9c433fa8767113892f8bc17190ec0fbedf15af704` | 必须先保留 |
| `apply_patch.py` | 4,757 | `89aa630459211dda0fa9efcb3395b154932cb920898f4f2e25062dc024b920fd` | 必须先保留 |
| `payload/dagbt/residual.py` | 27,942 | `49762cdd524fab2007c135560a85e3fef9da989129416f377b11df97b953e08c` | 历史 Git 可恢复 |
| `payload/dagbt/residual_plan.py` | 8,914 | `cb4e8ce95201f1f0b76e7e4ec7e7d9821106576b927c2291d06c89af89306720` | 历史 Git 可恢复 |
| `payload/dagbt/runner.py` | 91,346 | `6a8cc8ffc6e50bec5ca6609c28680f04df508345fe5fef3aff1ce955fa96aca3` | 历史 Git 可恢复 |
| `payload/docs/PERSONAMEM_A48_PLANNER_FIX_20261011.md` | 6,321 | `bd8bc99f49b0be4a12abffb9c433fa8767113892f8bc17190ec0fbedf15af704` | 历史 Git 可恢复 |
| `payload/tests/test_residual_planner_protocol.py` | 15,235 | `a66f56a888db59e525f95c0873b52323ef68d1ec197b0607f112b87dd39a5c6f` | 历史 Git 可恢复 |

#### dagv2_deploy/20261011_a48dc8d_v3/patch

| 文件 | 当前 bytes | 当前 SHA256 | 类别 |
| --- | ---: | --- | --- |
| `patch.json` | 2,965 | `8ae4ada55a74c12b50b99da8186e1cbc2c471c42dbd6e09fbd011be3eaa3028c` | 必须先保留 |
| `payload/DEPLOYMENT.json` | 59,848 | `59f51db1086ae9fdf521fd8050bc130d081b931414c08b1e5eabe0c6d7192909` | 必须先保留 |
| `README.md` | 8,647 | `517ce42c8f683d8a91aabe3c1854758aec1523639f92f895fa85478bccd49df3` | 必须先保留 |
| `apply_patch.py` | 4,777 | `56f76d4e5bf41e32a452dfc14d7394e2550bcf7505f3efb0b55a6302bf2b9fdb` | 必须先保留 |
| `install_and_smoke.sh` | 538 | `6508c99a1b736b32c1ad10a7d507b210188138a42e68aacb2f174b7f46a96347` | 必须先保留 |
| `payload/configs/residual-memory.personamem16k.json` | 1,384 | `ec4a7ddf03ccd83e5b04d85d063efb70f18efde5e5b710ae816fa4a06f972377` | 历史 Git 可恢复 |
| `payload/dagbt/bridge.py` | 41,462 | `c60570142d0c3ebaf8d37bf544bd945306963b93bd34a804d3125b3fbd479397` | 历史 Git 可恢复 |
| `payload/dagbt/joint_reading.py` | 43,254 | `389e9b90e93a48e0a00ef7adc6c14c26b04ac23d6cbb00cd467789432f2f3aae` | 历史 Git 可恢复 |
| `payload/dagbt/navigation_query.py` | 8,213 | `e6b3675f395f22d2b9a415c1b1c7d12dd8090d864f2937f8cf61da45fe6fffc4` | 历史 Git 可恢复 |
| `payload/dagbt/reasoning.py` | 14,795 | `ef5653512bc45c2dd589a245283fd6093fa09a11c11446b5f8d2acce034c8d75` | 历史 Git 可恢复 |
| `payload/dagbt/runner.py` | 93,749 | `c508a8ee00ea02ee4c7d2c33622fa251c6f75b5c789b1aaf50497878b5ba5066` | 历史 Git 可恢复 |
| `payload/dagbt/token_counting.py` | 11,380 | `cf2e78158e229fa567ef00b6f64624f44fca7a8e5b417fced53c0b86709535fa` | 历史 Git 可恢复 |
| `payload/dagbt/transport.py` | 14,871 | `9c974dd54e6f68243d29039b8e6c86567b9bc6c0ec91dec0e47659877e7189ee` | 历史 Git 可恢复 |
| `payload/docs/PERSONAMEM_A48_RUNTIME_FIX_20261011.md` | 8,647 | `517ce42c8f683d8a91aabe3c1854758aec1523639f92f895fa85478bccd49df3` | 历史 Git 可恢复 |
| `payload/docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md` | 11,305 | `d9d8af3d7517b75b1a66f197a3a7e348e83561db8107613b421662b105c4aa55` | 历史 Git 可恢复 |
| `payload/scripts/demo_residual_memory.py` | 16,920 | `987c3132e1037a23725d83547d7b3ba78f2318c196864ed25412f66ba3680051` | 历史 Git 可恢复 |
| `payload/tests/test_deployment_tokenization_integration.py` | 14,573 | `2ed09da56ad8585410325db56c42eb684b0da4a11810c286fb807b9a51bc4b2f` | 历史 Git 可恢复 |
| `payload/tests/test_joint_value_contract.py` | 10,565 | `1fe3aa4d1f76b38739028fe602633fdd3719e25a5499278239b633190a38683e` | 历史 Git 可恢复 |
| `payload/tests/test_joint_wire_serialization.py` | 4,466 | `2a2189c8a5c0b02db3973797be53cf04ef368fa702da4598d26831af82a1323a` | 历史 Git 可恢复 |
| `payload/tests/test_navigation_query.py` | 7,954 | `c1d4dfae1bd7898bfff51d928abc1dfecbdcf02f1a0fe08ad54c30a6a1482187` | 历史 Git 可恢复 |
| `payload/tests/test_personamem_joint_protocol.py` | 37,462 | `584dafaa77ba83c348e94df2d564e4fcc992f25bd900b1535acc54029f5ed564` | 历史 Git 可恢复 |
| `payload/tests/test_token_counting.py` | 10,720 | `3dcb6baa227b95bb3796e19be6bff87fcc99bab2d3ea77d68b4a37244340941a` | 历史 Git 可恢复 |
| `__pycache__/apply_patch.cpython-311.pyc` | 9,669 | `a788b998fafff3410ceebbff6338fd339e9baaa94fb5fdb96871348026dcf13c` | 已列明缓存 |
| `validation.json` | 19,494 | `5e4e77e53f4295527de8380ae119d4d78bbdcf41dc26debf7151db6e0745b5ff` | 有匹配外部验证副本 |

#### dagv2_deploy/20261012_a48dc8d_v3_1/patch

| 文件 | 当前 bytes | 当前 SHA256 | 类别 |
| --- | ---: | --- | --- |
| `patch.json` | 2,009 | `e79ac2808de0eb5041fd0828a5e8ecf127b77c960d0f15ef90118d26916d1e99` | 必须先保留 |
| `payload/DEPLOYMENT.json` | 135,585 | `d93701a9e43eca5250f9022b76f69f5505d93d0da59ecc9b213f0e944301ff33` | 必须先保留 |
| `README.md` | 6,735 | `f6be3a6433c9b233e01e844d0dc9cf70346b85858f32b01a15fe0be3588ef85a` | 必须先保留 |
| `apply_patch.py` | 4,783 | `27844c66856dc2e8e0f31bffbe0e1861c85c3dabbb052b64b92b06c9eef5476c` | 必须先保留 |
| `install_and_smoke.sh` | 540 | `b80e10df99024937d416ae85781d841354c6e546c67683a018796bab402de642` | 必须先保留 |
| `payload/dagbt/fact_state.py` | 10,441 | `08bdc7b4c3cb79bf2503d71ce68d4adc350a902fc05a40cb5aa3ac7800e1b672` | 历史 Git 可恢复 |
| `payload/dagbt/joint_reading.py` | 44,359 | `77337892d94e0d0d6ef74da870ef01dc812ccd3912c59db73ff0faad48d5aabb` | 历史 Git 可恢复 |
| `payload/dagbt/residual.py` | 28,790 | `893b6cd0e2b50fa6ad013a5961785534283f7487ecf5750b62c198ba3269cada` | 历史 Git 可恢复 |
| `payload/dagbt/residual_control.py` | 40,370 | `f60aabfc195c764962c0962964374c0c615871c522c20e362565a28de973ba8e` | 历史 Git 可恢复 |
| `payload/dagbt/residual_plan.py` | 10,367 | `7094954b2083ad1ad74be0a931660983e82a0bc1463f1d0a16fdd3864aec4131` | 历史 Git 可恢复 |
| `payload/dagbt/runner.py` | 94,040 | `6a36bb00e15706068a3ba3a316d8e73f5703aab5a636d50d97a2e8294717214a` | 历史 Git 可恢复 |
| `payload/dagbt/token_counting.py` | 14,808 | `752158005dd27ee16707fcd21ce4675ad4b2371165c0ac2f57cf65ea135868ab` | 历史 Git 可恢复 |
| `payload/docs/PERSONAMEM_A48_SCOPE_FIX_20261012.md` | 6,735 | `f6be3a6433c9b233e01e844d0dc9cf70346b85858f32b01a15fe0be3588ef85a` | 历史 Git 可恢复 |
| `payload/tests/test_deployment_tokenization_integration.py` | 17,246 | `bbe285741f24eab8868aee47dfad9b619dd79ee775018740f0cfbbe07f1d611e` | 历史 Git 可恢复 |
| `payload/tests/test_token_counting.py` | 18,132 | `58e54137bdc8b82a1ce915f25cfac05ca37b479d7475f9017ceed1307aa1693e` | 历史 Git 可恢复 |
| `payload/tests/test_variable_scopes.py` | 17,894 | `bc8557bdb436a09039412b54ceb1f54cc1ee113f4e7e22fd38f55dc6fb478ce3` | 历史 Git 可恢复 |
| `__pycache__/apply_patch.cpython-311.pyc` | 9,677 | `81aeac58756e72031db8b1f5e3883937d4a52b3969ff60d06edc9f00bc20c816` | 已列明缓存 |
| `validation.json` | 91,252 | `0e4f85e2651569772a8c271a44712963b74556f3d49b517e589b9c9ae3accae6` | 有匹配外部验证副本 |

## 14 份 metadata 保留计划

保留根固定为 /Users/mao/projects/dagv2_analysis/personamem_v4_validation/historical_deployments。以下源文件都已校验哈希；目的副本当前 **0/14 存在**，总计 **276,682 bytes**。本次未创建任何保留副本，正式清理必须先复制并逐一验证全部 14 份。

| 原 staging | 源相对路径 | 目的相对 historical_deployments | 当前目的存在 |
| --- | --- | --- | --- |
| `dagv2_deploy/20261011_a48dc8d_v2/patch` | `patch.json` | `20261011_a48dc8d_v2/patch.json` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v2/patch` | `payload/DEPLOYMENT.json` | `20261011_a48dc8d_v2/payload/DEPLOYMENT.json` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v2/patch` | `README.md` | `20261011_a48dc8d_v2/README.md` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v2/patch` | `apply_patch.py` | `20261011_a48dc8d_v2/apply_patch.py` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | `patch.json` | `20261011_a48dc8d_v3/patch.json` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | `payload/DEPLOYMENT.json` | `20261011_a48dc8d_v3/payload/DEPLOYMENT.json` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | `README.md` | `20261011_a48dc8d_v3/README.md` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | `apply_patch.py` | `20261011_a48dc8d_v3/apply_patch.py` | 否 |
| `dagv2_deploy/20261011_a48dc8d_v3/patch` | `install_and_smoke.sh` | `20261011_a48dc8d_v3/install_and_smoke.sh` | 否 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | `patch.json` | `20261012_a48dc8d_v3_1/patch.json` | 否 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | `payload/DEPLOYMENT.json` | `20261012_a48dc8d_v3_1/payload/DEPLOYMENT.json` | 否 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | `README.md` | `20261012_a48dc8d_v3_1/README.md` | 否 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | `apply_patch.py` | `20261012_a48dc8d_v3_1/apply_patch.py` | 否 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/patch` | `install_and_smoke.sh` | `20261012_a48dc8d_v3_1/install_and_smoke.sh` | 否 |

### 外部已有验证记录与其他保留文件

两份外部重复验证记录重新哈希均匹配原 staging 与 review：

- `/Users/mao/projects/dagv2_deploy/20261011_a48dc8d_v3/validation.json`：19,494 bytes，SHA256 `5e4e77e53f4295527de8380ae119d4d78bbdcf41dc26debf7151db6e0745b5ff`。
- `/Users/mao/projects/dagv2_deploy/20261012_a48dc8d_v3_1/validation.json`：91,252 bytes，SHA256 `0e4f85e2651569772a8c271a44712963b74556f3d49b517e589b9c9ae3accae6`。

plan 列明的 12 份清理范围外验证/说明文件均存在、规范路径及大小匹配。旧 plan 未记录这些条目的 SHA256，因此只确认 existence/size；不声称 12 个文件都已证明字节未变。上述两份重复验证记录有单独 hash 证据。

| 文件 | 当前 bytes | 大小匹配 |
| --- | ---: | --- |
| `dagv2_deploy/20261011/deployment_validation.json` | 598 | 是 |
| `dagv2_deploy/20261011/PERSONAMEM_RESTART_20261011.md` | 9,699 | 是 |
| `dagv2_deploy/20261011_a48dc8d/verification.json` | 690 | 是 |
| `dagv2_deploy/20261011_a48dc8d/PERSONAMEM_A48_RESTART_20261011.md` | 9,428 | 是 |
| `dagv2_deploy/20261011_a48dc8d/offline_preflight.json` | 14,565 | 是 |
| `dagv2_deploy/20261011_a48dc8d_v2/live_planner_probe.json` | 26,628 | 是 |
| `dagv2_deploy/20261011_a48dc8d_v2/PERSONAMEM_A48_PLANNER_FIX_20261011.md` | 6,321 | 是 |
| `dagv2_deploy/20261011_a48dc8d_v2/verification.json` | 824 | 是 |
| `dagv2_deploy/20261011_a48dc8d_v3/validation.json` | 19,494 | 是 |
| `dagv2_deploy/20261011_a48dc8d_v3/installer_verification.json` | 486 | 是 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/validation.json` | 91,252 | 是 |
| `dagv2_deploy/20261012_a48dc8d_v3_1/installer_verification.json` | 486 | 是 |

## 唯一 diagnostics、原始记录和源工作树保护

以下只核对文件元数据，没有打开、解包或计算保护归档的内容 hash。全部存在、大小与上次核对相符，且在清理文件/目录集合之外。

| 保护文件 | 当前 bytes | 清理范围外 |
| --- | ---: | --- |
| `/Users/mao/projects/dagv2/scripts/personamem_v3_1_diagnostics.tar.gz` | 924,139,875 | 是 |
| `/Users/mao/projects/dagv2/scripts/dagv2_results_20261008_025515.tar.gz` | 397,869 | 是 |
| `/Users/mao/projects/dagv2/scripts/dagv2_a48_v2_smoke_debug.tar.gz` | 150,719,323 | 是 |
| `/Users/mao/projects/dagv2/scripts/dagv2_a48_v3_smoke_debug.tar.gz` | 46,580,122 | 是 |
| `/Users/mao/Downloads/dagbt_webwalker_a5_v1.tar.gz` | 637,097 | 是 |
| `/Users/mao/Downloads/dagbt_webwalker_a5_v1.tar.gz.sha256` | 95 | 是 |
| `/Users/mao/Downloads/evidence_logs_start_20260927_034132_625737_20260930_030305_3729264.tar.gz` | 295,192,359 | 是 |
| `/Users/mao/Downloads/evidence_logs_start_20260927_034132_625737_20260930_030305_3729264.tar.gz.sha256` | 140 | 是 |

在下面明确限定的文件名扫描范围内，personamem_v3_1_diagnostics.tar.gz 仅发现 **1 份**，为 /Users/mao/projects/dagv2/scripts/personamem_v3_1_diagnostics.tar.gz，924,139,875 bytes（881.33 MiB）。这是限定范围内的唯一性，未扫描整个用户磁盘，不外推全机唯一。

| 源工作树 | 目录/.git 存在 | 与 staging 删除根重叠 |
| --- | --- | --- |
| `/Users/mao/projects/dagv2` | 均存在 | 无 |
| `/Users/mao/projects/dagv2-personamem-a48` | 均存在 | 无 |
| `/Users/mao/projects/dagv2-personamem-v4` | 均存在 | 无 |
| `/Users/mao/projects/dagv2-personamem-v4-reconcile` | 均存在 | 无 |

dagv2/scripts 下仅 4 个在归档表中明确列出的旧补丁/校验和属于已审定例外；工作树本身、源码、Git 对象、实验输出与日志不在删除集合。其余三个工作树下没有归档删除候选。没有读取工作树实验数据或 live writer 状态。

## 清单外部署包检查

本次文件名/元数据扫描范围为：

- `/Users/mao/projects/dagv2_deploy`
- `/Users/mao/projects/dagv2/scripts`
- `/Users/mao/projects/dagv2-personamem-a48/scripts`
- `/Users/mao/projects/dagv2-personamem-v4/scripts`
- `/Users/mao/projects/dagv2-personamem-v4-reconcile/scripts`
- `/Users/mao/projects (only top-level dagv2*/personamem* archive filenames)`

递归扫描不跟随符号链接，并排除 .git、.venv、__pycache__；仅记录文件名含 dagv2/personamem 的 tar.gz、tgz 及其 sha256。Downloads 只 stat 上表明确列明的保护路径。

扫描结果：
- 匹配归档/校验和 18 项，其中锁定清理候选 14 项，明确保护的 debug/results/diagnostics 4 项。
- 其余未列明候选 0 项。当前限定范围未发现新增 DAGV2 deploy/patch 包；没有将任何新包或其他工程文件判为可删。

## 清理脚本静态结论与真实发布 gate

脚本的固定范围仍为 14 文件与 3 staging 根。静态检查确认：

1. 校验锁定 review hash、精确允许集合、规范路径，以及全部目标的当前 size/hash；staging 必须精确匹配已列文件，历史 Git payload 与外部验证副本必须可恢复/可核对。
2. 安装 gate 要求完整通过的新归档安装收据，并检查对应包 hash、checksum、DEPLOYMENT.source_commit 与 validation.source_commit/release_ready；新包不得落入删除范围。
3. 所有 14 份 metadata 先复制并校验，再重验 gate/review/全部待删对象；随后仅逐个删除白名单文件并记录收据，目录非空则停止，不通配清扫新日志。
4. **脚本未把 source_commit 固定为当前 R19 / 0cc2cc7，也不会自动证明输入收据就是本次最终版本。** 必须由正式发布流程提供当前最终发布的真实通过收据；不能使用旧版本收据替代。本次没有验证该 gate，未确认 R19 通过或 release_ready，也没有授权执行。

## 相比前一报告

锁定 review、plan、脚本、14 归档、3 staging 的 51 文件、33 Git payload、保护文件大小、四个工作树和 0/14 metadata 保留副本状态均没有发现变化。当前只读确认的 RELEASE 身份为 0cc2cc78498bcd215252fb8e82d2168868a71b3f。新增旧包数量为 0（限上述范围）。

本次唯一新增文件是本外部 freshness 报告。未删除、移动、重写或复制任何归档/staging/metadata；未执行清理脚本，未触及实验运行或服务。

