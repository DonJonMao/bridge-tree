# R13 first-case structural review

The first case naturally published `budget_exhausted`; the later operator stop of the overall run does not change that terminal outcome.

Calls: planner 1 + history 18 + semantic composition 4 = 23/24. There were no JSON repairs and no audit calls. All 18 history windows completed; their three reads used 7, 5, and 6 windows.

The four successful semantic calls and the next failed batch share one identity and form one `JointReader.read()` window loop. Completed window source counts were 38, 22, 25, 27; the final selected window had 5 sources and a total visible context of 40 sources. Its preflight failed before generation.

One LLM call remained, reserved for audit. At least two more calls were required: the last ordinary semantic window and one audit. Thus the current path needed at least 25 total calls; more might be needed if evidence, output, or audit still failed.

The final five-source window moved from unread markers into four failed-review markers, each retaining the complete 40-source context. Zero unread markers does not mean all work passed. The failed batch input_tokens field repeats the previous successful request count and must not be interpreted as a newly paid request.

No evidence here establishes repeated controller composition. The concrete pressure is history window count plus a multiwindow terminal context. The proposed prefix-admission change should be evaluated as an efficiency hypothesis, not an already-proven accuracy improvement.

JSON report contains only explicit structural/count/hash allowlists. No labels, model generation, network tokenization, or experiment mutations were performed by this report script.
