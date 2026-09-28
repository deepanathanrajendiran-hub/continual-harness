# Task 8 implementation report

Status: DONE. The documentation and parser/merge-backed contract tests are green.
The first updated native Codex smoke completed successfully and exposed one
shared-schema handoff gap; a second native smoke confirmed the corrected handoff
with two fresh workers and a separate reviewer. Native Claude is unavailable.
Commit: `c95f1ea451c4bfea41150c18640b8329199c273d`
(`docs(skills): coordinate fresh Horizon workers in Codex and Claude`).

## Test-first evidence

I first changed only `tests/test_skill_contract.py`, using the AST editor after
`list_symbols`. Neither Horizon skill nor the shared CLI reference changed before
the old-skill native baseline completed.

RED command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_skill_contract.py -q -p no:cacheprovider
```

RED output:

```text
....FF....                                                               [100%]
2 failed, 8 passed in 0.08s
```

Both failures were the parameterized Horizon cases, one for Codex and one for
Claude. The parser-backed shared-reference scan found none of `step-begin`,
`step-attach`, `step-finish`, or `step-recover`. Existing entrypoint/reference
checks and all other contract cases passed. Two earlier test-plumbing runs found
lost pytest decorators after structural replacement and the reference's special
`--help` example; those were corrected before recording the behavioral RED above.

GREEN command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_skill_contract.py -q -p no:cacheprovider
```

GREEN output:

```text
..........                                                               [100%]
10 passed in 0.07s
```

The test now reads each Horizon skill's linked `references/commands.md`, expands
`RUNTIME`, `CURRENT_REVISION`, and `PACKET_REVISION` with `string.Template`, and
passes every documented `python3 "$HARNESS"` example through the real argparse
parser for both runtimes. It requires all four state lifecycle commands while
retaining the entrypoint, link, and symlink resolution checks.

## Old-skill native baseline

The controller's independently inspected baseline is recorded in
`native-baseline-evidence/report.md`. Native Codex completed the parser task: all
three acceptance tests passed, the evaluator-owned test hash remained unchanged,
two checkpoints were saved, a distinct independent reviewer passed the final
snapshot, and the goal completed. The old skill nevertheless created a
conversation-mode goal despite the explicit state-mode request and reused the same
worker for both increments. This is evidence of missing old-skill mode guidance,
not a model failure for a supported workflow. A usage-limit interruption means its
timing is not a clean performance comparison. The saved account is a lifecycle
report with selected raw artifacts, not a complete exported native tool transcript.

## Implementation

- `.agents/skills/horizon/SKILL.md`: added the concise Codex state-mode entrypoint,
  fresh `collaboration.spawn_agent` dispatch with `fork_turns: "none"`, actual
  handle binding, terminal inspection, one formatting-only repair allowance,
  recovery/liveness rules, reviewer separation, and the boundary against recursive
  Horizon/native goal, task, schedule, or API creation. It now explicitly gives
  every worker the resolved shared packet/update schema with the saved packet.
- `.claude/skills/horizon/SKILL.md`: added the same shared behavior with a fresh
  supported general-purpose `Agent` invocation and an explicit unavailable-mode
  outcome when freshness or lifecycle cannot be observed, including the same
  explicit shared-schema handoff.
- `docs/harness-cli.md`: documented opt-in compatibility, the coordinator/worker
  split, packet and update contracts, a valid JSON update, all four parser-backed
  commands, packet versus current revisions, terminal/recovery evidence, all five
  attempt statuses, replay results, recovery, limits, durable archived-entry
  retrieval, stale evidence, and absence of automatic transcript export. Exact
  `upsert` and `archive` JSON envelopes, entry-ID syntax, and nonempty field rules
  remove the final need for workers to infer operation shape.
- `README.md`: added the user-facing “Use Horizon state mode” request and replaced
  the obsolete unconditional under-100-line claim with the progressive-disclosure
  boundary.
