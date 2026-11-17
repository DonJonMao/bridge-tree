# R10 first-case capacity and control review

Frozen commit: `b160f3ad449796a714c3d45df232b29032262dce`. Final status: `unresolved_or_exhausted`; LLM 19, ANN 3, JSON repairs 1. No labels were read.

All 17 generated reading batches completed without validation failures; model unresolved lists, failed records and evidence obligations were empty. No missing-source feedback was triggered. The only pending variable was `recent_changes`, from 37 unread-source obligations.

After the last successful history batch (event 506), events 507–620 contain 38 prefix trials. Every ordinary request/repair check passed; every additional unknown-draft forecast check failed. Event 621 raised `InputOverflow`.

| Prefix example | Input | Ordinary repair | Whole-review forecast | Ordinary total | Forecast total | Limit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Minimum forecast, events 522–524 | 7201 | 7291 | 8915 | 11651 | 17371 | 16384 |
| Largest prefix, events 507–509 | 9542 | 9632 | 11364 | 13992 | 19820 | 16384 |

Ordinary totals include one 4096-token output allowance, 256 margin and 8 fixed tokens. The forecast adds another full 4096-token unknown-draft workspace. These are recorded actual tokenization counts. Fitting the ordinary request does not prove an unknown failed reply will remain repairable.

The controller then marked the history query exhausted. Two terminal requests returned exact public options with matching legal labels and passed input validation. They still depended on `recent_changes`, so its unread obligations correctly blocked audit. This was not model abstention or malformed terminal output.

No source/configuration/result files, process state or budgets were changed. The adjacent JSON contains hashes and all prefix checks without source or option text.
