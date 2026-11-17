# Independent review: exact summary recheck

Review scope: the isolated `dagv2-personamem-v4-reconcile` candidate after R7 was
stopped. No release edits, network requests, evaluation-label reads, or package
operations were performed.

## Verified candidate behavior

`tests/test_v4_summary_noop_review.py` adds nineteen independent offline cases. The
real reader, state integration, provenance, obligation management, wire source
visibility, and call ledger run with scripted model replies. All nineteen pass.

- A valid exact no-op after a real summary revision preserves every route,
  ancestry link, variable version, and dependent terminal binding verbatim.
- A later genuine counter against the original ancestor invalidates the revised
  history and its dependent terminal.
- A same-batch genuine counter survives rejection of the no-op candidate.
- Stale versions, retired targets, missing originals, and wrong scopes remain
  rejected; exact equality does not bypass validation.
- A paid, explicitly acknowledged durable review can discharge a previous failed
  draft and evidence obligation without increasing fact versions. Missing
  resolution IDs leave both obligations pending.
- An unrelated whole-value disagreement remains unresolved.
- Repeated integrations and source-order permutations add only history records;
  they do not change the material-progress signature.
- A genuine exact-text or source-proof change still creates a versioned revision.

The implementation classifies no-ops only after full revision validation and
same-batch counter checks. It skips the support integration itself rather than
removing revision metadata and inserting an ordinary support. Reader whole-value,
handoff-capacity, and durable resolution checks remain in their original order.

## Adjacent provenance issue found and fixed by reader

A separately reproduced existing path was relevant: after a real revision,
an ordinary support without `summary_revision`, but with the identical variable,
value, scope, parents and source set, creates another route without the revision
ancestry. A later counter to the original ancestor invalidates the revised route
but leaves this ordinary duplicate live. Reproduction used only scripted text.

This was not caused by the new explicit no-op branch. Root approved the minimal
repair and reader implemented it: ordinary support whose exact base identity
matches any historical revised route or a fully validated revision in the same
batch does not create an ancestry-free route. The base identity still includes
variable, typed value, scopes, actual parents, normalized source set, and any
binding derivation. Existing full identity calculation remains unchanged.

Seven additional independent cases pass: ordinary replay before/after ancestor
counter, ordinary replay in the same batch as counter, both row orders of a new
revision plus ordinary clone, truly independent original-source OR support, and
support with a genuinely new actual parent version. Existing retired/revoked
routes participate in matching, so replay after counter cannot revive a proof.
Different source or parent proofs are not blocked. This guards new insertions;
it does not migrate ancestry-free clones in old checkpoints. Final real-service
validation must use a new output directory.

## Scope comparison requirement

The requirement that a history variable's scope string differ from the terminal
scope was not a sound role-separation invariant. A sourced current constraint can
legitimately share entity and time with a current response. Variable identity,
task demand, explicit validated scopes, actual parent bindings, source cutoff,
and history/terminal/audit phase boundaries carry the necessary distinctions.
The reviewed removal preserves those checks and does not rewrite scope strings.

These checks establish execution contracts, not improved answer accuracy or a
successful final real-service smoke run. Packaging and final installation remain
separate root-owned steps.
