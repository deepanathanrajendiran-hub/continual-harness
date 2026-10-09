import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from bench.evo import config, copies
from bench.evo import harborcheck as hc
from bench.tb4 import run as tb4run
from bench.tb4.copies import tree_digest

FIRST, SECOND = hc.STEPS
QUIET = {"log": lambda message: None}


def cp(cmd, code=0, out=""):
    return subprocess.CompletedProcess(cmd, code, out, "")


# ---------------------------------------------------------------- the dummy task


def test_dummy_task_toml_is_the_generated_default():
    text = (hc.DUMMY / "task.toml").read_text()
    assert text == hc.dummy_toml()
    data = tomllib.loads(text)
    assert [s["name"] for s in data["steps"]] == list(hc.STEPS)
    assert data["multi_step_reward_strategy"] == "mean"
    assert data["agent"]["timeout_sec"] == 1800.0
    assert data["verifier"]["timeout_sec"] == hc.VERIFIER_TIMEOUT_SEC
    assert data["verifier"]["collect"] == [{"command": hc.BEFORE_COLLECT_COMMAND, "timeout_sec": 60.0}]


def test_dummy_has_every_step_file_and_an_arch_neutral_image():
    for name in hc.STEPS:
        for rel in ("instruction.md", "tests/test.sh", "solution/solve.sh"):
            assert (hc.DUMMY / "steps" / name / rel).is_file(), (name, rel)
    assert (hc.DUMMY / "steps" / FIRST / "tests" / hc.TESTS_MARKER).is_file()
    dockerfile = (hc.DUMMY / "environment" / "Dockerfile").read_text()
    assert dockerfile.startswith("FROM ubuntu:22.04\n")
    assert "amd64" not in dockerfile and "x86_64" not in dockerfile
    assert "COPY probe.sh /opt/evo-check/probe.sh" in dockerfile and hc.IMAGE_FILE in dockerfile
    assert "apt-get" not in dockerfile  # no network step: probe.sh needs only what ubuntu:22.04 ships


def test_instructions_and_solutions_run_the_same_probe_commands():
    for name, command in ((FIRST, "bash /opt/evo-check/probe.sh plant"),
                          (SECOND, f"bash /opt/evo-check/probe.sh record {SECOND}")):
        step = hc.DUMMY / "steps" / name
        assert command in (step / "instruction.md").read_text()
        assert command in (step / "solution" / "solve.sh").read_text()
    assert "bash /opt/evo-check/probe.sh plant" in hc.SLEEP_INSTRUCTION and hc.SLEEPER in hc.SLEEP_INSTRUCTION
    assert hc.CANARY_REL in hc.CANARY_INSTRUCTION and "Write tool" in hc.CANARY_INSTRUCTION


def test_every_dummy_script_parses():
    scripts = sorted(hc.DUMMY.rglob("*.sh"))
    assert len(scripts) == 5
    for script in scripts:
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0, script


def test_probe_plants_and_records_the_files_the_findings_read(tmp_path):
    root, home, project = tmp_path / "root", tmp_path / "home", tmp_path / "project"
    for d in (root / "tmp", root / "tests", root / "logs" / "verifier", home, project):
        d.mkdir(parents=True)
    (root / "tests" / hc.TESTS_MARKER).write_text("x\n")
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(home), "EVO_CHECK_ROOT": str(root),
           "EVO_CHECK_DECOY": "0"}
    probe = hc.DUMMY / "environment" / "probe.sh"
    assert subprocess.run(["bash", str(probe), "plant"], cwd=project, env=env).returncode == 0
    assert subprocess.run(["bash", str(probe), "record", "later"], cwd=project, env=env).returncode == 0
    out = root / "logs" / "artifacts" / "probe"
    assert sorted(p.name for p in out.iterdir()) == sorted([FIRST, hc.PLANTED, "later"])
    for label in (FIRST, hc.PLANTED, "later"):
        assert sorted(p.name for p in (out / label).iterdir()) == sorted(hc.PROBE_FILES)
    planted = out / hc.PLANTED
    assert hc.SENTINEL in (planted / "tmp.txt").read_text().splitlines()
    assert hc.SENTINEL not in (out / FIRST / "tmp.txt").read_text().splitlines()
    assert (planted / "ledger.txt").read_text().splitlines() == sorted(hc.LEDGER_FILES)
    assert hc.MEMORY_FILE in (planted / "dot-claude.txt").read_text().splitlines()
    assert hc.TESTS_MARKER in (planted / "tests.txt").read_text().splitlines()
    assert (home / ".claude" / "projects" / "-app" / "memory" / "check.md").is_file()
    assert subprocess.run(["bash", str(probe), "bogus"], cwd=project, env=env,
                          capture_output=True).returncode == 2


