# V4 citation capacity verification

Read only the eight recorded unresolved/InputOverflow rows through gzip; no archive expansion, evaluation labels, or generation calls. Requests went only to the configured deployment tokenize endpoint.

## Initial packing-only replay

`v4_capacity_replay.json` reconstructs the original first rejected window from source documents, original source aliases, fact state, scopes, plan and original settings. Deployment counts reproduce all eight overflows. The first V4 reader candidate, with lossless observation-table packing, still fails all eight: 17,931–21,365 total tokens including the unchanged 4096 output reserve, 256 input margin and envelope. Adding personal-response guidance to those legacy plans raises this to 18,448–21,882. These counts precede the later citation-refinement prompt addition; they isolate why packing alone was insufficient.

Each case has only two to four known routes, so the new route table does not apply. One route cites 89–124 source spans, often for a short value such as a feeling or preferred activity. Minimum mandatory downstream payloads contain 96–141 original spans. No span was deleted in this replay.

## Final proof-admission check

`v4_capacity_admission.json` replays each old broad support immediately BEFORE its original integration, rebuilding preceding fact batches from the recorded history. The new reader checks the prospective next task’s actual mandatory payload with the production wire/schema and deployment tokenizer, including repair/output reserve. All eight broad proofs are now explicitly rejected for scoped citation refinement before they enter state. The original live state remains unchanged in all eight checks; generation request count is zero.

The failed draft and full visible source text remain in the scoped repair input. The model must identify a shorter sufficient source set, preserving necessary joint premises and counters; otherwise it must return partial/unresolved. This is not automatic truncation and uses no arbitrary span-count cap. The check does not prove that the model will repair these cases successfully or answer them correctly.

Offline production-reader tests cover successful explicit refinement at a real token boundary, an infeasible proof remaining pending without altering a prior fact, a valid counter surviving rejection of a large support, and a conflicting value not bypassing capacity checks by becoming unbound. Binary prefix batching accepts only exactly checked prefixes, preserves every unconsumed group, and has a fallback for nonmonotone packing.

Reproduce token-count admission only:

```sh
/Users/mao/projects/dagv2/.venv/bin/python /Users/mao/projects/dagv2_analysis/personamem_v3_1_full_20261013/replay_v4_capacity.py --admission
```
