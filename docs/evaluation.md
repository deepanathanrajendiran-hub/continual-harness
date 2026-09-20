# Evaluating horizon and refine

Passing tests establishes implementation behavior. It does not establish that
the skills improve an agent's success rate, time, or cost.

The earlier [interruption experiment](superpowers/bench2-interruption.md) had
three runs per arm. Both baseline and horizon completed 3/3 tasks, needed three
stints, and reported zero redone work. Mean tokens were approximately 119.9k
baseline and 118.0k horizon. This small result does not demonstrate an outcome
advantage. Keep it separate from the current version's regression results.

## Repeatable comparison

Use four conditions: baseline, horizon only, refine only, and both. For each
condition keep the model/version, available tools, task inputs, budget, and
interruption schedule fixed. Start from isolated repository copies and clean
runtime state. Do not let notes or solutions leak between conditions.

Include independent task families:

- Code: a refactor with integration tests and hidden behavioral cases.
- Research: a source-backed report with explicit coverage requirements.
- Decision work: a recommendation with conflicting evidence and stated tradeoffs.
- Interruption: resume both immediately after and midway through an increment.

For refine conditions, use a training task to produce an authorized lesson and
a held-out later task that can exercise it. Keep the held-out task out of the
lesson-generation context. Compare against the identical later task with no
lesson. Record a missing lesson as a result, not a reason to discard a run.

Before running, freeze the success rubric and equal token/time limits. Use
reviewers who see raw artifacts and the rubric but not condition labels or
the producing agent's claimed success. Preserve all failures and timeouts.
Use multiple paired runs per task and report the sample size; choose a larger
sample if a pilot shows high variation.

## Record per run

| Field | Meaning |
| --- | --- |
| Condition, task ID, model/version | Reproducibility and comparison groups |
| Final success and unmet criteria | Independent outcome assessment |
| False completion | Agent claimed success while a required criterion failed |
| Tokens, elapsed time, increments | Cost of reaching the outcome or limit |
| Redone work after interruption | Repeated work caused by missing or unused state |
| Lesson entry and later task reference | Which refinement was actually exercised |
| Helpful/ineffective/harmful observation | Concrete behavior with supporting evidence |
| Unassessed lessons | Applied lessons that no later task exercised |

Retain raw transcripts, artifacts, gate output, review evidence, and interruption
points. Use `refine-outcome` for observed lesson results; the ledger does not
collect model token usage or run this experiment automatically. An agent's own
outcome label is supporting evidence, not the independent evaluation result.

Report paired differences, dispersion, failures, and uncertainty. Separate
correctness improvements such as rejecting stale completion from claims that
an agent completed more tasks. Do not tune the skill on the held-out evaluation
and then describe that same set as an independent test.
