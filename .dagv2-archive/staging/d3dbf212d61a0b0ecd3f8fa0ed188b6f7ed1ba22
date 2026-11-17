# Discovery frontier: Full21 production follow-up

This is an additive report. The first implementation report and Full21 tested snapshot remain historical records; neither is rewritten to imply a clean initial result.

## Evidence and authorized scope

Root's immutable Full21 record reported **5 failed, 1927 passed, 69 warnings, 107.68 seconds** on the first frozen source. Root authorized only the concrete production regressions below. The fifth failure was a log-only snapshot assertion owned and corrected by root. RELEASE remains frozen; this follow-up did not commit, invoke HTTP/model services, run a full suite or modify RELEASE.

## 1. Scope guard rejection must remain side-effect free

Three variants of the existing `test_scope_rejection_preserves_reader_and_source_ownership_before_counting` failed because the new outer exception handler unconditionally copied pre-existing hard obligations into `state.pending`, even when the mandatory-scope guard rejected the call before any work or counting.

The handler now compares the before/after hard-obligation state and exposure count. It synchronizes pending only if hard work actually changed or an attempted exposure was entered. A rejected scope cannot mutate the previous fact state, source ownership, active reader identity, events or budgets. Actual interrupted work still becomes visible to the free residual evaluator. Existing guard tests were retained unchanged.

## 2. Restore stable originals, not ephemeral aliases

`test_durable_feedback_keeps_stable_ids_and_rebinds_every_alias_after_checkpoint` exposed that the first new exposure validator required an old temporary source alias to exist in the current mapper. The original source and all its metadata were unchanged.

New snapshots include `source_namespace`: each saved alias is bound to its stable source ID, document ID and complete original-span hash. Restore validates a unique current original with that stable identity and hash, then builds the old-to-current alias mapping. Alias permutation, including when every old alias still exists but now denotes a different original, is legal. Different text, role, temporal metadata, offsets or adjacency is rejected.

Execution state is rebound consistently: frontier keys/current source aliases, unread source keys, `read_states` and clues. `restore_obligations` returns the rebound reader snapshot, and `ResidualControl.restore` uses it instead of overwriting the reader with old alias indices. Failed-obligation batch identities and paid failed-review IDs are not remapped as source aliases. Legacy snapshots lacking stable namespace provenance retain their existing hard interpretation; no original is guessed from a name.

Historical request provenance remains explicit. An exposure's `source_alias` and `request_identity` still describe its actual archived wire; a separate `current_source_alias` identifies its current binding for restore checks. Promotion origins retain their discovery alias with the same explicit current binding. Active frontier metadata uses the current alias and retains `source_alias_history`. This history is excluded from strict current-context comparison so a legally restored frontier can actually resume.

## 3. Alias changes cannot buy progress or retry eligibility

The old material signature hashed temporary aliases inside read states, unread source keys and clues. Rebinding these aliases while retaining the controller's opaque `read_attempts`, `read_effects` and compose guards would change its material identity merely because of renaming. No extra live model request was observed; the inconsistency was identified by code review and direct state tests.

Those source-keyed signature fields now normalize to `['source', stable_source_id]`. Unknown aliases retain the distinct tagged form `['unavailable_alias', original_alias]`; they are not guessed or conflated with known originals. Failed-obligation batch identities remain unchanged. Source namespace and all new queue/history logs stay excluded from semantic progress.

Direct alias-permutation restore tests establish identical before/after material signatures. The independent real-controller resume case additionally checks unchanged opaque guards, no reread of already exposed originals, preserved budget accounting, and successful resumption of the ordered remaining frontier.

## Targeted validation

- Original production regression files plus implementation tests: **40 passed, 0.63 seconds**. This includes all three original mandatory guard variants, durable stable-ID feedback recovery, and a new stable material-signature/ownership test. No existing source/pending guard assertion was weakened.
- Independent new alias boundary group: **5 passed, 1.26 seconds**. It covers true alias permutation; frontier order and real continuation; archival exposure/promotion ownership; stable signature and opaque guards; actual controller restore; and rejection of changes to exposed text, promoted source role or frontier time metadata.
- One independent fixture correction registered an externally injected source in engine spans before controller resume; the earlier `unknown_span` failure was not a production regression.
- Frozen-hash independent full file: **35 passed, 1.43 seconds**, with matching before/after source hashes. Test SHA256 `2f11c6d7ae9f25588c8a98b9fbd0424ff28d1e964d503bd1becc7f8bba04ded6`; final2 receipt SHA256 `cb8a934f3edf499727f74b468dda0735ecf806ac41e296017c03a8648de10337`. Root owns full-suite 22; no full-suite success is claimed by this report.
- `git diff --check` passed. A separate read-only production review found no confirmed outstanding issue on the second frozen hashes.

## Second source freeze

- `dagbt/joint_reading.py`: `f5568ea4ad837dc32f8ebfb94afae4516efb5bb20f83dccdb2e0904eb94710eb`
- `dagbt/residual_control.py`: `b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211`
- `tests/test_v4_discovery_frontier.py`: `dbdfde98e371660a77114cbac24ff29bc93b6721ce646e269ef653ecfd758c66`

This follows the same general ordinary-residual policy and conditional semantic guarantees as the first report. It does not establish real-model accuracy or authorize reinterpretation of R17/older runs. A fresh source/run identity remains required.
