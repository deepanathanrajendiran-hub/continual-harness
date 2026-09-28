# Task 3 implementer report

**Status:** DONE  
**Commit:** `42c49ab feat(horizon): persist explicit versioned execution mode`

## Implemented

- Added explicit, keyword-only `execution="state"` creation. State goals start with the shared schema at revision 0; omitted mode continues to create the legacy record. Unsupported platforms fail before the goals directory is requested. The initial maximum-ID packet is previewed with verdict reservations before the CREATE lock, and creation saves once.
- Added versioned load validation, cross-checking reserved attempts, sequential turns, and terminal attempt/checkpoint pairing. Added `execution_mode`, `require_idle`, `commit_revision`, and `summary`. Revision commits check the saved revision, validate a copied candidate, increment once, and use the existing atomic save.
- Added `.claude/harness/bin/task_state.py -> ../../../harness/task_state.py` for legacy bin-only callers and a real subprocess regression from an unrelated working directory.
- Added state creation, malformed record, oversized immutable packet, platform, revision conflict, atomic replacement, summary, and legacy compatibility tests.

Files in the commit: `harness/goal.py`, `tests/test_goal.py`, `.claude/harness/bin/task_state.py`.

## TDD evidence

RED command (with `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and `PYTHONPATH=/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages`):

```text
python3 -m pytest tests/test_goal.py -q -p no:cacheprovider --tb=short
12 failed, 71 passed in 0.73s
```

All 12 new state-mode cases failed at `TypeError: create() got an unexpected keyword argument 'execution'`, the expected absent feature. Existing cases passed.

GREEN command with the same environment:

```text
python3 -m pytest tests/test_goal.py tests/test_task_state.py -q -p no:cacheprovider --tb=short
111 passed in 0.75s
```

The isolated legacy import regression was also run on its own:

```text
python3 -m pytest tests/test_goal.py::test_legacy_bin_import_can_create_and_load_state_goal -q -p no:cacheprovider --tb=short
1 passed in 0.08s
```

This test starts `sys.executable` with only `.claude/harness/bin` on `PYTHONPATH`, changes into a separate temporary project, imports `goal`, and creates/loads a state goal.

Additional checks: `git diff --check` exited 0. A temporary state goal was created through the legacy bin import and its JSON inspected: `files 1 revision 0 mode state turns 0`. The first ad hoc one-line inspection command had a shell quoting `SyntaxError`; the corrected heredoc command passed. The focused tests had clean output.

## Self-review and concerns

Reviewed the complete diff and symlink target. Goal and task-state tests pass, including old legacy tests. The only scope boundary is intentional: CLI status routing and remaining lifecycle mutators belong to Tasks 7 and 6, and future packet growth is assigned to Task 5. No known correctness concern within Task 3 remains.

One transient tool blocker occurred after the initial goal integration. The `mcp__ast_editor__add_top_level` MCP tool returned `isError=true` with this exact text:

> This action was rejected due to unacceptable risk. Reason: Automatic approval review failed: You've hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 6:04 AM. Do not bypass this rejection through a workaround or indirect execution. Continue with a safer alternative, or carry out checks to prove that the action is authorized or low risk before trying again. Complete unaffected work without asking for confirmation. Report anything that remains blocked, clarify why it was blocked by auto-review, inform the user of the risk and ask for approval.

The one retry through the same AST editor succeeded; subsequent focused tests and the commit completed. No alternate Python editing method was used.

## Review fix round 1 — `e8f2676`

The Task 3 review found that saved goals still used default `json.loads`, which silently accepted duplicate keys and non-finite numbers. `goal.load` now passes the existing `task_state` duplicate-key, non-finite constant, and finite-float hooks to `json.loads`. Parsing failures become `GoalStateError`; no worker-update size limit is applied to goal histories. The commit changes only `harness/goal.py` and `tests/test_goal.py`.

RED command, with the same three environment settings listed above:

```text
python3 -m pytest tests/test_goal.py -q -p no:cacheprovider --tb=short -k 'duplicate_keys_in_saved_goal or nonfinite_saved_numbers'
6 failed, 83 deselected in 0.11s
```

The duplicate-key cases raised no error for either conversation or state goals. `NaN`, `Infinity`, `-Infinity`, and `1e999` reached later state validation, which produced a turn-count error rather than the required non-finite parse error. An earlier RED run used a duplicate `turns` value of 1 and yielded `5 failed, 1 passed, 83 deselected in 0.10s`; that state-mode case passed only because existing turn-count validation caught the changed value. I corrected the duplicate to an identical value and reran RED before editing production code.

GREEN command, with the same environment:

```text
python3 -m pytest tests/test_goal.py tests/test_task_state.py -q -p no:cacheprovider --tb=short
117 passed in 0.66s
```

`git diff --check` exited 0. Self-review confirmed the diff is limited to strict decoding and the six focused regressions. The CLI formatter remains Task 7 scope; the malformed candidate execution minor remains on the controller's triage ledger.