# ---------------------------------------------------------------- variants and copies


@pytest.mark.parametrize("variant, steps, verifier_timeout, agent_timeout", [
    ("check", hc.STEPS, 120.0, None),
    ("vtimeout", hc.STEPS[:1], 20.0, None),
    ("probe", hc.STEPS, 120.0, 60.0),
    ("canary", hc.STEPS[:1], 120.0, None),
])
def test_variants(tmp_path, variant, steps, verifier_timeout, agent_timeout):
    dest = hc.build_variant(tmp_path / "v", variant)
    data = tomllib.loads((dest / "task.toml").read_text())
    assert [s["name"] for s in data["steps"]] == list(steps)
    assert sorted(p.name for p in (dest / "steps").iterdir()) == sorted(steps)
    assert data["verifier"]["timeout_sec"] == verifier_timeout
    assert data["steps"][0].get("agent", {}).get("timeout_sec") == agent_timeout
    instruction = (dest / "steps" / FIRST / "instruction.md").read_text()
    assert (instruction == hc.SLEEP_INSTRUCTION) == (variant == "probe")
    assert (instruction == hc.CANARY_INSTRUCTION) == (variant == "canary")
    assert (dest / "steps" / FIRST / "tests" / "sleep_sec").is_file() == (variant == "vtimeout")


def test_variant_refuses_unknown_names_and_existing_destinations(tmp_path):
    with pytest.raises(ValueError):
        hc.build_variant(tmp_path / "x", "nope")
    hc.build_variant(tmp_path / "v", "check")
    with pytest.raises(FileExistsError):
        hc.build_variant(tmp_path / "v", "check")


@pytest.mark.parametrize("variant", hc.VARIANTS)
@pytest.mark.parametrize("kind", ("agent", "validation"))
def test_prepared_copies_carry_the_main_run_hooks(tmp_path, variant, kind):
    before = tree_digest(hc.DUMMY)
    task = hc.prepare(tmp_path / "work", variant, kind, "evo-local/dummy:test")
    assert tree_digest(hc.DUMMY) == before
    data = tomllib.loads((task / "task.toml").read_text())
    assert data["environment"]["docker_image"] == "evo-local/dummy:test"
    assert data["verifier"]["collect"][0]["command"] == hc.BEFORE_COLLECT_COMMAND
    for step in data["steps"]:
        assert step["verifier"]["timeout_sec"] == data["verifier"]["timeout_sec"]
        assert any(c["command"] == copies.COLLECT_COMMAND(step["name"]) for c in step["verifier"]["collect"])
        assert (task / "steps" / step["name"] / "workdir" / "setup.sh").read_text() == copies.SETUP_SH
        assert (task / "steps" / step["name"] / "solution" / "solve.sh").is_file() == (kind == "validation")
    if variant == "probe":
        assert data["steps"][0]["agent"]["timeout_sec"] == hc.PROBE_AGENT_TIMEOUT_SEC


# ---------------------------------------------------------------- harbor commands


