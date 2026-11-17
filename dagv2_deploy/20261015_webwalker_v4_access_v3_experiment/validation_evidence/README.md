# access_v3 validation evidence

This is a diagnostic revision, not an accepted engineering or benchmark result.

Algorithm commit: a3406e8d3113d4b359bdf7f1374c3ef16359ea1d. Release source commit: bbf03c94894e56ed007bbde9c4b02f9211f24d57 (documentation-only delta).

2511 regression checks and 130 installed-payload checks passed. The installed offline HTTP smoke passed for both arms. The real-model smoke completed four tasks, but both arms scored 0/2. JOINT question wwqa-0001 remains blocked by capacity after repeated invalid evidence-obligation responses. RESIDUAL answered that question but the judge marked it wrong. No actual oversized repair was sent in this run. Full680 is deferred.

The archive audit and clean final-archive installation log are saved alongside these records. Worker input/private configs and credentials are excluded. Requests were recorded by Transport without authorization headers. Generation result and request records are unchanged copies.

The existing native json_schema transport is not a compatible config-only fix: the current exact deployment token counter accepts only plain. A read-only zero-network check rejected json_object and json_schema with unsupported_response_protocol. No model probe or tokenizer fallback was used.
