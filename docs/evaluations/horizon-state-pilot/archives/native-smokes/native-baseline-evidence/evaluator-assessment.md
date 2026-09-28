# Independent baseline assessment

The parser task passed, but the requested state-mode workflow did not occur. This is evidence of missing guidance in the old skill, which documents only the conversation loop; it is not evidence of a model failing a documented state-mode feature.

The evaluator inspected the actual durable goal after the coordinator finished: status `complete`, two used turns, two checkpoints, one passing review bound to the second checkpoint's hash, and no `execution` state record (legacy conversation mode). There were zero state-mode reservations and no saved packets. The coordinator used `/root/native_baseline_codex/native_worker` for both increments. The native collaboration tree independently exposed that handle; the coordinator's report records its reuse. The independent reviewer handle is `/root/native_baseline_codex/native_reviewer`, distinct from the editor. Its written pass verdict survived a host usage-limit error, and the coordinator recorded that artifact without inventing a successful host response.

An evaluator-run acceptance command passed all three tests; raw output is in `evaluator-acceptance.txt`. Final parser SHA-256 is `b1bf7a081d3bdcc25979f4bc1a57be5d53a4709fc111593f332ccf432ccedfad`. The acceptance test SHA-256 remains the frozen `e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86`. The actual source contains `return int(value)`.

The coordinator report's statement that no functional gap remains applies to parser behavior. Its mode and worker-reuse records show the explicit state-mode workflow requirement was unmet. Full host transcript export is unavailable in the tools used here; written agent accounts are not represented as a complete observed trace. Command results, goal records, hashes, and native handle observations supply the stated evidence. Token usage and cost are unobserved.

This run crossed an account usage interruption before review recording/completion; it is unsuitable for clean elapsed-time comparison. It is a Task 8 behavioral baseline, not one of the Task 10 pilot trials. The old skill/reference snapshots and hashes were frozen before any new instruction edits.
