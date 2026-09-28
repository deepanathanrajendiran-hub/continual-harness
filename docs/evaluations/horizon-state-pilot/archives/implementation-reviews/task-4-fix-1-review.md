### Spec Compliance

- ✅ Spec compliant for the scoped fix. `attach` validates the slug before constructing a goal path or entering `goal_locked` (`harness/steps.py:233-240`); `_state` and `store_blob` also validate before slug-derived reads or writes (`harness/steps.py:37-63`). The validator excludes `/`, `.`, and other path separators, so a path-like slug cannot create an escaped directory or lock file.
- ✅ Valid goal names remain usable. `goal.slugify` produces Unicode word characters, underscores, and hyphens, and `_unique_slug` appends unrestricted numeric collision suffixes (`harness/goal.py:206-235`). The new `r"[\w-]+"` slug validator accepts that alphabet without imposing the attempt-ID length limit (`harness/steps.py:33-35`); `_require_id` still enforces the ASCII/64-character attempt-ID contract (`harness/steps.py:29-31`, `harness/steps.py:233-235`).
- ⚠️ Terminal result shape remains a Task 5 integration check: `attempt.result.checkpoint` is historical, while `goal.summary.last_checkpoint` remains current, as recorded in `task-5-integration-notes.md`. This fix does not alter that boundary.

### Strengths

- The invalid-slug regression asserts that no escaped directory exists after rejection (`tests/test_horizon_steps.py:211-219`). Both runtime fixture variants also exercise Unicode and leading-underscore slugs through reservation and binding (`tests/test_horizon_steps.py:221-229`).
- The change is limited to the slug boundary and its focused tests; the attempt-ID validator and reservation flow are unchanged (`harness/steps.py:29-63`, `harness/steps.py:233-240`).

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

None.

### Assessment

**Task quality:** Approved.

**Reasoning:** The fix closes the lock-path side effect and preserves the goal slug alphabet, including collision suffixes, without relaxing request or attempt IDs. No new breakage is apparent in the scoped diff.

**Checks:** Read the fix diff once and the appended fix evidence; inspected only unchanged `goal.slugify` and `_unique_slug` to verify the named compatibility risk. Did not rerun the reported focused suite (`46 passed`).
