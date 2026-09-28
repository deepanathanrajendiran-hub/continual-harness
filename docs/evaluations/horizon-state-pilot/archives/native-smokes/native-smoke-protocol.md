# Native Horizon skill baseline and smoke protocol

Task 8 uses this disposable fixture for both the old-skill behavioral baseline and the updated-skill smoke. Run only after the state CLI from Task 7 is available. Do not edit either Horizon skill until the old-skill baseline is recorded. This is separate from Task 10's comparative pilot and does not count toward its 72 trials.

## Frozen seed

Source lives in `native-smoke-seed/` alongside this document. The controller authored the Python files with the AST editor. Fresh projects must receive identical seed bytes; never give the second run a repaired project from the first.

Two fresh Codex projects have been copied and their file hashes verified: native-baseline-project/ and native-updated-project/. Empty isolated home directories are native-baseline-home/ and native-updated-home/. No Horizon goal or native worker has been launched in these projects yet. Before use, verify their seed hashes; once a run begins, preserve its evidence and do not overwrite its files with the seed.

Run-log/evaluation evidence directories are native-baseline-evidence/ and native-updated-evidence/, outside each watched project. Supply the appropriate directory in both coordinator environment briefs. Save coordinator tool outputs, terminal-state observations, update files, and review evidence there so evaluation bookkeeping cannot invalidate a verification snapshot. Worker evidence references that become task entries still name real project-contained artifacts as required by the protocol.

| File | SHA-256 |
| --- | --- |
| parser_example.py | d170165014bb83537c7b470400c733c756b8971b3c743fbcabf3a6dff9865217 |
| tests/test_parser_example.py | e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86 |

Acceptance: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`. The evaluator owns the test file and checks that its hash remains unchanged. The parser must reject empty input while preserving valid integers and zero.

Seed verification returned exit 1, exactly one failing assertion out of three:

```text
test_empty_input_is_rejected (test_parser_example.ParserTests.test_empty_input_is_rejected) ... FAIL
test_valid_integer_is_preserved (test_parser_example.ParserTests.test_valid_integer_is_preserved) ... ok
test_zero_is_preserved (test_parser_example.ParserTests.test_zero_is_preserved) ... ok

======================================================================
FAIL: test_empty_input_is_rejected (test_parser_example.ParserTests.test_empty_input_is_rejected)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/deeps/Documents/NEW STUFF/fun /.superpowers/worktrees/horizon-state/.superpowers/sdd/2026-09-19-horizon-state-mode/native-smoke-seed/tests/test_parser_example.py", line 6, in test_empty_input_is_rejected
    with self.assertRaises(ValueError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 3 tests in 0.000s

FAILED (failures=1)
```

## Fixed user task

Use Horizon state mode to fix the parser in this disposable project. Use exactly two work increments: first investigate the empty-input bug and save the findings without changing parser source, then fix the parser. Preserve the supplied acceptance tests. Require independent review before marking the goal complete. Use Sol at high reasoning for the Codex run. Read the supplied project Horizon skill and its linked reference. Follow the runtime's native worker tools; report any missing capability rather than silently substituting a different mode.

Each run supplies only its project path, the current skill path and actual harness entrypoint location as environment context. Do not inject the updated state-protocol instructions into the old-skill baseline prompt.

Carry the user's standing workspace constraints into every fresh editing worker: use the AST editor for Python/config changes (discover/list symbols, then structural edits), preserve evaluator-owned tests, and restrict edits to the disposable project and designated run-evidence directory. Supplying these standing constraints to both runs is not an added Horizon protocol hint.

## Evidence

Old-skill/reference snapshots were saved before Task 8 edits:

| Snapshot | Original path | SHA-256 |
| --- | --- | --- |
| native-baseline-codex-skill.md | .agents/skills/horizon/SKILL.md | 7fcacce4183baf14679e5d45324babc9535ba2017a4f249503f5310b91165b51 |
| native-baseline-claude-skill.md | .claude/skills/horizon/SKILL.md | 0926c33f5b9b4c8c4d9e7286e509af5364e7ccae4de1f543a6239ea56645fef7 |
| native-baseline-cli-reference.md | docs/harness-cli.md | 00eb85402c8b089f8d269abc9bda00287b98509ff2d8eda4e54e1465191a0288 |

These snapshots are audit evidence, not directly installed skills. Before the actual baseline run, confirm the real loaded skill/reference paths still match; use their actual scripts and links so relocating an audit copy does not create an artificial missing-file failure.

Record the exact skill bytes/digest for each run, runtime capability, actual native coordinator/worker/reviewer handles, lifecycle observations, invoked commands and their tool results, goal JSON and packet/update/evidence references, and source/test hashes. Keep raw observed outputs separate from interpretation. If a tool transcript cannot be exported, disclose that limitation; never reconstruct missing calls as observed facts.

After each run, independently rerun acceptance, inspect goal records, confirm one charged reservation per increment, verify terminal handles and review separation, and check the immutable acceptance hash. Missing mode instructions in the old skill are a baseline gap, not a model failure. Shared --runtime claude CLI tests cannot stand in for a native Claude host run. Recheck native Claude authentication once at Task 8; if unavailable, preserve that capability result and label native support experimental.
