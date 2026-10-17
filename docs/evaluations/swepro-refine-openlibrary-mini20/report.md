# SWE-bench Pro refine study, plan B with a 20-step cap: refine's notes helped

**Result: positive and significant.** On 44 unseen openlibrary tasks, mini-swe-agent with
DeepSeek V4 Flash passed 103 of 132 runs with refine's frozen notes and 77 of 132 without
them (78% against 58%). The pre-registered primary analysis gives a mean per-task gain of
**+0.197** (95% interval +0.11 to +0.28), two-sided sign-flip **p = 0.0001**. The notes
helped on 21 tasks, hurt on 3 and tied on 20.

This holds for one repository, one cheap model and a tight 20-step cap. It says nothing yet
about stronger models or looser budgets, where the earlier studies hit the ceiling.

## What ran

- **Pool.** The 74 validated openlibrary tasks in SWE-bench Pro v2 (`scaleapi/SWE-bench_Pro-os`
  at `66f92766`), excluding the 8 pilot tasks. Seeded split: 30 practice, 44 test
  (`split.json`).
- **Agent.** mini-swe-agent 2.4.6, `deepseek/deepseek-v4-flash` via LiteLLM, `step_limit` 20
  (Amendment 4), agent timeout 3003 s. Network open only to `api.deepseek.com`; web search
  off. All 9 network probes passed.
- **Practice.** The agent solved the 30 practice tasks in order. After each, refine (Claude Code
  on DeepSeek V4 Flash) read the task statement, the agent's trajectory and a result line
  ("passed" or "failed: K of N graded tests failed") and could make one edit. Only the notes
  file (rho, CLAUDE.md) reaches this agent; it is appended to the system prompt. Practice
  passed 19 of 30; 28 edits, all rho; 2 sessions made no change.
- **Gate and freeze.** 19/30 lay inside the pre-registered band (stop if ≥26 or ≤4), so the
  rule was ask_user; the user said go. The notes, code and analysis were frozen at tag
  `swepro-prereg-openlibrary-mini20` (commit 75779a1, bundle `ec58109a…`). The copy check
  was clean.
- **Test.** Each of the 44 test tasks ran 3 times without notes (plain) and 3 times with the
  frozen notes (refined), the two arms side by side per attempt. Every run was scored by
  re-applying its patch to a pristine image (`patch_replay`).

## Primary result

Two-sided sign-flip permutation on d = refined − plain pass share per task (Monte Carlo,
100,000 draws, seed as frozen), alpha 0.05.

| | |
|---|---|
| Tasks analysed | 44 (none incomplete) |
| Mean d | **+0.197** |
| 95% interval | [+0.11, +0.28] |
| Two-sided p | **0.0001** |
| Refined won / lost / tied | 21 / 3 / 20 |

How the 44 tasks split:

- 14 tasks passed every run in both arms (3/3 vs 3/3) and 2 failed every run in both, so 16
  tasks had no room to move.
- Of the other 28, refined was better on 21: one +3, six +2 and fourteen +1.
- The 3 losses are each one run on a task plain always solved (3/3 → 2/3).

## Per-task results

