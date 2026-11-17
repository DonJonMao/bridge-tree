# R18 release pipeline preflight

Read-only review of RECONCILE commit `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`. RECONCILE and RELEASE were both clean at the end of this review; RELEASE remains `bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94` while R17 is active. No checkout switch, test rerun, approval invocation, archive build, installation, service call, label read or cleanup was performed. Only this external report was written.

## Conclusion

The existing build, install and final-archive verification code accommodates the new committed source set without a production change or relaxed gate. The external approval verifier already accepts the exact new whole-suite command. The outstanding incompatibilities are deliberately truthful identity/state boundaries and stale execution documentation: the new source has not been installed into RELEASE or passed its own model smoke. Old R17 model evidence cannot approve the new source.

## Independently checked inventory

| Identity | Current RECONCILE result | Consequence |
| --- | --- | --- |
| Git source inventory | 303 regular tracked blobs; 76,172,723 bytes | Dynamic enumeration covers both added test files |
| Release path/object rules | No disallowed path or object; generated metadata is untracked | Current build policy accepts the entire committed set |
| Expected tar member count | 305: 303 committed files plus `VALIDATION_PERSONAMEM_V4.json` and `DEPLOYMENT.json` | No 301/303 hard-coded archive count needs changing |
| Runtime source inventory | 104 files, exactly equal to `reconcile_8dac32b_validation.json.source_hashes` | Count stays 104, but two hashes changed |
| Changed runtime hashes from R17 | `dagbt/joint_reading.py`, `dagbt/residual_control.py` | A fresh model manifest is mandatory |
| Frozen installation assets | 57 entries: 54 tracked/packaged, 3 reused vectors | Existing asset-copy and idempotence checks apply |
| Tracked pytest files | 85 files matching `test_*.py` or `*_test.py`; none outside `tests/` | Explicit `pytest -q tests` covers the committed default test-file inventory |

The reused vectors are the existing `passage_vectors.npy` for `2wikimultihopqa`, `hotpotqa` and `musique`. `scripts/build_personamem_v4.py`, `scripts/install_personamem_v4.py`, `scripts/personamem_v4.sh`, `scripts/personamem_v4.py`, `configs/personamem-v4.json` and `original_manifest.json` have identical Git blobs in 8dac32b and bcbd16f. The public config SHA-256 remains `6b16e1579ef1c7f83e15c0b5b6aae84ba21f45fe664de4a5bf1e4a80f5556e05`.

## Why each pipeline stage still covers the candidate

`scripts/build_personamem_v4.py:37` requires a clean checkout, approved exact full HEAD and the baseline ancestor. At line 51 it enumerates every committed blob through `git ls-tree -rz --full-tree`, reads blob bytes rather than mutable working-tree bytes, adds the two metadata files, scans for supplied private literals and round-trips the complete tar. Its return count is dynamic. There is no source-file count or runtime-count constant to update. The build script alone does not verify the test/model claims inside the supplied approval; the strict external approval step remains necessary.

`scripts/install_personamem_v4.py:84` verifies every entry in the generated release manifest. `frozen_assets` at line 97 enumerates every frozen asset in the original manifest and permits only the three existing vector-path classes to be missing from the package. `install` at line 245 validates the public config, checks unmanifested files, plans protected local credentials, copies/verifies missing vectors, reuses only a compatible completed derived index and rechecks the package/assets. This change added no installation dependency, new index type, credential field or asset class.

`verify_final_archive_install.py:147` compares the archive metadata and every source member against the named commit's dynamic Git tree and blobs. The bound is 10,000 members/1 GiB, comfortably above the expected 305 members and approximately 76 MB committed source bytes. The verifier separately checks two real isolated installations, all manifest assets, exactly three copied vector files with distinct base inodes, protected credentials, the production index inspection, unchanged packaged bytes, status/help and zero network attempts. The runtime count of 104 is not confused with the source/tar count or asset count. No hard-coded 301-source assumption exists in the verifier.

`prepare_source_approval.py:93` now accepts only the existing four-argument Python pytest form or the exact five-argument form ending in `tests`. The latter requires a clean checkout and verifies that the committed default test-file inventory is nonempty and entirely under `tests/`. Selectors and subsets remain rejected. Both `verify_test_log` calls receive the checkout root. This was already independently probed; it was not rerun here. Test-log digest and exact all-passed summary, matching-release attestation, full expected commit, source/config hashes, fixed 14-question paired model run, all 28 current rows and the production model gate remain mandatory.

## Exact record updates required when upgrade is actually permitted

These are future record updates, not permission to change RELEASE while R17 is alive. Preserve the current R17 candidate and actual run as historical evidence before promoting the next candidate.

