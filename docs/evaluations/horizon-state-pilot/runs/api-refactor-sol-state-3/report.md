# Frozen trial report: api-refactor-sol-state-3

## Identity and outcome

- Trial: `api-refactor / gpt-5.6-sol / state / repeat3`
- Goal slug: `rename-normalize-to-normalize_name-in-names-py-update-both-p`
- Final Horizon status: `complete`
- Execution revision: `7`
- Budget: 1 of 4 worker attempts used; `budget_exhausted: false`; fixed 15-minute ceiling preserved
- Checkpoint: `eda081e65e6dbfeaa779bbcbd79833084cffda93d4ffd4b4824704288e92988c`
- Gate: pass, exit 0, 1 test run, 0 failures
- Independent review: pass, recorded against the same checkpoint hash
- Objective and review control files: exact byte equality to the saved goal fields; 204 objective bytes and 576 review-criterion bytes, neither with a trailing LF

The implementation now defines `normalize_name` with the original `strip().casefold()` behavior, assigns `normalize = normalize_name` as a compatibility alias, and updates `greet.py` and `tags.py` to import and call `normalize_name`. Existing imports of `normalize` remain valid. The protected acceptance test was not edited, moved, regenerated, or removed.

## Native roles and boundaries

- Coordinator: `/root/pilot_api_refactor_sol_state_3`; configured by the frozen dispatch as gpt-5.6-sol/high; owned Horizon lifecycle, evidence export, gate acceptance, review recording, and final completion.
- Editing worker: `/root/pilot_api_refactor_sol_state_3/state_editor_001`; fresh context, gpt-5.6-sol/high; bound immediately to `request-001`; edited only the three source files and returned one schema-version-1 update. It was observed in terminal `completed` state before `step-finish`.
- Independent reviewer: `/root/pilot_api_refactor_sol_state_3/independent_reviewer`; fresh context, gpt-5.6-sol/high; performed no edits or lifecycle calls; returned `verdict: pass` and was observed in terminal `completed` state before the review was recorded.

The worker and reviewer received the exact scoped project/evidence paths. The editing worker also received the resolved Packet/update schema and the requirement to discover the AST editor, call `list_symbols`, use `find_references` for the rename, and make every Python edit through the narrowest AST operation. Full internal native tool transcripts are not exposed to the coordinator, so the exact worker tool-call sequence is unknown; the coordinator independently used AST `list_symbols` after the worker stopped and verified the resulting source bytes. No worker update formatting repair was requested.

## Lifecycle and verification

The lifecycle was `doctor -> start -> status -> step-begin -> fresh worker -> step-attach -> observed terminal worker -> step-finish -> fresh independent review -> review -> complete -> final status`. Revisions advanced 0, 1, 2, 5, 6, and 7. There was no recovery, replacement goal, second attempt, budget extension, abandon/reopen, app goal, sidebar task, install, merge, push, or second trial.

`step-finish` ran the exact fixed gate:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
test_names_and_callers (test_acceptance.AcceptanceTests.test_names_and_callers) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

The editing worker also reported a successful pre-finish unittest run in its terminal update. The authoritative fixed gate is the Horizon `step-finish` checkpoint above. The independent reviewer separately imported both names and both callers, confirmed `normalize is normalize_name`, and checked the expected outputs.

Final watched-project evidence:

| Path | SHA-256 | mtime_ns | Result |
| --- | --- | ---: | --- |
| `greet.py` | `b0eb603b4f53661a32f0477eebb52d25e81becb6b0ac55f438f6fb8fe8604878` | `1791386053824684304` | Updated caller |
| `names.py` | `09b84dc3cf84531060aa4439ff6af23d304aab67e6406e9b2e1de0040f9a2b5e` | `1791386041394713331` | New function plus compatibility alias |
| `tags.py` | `b2e22fd1cdcde0196180b088548ef65728b661f5f9c77ed31e06fa415afea8b7` | `1791386063139960905` | Updated caller |
| `tests/test_acceptance.py` | `cabb3c9379120181bc94744b6915cd9add3bb489c5009cf8553d532928ce9297` | `1790650615811070952` | Exact seed hash and original nanosecond mtime |

