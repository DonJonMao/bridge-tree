# R9 first-case structural review

The first unit ended `unresolved_or_exhausted`: LLM 16, ANN 3, JSON repairs 6; no terminal generation or completed audit. No labels or predictions were inspected.

All three retrieval histories were explicitly declared `personal_history_summary`. Calls 3 and 4 (`music_prefs`) and call 7 (`event_history`) successfully performed exact unchanged revisions without version increments. Call 5 extended the music proof from 21 to 24 sources, retained ancestry, and raised its version to 2.

The later event-history revisions repeatedly omitted the same 13 of 22 required old sources, despite all old sources being visible and explicitly named by the revision contract. Calls 8/9 kept the exact value but cited only 9 old sources. Calls 10/11 cited 9 old plus 13 new sources; calls 12/13 cited 9 old plus 14 new sources. Correctly supplied failed-batch IDs did not cure the missing provenance.

Those failed reads retained 79 original source spans. The interests draft cited 19 spans; together with accepted parent proofs it needed a 31-span union, but preserving unresolved event originals expanded it to 87. Recorded terminal handoff base/repair token counts were 15311/15537, then 15313/15539. Including unchanged output allowance and margins, admission totals were 19897/19899 against 16384. The hypothetical request after resolving failed records was not tokenized, so the audit does not assert it would fit.

The failure chain is therefore a repeated model omission of explicit revision sources followed by retained-original capacity pressure. The new declaration, no-op, and true-summary-revision paths were exercised successfully before that failure. Source, configuration, output files and process state were not modified by this audit.