def test_claude_code_check_uses_the_main_run_flags(tmp_path):
    cmd = hc.check_command(tmp_path / "task", "claude-code", "check__dummy__control__a1", tmp_path / "jobs",
                           prompt=tmp_path / "p.md")
    pairs = {(cmd[i], cmd[i + 1]) for i in range(len(cmd) - 1)}
    for pair in (("-p", str(tmp_path / "task")), ("-a", "claude-code"), ("-m", config.MODEL),
                 ("--effort", "high"), ("--ak", "version=2.1.293"), ("--ak", "disable_web_search=true"),
                 ("--ae", "CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}"),
                 ("--ae", "CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000"), ("--agent-timeout-multiplier", "1.0"),
                 ("--agent-setup-timeout-multiplier", "2.0"), ("--extra-instruction-path", str(tmp_path / "p.md")),
                 ("--ek", "keep_containers=true"), ("-n", "1"), ("-k", "1"), ("-r", "0"),
                 ("-o", str(tmp_path / "jobs")), ("--job-name", "check__dummy__control__a1")):
        assert pair in pairs, pair
    assert cmd[:2] == ["harbor", "run"] and cmd[-1] == "-y"
    assert "--no-force-build" in cmd and "--resume-trajectory" not in cmd and "--skill" not in cmd


def test_oracle_check_has_no_model_flags_and_a_skill_is_appended(tmp_path):
    oracle = hc.check_command(tmp_path / "t", "oracle", "j", tmp_path / "jobs")
    assert oracle[oracle.index("-a") + 1] == "oracle"
    assert not {"-m", "--ak", "--ae", "--effort", "--extra-instruction-path"} & set(oracle)
    with_skill = hc.check_command(tmp_path / "t", "claude-code", "j", tmp_path / "jobs", skill=tmp_path / "horizon")
    assert with_skill[-2:] == ["--skill", str(tmp_path / "horizon")]


# ---------------------------------------------------------------- fixture trial directories


def good_files() -> dict:
    """What a passing two-round check leaves in its trial directory, keyed by relative path."""
    def probe(step, label, **overrides):
        files = {"pwd.txt": "/app", "user.txt": "root", "home.txt": "/root", "tmp.txt": "claude-0",
                 "project.txt": "a.txt", "tests.txt": "", "verifier.txt": "", "dot-claude.txt": "",
                 "ledger.txt": "", "procs.txt": "1 0 sleep infinity"}
        files.update(overrides)
        return {f"steps/{step}/artifacts/logs/artifacts/probe/{label}/{k}": v for k, v in files.items()}

    ledger = "\n".join(sorted(hc.LEDGER_FILES))
    decoy = f"1 0 sleep infinity\n42 1 {hc.DECOY}"
    files = {}
    files.update(probe(FIRST, FIRST))
    files.update(probe(FIRST, hc.PLANTED, **{"tmp.txt": hc.SENTINEL, "ledger.txt": ledger,
                                             "dot-claude.txt": f".claude\n{hc.MEMORY_FILE}", "procs.txt": decoy}))
    files.update(probe(FIRST, hc.BEFORE, **{"ledger.txt": ledger, "procs.txt": decoy}))
    files.update(probe(SECOND, SECOND, **{"project.txt": ".claude\na.txt", "ledger.txt": ledger}))
    files.update(probe(SECOND, hc.BEFORE, **{"ledger.txt": ledger}))
    files[f"steps/{FIRST}/verifier/{hc.VERIFIER_MARKER}"] = f"{hc.TESTS_MARKER}\ntest.sh"
    for step in hc.STEPS:
        files[f"steps/{step}/artifacts/logs/artifacts/{step}/harness/goals/check-goal.json"] = "{}"
        files[f"steps/{step}/verifier/reward.txt"] = "1"
    return files


def step_result(name, reward=1.0, exception=None):
    return {"step_name": name,
            "verifier_result": {"rewards": {"reward": reward}} if reward is not None else None,
            "exception_info": ({"exception_type": exception[0], "exception_message": exception[1]}
                               if exception else None),
            "agent_execution": {"started_at": "2026-10-10T10:00:00Z", "finished_at": "2026-10-10T10:01:00Z"},
            "verifier": {"started_at": "2026-10-10T10:01:00Z", "finished_at": "2026-10-10T10:01:05Z"}}