| Task | Plain | Refined | Diff (passes) |
|---|---|---|---|
| b112069e | 0 /3 | 3 /3 | +3 |
| fdbc0d8f | 1 /3 | 3 /3 | +2 |
| dbbd9d53 | 1 /3 | 3 /3 | +2 |
| c4eebe66 | 0 /3 | 2 /3 | +2 |
| 3c48b4bb | 0 /3 | 2 /3 | +2 |
| 25858f9f | 1 /3 | 3 /3 | +2 |
| 123e6e5e | 1 /3 | 3 /3 | +2 |
| f343c08f | 2 /3 | 3 /3 | +1 |
| f0341c0b | 2 /3 | 3 /3 | +1 |
| e390c121 | 0 /3 | 1 /3 | +1 |
| e010b2a1 | 2 /3 | 3 /3 | +1 |
| c05ccf2c | 0 /3 | 1 /3 | +1 |
| 9bdfd29f | 2 /3 | 3 /3 | +1 |
| 7f6b722a | 0 /3 | 1 /3 | +1 |
| 798a5825 | 0 /3 | 1 /3 | +1 |
| 6afdb09d | 2 /3 | 3 /3 | +1 |
| 53d376b1 | 0 /3 | 1 /3 | +1 |
| 5069b09e | 2 /3 | 3 /3 | +1 |
| 43f9e7e0 | 2 /3 | 3 /3 | +1 |
| 322d7a46 | 1 /3 | 2 /3 | +1 |
| 111347e9 | 0 /3 | 1 /3 | +1 |
| e1e50298 | 3 /3 | 3 /3 | +0 |
| d8162c22 | 3 /3 | 3 /3 | +0 |
| c12943be | 3 /3 | 3 /3 | +0 |
| b67138b3 | 0 /3 | 0 /3 | +0 |
| 9c392b60 | 2 /3 | 2 /3 | +0 |
| 910b0857 | 3 /3 | 3 /3 | +0 |
| 8a5a63af | 3 /3 | 3 /3 | +0 |
| 89e4b443 | 3 /3 | 3 /3 | +0 |
| 7cbfb812 | 0 /3 | 0 /3 | +0 |
| 798055d1 | 2 /3 | 2 /3 | +0 |
| 5c6c22f3 | 3 /3 | 3 /3 | +0 |
| 58999808 | 3 /3 | 3 /3 | +0 |
| 4a5d2a7d | 3 /3 | 3 /3 | +0 |
| 427f1f4e | 1 /3 | 1 /3 | +0 |
| 3f7db6bb | 3 /3 | 3 /3 | +0 |
| 3aeec6af | 3 /3 | 3 /3 | +0 |
| 2abe28b4 | 2 /3 | 2 /3 | +0 |
| 0d13e6b4 | 3 /3 | 3 /3 | +0 |
| 0a90f9f0 | 3 /3 | 3 /3 | +0 |
| 00bec1e7 | 3 /3 | 3 /3 | +0 |
| f8cc11d9 | 3 /3 | 2 /3 | -1 |
| d109cc7e | 3 /3 | 2 /3 | -1 |
| 2fe532a3 | 3 /3 | 2 /3 | -1 |

## Secondary outcomes

| Outcome | Plain | Refined |
|---|---|---|
| Runs | 132 | 132 |
| Passes (re-grade) | 77 | 103 |
| Graded tests failed per run (mean) | 2.34 | 1.12 |
| Tokens per run (mean) | 357k | 343k |
| Agent minutes per run (median) | 1.8 | 1.8 |
| Agent timeouts (3003 s, scored on the patch left) | 24 | 19 |
| Non-zero agent exits (scored 0) | 2 | 1 |
| In-sandbox vs re-grade disagreements | 0 | 0 |
| Invalid after reruns | 0 | 0 |

**Cost.**
- The DeepSeek balance went from $10.19 to $7.51 over the test phase, so the 264 runs cost
  about $2.70.
- The `cost_usd` figures in the records are Claude Code's and LiteLLM's own estimates, not
  money spent. Refine's figure in particular uses Anthropic list prices.

## Validity

| Check | Result |
|---|---|
| Every refined run logged the frozen bundle hash | met |
| No plain run found notes | met |
| Every run has a valid re-grade | met |
| All 9 network probes passed | met |
| Every run used the study's model | met: 261 runs report `deepseek/deepseek-v4-flash`; the 3 non-zero exits ended before reporting a model |
| No transcript touched `/tests`, `/solution` or `/logs/verifier` | **not met: 13 runs flagged** (5 plain, 8 refined) |

The frozen check "Every run reported Claude Code 2.1.293 and claude-sonnet-5-5" was written for
the Claude Code studies and cannot apply to this harness. The model row above replaces it,
and the substitution is recorded in `deviations.md`.

**The 13 flagged runs.** The audit regex matched a root path `/tests`, `/solution` or
`/logs/verifier` in the agent's commands.
- Flagged runs (passes marked): 322d7a46 refined a3 (pass); 7cbfb812 plain a3, refined a2,
  refined a3; 9c392b60 plain a1 (pass), refined a2 (pass); c12943be plain a1 (pass); c4eebe66
  refined a2 (pass), refined a3; d8162c22 plain a2 (pass); e1e50298 plain a1 (pass); f0341c0b
  refined a2 (pass); f8cc11d9 refined a2 (pass).
