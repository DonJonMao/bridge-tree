# Exact whole-suite command compatibility

Only external `prepare_source_approval.py` and its external unit-probe file were changed. Neither source checkout, the running full20 test, candidate receipts, model runs, configuration, evaluation labels nor approval output was modified.

The recorded full20 command is `/Users/mao/projects/dagv2/.venv/bin/python -m pytest -q tests`. Previously the verifier accepted only the four-argument `python -m pytest -q` form. Rewriting the execution record to remove `tests` would be inaccurate. The verifier now recognizes the exact recorded whole-directory form as well as its existing form.

The new `verify_test_command` helper accepts only:

* A Python executable named `python` or `python3`, followed by exactly `-m pytest -q`.
* The same sequence followed by exactly `tests`, with no further options or paths.

For the explicit `tests` form, the source checkout must be supplied and clean. The helper enumerates tracked paths from `HEAD` using NUL-delimited `git ls-tree`; the committed inventory must contain default pytest test-file names (`test_*.py` or `*_test.py`), and every such path must be inside `tests/`. Thus a clean commit containing a tracked test outside that directory cannot use the explicit-directory form. The enclosing existing `prepare` checks still require that this is the exact expected clean commit, both before and after verification. Both calls to `verify_test_log` now receive that checkout root.

No test selector, individual file, subdirectory, `-k`, `--ignore`, alternate target or appended option is accepted. Execution command strings remain unchanged in receipts. Test-log hash, all-passed summary, exact matching-source attestation, frozen source/config hashes, fixed label-free 14-question smoke, production model gate, clean-commit checks and exclusive new approval-output behavior are unchanged.

Validation was limited to a pure helper probe, without calling `prepare` or manufacturing passing receipts:

```
/Users/mao/projects/dagv2/.venv/bin/python -B test_prepare_source_approval_command.py
Ran 6 tests in 0.004s
OK
```

The probes cover both valid command forms; required source-root context; clean versus dirty checkouts; both outside-test naming patterns; an empty committed test inventory; and selectors/subsets/additional arguments. Git is mocked only inside these command-parser unit probes. No real model or source test suite was started.

SHA-256:

* `prepare_source_approval.py`: `84d59d9c0f6b7fd6b3efc4bef7810a7219da0f7c282a5c52cf16248d7c8b596d`
* `test_prepare_source_approval_command.py`: `ab532ce53723f1ddd88914df588064616e6aa899f97a19179f2de502dc795556`

Read-only checks after the external change found RECONCILE clean at `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`, and RELEASE clean at `bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`. This is compatibility with an exact execution record, not relaxation of the model gate or a release approval.