def make_trial(root: Path, files=None, steps=None):
    trial = root / "dummy__AbC1234"
    trial.mkdir(parents=True)
    for rel, text in (good_files() if files is None else files).items():
        path = trial / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
    result = {"trial_name": trial.name,
              "step_results": steps if steps is not None else [step_result(n) for n in hc.STEPS]}
    (trial / "result.json").write_text(json.dumps(result))
    return trial, result


def _set(files, step, label, name, text):
    files[f"steps/{step}/artifacts/logs/artifacts/probe/{label}/{name}"] = text
    return files


def _drop(files, rel):
    del files[rel]
    return files


def test_a_clean_check_passes(tmp_path):
    trial, result = make_trial(tmp_path)
    findings = hc.check_findings(trial, result)
    assert findings["failures"] == [] and findings["ok"] is True
    assert findings["facts"]["user"] == "root" and findings["facts"]["pwd"] == "/app"
    assert findings["facts"]["rewards"] == {FIRST: 1.0, SECOND: 1.0}


BREAKS = {
    "round 1 setup did not run": (lambda f: _set(f, FIRST, FIRST, "tmp.txt", hc.IMAGE_FILE),
                                  f"{FIRST}: setup.sh did not empty /tmp"),
    "round 2 tmp kept": (lambda f: _set(f, SECOND, SECOND, "tmp.txt", hc.SENTINEL),
                         f"{SECOND}: setup.sh did not empty /tmp"),
    "ledger wiped": (lambda f: _set(f, SECOND, SECOND, "ledger.txt", ""),
                     f"{SECOND}: setup.sh removed the ledger files"),
    "memory kept": (lambda f: _set(f, SECOND, SECOND, "dot-claude.txt", hc.MEMORY_FILE),
                    f"{SECOND}: setup.sh left the ~/.claude/projects memory"),
    "memory never planted": (lambda f: _set(f, FIRST, hc.PLANTED, "dot-claude.txt", ".claude"),
                             f"{FIRST}: the ~/.claude/projects memory was not planted"),
    "setup left": (lambda f: _set(f, SECOND, SECOND, "project.txt", "a.txt\nsetup.sh"),
                   f"{SECOND}: setup.sh is still in the project"),
    "decoy survived": (lambda f: _set(f, SECOND, SECOND, "procs.txt", f"7 1 {hc.DECOY}"),
                       f"{SECOND}: the collect hook left the stray claude decoy running"),
    "decoy never ran": (lambda f: _set(f, FIRST, hc.BEFORE, "procs.txt", "1 0 sleep infinity"),
                        f"{FIRST}: the stray claude decoy was not running before the collect hook"),
    "tests readable": (lambda f: _set(f, SECOND, SECOND, "tests.txt", hc.TESTS_MARKER),
                       f"{SECOND}: round 1's /tests is readable"),
    "verifier readable": (lambda f: _set(f, SECOND, SECOND, "verifier.txt", hc.VERIFIER_MARKER),
                          f"{SECOND}: round 1's /logs/verifier is readable"),
    "no collect copy": (lambda f: _drop(f, f"steps/{SECOND}/artifacts/logs/artifacts/{SECOND}/harness/goals/"
                                           "check-goal.json"),
                        f"{SECOND}: the collect hook did not copy the ledger"),
    "probe missing": (lambda f: _drop(f, f"steps/{SECOND}/artifacts/logs/artifacts/probe/{SECOND}/tmp.txt"),
                      f"{SECOND}: probe file {SECOND}/tmp.txt missing"),
    "tests never seen": (lambda f: _drop(f, f"steps/{FIRST}/verifier/{hc.VERIFIER_MARKER}"),
                         f"{FIRST}: the verifier did not list {hc.TESTS_MARKER} in /tests"),
    "sentinel never planted": (lambda f: _set(f, FIRST, hc.PLANTED, "tmp.txt", ""),
                               f"{FIRST}: the /tmp sentinel was not planted"),
}