| Record/field | Required value/evidence for this candidate |
| --- | --- |
| Candidate `source_commit` and CLI `--expected-commit` | `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8` after the actual upgrade; use a later commit if source changes again |
| Candidate `release_ready` | Remains `false`; only strict approval creates a separate approved record after model success |
| Candidate `source_hashes` | Exact 104-entry map in the new-source record, with the two changed runtime hashes |
| Candidate `config_sha256` | Rechecked public config hash above; no config change is presently required |
| `offline_tests.command` | Exact `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`; do not rewrite the execution command to the old four-argument form |
| `offline_tests.passed`, `warnings`, `seconds`, `exit_code` | Existing actual full20 evidence: 1880, 69, 106.15, 0 |
| `offline_tests.report` | `/Users/mao/projects/dagv2_analysis/personamem_v4_validation/full_tests_20_proof_scope.txt` |
| `offline_tests.report_sha256` | `98023913f92ea84c12bb2a48c7e56768b57c536861f92b3cd23ead45ba979ed7` |
| `offline_tests.receipt` / `tested_files` | Existing `full_tests_20_proof_scope_receipt.json` / 303 |
| `offline_tests.runtime_matches_release` | Currently correctly `false` in the reconcile record. Set to `true` only after the actual release checkout and tested/committed bytes have been reverified identical |
| `model_smoke.output` | A new actual run directory; planned `outputs/v4_validation_r18`, never R17 reuse |
| `model_smoke` process/state/manifest fields | Record only the new actual PID, state, writer status and new manifest digest as they exist; do not copy R17's PID or manifest hash |
| `model_smoke.questions`, config, label policy | Fixed 14, `configs/personamem-v4.json`, `labels_used_for_selection=false`; paired arms unchanged |
| Model success | The new run must reach `complete`, `failed_arm_tasks=0`, no live writer, and strict production `check` passed on all 28 rows |
| Source approval, tar/install receipts | New actual output records for the exact successful source and archive; no prefilled success or reuse of old model evidence |

The raw full20 execution receipt must stay unchanged: it correctly records testing in RECONCILE and the previous base HEAD with matching before/after source snapshots. The separate new-commit verification establishes that those 303 tested bytes equal commit 8dac32b. Do not relabel the original test location/base commit as though the suite had run elsewhere. No full-suite rerun is required solely to change the candidate document if bytes remain identical.

## `release_commands.md` changes to make before following its future commands

The reviewed copy still states both worktrees are bcbd16f, full19/1838/106.30 seconds, 301 source files, and R17 as the model run. Those statements describe the prior snapshot and must be updated or explicitly marked historical. In particular:

1. Describe the current split correctly until upgrade: RELEASE bcbd16f/R17, RECONCILE 8dac32b/full20. Retain the prohibition on switching the active RELEASE checkout.
2. After permitted integration, update the hard-coded `test "$DAGBT_RELEASE_SOURCE" = ...` assertion to the actual final commit and update `DAGBT_RELEASE_TEST_LOG` to full20 for this source.
3. Set `DAGBT_RELEASE_SMOKE` to the new actual output, expected R18, and preserve R17 launch commands/results as history rather than instructions to rerun R17.
4. Update source/tar counts to 303/305, full20 metrics and log SHA, and describe proof-input projection plus its conservative review protection. Runtime 104 and frozen assets 57 remain the same counts.
5. Continue passing `--source-repo "$DAGBT_RELEASE_REPO"` and the exact expected commit to archive verification. That repository must actually contain the named committed source; the current default path is the still-frozen RELEASE.
6. Keep source approval, actual tar installation and cleanup as distinct real receipts. Existing reviewed cleanup paths/hash and final tar path need no change merely because the source count increased. All exclusive-output paths must still be checked fresh before execution.

At review time `source_approval_final.json`, `final_archive_installation.json` and the planned final `dagv2_personamem_v4.tar.gz` do not exist. This is consistent with the unpassed model gate. No remaining command-parser or file-count code incompatibility was found; actual new-source model success and final archive installation remain unverified.

## Reviewed-file hashes

* `scripts/build_personamem_v4.py`: `32114ee5a7e33726998691b5ff843eb58646ad8492b26c57198ca7ed15515ce5`
* `scripts/install_personamem_v4.py`: `439a1ace87629dc0ff13d7da00e3e0be44dcc2464bbbc2d5f3375800a6d5f27b`
* External `prepare_source_approval.py`: `84d59d9c0f6b7fd6b3efc4bef7810a7219da0f7c282a5c52cf16248d7c8b596d`
* External `verify_final_archive_install.py`: `c89fbd9fb6711d4811eac6d9a985963e4fb29b9c15a05c52198eb75255afda1a`
* Reviewed historical `release_commands.md`: `bb777fc5063acdb57f696e1f4e0a16de36b11afce58b6d391de5fa9854a14a49`
