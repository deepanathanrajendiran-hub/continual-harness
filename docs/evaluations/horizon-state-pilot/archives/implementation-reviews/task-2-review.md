### Spec Compliance

- ❌ Issues found: `build_packet` can return more than the binding 24 KiB limit when `reserve_verdicts=True`; `validate_execution` does not enforce the shared attempt-record and active-attempt contract; schema-version booleans and JSON numeric overflow evade strict rejection; and independent `set`/`upsert` operations can be rejected as contradictory (`harness/task_state.py:27-39`, `:174-184`, `:200-215`, `:282-295`, `:355-363`, `:427-431`).
- ⚠️ Cannot verify from this task's diff: the later step commands' revision and lifecycle behavior; their integration belongs to subsequent tasks.

### Strengths

- The merge copies the task before applying operations, retains omitted fields, attaches provenance only to upserts, and records before/after values plus archive reasons (`harness/task_state.py:13-64`). The preservation and late-rejection tests exercise this behavior (`tests/test_task_state.py:8-34`, `:255-271`).
- New evidence is resolved inside the project and hashed by content, while historical evidence is inspected for warnings without changing persisted entries (`harness/task_state.py:218-280`). The changed-bytes-with-preserved-mtime case is covered (`tests/test_task_state.py:119-145`).
- The serializer is deterministic, text limits use UTF-8 bytes, and packet construction retains the objective, gate, paths, and entries (`harness/task_state.py:83-99`, `:153-164`, `:411-430`).

### Issues

#### Critical (Must Fix)

- `harness/task_state.py:355-363`, `:423-430`: Reservation replaces the *whole* latest checkpoint and review with excerpt placeholders for measurement, then returns the original objects. Their other fields are omitted from the byte count. A focused probe returned a 26,781-byte packet with `reserve_verdicts=True` against `PACKET_LIMIT = 24,576`; preserve metadata in the measured copy, reserve only excerpt slots, and enforce the limit on the actual returned serialization.

#### Important (Should Fix)

- `harness/task_state.py:174-184`: `validate_execution` only checks that `attempts` is a list. It accepts malformed attempt records, invalid statuses, multiple nonterminal attempts, and an `active_attempt` that identifies no nonterminal attempt, contrary to the shared execution contract. Validate each record's fixed fields, status, IDs, and active-attempt consistency.
- `harness/task_state.py:176-179`, `:282-290`: `schema_version=True` passes because `True == 1`; the integer rule explicitly rejects booleans. Use the same non-boolean integer check as revisions for both execution and update schema versions. The focused probe confirmed acceptance in `validate_execution`.
- `harness/task_state.py:208-215`: `parse_constant` rejects literal `NaN`/`Infinity`, but JSON number `1e999` becomes Python `inf` through the default float parser and `read_update` returns it. The shared contract requires JSON decoding to reject non-finite numbers. Use a finite-checking `parse_float` and add a regression case; the focused decoder probe confirmed infinity.
- `harness/task_state.py:27-39`: One `touched` set tracks both task fields and entry IDs. An entry ID of `summary` or `next_action` is valid, so a `set` of that field plus an `upsert` of that entry is wrongly rejected as contradictory. Track fields and entry IDs separately.

#### Minor (Nice to Have)

- `harness/task_state.py:74-80`: The two regexes are compiled a second time without binding the results, and `_KINDS` is assigned twice. Remove the redundant lines.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The core merge and evidence design is sound, and the reported focused suite passed 23 tests without warning output. The packet cap is violated by a returned packet, and the strict execution and JSON schemas still admit invalid states and input.

- Check: one focused outside-diff integration check inspected the goal-state field names and checkpoint construction in `harness/goal.py:138-139`, `:279-285`, `:375-379`; the packet's expected `goal`, `gate`, `watch_paths`, `budget`, `used`, and `cwd` fields align with that file.
- Check: one focused in-memory probe confirmed `schema_bool=accepted`, `json_overflow_nonfinite=True`, and `reserved_packet_bytes=26781` versus `limit=24576`; the reported test suite was not rerun.