@pytest.mark.parametrize("name", sorted(BREAKS))
def test_each_broken_behaviour_is_named(tmp_path, name):
    mutate, expected = BREAKS[name]
    trial, result = make_trial(tmp_path, files=mutate(good_files()))
    findings = hc.check_findings(trial, result)
    assert findings["ok"] is False
    assert any(f.startswith(expected) for f in findings["failures"]), findings["failures"]


def test_rewards_exceptions_and_missing_rounds_fail(tmp_path):
    trial, result = make_trial(tmp_path / "a", steps=[step_result(FIRST, reward=0.0)])
    failures = hc.check_findings(trial, result)["failures"]
    assert f"{FIRST}: reward 0.0, expected 1.0" in failures and f"{SECOND}: did not run" in failures
    timed_out = step_result(FIRST, exception=("AgentTimeoutError", "Agent execution timed out after 1800.0 seconds"))
    trial, result = make_trial(tmp_path / "b", steps=[timed_out, step_result(SECOND)])
    assert any(f.startswith(f"{FIRST}: AgentTimeoutError") for f in hc.check_findings(trial, result)["failures"])
    assert hc.check_findings(None, None) == {"ok": False, "failures": ["no trial directory with result.json"],
                                             "facts": {}}


def test_verifier_timeout_passes_only_on_the_short_override(tmp_path):
    short = ("VerifierTimeoutError", "Verifier execution timed out after 20.0 seconds")
    trial, result = make_trial(tmp_path / "a", files={}, steps=[step_result(FIRST, reward=None, exception=short)])
    assert hc.verifier_timeout_findings(trial, result)["ok"] is True
    trial, result = make_trial(tmp_path / "b", files={}, steps=[step_result(FIRST, reward=1.0)])
    findings = hc.verifier_timeout_findings(trial, result)
    assert findings["ok"] is False and "no exception" in findings["failures"][0]
    default = ("VerifierTimeoutError", "Verifier execution timed out after 600.0 seconds")
    trial, result = make_trial(tmp_path / "c", files={}, steps=[step_result(FIRST, reward=None, exception=default)])
    assert hc.verifier_timeout_findings(trial, result)["ok"] is False


def test_timeout_probe_records_without_asserting(tmp_path):
    claude = "claude --verbose --output-format=stream-json --print"
    files = {
        f"steps/{FIRST}/artifacts/logs/artifacts/probe/{hc.BEFORE}/procs.txt":
            f"1 0 sleep infinity\n50 1 {claude}\n51 50 /bin/bash -c sleep 600\n52 51 sleep 600\n42 1 {hc.DECOY}",
        f"steps/{SECOND}/artifacts/logs/artifacts/probe/{SECOND}/procs.txt":
            f"1 0 sleep infinity\n52 1 sleep 600\n90 1 {claude}",
        f"steps/{FIRST}/artifacts/logs/artifacts/{FIRST}/harness/goals/check-goal.json": "{}",
    }
    timed_out = step_result(FIRST, reward=0.0, exception=("AgentTimeoutError",
                                                          "Agent execution timed out after 60.0 seconds"))
    trial, result = make_trial(tmp_path, files=files, steps=[timed_out, step_result(SECOND)])
    out = hc.timeout_probe_findings(trial, result)
    assert out["ok"] is None and out["failures"] == []
    rec = out["recorded"]
    assert rec["round_1_exception"]["type"] == "AgentTimeoutError"
    assert rec["round_1_verifier_ran"] is True and rec["round_1_reward"] == 0.0
    assert rec["round_1_ledger_collected"] is True
    assert rec["round_2_started"] is True and rec["round_2_reward"] == 1.0
    assert rec["running_before_collect"] == [claude, "/bin/bash -c sleep 600", "sleep 600", hc.DECOY]
    assert rec["still_running_in_round_2"] == ["sleep 600"]
    assert rec["claude_like_in_round_2"] == [claude]
    assert hc.timeout_probe_findings(None, None)["ok"] is False