- `tests/test_skill_contract.py`: added the parser-backed reference contract above.
  A focused test also parses the documented full update and operation envelopes
  and sends them through the real `task_state.merge_update` validator.

Frozen first updated-smoke hashes:

```text
dc2e43c7d128865e178833e6503aa1a2349ebeb630b6a5bf219a40619369f25b  .agents/skills/horizon/SKILL.md
5da6cf03cdcb2e3bfcf38ccfedd4ba41d742999a7f29017ef14456a17308bcf9  .claude/skills/horizon/SKILL.md
615f5d7860bf7efbd0a2dac10678c8a0ad5e8756960ec23389b3e272732fb973  docs/harness-cli.md
707a41361453aff1182e0dce2ae4830ec35e70bb4c993e563e19ad55ceb194b8  README.md
574e7c1541d920b59cfd03fa2c426f2ce9a2e7e0035e7820860daced2310d493  tests/test_skill_contract.py
```

## Validation so far

Measured skill sizes after the schema-handoff clarification:

```text
129 lines, 960 words  .agents/skills/horizon/SKILL.md
129 lines, 951 words  .claude/skills/horizon/SKILL.md
```

Confirmation-smoke instruction/reference hashes:

```text
7c1dc1edf666a9c4644da8f4e54a87eccb1f6b6bc7cc276e7590c44536af7dbf  .agents/skills/horizon/SKILL.md
9cbd38f352d606360610f086b60cb2f51d6d14603e22f4f73e3e9a9fb620d691  .claude/skills/horizon/SKILL.md
bc20f82f0e884b5752bd04f31818150c756e0907af515405763b8202d0250490  docs/harness-cli.md
```

The two skill hashes are also the final skill hashes. After the behaviorally
confirmed smoke, the shared reference alone gained the exact operation-envelope
examples and now hashes to
`04817de80b3f667d73a05c82ba3ec6c79eb1c9f24e0d8c6ae6d41bfffec7fdee`.
That post-smoke change adds no lifecycle instruction; it is protected by the real
merge-contract test described below.

