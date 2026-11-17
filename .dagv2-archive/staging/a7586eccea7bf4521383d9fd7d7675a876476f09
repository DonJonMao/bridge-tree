# R9 independent source-retention protocol review

Audited baseline: `6483c38f081acdac577d057cee46fa1adff807d1`.
Scope: read-only source and original R9 request/response structure. No labels,
answer predictions, source text, or credentials were analyzed or displayed. No
generation or tokenization calls were made. One in-memory state-validator probe
was run; it did not modify output files or publish evidence.

## Finding

Precise missing/required source-identity feedback is a minimal, justified repair.
The validator correctly rejected the R9 revisions. The existing repair feedback
reported only a generic retention error, even though the missing identity set was
computable exactly. The prompt also contains a real ambiguity: the base SYSTEM
demands the shortest sufficient source set without an exception, while explicit
summary revision requires retention of all inherited original premises and
counter sources. This should be disambiguated, not resolved by dropping either
provenance protection or ordinary proof minimization.

## Independently checked R9 wire evidence

In calls 8–13, the offered contract consistently required 22 aliases. They exactly
matched the selected old event-history route's source set. All were present in
the original text table; each visible alias was unique. The failed observation
ID remained `obs_event_history_1`, and the local repair allowed that ID to be
edited in place. There was no evidence of an invisible-source, alias-collision,
or frozen-invalid-draft defect preventing compliance.

The same thirteen aliases were repeatedly omitted:

`s11, s12, s13, s21, s22, s23, s24, s25, s52, s53, s54, s55, s56`.

Calls 10 and 11 returned 22 citations by adding thirteen different new aliases;
the thirteen required old identities were still absent. Calls 12 and 13 added
fourteen different aliases and still omitted that same old set. Equal or larger
cardinality therefore did not satisfy the identity-retention requirement.

In a strictly in-memory structural feasibility probe, the call-9 candidate with
the same unchanged value and the explicit complete 22-source set passed
`FactState.validate_summary_revision`, was recognized as an exact no-op, and
left routes and versions unchanged. This demonstrates feasibility of the state
gate only. It does not establish that a model would make the repair, that all
downstream requests would fit, or that an answer would be correct.

## Minimal implementation boundaries

- In `dagbt/fact_state.py`, `validate_summary_revision` must validate declaration,
  phase authorization at its caller, target identity, current version, scope,
  actual parents, and target eligibility before emitting a typed missing-source
  diagnostic. Required and missing IDs should come from the already validated
  selected targets through `summary_revision_sources`.
- Do not replace selected-target requirements with the union of every eligible
  route merely because the wire contract lists all eligible alternatives. That
  would needlessly require independent OR proofs when only one is revised.
- In `dagbt/joint_reading.py`, `_observation` should translate authoritative
  stable IDs into the current visible aliases for model feedback. It must not add
  aliases to the returned observation or synthesize a corrected support.
- The repair envelope currently uses `feedback=error[:240]` in `read`. Complete
  missing/required lists need separate structured fields; a longer error string
  alone will truncate the actionable identities.
- `_store_failed_reviews`, `_failed_payload`, and `_remap_review_sources` must
  preserve those lists in stable-ID form internally and remap them for later
  visible aliases. Diagnostic requirements are not validated facts and must not
  release failed obligations. Existing original-draft and counter preservation
  remains authoritative.
- Every resulting actual repair request still needs the existing exact wire
  capacity check, call accounting, and finite repair allowance. If the additional
  feedback does not fit, the failure stays explicit; no sources may be removed to
  make it pass.

## Prompt clarification

State explicitly that an emitted `summary_revision` first preserves every
required old premise, actual-parent premise and relevant counter identity for
its selected targets. These mandatory identities take precedence over ordinary
shortest-sufficient-proof guidance. Only the additional sources are minimized.
Overlapping old spans cannot be removed merely as redundant, and an equal number
of new aliases cannot replace missing old identities. The model must re-read the
original text and explicitly return the required aliases. If it cannot establish
a supported fitting revision, it must remain partial or unresolved.

Limit this exception to explicit summary revision. Do not turn every visible
source or retained failed reading window into a mandatory support citation.
Ordinary supports still use genuinely sufficient minimal proofs. The R9 behavior
is consistent with the current prompt ambiguity, but the logs alone do not prove
it was the sole cause of the model's omission.

## Remaining limits

The later capacity pressure is real and separate: failed original windows were
retained and expanded the prospective terminal request. This review does not
support clearing those records, clipping original sources, weakening ancestry,
increasing budgets, or asserting the post-repair terminal request would fit.
Root/reader own implementation and a new real-service smoke run.

## Candidate implementation review completed

The subsequent candidate implements typed source-gap metadata after revision
eligibility checks, verifies every required original is visible, emits complete
structured alias lists independently of the 240-character feedback limit, and
preserves stable IDs in durable entries. Current repair feedback is bound to both
the error and the exact raw draft digest; it cannot silently follow a changed
unvalidated draft. Requirements are computed from selected targets. The prompt
now gives explicit revision retention precedence over ordinary minimization.

This independent review found one implementation regression: recursively treating
every model-written `summary_revision_sources` key as trusted caused malformed
draft retention to raise an uncaught error. Reader fixed it by strictly remapping
only the controller-owned field at a failed entry's top level. Unvalidated
observation/slot contents retain the ordinary draft-remapping behavior.

The independent file `tests/test_v4_summary_source_feedback_trust_review.py`
contains three passing real-reader regressions for that field appearing in an
observation, a slot, and revision metadata. Each becomes a durable malformed-draft
failure and survives later payload construction without acquiring trusted status.
Final review found no further blocking issue in the candidate diff. Production
and test edits were then frozen for root's full suite. This does not change the
real-service and accuracy limits stated above.
