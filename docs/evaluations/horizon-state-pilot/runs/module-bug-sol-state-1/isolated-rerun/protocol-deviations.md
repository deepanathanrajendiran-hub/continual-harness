# Protocol deviations

1. Before goal creation, the original coordinator turn was interrupted by an external usage limit. A later read-only account check allowed continuation. No goal, worker, or trial evidence had been created by that failed turn beyond evaluator/root setup. The same seed, project, and local marker were preserved; no reset credit was consumed. Uninterrupted elapsed timing cannot be inferred from the original root dispatch timestamp.
2. The goal began at `2026-09-29T02:56:25.090905+00:00`. During the external wait for the already dispatched and attached worker, the 15-minute wall budget expired. Status before finish recorded `budget_exhausted: true`. Following the skill's late-finish rule, the coordinator recorded the terminal worker result and closed the existing attempt. No new implementation attempt, reopen, budget extension, or reset was used.
3. The worker update's summary abbreviated the protected mtime to whole seconds (`1790599028`) and said the packet lacked the evaluator baseline. The coordinator did not repair the worker update because it was schema-valid and the full evaluator baseline existed separately in `seed-hashes.csv`. Independent coordinator evidence recorded the exact required nanosecond mtime `1790599028272458609` and matching SHA-256.

Format repairs: none.