- 9 of them passed: 4 plain, 5 refined.
- The operator rules forbid reading test-phase transcripts, so what the commands did was not
  inspected. Those paths hold nothing during the agent phase: the images were validated to
  contain no tests or fix. The score comes from re-applying only the code patch to a pristine
  image.

Two sensitivity checks, not pre-registered, both leave the result intact:

| Treatment of flagged runs | Tasks | Mean d | p |
|---|---|---|---|
| As pre-registered (counted) | 44 | +0.197 | 0.0001 |
| Every flagged run scored as a fail | 44 | +0.189 | 0.0003 |
| Every task with a flagged run dropped | 35 | +0.219 | 0.0002 |

## Interim looks

The user asked for the running score five times during the test, at 5, 12, 15, 20 and 41 of 44
tasks. Each look is logged in `deviations.md`. No look changed anything: there is no interim
stopping rule, and the run went to all 44 tasks.

The effect was larger early: 12 better, 0 worse, 8 tied over the first 20 tasks, against 9
better, 3 worse and 12 tied over the last 24.

## What refine learned

The frozen notes (about 2,400 words, `bundle/.claude/CLAUDE.md` in the runs directory) fall
into six themes:
1. budget the 20 steps and get a first edit on disk by step 6;
2. write edits with an anchored heredoc that fails loudly;
3. don't spend steps on vendored infogami, git history, formatters or convention questions;
4. treat the requirement's literals and New Interfaces block as the spec;
5. tell environment failures (database, statsd) and recorded-expectation diffs apart from real
   regressions;
6. a few openlibrary facts, such as the generated `solr_types.py`, `MockSite` and test
   layout.

A review of the notes found:
- several rules trace back to a single practice task (the `requests` migration, the additive
  author-identifier helper, the field-ownership rule);
- about a third of the text is run anecdotes;
- "write early" is restated about five times, since one-edit-per-session refine has no
  consolidation step.

The study measures the notes as refine wrote them. It does not show which parts did the work.

## Limits

- One repository (openlibrary), one model (DeepSeek V4 Flash), one agent (mini-swe-agent).
- The 20-step cap creates much of the headroom, and many notes are about spending steps. At
  100 steps the same agent passed 8 of 8 pilot tasks. Claude Code with Sonnet (29/30) and Haiku
  (30/30) left no headroom on ansible.
- Plain against refined cannot separate useful lessons from the effect of any added text; a
  placebo-notes arm would.
- Part of the gain may be learning this codebase rather than general skill, since practice and
  test tasks come from the same repository.
- The openlibrary fixes are public, so the model may have seen some of them; both arms share
  this.
- Refine edits were auto-approved, which normal refine use does not do.
- The amd64 images ran under Rosetta on Colima, so scores are not comparable with the public
  leaderboard.
- One operator ran the study, and the running score was looked at five times (see above).

## Follow-ups this result suggests

- **Ablations on the same 44 tasks:**
  - notes with single-task rules stripped, to test whether refine overfitted;
  - a terse rewrite with no anecdotes and no repeats, to test the dilution critique;
  - a placebo notes file of the same length.
- **Cap sensitivity:** repeat at a looser cap (for example 40 steps) to see whether the gain is
  mostly step budgeting.
- **Refine design:** a periodic consolidate-and-prune pass or a word budget for the notes file.

## Deviations

See `deviations.md`. This report was written by hand from `summary.json` because the
frozen report template is worded for the Claude Code harness. The numbers come unchanged from
`bench/swepro/analysis.py` at the frozen commit.

## Credit

SWE-bench Pro by Scale AI, MIT License,
<https://github.com/scaleapi/SWE-bench_Pro-os>, commit
`66f92766bba642462d4bbe5479e83f91f9211862`. mini-swe-agent by the SWE-agent team, MIT
License. This report reproduces no hidden tests, reference patches, per-test results or
transcripts.
