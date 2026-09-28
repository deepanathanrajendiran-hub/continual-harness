### Spec Compliance

- ❌ Issues found: `attach` enters the goal lock using an unvalidated slug (`harness/steps.py:226`) and only validates it when `_state` runs inside that lock (`harness/steps.py:227`). The shared ID contract requires a valid slug. A slug containing `../` can make `goal._path` point outside the goal directory (`harness/goal.py:238`); `goal_locked` then creates the parent and lock file there (`harness/filelock.py:129-133`) before the request is rejected. Validate the slug before deriving the lock path, as `begin` already does.
- ⚠️ Cannot verify from this diff: Task 5/6 must save each terminal attempt's own `last_checkpoint` and outcome in `attempt.result` for `report` to preserve them after an independent review. `report` overlays that saved object on the current summary (`harness/steps.py:136-141`), and Task 4's replay test supplies it manually (`tests/test_horizon_steps.py:180-197`).

### Strengths

- `begin` checks request replay before admission, prepares the packet outside the lock, rechecks replay and revision under the lock, validates the current snapshot and procedure, then commits one reserved turn (`harness/steps.py:154-214`). The stale snapshot and revision tests check that neither failure charges a turn (`tests/test_horizon_steps.py:135-169`).
- Packet bytes are stored under their SHA-256 with a unique temporary file and atomic replacement; reads check project containment, filename, and digest (`harness/steps.py:54-109`). Replay and attach also check canonical packet bytes, attempt identity, base revision, and procedure digest (`harness/steps.py:112-130`).
- Rebinding the same handle returns before the stale revision check, while a different handle conflicts; attaching does not rehash the source tree after the worker may have started editing (`harness/steps.py:235-253`, `tests/test_horizon_steps.py:199-207`). The fixture runs these behaviors under both runtime markers (`tests/conftest.py:10-32`).

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `harness/steps.py:226`: Validate `slug` before calling `filelock.goal_locked(goal._path(slug))`. The current ordering permits an invalid path-like slug to create a directory and `.flock` file outside the goal directory before `_state` raises `StepError`; this is an avoidable filesystem side effect from invalid protocol input.

#### Minor (Nice to Have)

None.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** Reservation, replay, blob integrity, and worker binding follow the requested transition and have focused coverage. The invalid-slug lock path is a concrete boundary error; the terminal replay outcome depends on later tasks persisting the saved result fields.

**Checks:** Reviewed the supplied diff once; inspected only unchanged `goal._path`, `goal.summary`, `goal.commit_revision`, `filelock.goal_locked`, `paths.project_root`, and `task_state.build_packet`/`procedure` for the named path, replay, lock, and packet integration risks. Did not rerun the reported 157-test focused suite because the code review raised no untested behavior requiring it.