def canary_stream(is_error, target="/app/.claude/harness/gates/x/request.md"):
    events = [
        {"type": "system", "subtype": "init", "claude_code_version": "2.1.293"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": target, "content": "canary\n"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": is_error,
             "content": "denied" if is_error else "File created successfully"}]}},
        {"type": "result", "subtype": "success", "is_error": False, "result": "Done."},
    ]
    return "\n".join(json.dumps(e) for e in events)


@pytest.mark.parametrize("is_error, collected, ok", [
    (False, True, True), (True, False, False), (True, True, False), (False, False, False)])
def test_canary_needs_a_successful_write_and_the_collected_file(tmp_path, is_error, collected, ok):
    files = {f"steps/{FIRST}/agent/claude-code.txt": canary_stream(is_error)}
    if collected:
        files[f"steps/{FIRST}/artifacts/logs/artifacts/{FIRST}/harness/gates/x/request.md"] = "canary"
    trial, result = make_trial(tmp_path, files=files, steps=[step_result(FIRST)])
    findings = hc.canary_findings(trial, result)
    assert findings["ok"] is ok
    assert findings["facts"]["writes"] == [{"file_path": "/app/.claude/harness/gates/x/request.md",
                                            "is_error": is_error,
                                            "result": "denied" if is_error else "File created successfully"}]


# ---------------------------------------------------------------- whole runs against a fake host


class FakeHost:
    """Answers docker and harbor calls; `harbor run` writes the given trial into its job directory."""

    def __init__(self, files=None, steps=None, arch="arm64"):
        self.calls, self.envs = [], []
        self.files, self.steps, self.arch = files, steps, arch

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[:2] == ["harbor", "run"]:
            self.envs.append(kwargs.get("env"))
            make_trial(Path(cmd[cmd.index("-o") + 1]) / cmd[cmd.index("--job-name") + 1],
                       files=self.files, steps=self.steps)
            return cp(cmd)
        if cmd[0] == "docker" and "inspect" in cmd:
            return cp(cmd, 0, json.dumps([{"Id": "sha256:dummy", "Architecture": self.arch,
                                           "Config": {"WorkingDir": "/app", "User": ""}}]))
        return cp(cmd)


def test_run_check_end_to_end_with_a_fake_host(tmp_path):
    host = FakeHost()
    out = hc.run_check(tmp_path, agent="claude-code", token="tok", run=host, **QUIET)
    assert out["ok"] is True and out["job_name"] == "check__dummy__control__a1"
    assert out["image_id"] == "sha256:dummy" and out["arch"] == "arm64"
    saved = json.loads((tmp_path / "checks" / "check__dummy__control__a1" / "findings.json").read_text())
    assert saved == out
    harbor = next(c for c in host.calls if c[:2] == ["harbor", "run"])
    assert harbor[harbor.index("-a") + 1] == "claude-code"
    task = Path(harbor[harbor.index("-p") + 1])
    assert not list(task.rglob("solution"))
    prompt = Path(harbor[harbor.index("--extra-instruction-path") + 1])
    assert prompt.read_text() == config.prompt_text("control", 30)
    assert host.envs[0]["CLAUDE_CODE_OAUTH_TOKEN"] == "tok" and host.envs[0]["CLAUDE_FORCE_OAUTH"] == "1"
    assert any(c[:2] == ["docker", "build"] and config.image_tag("dummy") in c for c in host.calls)
    with pytest.raises(FileExistsError):
        hc.run_check(tmp_path, agent="claude-code", token="tok", run=host, **QUIET)


def test_oracle_check_keeps_solutions_needs_no_token_and_flags_a_wrong_arch(tmp_path):
    host = FakeHost(arch="amd64")
    out = hc.run_check(tmp_path, agent="oracle", run=host, **QUIET)
    assert out["job_name"] == "check__dummy__oracle__a1" and out["ok"] is False
    assert out["failures"][0] == "image architecture amd64, expected arm64"
    harbor = next(c for c in host.calls if c[:2] == ["harbor", "run"])
    assert host.envs == [None] and "--extra-instruction-path" not in harbor
    task = Path(harbor[harbor.index("-p") + 1])
    assert (task / "steps" / FIRST / "solution" / "solve.sh").is_file()


