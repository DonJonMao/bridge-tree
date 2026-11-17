# R12 missing-information and source-obligation review

Read-only review; no algorithm changes, labels, or service calls.

R12 call 8's `event_history` is a `personal_history_summary`. The response had one support with seven citations, no partial/unknown/contradiction observations, and two unresolved descriptions about unspecified event details and participation roles. The batch was complete with one valid row. The resulting obligation's 53 sources equal the entire visible window; 46 were outside the support's citations. Its descriptions exactly match the two unresolved strings.

`JointReader._update_evidence_obligations` conservatively assigns all visible sources to a nonempty string-valued `slot.unresolved`, because that field has no per-issue source mapping. Discharge subsequently requires explicit complete review. Thus the 53-source obligation comes from this retention rule; it is not evidence of 53 contradictions or a model judgment that all 53 passages are premises of the issue.

The missing attributes have not been proven irrelevant to the task, so no automatic clearing or schema/control change is approved. The open summary contract does not require fixed fields for those attributes. Sharing a string field between missing-information gaps and source-linked unresolved issues is a possible overconstraint, requiring a separately defined contract before any change. The current nonempty output floor must account for this actual outstanding obligation in full.

The separate reservation review confirmed ordinary calls reserve one audit call, and the controller prioritizes terminal/audit as soon as ready. Two remaining calls cannot complete necessary history + terminal + audit; reserving two instead merely rejects earlier. No evidence establishes a feasible completion path wasted on unnecessary work here. Reservation remains unchanged.
