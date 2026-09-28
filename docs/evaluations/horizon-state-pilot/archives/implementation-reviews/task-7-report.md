# Task 7 report — state-mode CLI entry points

## Implementation

- Added `start --execution {conversation,state}` and the four state protocol commands:
  `step-begin`, `step-attach`, `step-finish`, and `step-recover`.
- Routed the commands directly to `steps.begin`, `steps.attach`, `steps.finish`, and
  `steps.recover`; successful reports use their durable `exit_code`.
- Kept state-specific behavior in `steps`/`goal`. `cli.status` now delegates to
  `goal.summary`, so ordinary CLI status and step reports use the same compact
  representation.
- Added structured state-command errors. Rejections exit 2 and include
  `error`, `message`, `update_accepted: false`, and every identifier known from
  the request or readable saved state. A malformed/unreadable goal emits no
  fabricated execution revision or outcome.
- Extended `doctor` with `state_supported` and an explicit declaration that
  worker availability belongs to the host, not the Python CLI. It stays read-only.
- Retained the already-landed pre-gate refusal for legacy `check` on state goals.

## Test evidence

### RED

Before production edits, I added the real symlink-client fixture and parser/flow
tests, then ran:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' \
python3 -m pytest tests/test_horizon_steps.py tests/test_skill_contract.py -q -p no:cacheprovider
```

Result: `6 failed, 120 passed in 9.05s`.

The expected failures occurred for both `codex` and `claude`: `start` rejected
`--execution state`, all four parser forms were absent, and `doctor` had no
`state_supported` field. The real CLI client initially encountered argparse's
non-JSON usage output at the missing option, which confirmed the missing parser
surface rather than a lifecycle failure.

### GREEN

After the CLI implementation and integrated test additions, I ran:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' \
python3 -m pytest tests/test_horizon_steps.py tests/test_skill_contract.py tests/test_horizon_cli.py tests/test_runtime_separation.py -q -p no:cacheprovider
```

Result: `173 passed in 22.43s`.

This uses the real `.agents` and `.claude` Horizon symlink entrypoints in
isolated homes. The added state flows cover reservation before source work,
legacy-check refusal, stale revision and nonpositive timeout rejection,
attach, external update/terminal evidence, finish, replay, required review,
stale artifacts, completion, recovery, malformed execution schema, and
read-only doctor behavior. The pre-existing real CLI suite also covers command
failure, skipped gates, external-input `--force`, and coverage-review flows for
both runtimes.

The final covering command includes `tests/test_runtime_separation.py`, which
protects legacy runtime routing consumed by the changed parser, compact status,
and doctor paths.

Additional validation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile harness/cli.py
git diff --check
```

Both commands exited 0 with no output.

## Files changed

- `harness/cli.py`
- `tests/conftest.py`
- `tests/test_horizon_steps.py`
- `tests/test_skill_contract.py`

## Self-review

The new dispatch is deliberately thin; lifecycle and validation stay in the
already-approved core modules. File arguments are parsed as `Path`, and timeout
and expected revision as `int`. The error adapter only reads a goal after a
step failure and only emits execution-state fields when that read validates;
it never claims a terminal result. The doctor test compares the project tree
before and after the command.

The Task 6 recovery evidence contract remains unchanged: a finishing recovery
requires exactly one case-insensitive standalone `gate-state: stopped` or
`gate-state: not-started` header. A saved gate record requires `stopped` plus
exactly one matching `gate-pid` header; supporting prose excluding headers must
be at least 40 UTF-8 bytes. `not-started` is valid only when no gate record is
saved, and the CLI never signals a saved PID.

## Concerns

None. Task 8 still owns user-facing skill and CLI documentation; this task
does not modify either skill or `docs/harness-cli.md`.

## Fix round 1 — finishing-recovery CLI coverage

The review found that the real CLI fixture only covered recovery before a
worker was attached. I added a focused two-runtime test that uses the real
skill symlink to create, reserve, and attach an attempt, then seeds the durable
finishing record that an interrupted finish would have persisted. This keeps
crash/process-boundary stress in Task 9 while exercising the CLI recovery
boundary here.

For an attempt with saved gate PID `12345`, the test rejects an invalid
gate-state value, duplicate state headers, conflicting state headers, duplicate
PID headers, and a mismatched PID. Every rejected invocation exits 2, retains
the same finishing attempt and execution revision, and returns structured
`StepError`, `message`, identifiers, and `update_accepted: false`. A
case-insensitive `GATE-STATE: StOpPeD` plus one matching `gate-pid: 12345` and
substantive observation succeeds, returning the recovered terminal result with
exit code 1.

No production code changed: Task 6 already enforces this contract; this round
adds the missing real-entrypoint regression coverage.

### Fix verification

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' \
python3 -m pytest tests/test_horizon_steps.py -q -p no:cacheprovider
```

Result: `118 passed in 12.90s`.

Final required covering command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' \
python3 -m pytest tests/test_horizon_steps.py tests/test_skill_contract.py -q -p no:cacheprovider
```

Result: `128 passed in 13.05s`. `git diff --check` was clean.

Self-review: the test's only direct state manipulation is a valid persisted
finishing record used to reproduce an interrupted finish. All observed protocol
operations, including recovery, run through both actual CLI symlinks. It does
not signal a PID or assert anything about process liveness beyond the supplied
coordinator evidence contract.