def test_claude_code_runs_need_a_token_and_agents_are_checked(tmp_path):
    with pytest.raises(ValueError):
        hc.run_check(tmp_path, agent="claude-code", token=None, run=FakeHost(), **QUIET)
    with pytest.raises(ValueError):
        hc.run_job("check", "codex", "j", tmp_path, run=FakeHost(), **QUIET)


def test_vtimeout_probe_and_canary_jobs(tmp_path):
    short = ("VerifierTimeoutError", "Verifier execution timed out after 20.0 seconds")
    vt = hc.verifier_timeout_check(tmp_path, run=FakeHost(files={}, steps=[step_result(FIRST, None, short)]),
                                   **QUIET)
    assert vt["job_name"] == "check__dummy-vtimeout__oracle__a1" and vt["ok"] is True
    assert vt["variant"] == "vtimeout"
    pr = hc.timeout_probe(tmp_path, "tok", run=FakeHost(files={}, steps=[step_result(FIRST), step_result(SECOND)]),
                          **QUIET)
    assert pr["job_name"] == "check__dummy-probe__control__a1" and pr["ok"] is None
    host = FakeHost(files={f"steps/{FIRST}/agent/claude-code.txt": canary_stream(False),
                           f"steps/{FIRST}/artifacts/logs/artifacts/{FIRST}/harness/gates/x/request.md": "canary"},
                    steps=[step_result(FIRST)])
    ca = hc.canary(tmp_path, "tok", skill=tmp_path / "bundle", run=host, **QUIET)
    assert ca["job_name"] == "canary__dummy__horizon__a1" and ca["ok"] is True
    harbor = next(c for c in host.calls if c[:2] == ["harbor", "run"])
    assert harbor[-2:] == ["--skill", str(tmp_path / "bundle")]
    task = Path(harbor[harbor.index("-p") + 1])
    assert (task / "steps" / FIRST / "instruction.md").read_text() == hc.CANARY_INSTRUCTION


def test_a_running_trial_blocks_a_check(tmp_path):
    def busy(cmd, **kwargs):
        if cmd[:3] == ["docker", "ps", "-q"]:
            return cp(cmd, 0, "r1\n")
        if cmd[:2] == ["docker", "inspect"]:
            return cp(cmd, 0, json.dumps([{"Id": "r1", "Config": {"Labels": {
                "com.docker.compose.project": "x__abc1234__env"}}}]))
        return cp(cmd)

    with pytest.raises(tb4run.RunnerBusy):
        hc.run_check(tmp_path, agent="oracle", run=busy, **QUIET)
    assert not (tmp_path / "checks").exists()


def test_main_dispatches_and_sets_the_exit_code(tmp_path, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(hc, "run_check", lambda runs, **kw: seen.append(("check", kw["agent"], kw["token"]))
                        or {"job_name": "j", "ok": True, "failures": []})
    monkeypatch.setattr(hc, "canary", lambda runs, token, **kw: seen.append(("canary", token, kw["skill"]))
                        or {"job_name": "c", "ok": False, "failures": ["x"]})
    monkeypatch.setattr(hc, "timeout_probe", lambda runs, token, **kw: seen.append(("probe", token))
                        or {"job_name": "p", "ok": None, "failures": [], "recorded": {"a": 1}})
    monkeypatch.setattr(hc.tb4run, "read_token", lambda: "tok")
    assert hc.main(["check", "--agent", "oracle", "--runs", str(tmp_path)]) == 0
    assert hc.main(["canary", "--skill", str(tmp_path / "s"), "--runs", str(tmp_path)]) == 1
    assert hc.main(["probe", "--runs", str(tmp_path)]) == 0
    assert seen == [("check", "oracle", None), ("canary", "tok", tmp_path / "s"), ("probe", "tok")]
    assert '"recorded"' in capsys.readouterr().out