The test directory still contains exactly the protected acceptance file. No `.pyc` or `__pycache__` artifact was present at the coordinator inspection. The mandatory pre-marker `git rev-parse --show-toplevel` exited 128 with `not a git repository`, as required.

## Durable artifacts

- Initial raw goal: `goal-initial.raw.json`, 1,723 bytes, SHA-256 `798c7c9822c534baaca6b685a52743cc963771e20f3ab98eb069870bea8a0894`
- Raw packet: `packet-request-001.raw.json`, 1,890 bytes, SHA-256 `08a240fbb4ef5e12f794013737d12ef67b4184545211ee3037aa0faa84e5fdf5`
- Raw native worker payload: `worker-request-001-update.raw.json`, 665 bytes, SHA-256 `3dea938881ac5da1ad5b46c9f09a8b7346c84591ff5e7164fbe17ce92a36989e`
- Raw native reviewer payload: `reviewer-native-terminal.raw.txt`, 2,528 bytes, SHA-256 `8e04c30af5b58f2962cb96ef43de960a2508215c8f1d6656442fe0250a083d97`
- Final raw goal: `goal-final.raw.json`, 12,481 bytes, SHA-256 `f766056f5a51dadb8dd280bfd27adff6f03e1b1d6fe8b83039f8103a5ea4db4e`
- Final raw audit copy: `audit-final.raw.json`, 12,481 bytes, same SHA-256 `f766056f5a51dadb8dd280bfd27adff6f03e1b1d6fe8b83039f8103a5ea4db4e`
- All five content-addressed packet/update/candidate/audit/worker-evidence objects are copied byte-for-byte in `audit-objects/`; sizes and hashes are listed in `raw-artifact-hashes.txt`.
- Exact gate output is in `fixed-gate-output.txt`; lifecycle projections are in `lifecycle-*.json`; coordinator-authored observations are separately labeled in `written-tool-accounts.md`.

## Format repairs and deviations

- Worker update format repairs: 0. The worker returned a valid schema-version-1 JSON update on its first terminal response.
- Reviewer format repairs: 0. The reviewer returned a self-contained pass verdict on its first terminal response.
- Coordinator evidence-export repair: 1 issue affecting the raw packet copy. The initial patch-based export added one trailing LF, making the evidence copy 1,891 bytes. The reviewer detected this while confirming that the immutable project packet was still the correct 1,890-byte `08a240…` object. The coordinator removed only the export LF and reverified the expected byte count and SHA-256. The saved reviewer payload retains its historical observation. Raw worker/reviewer terminal exports were likewise stored without editor-added terminal LFs. No watched project byte changed during these export corrections.
- Environment correction `a0596a5` moved this previously unrun row from temporary outside-Git paths to persistent `/Users/deeps/Documents/horizon-state-pilot-2f65f2a/api-refactor-sol-state-3/{project,home}`. The frozen brief states that source/control bytes were unchanged. This trial used those corrected paths.
- Because project/home are outside the normal writable roots, 11 trial-local marker/lifecycle/status calls used scoped `require_escalated`. Observed wrapper wall time was about 32.5 seconds versus about 0.081 seconds of child-process time. No escalation was rejected, and no global host configuration was changed.
- One initial unscoped native agent inventory used to confirm the spawned handle also displayed a preexisting sibling task's completed status summary. No sibling path, implementation, lifecycle state, or evidence artifact was opened or used. Later inventories were scoped to this trial.

## Unknowns

- The authorized corpus does not expose the Horizon tree-hash derivation, so the independent reviewer did not recompute `eda081e…`; it confirmed consistent binding across the live audit, fixed-gate evidence, and lifecycle record.
- Per-role usage and cost are `null` because the host did not report coordinator, worker, and reviewer usage consistently for both paired arms.
- Full internal worker/reviewer tool transcripts are unavailable. Actual native terminal payloads, host handles, terminal-state observations, lifecycle JSON, raw goal/audit objects, and evaluator-facing evidence are preserved.

No required outcome remains open. The saved Horizon goal is complete only after the fixed gate pass and the independent review pass on the same checkpoint.
