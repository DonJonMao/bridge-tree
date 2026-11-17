# R20 review-wire actual-token selection implementation receipt

Owner: `/root/control_v4`. Authorized worktree: `/Users/mao/projects/dagv2-personamem-v4-reconcile`, base `6c046374008ce2e45f817d6bc9876b3ab927ab18`.

This owner's production/test changes are frozen at the SHA256 identities below. RELEASE/R20 were not changed. No existing tests, Reasoner, Transport, counter, codec or config were edited by this owner. No service/tokenizer/model endpoint, full suite, commit or run-management command was invoked in this implementation task. Test HTTP/model responses are explicit local fakes.

## Implemented API and semantics

- `JointReader._wire_candidates(data)` returns independent `(wire, system)` pairs, with the complete history-after/review-before baseline first and at most one review candidate second. Construction is pure; each system includes exactly its applicable decoding instructions.
- `_prepare_wire(data)` remains the pure byte-proposed compatibility representation. Its docstring explicitly says it is not final actual-token selection.
- `_select_wire(operation, candidates, schema=None, *, output_token_cap=None)` uses actual `Reasoner._payload` serialization and the same production `_count_payload` path, returning `(wire, system, accounting)`. It selects review only if both counts explicitly have `token_count_is_estimate is False` and review is strictly smaller. Equal/larger counts select baseline. A nonactual baseline skips optional candidate counting; a nonactual candidate selects baseline. Count errors propagate unchanged.
- `_estimate` returns the same selector's chosen count. Both actual production request sites construct candidates at the old pure preparation locations and pass them through the new `wire_candidates` keyword to `_request_with_exposure`.
- Actual selection occurs inside the wrapper's existing try, after attempted source exposure/unread bookkeeping. A tokenizer error therefore retains the existing failed/not_sent semantics and does not increment Reasoner sequence or send a request.
- Actual operation/schema/cap/reserve options pass unchanged to the existing Reasoner request. Final Reasoner/Transport counts, context checks, usage checks and existing bounded retries remain intact. There is no new cache, budget reservation, fallback-on-service-error, source trimming, cap reduction, permission change or canonical identity change.
- The wrapper's old single `(wire,system)` compatibility path is counted normally; it does not prove a multi-candidate nonincrease result. Both production sites pass all candidates.

## This owner's verification

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_review_wire_selection.py
30 passed in 0.33s
```

The new file covers:

- Pure independent candidate construction and nonmutation.
- Byte-beneficial review with actual count smaller/equal/larger, including a synthetic +9-token regression.
- Actual metadata required exactly as Boolean False; nonactual values do not authorize review.
- Count errors on either candidate propagate as the same exception object after exposure, with not_sent/unread/budget/sequence state preserved.
- Baseline-fit/candidate-overflow, baseline-overflow/candidate-fit, and both-overflow boundaries using unchanged output/margin/safety reserves.
- All six joint operation names through real Reasoner and Transport implementations, with an explicit fake deployment tokenizer and fake generation response. The selected complete messages equal those counted and sent; actual Transport usage verification passes; one logical/model-budget charge remains.
- Shared production counter caching: two candidate HTTP fakes followed by four cache-hit counts across estimate/selection/Reasoner/Transport. Cap changes preserve the appropriate separate wire identity; schema or field-order changes produce distinct message counts.
- Canonical forecast identity and original state remain unchanged by which representation wins.

`git diff --check` passed. The separate contracts owner reported its new independent file passed 66 tests in 0.14s, covering the two production call sites and additional output-mode/exception boundaries. That owner's receipt is separate evidence.

## Existing related tests: compatibility failures reported, not edited

```text
/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests/test_v4_review_wire.py tests/test_v4_review_wire_independent.py tests/test_v4_history_wire_review.py tests/test_v4_history_wire_integration.py
32 failed, 208 passed in 1.00s
```

The 32 failures group into three outdated assumptions:

1. Twelve existing tests intercept `Reasoner.estimate`; the new selector must call `_payload/_count_payload` to inspect actual-versus-estimated accounting. Their spies no longer see the measurement. Files/counts: `test_v4_review_wire.py` (1), `test_v4_history_wire_review.py` (3), `test_v4_history_wire_integration.py` (8).
2. Eighteen parameters of `test_v4_review_wire_independent.py::test_estimate_and_actual_request_have_identical_complete_wire_and_schema` manually send the pure `_prepare_wire` byte candidate and demand every probed payload equal that sent candidate. Their injected accounting is nonactual, so production selection correctly retains baseline; furthermore a multi-candidate selector intentionally measures alternatives.
3. Two additional independent tests demand the review pool in a repair-capacity probe or durable-recovery request despite their accounting being nonactual: `test_actual_repair_capacity_failure_retains_guard_and_does_not_charge` and `test_real_durable_recovery_charges_existing_budget_and_keeps_unresolved_obligation`. Both were separately inspected with short tracebacks; their first failure is the pool-presence assertion, not a demonstrated budget or guard regression.

Root was informed and owns updating these existing assertions and broader validation. None were silently skipped, changed or counted as passing. No claim is made that the full suite currently passes.

## Frozen files

| File | SHA256 |
| --- | --- |
| changed `dagbt/joint_reading.py` | `f7a01fd53130d1782766c1fbdb09cc43d7ead1ca864e77c5597272b896cb7490` |
| new `tests/test_v4_review_wire_selection.py` | `5a57750b159876747713094c7e2879a31c30903e093b3a2ba621a18b86be7723` |
| unchanged `dagbt/reasoning.py` | `52e1d03bc8848f66be4fb3d20928765e0df34e5317f695d1d8b3bec18b4895da` |
| unchanged `dagbt/transport.py` | `9c974dd54e6f68243d29039b8e6c86567b9bc6c0ec91dec0e47659877e7189ee` |
| unchanged `dagbt/token_counting.py` | `752158005dd27ee16707fcd21ce4675ad4b2371165c0ac2f57cf65ea135868ab` |
| unchanged `dagbt/review_wire.py` | `d7d9174ea9f0b319f6fc994adce866d2ad494f83b5316382511d52dcfd8e75fb` |

## Limits

The comparison guarantees no review-layer input-token increase only relative to its pre-review baseline when actual counting succeeds. It does not optimize existing history/source/table representations, guarantee a previously over-capacity closure will fit, establish model comprehension, fix the unissued 77-source request, or prove case success/accuracy. Additional candidate counts can add tokenizer latency and failure opportunities, while retaining the established fail-closed semantics. No actual-token endpoint measurement or R20 outcome analysis was performed during this implementation task.
