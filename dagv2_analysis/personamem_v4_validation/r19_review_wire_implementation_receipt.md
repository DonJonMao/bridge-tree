# R19 review-wire implementation receipt

Owner: `/root/control_v4`. Worktree: `/Users/mao/projects/dagv2-personamem-v4-reconcile`, base `0cc2cc78498bcd215252fb8e82d2168868a71b3f`.

Implementation and this owner's new test file are frozen at the hashes below. No commit, full suite, tokenizer, external service, model request, RELEASE edit, label read, score read or experiment process operation was performed by this owner.

## Implemented boundary

- Added `dagbt/review_wire.py` exposing `pack_with_status`, `unpack`, `INSTRUCTION`.
- Changed only `JointReader._prepare_wire` in existing production source, running the existing history layer first and the independent review layer second with independent applied flags/instructions.
- Exact string sharing covers only the reviewed explicit parent/known/validated/failed/whole-value/repair paths. Nullable failure observation/slot fields are supported because actual producers emit them. Old known tables are preserved without decoding cells; unregistered frozen/application/source/raw fields stay literal.
- Every visited row is scanned for both new reserved reference fields before replacements. Malformed containers, reserved collisions, unsupported serialization and no net byte benefit cause complete layer fallback. Decoder rejects bad pools, reference types, missing keys and literal/reference conflicts.
- Original field positions, roles, metadata, order and JSON types are retained. Literal pool values are looked up once. Encoder round-trip compares full unsorted UTF-8 JSON with `allow_nan=False`; tests also use an independently written inverse.
- Byte candidate selection includes the added system instruction. Exact production token admission, source/owner/state/repair/publication guards and output schema are untouched. Model output references remain rejected by the existing observation guard.

## This owner's tests

Final command:

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_review_wire.py
53 passed in 0.53s
```

An initial 49-case run had one test-fixture `KeyError: variable` before reaching the helper; adding the missing schema fields to the new synthetic fixture produced 49 passed. Four explicit history-collision/review-applied cases were subsequently added, resulting in the final 53 passed above. No existing tests were edited.

Coverage includes no-parent sharing; all registered review paths; roles, scopes, counter stance, source/version metadata; typed nested literals; key order and Boolean/integer/float distinctions; raw invalid responses including malformed text; old table literals; noncandidate-row collisions; malformed containers and decoder references; no net benefit; deterministic/nonmutating transforms; both layers' independent flags; mocked estimate payload/schema/options invariance; and unchanged rejection of input-only references in model outputs. Tests do not call a tokenizer or external model.

Existing related-test compatibility run:

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_history_wire_review.py -k 'not estimate and not estimation and not actual_read and not terminal_only_repair'
5 failed, 41 passed, 6 deselected in 0.39s
```

The five failures are four parameters of `test_prepare_collision_keeps_old_wire_and_never_adds_reference_instruction` and `test_prepare_has_no_stale_applied_status_between_requests`. They assert that a history-layer collision leaves the entire prepared wire physically unchanged. With the authorized independent review layer, history collision still leaves history fields literal and adds no history instruction, while review sharing may legitimately apply. The new four-case test verifies that review inverse exactly restores the history-collision input, and only the applied review instruction is added. These existing assertions were reported to root for reconciliation, not silently changed or counted as passing. There is no claim that all existing tests or the full suite passed.

The separate contracts owner reported 117 independent tests passed; its signed report/receipt and test hash are separate evidence, not a run by this owner.

## Frozen SHA256

| File | SHA256 |
| --- | --- |
| `dagbt/review_wire.py` | `d7d9174ea9f0b319f6fc994adce866d2ad494f83b5316382511d52dcfd8e75fb` |
| `dagbt/joint_reading.py` | `47290d56d15a7e2b5998254ccb89f08e0eca53f784ae1c0a5b6d65e11c5c07a4` |
| `tests/test_v4_review_wire.py` | `f8280a26a8c3abf6faceccf33ceb164b4fca06ddc017080a8c6567a03853bc32` |
| unchanged `dagbt/history_wire.py` | `1117bc614be0205fa1ef7a65dd0b1a111069ab65da60acf2ff35a9f1a0fe3cb9` |
| unchanged `dagbt/residual_control.py` | `b22de008c594fe8b5c50fc0a63c9001aa83178cc92cd2b2119f79ea0431d7211` |

## Limits

This receipt proves the tested representation boundary only. No R19 saved wire was token-counted by this owner. No claim is made that the new wire saves 367 tokens, fits 16K, makes case01 complete, improves model understanding, or improves accuracy. Root owns any saved-wire replay, old-test reconciliation, broader verification, documentation, commit, deployment and subsequent runtime validation.