The current skill-creator `quick_validate.py` returned `Skill is valid!` for each
skill. `git diff --check` returned no output. Adjacent verification command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH='/Users/deeps/.cache/uv/archive-v0/044nI_HLHtvNp2AOxHKcK/lib/python3.14/site-packages' python3 -m pytest tests/test_skill_contract.py tests/test_horizon_cli.py tests/test_runtime_separation.py -q -p no:cacheprovider --tb=short
```

Output:

```text
57 passed in 11.04s
```

After the schema-handoff clarification, the affected contract command returned
`10 passed in 0.08s`. After adding the exact operation envelopes and their real
merge-contract test, the same command returned `11 passed in 0.21s`. Both skill
validators again returned `Skill is valid!`, and `git diff --check` again produced
no output. The final skill measurements are 129 lines/960 words for Codex and
129 lines/951 words for Claude. Task 9 owns the full integration suite.

The fresh pre-commit repetition returned `11 passed in 0.22s`; both validators
again returned `Skill is valid!`, `git diff --check` and
`git diff --cached --check` produced no output, and the tracked worktree was clean
after commit.

## Native smoke status and limitations

The controller independently inspected the first updated native Codex smoke in
`native-updated-evidence/report.md`. It completed in state mode at execution
revision 12 with exactly two accepted attempts and an inactive worker slot. The
two distinct workers were `/root/native_updated_codex/increment_1_investigate`
and `/root/native_updated_codex/increment_2_fix`; both used Sol, high reasoning,
and `fork_turns: none`. The first only investigated and saved evidence while the
parser hash remained unchanged. The second used `list_symbols` followed by
`replace_function_body`, preserved the evaluator-owned test hash, and fixed the
parser. Both workers reached observed terminal state, both updates were accepted,
and the two checkpoints recorded the expected failing then passing gates.

The separate reviewer `/root/native_updated_codex/independent_review` used Sol,
high reasoning, and fresh context, independently reran the exact acceptance command,
returned `VERDICT: pass`, and was recorded against the final checkpoint hash before
the goal completed. Evaluator acceptance also returned 3/3 passing tests; the test
SHA-256 remained `e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86`.
No formatting or implementation repair request was used.

The first smoke also confirmed the documented transcript limitation: complete native
worker/reviewer transcript export was unavailable. The controller preserved exact
dispatch prompt copies, packet paths and hashes, host handles/status observations,
updates, evidence files, audit records, gates, and review output instead. Those
records showed both worker prompts received the packet but only a coordinator
summary of update fields; neither received the explicitly referenced full shared
schema required by the integration notes. The packet procedure is intentionally
short and does not contain full operation shapes. Both skills and the shared
reference now explicitly require dispatching the resolved `Packet and update`
section as a protocol artifact. The first smoke's successful parser/lifecycle
result was retained rather than overstated as evidence for the missing handoff
requirement; the corrected handoff was tested separately below.

The controller independently inspected the corrected smoke under
`native-confirmed-evidence/`. It completed a state-mode goal at revision 12 with
exactly two accepted attempts, two checkpoints (expected fail, then pass), and no
active attempt. The saved packets were 1,815 and 4,116 bytes. Distinct Sol/high,
`fork_turns: none` workers `/root/native_confirmed_codex/horizon_increment_001`
and `/root/native_confirmed_codex/horizon_increment_002` performed investigation
and implementation respectively; both exact saved dispatches explicitly name the
resolved shared reference and its `Packet and update` section. Neither worker used
a repair request.

The separate Sol/high fresh reviewer
`/root/native_confirmed_codex/horizon_independent_review` returned PASS and was
recorded against tree hash
`c9453ecc61e7947cd15227303ed318cb669df5fc3123c6b5f1fede65e73ba6d9`
before completion. The evaluator-owned test hash remained
`e280cf50c2b5b21c99b9aa6e42f67dc140862afa64dbd3a8c84cda94a6ebab86`,
and root independently wrote `evaluator-acceptance.txt` from a 3/3 passing run.
The coordinator report's wording that calls this worker output is inaccurate; it
is evaluator evidence, not an exported worker transcript. Complete native
collaboration and AST-editor transcripts remained unavailable, so actual CLI JSON,
dispatch copies, handles/status observations, artifacts, hashes, gate output, and
the review bound the claims. The corrected handoff requirement is behaviorally
confirmed. The later exact JSON-envelope prose/examples were validated against the
actual merge contract and do not warrant another full native run.

Native Claude remains unavailable: `native-claude-capability.md` records the one
authorized Task 8 recheck of `/Users/deeps/.local/bin/claude` 2.1.276. `claude auth
status --json` exited 1 with `loggedIn: false`, `authMethod: none`, and
`apiProvider: firstParty`. No login, credential, permission, or global-setting
change was attempted. Claude state-mode behavior is therefore unverified and must
be described as experimental; shared `--runtime claude` CLI coverage is not a
native Claude result.

## Self-review and concerns

The final diff is limited to the two Horizon entrypoints, shared CLI reference,
README, and skill contract test. Both entrypoints retain their own runtime, state
path, worker tool, schedule guidance, harness symlink, and shared-reference link.
Conversation mode remains the default and its existing increment workflow remains
separate. State instructions give workers the packet, referenced artifacts, and
resolved complete schema while keeping lifecycle ownership with the coordinator.
The reference uses the real CLI argument names and distinguishes packet base
revision from current execution revision. Its operation examples now pass the real
merge validator, including exact `entry` versus `id` keys.

No known local contract or validator concern remains. Native Claude behavior is
still unverified/experimental because the installed CLI is unauthenticated. Full
native transcript export was unavailable in both Codex smoke runs; the preserved
artifacts and scope of that limitation are stated above.
