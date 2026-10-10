"""Task copies, per-round hooks and prompt files (bench/evo/copies.py). Every task here is synthetic."""
import datetime
import os
import signal
import subprocess
import tomllib

import pytest

from bench.evo import config, copies, patch
from bench.tb4.copies import tree_digest

ROUNDS = ("round-1", "round-2", "round-3")
TAG = "evo-local/theme_demo:9fcae3e5539d"

TASK_TOML = """schema_version = "1.2"
multi_step_reward_strategy = "mean"

[metadata]
name = "demo"
difficulty = "medium"
category = "code_build"
created = 2026-01-02

[metadata.requirement_chain]
num_steps = 3

[[metadata.requirement_chain.steps]]
step = "round-1"
change_types = ["extension"]

[[metadata.requirement_chain.steps]]
step = "round-2"
change_types = ["correction", "conflict"]

[[steps]]
name = "round-1"

[[steps]]
name = "round-2"

[steps.agent]
timeout_sec = 3600.0

[[steps]]
name = "round-3"

[steps.verifier]
timeout_sec = 300.0

[agent]
timeout_sec = 1800.0

[verifier]
timeout_sec = 1200.0

[verifier.env]
"MODE.x" = "strict"

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
"""

GO_DOCKERFILE = (
    "FROM ubuntu:22.04\n"
    "RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz | tar -C /usr/local -xz\n"
    "WORKDIR /app\n"
)


def make_task(root, toml=TASK_TOML, dockerfile=GO_DOCKERFILE):
    task = root / "theme_demo"
    (task / "environment").mkdir(parents=True)
    (task / "environment" / "Dockerfile").write_text(dockerfile)
    (task / "task.toml").write_text(toml)
    for name in ROUNDS:
        step = task / "steps" / name
        (step / "tests").mkdir(parents=True)
        (step / "solution").mkdir()
        (step / "instruction.md").write_text(f"synthetic request {name}\n")
        (step / "tests" / "test.sh").write_text("#!/bin/bash\necho 1 > /logs/verifier/reward.txt\n")
        (step / "solution" / "solve.sh").write_text("#!/bin/bash\ntrue\n")
    (task / "steps" / "round-2" / "workdir").mkdir()
    (task / "steps" / "round-2" / "workdir" / "data.csv").write_text("a,b\n")
    (task / "solution").mkdir()
    (task / "solution" / "README.md").write_text("top-level solution\n")
    return task


# ---- dump_toml -------------------------------------------------------------------------------

def test_dump_toml_round_trips_a_rich_document():
    data = {
        "schema_version": "1.2",
        "flag": True,
        "count": -3,
        "ratio": 0.5,
        "limit": float("inf"),
        "day": datetime.date(2026, 1, 2),
        "at": datetime.datetime(2026, 10, 9, 7, 30, tzinfo=datetime.timezone.utc),
        "text": 'quote " backslash \\ tab \t newline \n bell \x07 del \x7f unicode é ✓',
        "a.b c": "quoted key",
        "empty_list": [],
        "mixed": [1, "x", {"k": 1, "nested": {"deep": [1, 2]}}],
        "table": {"x": 1, "empty": {}, "sub": {"y": [1.5, 2.5]}},
        "steps": [
            {"name": "round-1", "verifier": {"timeout_sec": 600.0, "collect": [{"command": "a\nb", "timeout_sec": 60.0}]}},
            {"name": "round-2", "agent": {"timeout_sec": 3600.0}},
        ],
        "metadata": {"requirement_chain": {"num_steps": 2, "steps": [{"step": "round-1"}, {"step": "round-2"}]}},
    }
    text = copies.dump_toml(data)
    assert tomllib.loads(text) == data
    assert copies.dump_toml(data) == text


def test_dump_toml_refuses_values_toml_cannot_hold():
    with pytest.raises(ValueError):
        copies.dump_toml({"x": None})
    with pytest.raises(ValueError):
        copies.dump_toml({"x": {1, 2}})


# ---- step_toml_overrides ---------------------------------------------------------------------

def test_step_overrides_add_timeouts_and_collect_hooks_and_keep_every_other_key():
    text = copies.step_toml_overrides(TASK_TOML, 1200.0, docker_image=TAG)
    out = tomllib.loads(text)
    steps = out["steps"]
    assert [s["name"] for s in steps] == list(ROUNDS)
    assert [s["verifier"]["timeout_sec"] for s in steps] == [1200.0, 1200.0, 300.0]
    for step in steps:
        assert step["verifier"]["collect"] == [
            {"command": copies.COLLECT_COMMAND(step["name"]), "timeout_sec": 60.0, "user": "root"}
        ]
    assert steps[1]["agent"] == {"timeout_sec": 3600.0}
    assert out["environment"]["docker_image"] == TAG
    for step in steps:
        step["verifier"].pop("collect")
        if step["name"] != "round-3":
            step["verifier"].pop("timeout_sec")
        if not step["verifier"]:
            step.pop("verifier")
    out["environment"].pop("docker_image")
    assert out == tomllib.loads(TASK_TOML)
    assert copies.step_toml_overrides(TASK_TOML, 1200.0, docker_image=TAG) == text


def test_step_overrides_without_an_image_leave_the_environment_alone():
    out = tomllib.loads(copies.step_toml_overrides(TASK_TOML, 1200.0))
    assert out["environment"] == tomllib.loads(TASK_TOML)["environment"]


def test_step_overrides_put_the_kill_hook_before_a_task_defined_hook():
    own = TASK_TOML.replace(
        '[[steps]]\nname = "round-1"\n',
        '[[steps]]\nname = "round-1"\n\n[[steps.verifier.collect]]\ncommand = "echo theirs"\n',
    )
    collect = tomllib.loads(copies.step_toml_overrides(own, 1200.0))["steps"][0]["verifier"]["collect"]
    assert [hook["command"] for hook in collect] == [copies.COLLECT_COMMAND("round-1"), "echo theirs"]


def test_step_overrides_refuse_what_the_copy_cannot_pin():
    with pytest.raises(ValueError, match="steps"):
        copies.step_toml_overrides('schema_version = "1.2"\n', 600.0)
    with pytest.raises(ValueError, match="docker_image"):
        copies.step_toml_overrides(TASK_TOML.replace("cpus = 2", 'cpus = 2\ndocker_image = "x"'), 600.0,
                                   docker_image=TAG)
    separate = TASK_TOML.replace("[verifier]\ntimeout_sec = 1200.0",
                                 '[verifier]\ntimeout_sec = 1200.0\nenvironment_mode = "separate"')
    with pytest.raises(ValueError, match="separate"):
        copies.step_toml_overrides(separate, 600.0)
    step_env = TASK_TOML.replace("[steps.verifier]\ntimeout_sec = 300.0",
                                 "[steps.verifier]\ntimeout_sec = 300.0\n\n[steps.verifier.environment]\ncpus = 1")
    with pytest.raises(ValueError, match="separate"):
        copies.step_toml_overrides(step_env, 600.0)


def test_collect_command_refuses_names_that_are_not_one_directory():
    for bad in ("", ".", "..", "a/b", "a\\b", "a\0b"):
        with pytest.raises(ValueError):
            copies.COLLECT_COMMAND(bad)
    assert "'round 1'" in copies.COLLECT_COMMAND("round 1")


# ---- make_copy -------------------------------------------------------------------------------

def test_agent_copy_has_hooks_timeouts_pin_and_arm_image_but_no_solutions(tmp_path):
    src = make_task(tmp_path / "src")
    before = tree_digest(src)
    dest = tmp_path / "copies" / "agent" / "theme_demo"
    digest = copies.make_copy(src, dest, kind="agent", image_tag=TAG)
    assert tree_digest(src) == before
    assert digest == tree_digest(dest)
    for name in ROUNDS:
        setup = dest / "steps" / name / "workdir" / "setup.sh"
        assert setup.read_text() == copies.SETUP_SH
        assert os.access(setup, os.X_OK)
        assert (dest / "steps" / name / "instruction.md").is_file()
        assert (dest / "steps" / name / "tests" / "test.sh").is_file()
    assert list(dest.rglob("solution")) == []
    assert (dest / "steps" / "round-2" / "workdir" / "data.csv").read_text() == "a,b\n"
    dockerfile = (dest / "environment" / "Dockerfile").read_text()
    assert "go1.22.5.linux-arm64.tar.gz" in dockerfile and "amd64" not in dockerfile
    data = tomllib.loads((dest / "task.toml").read_text())
    assert data["environment"]["docker_image"] == TAG
    assert [s["verifier"]["timeout_sec"] for s in data["steps"]] == [1200.0, 1200.0, 300.0]
    assert [s["verifier"]["collect"][0]["command"] for s in data["steps"]] == [
        copies.COLLECT_COMMAND(name) for name in ROUNDS]


def test_validation_copy_keeps_every_solution(tmp_path):
    src = make_task(tmp_path / "src")
    dest = tmp_path / "copies" / "validation" / "theme_demo"
    copies.make_copy(src, dest, kind="validation", image_tag=TAG)
    for name in ROUNDS:
        assert (dest / "steps" / name / "solution" / "solve.sh").is_file()
        assert (dest / "steps" / name / "workdir" / "setup.sh").is_file()
    assert (dest / "solution" / "README.md").is_file()


PYTHON_BLOCK_TEXT = (
    "\n"
    "# evo: python3 for the Horizon CLI, added to both arms when the image lacks it (bench/evo/copies.py)\n"
    "RUN command -v python3 >/dev/null 2>&1 || (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y "
    "--no-install-recommends python3 && rm -rf /var/lib/apt/lists/*)\n")


@pytest.mark.parametrize("kind", copies.KINDS)
def test_every_copy_ends_with_the_python3_block_after_the_arm_patch_and_records_it(tmp_path, kind):
    import json

    assert copies.PYTHON_BLOCK == PYTHON_BLOCK_TEXT
    assert copies.PYTHON_LINE == PYTHON_BLOCK_TEXT.splitlines()[-1]
    src = make_task(tmp_path / "src")
    before = tree_digest(src)
    dest = tmp_path / "copy" / "theme_demo"
    copies.make_copy(src, dest, kind=kind, image_tag=TAG)
    patched, changed = patch.arm_patch(GO_DOCKERFILE)
    assert (dest / "environment" / "Dockerfile").read_text() == patched + PYTHON_BLOCK_TEXT
    assert json.loads((dest / copies.ARM_PATCH_FILE).read_text()) == {
        "changed": changed, "artifacts": [], "added": [copies.PYTHON_LINE]}
    assert len(changed) == 1
    assert (src / "environment" / "Dockerfile").read_text() == GO_DOCKERFILE
    assert tree_digest(src) == before


def test_copies_of_one_task_have_one_digest_and_no_image_pin_when_none_is_given(tmp_path):
    src = make_task(tmp_path / "src")
    first = copies.make_copy(src, tmp_path / "a" / "theme_demo", kind="agent", image_tag=None)
    second = copies.make_copy(src, tmp_path / "b" / "theme_demo", kind="agent", image_tag=None)
    assert first == second
    data = tomllib.loads((tmp_path / "a" / "theme_demo" / "task.toml").read_text())
    assert "docker_image" not in data["environment"]


def test_a_task_without_a_verifier_timeout_gets_harbors_600_second_default(tmp_path):
    src = make_task(tmp_path / "src", toml=TASK_TOML.replace("[verifier]\ntimeout_sec = 1200.0\n", "[verifier]\n"))
    dest = tmp_path / "copy" / "theme_demo"
    copies.make_copy(src, dest, kind="agent", image_tag=TAG)
    data = tomllib.loads((dest / "task.toml").read_text())
    assert [s["verifier"]["timeout_sec"] for s in data["steps"]] == [600.0, 600.0, 300.0]


def test_make_copy_refuses_and_leaves_nothing_behind(tmp_path):
    src = make_task(tmp_path / "src")
    with pytest.raises(ValueError):
        copies.make_copy(src, tmp_path / "x" / "theme_demo", kind="oracle", image_tag=TAG)
    taken = tmp_path / "taken" / "theme_demo"
    taken.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        copies.make_copy(src, taken, kind="agent", image_tag=TAG)

    odd = make_task(tmp_path / "odd", dockerfile="FROM ubuntu:22.04\nRUN curl -fsSLO https://example.com/helm-v3.15.0-linux-amd64.tar.gz\n")
    with pytest.raises(patch.UnknownArchPattern):
        copies.make_copy(odd, tmp_path / "y" / "theme_demo", kind="agent", image_tag=TAG)
    assert not (tmp_path / "y" / "theme_demo").exists()

    own_setup = make_task(tmp_path / "own")
    (own_setup / "steps" / "round-2" / "workdir" / "setup.sh").write_text("#!/bin/bash\ntrue\n")
    with pytest.raises(ValueError, match="setup.sh"):
        copies.make_copy(own_setup, tmp_path / "z" / "theme_demo", kind="agent", image_tag=TAG)
    assert not (tmp_path / "z" / "theme_demo").exists()

def test_make_copy_refuses_symlinks_that_leave_the_task_so_it_never_writes_into_the_source(tmp_path):
    def move_out(task, relative, name):
        """Move one path of the task to tmp_path/<name>; the caller links the old path to it."""
        out = tmp_path / name
        (task / relative).rename(out)
        return out

    absolute_step = make_task(tmp_path / "absolute")
    outside_step = move_out(absolute_step, "steps/round-1", "outside-step")
    os.symlink(outside_step, absolute_step / "steps" / "round-1")

    relative_step = make_task(tmp_path / "relative")
    relative_outside = move_out(relative_step, "steps/round-1", "relative-outside-step")
    os.symlink(os.path.relpath(relative_outside, relative_step / "steps"), relative_step / "steps" / "round-1")

    toml_link = make_task(tmp_path / "toml")
    (tmp_path / "outside-toml").mkdir()
    outside_toml = move_out(toml_link, "task.toml", "outside-toml/task.toml")
    os.symlink(outside_toml, toml_link / "task.toml")

    cases = [(absolute_step, outside_step, "steps/round-1"),
             (relative_step, relative_outside, "steps/round-1"),
             (toml_link, outside_toml.parent, "task.toml")]
    for number, (task, outside, offender) in enumerate(cases):
        src_before, outside_before = tree_digest(task), tree_digest(outside)
        dest = tmp_path / f"copy{number}" / "theme_demo"
        with pytest.raises(ValueError, match=offender):
            copies.make_copy(task, dest, kind="agent", image_tag=None)
        assert tree_digest(task) == src_before
        assert tree_digest(outside) == outside_before
        assert not dest.exists()

    inside = make_task(tmp_path / "inside")
    os.symlink("instruction.md", inside / "steps" / "round-1" / "request.md")
    os.symlink("../round-2", inside / "steps" / "round-1" / "next")
    dest = tmp_path / "copy-inside" / "theme_demo"
    copies.make_copy(inside, dest, kind="agent", image_tag=None)
    assert os.readlink(dest / "steps" / "round-1" / "request.md") == "instruction.md"
    assert os.readlink(dest / "steps" / "round-1" / "next") == "../round-2"


# ---- SETUP_SH, run for real in a sandbox -----------------------------------------------------

def run_setup(work, home, tmp_root):
    (work / "setup.sh").write_text(copies.SETUP_SH)
    env = dict(os.environ, HOME=str(home), EVO_TMP_ROOT=str(tmp_root))
    return subprocess.run(["bash", str(work / "setup.sh")], cwd=work, env=env,
                          capture_output=True, text=True, timeout=30)


def test_setup_empties_tmp_and_claude_projects_but_never_the_project(tmp_path):
    tmp_root, home, work = tmp_path / "tmp", tmp_path / "home", tmp_path / "app"
    (tmp_root / "sentinel-dir" / "deep").mkdir(parents=True)
    (tmp_root / "sentinel-dir" / "deep" / "f").write_text("x")
    (tmp_root / ".hidden").write_text("x")
    (tmp_root / "file.txt").write_text("x")
    (work / ".claude" / "harness" / "goals").mkdir(parents=True)
    (work / ".claude" / "harness" / "goals" / "g.json").write_text("{}")
    (work / "src.py").write_text("print(1)\n")
    os.symlink(work, tmp_root / "link-to-project")
    (home / ".claude" / "projects" / "-app" / "memory").mkdir(parents=True)
    (home / ".claude" / "projects" / "-app" / "memory" / "MEMORY.md").write_text("m")
    (home / ".claude" / "settings.json").write_text("{}")
    before = tree_digest(work)
    result = run_setup(work, home, tmp_root)
    assert result.returncode == 0, result.stderr
    assert tmp_root.is_dir() and list(tmp_root.iterdir()) == []
    assert not (home / ".claude" / "projects").exists()
    assert (home / ".claude" / "settings.json").is_file()
    assert not (work / "setup.sh").exists()
    assert tree_digest(work) == before


def test_setup_exits_zero_when_nothing_exists(tmp_path):
    work = tmp_path / "app"
    work.mkdir()
    result = run_setup(work, tmp_path / "no-home", tmp_path / "no-tmp")
    assert result.returncode == 0, result.stderr
    assert list(work.iterdir()) == []


def test_setup_keeps_a_project_that_lives_under_tmp(tmp_path):
    tmp_root = tmp_path / "tmp"
    work = tmp_root / "proj" / "app"
    work.mkdir(parents=True)
    (work / "main.py").write_text("x = 1\n")
    (tmp_root / "proj" / "sibling.txt").write_text("y")
    (tmp_root / "junk").write_text("z")
    result = run_setup(work, tmp_path / "home", tmp_root)
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_root.iterdir()) == ["proj"]
    assert (work / "main.py").read_text() == "x = 1\n"
    assert not (work / "setup.sh").exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root can delete anything")
def test_setup_exits_zero_when_it_cannot_delete_something(tmp_path):
    tmp_root, work = tmp_path / "tmp", tmp_path / "app"
    work.mkdir()
    locked = tmp_root / "locked"
    locked.mkdir(parents=True)
    (locked / "f").write_text("x")
    locked.chmod(0o555)
    try:
        result = run_setup(work, tmp_path / "home", tmp_root)
    finally:
        locked.chmod(0o755)
    assert result.returncode == 0, result.stderr
    assert not (work / "setup.sh").exists()


# ---- COLLECT_COMMAND, run for real against a fake /proc of real processes -----------------------

def fake_proc(root, pid, ppid, argv, exe=None, status=True):
    entry = root / str(pid)
    entry.mkdir(parents=True)
    if status:
        (entry / "status").write_text(f"Name:\tx\nState:\tS (sleeping)\nPPid:\t{ppid}\n")
    (entry / "cmdline").write_bytes(b"".join(arg.encode() + b"\0" for arg in argv))
    if exe:
        os.symlink(exe, entry / "exe")


def run_collect(work, proc, arts, tmp_root, name="round-2"):
    env = dict(os.environ, EVO_PROC_ROOT=str(proc), EVO_ARTIFACTS_ROOT=str(arts), EVO_TMP_ROOT=str(tmp_root))
    return subprocess.run(["bash", "-c", copies.COLLECT_COMMAND(name)], cwd=work, env=env,
                          capture_output=True, text=True, timeout=60)


def test_collect_kills_claude_and_its_descendants_only_and_snapshots_the_round(tmp_path):
    procs = {key: subprocess.Popen(["sleep", "300"]) for key in
             ("wrapper", "claude", "child", "grandchild", "by_exe", "server", "hook", "kthread", "no_status")}
    pid = {key: p.pid for key, p in procs.items()}
    proc = tmp_path / "proc"
    versions = "/root/.local/share/claude/versions/2.1.293"
    fake_proc(proc, pid["wrapper"], 1, ["bash", "-c", "printf '%s' \"$x\" | claude --verbose --print | tee /logs/agent/claude-code.txt"], "/usr/bin/bash")
    fake_proc(proc, pid["claude"], pid["wrapper"], ["claude", "--verbose", "--output-format=stream-json", "--print"], versions)
    fake_proc(proc, pid["child"], pid["claude"], ["/bin/bash", "-c", "pytest -q"], "/usr/bin/bash")
    fake_proc(proc, pid["grandchild"], pid["child"], ["python3", "-m", "pytest", "-q"], "/usr/bin/python3.10")
    fake_proc(proc, pid["by_exe"], 1, [versions, "--print"], versions)
    fake_proc(proc, pid["server"], 1, ["python3", "-m", "http.server"], "/usr/bin/python3.10")
    fake_proc(proc, pid["hook"], 0, ["bash", "-c", copies.COLLECT_COMMAND("round-2")], "/usr/bin/bash")
    fake_proc(proc, pid["kthread"], 2, [])
    fake_proc(proc, pid["no_status"], pid["claude"], ["claude", "--print"], versions, status=False)
    work, arts, tmp_root = tmp_path / "app", tmp_path / "artifacts", tmp_path / "tmp"
    (work / ".claude" / "harness" / "goals").mkdir(parents=True)
    (work / ".claude" / "harness" / "goals" / "g.json").write_text("{}")
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (work / "pkg").mkdir()
    (work / "pkg" / "mod.py").write_text("")
    (work / "src.py").write_text("")
    tmp_root.mkdir()
    (tmp_root / "sentinel").write_text("s")
    try:
        result = run_collect(work, proc, arts, tmp_root)
        assert result.returncode == 0, result.stderr
        for key in ("claude", "child", "grandchild", "by_exe"):
            assert procs[key].wait(timeout=10) == -signal.SIGKILL, key
        for key in ("wrapper", "server", "hook", "kthread", "no_status"):
            assert procs[key].poll() is None, key
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.kill()
                p.wait()
    out = arts / "round-2"
    killed = (out / "killed.txt").read_text().splitlines()
    assert sorted(int(line.split()[0]) for line in killed) == sorted(
        pid[key] for key in ("claude", "child", "grandchild", "by_exe"))
    assert any(line.startswith(f"{pid['claude']} claude --verbose") for line in killed)
    assert (out / "harness" / "goals" / "g.json").read_text() == "{}"
    assert "sentinel" in (out / "tmp-ls.txt").read_text()
    assert (out / "project-files.txt").read_text().splitlines() == [
        "./.claude/harness/goals/g.json", "./pkg/mod.py", "./src.py"]
    assert (work / ".claude" / "harness" / "goals" / "g.json").read_text() == "{}"


def test_collect_exits_zero_with_nothing_to_kill_or_copy(tmp_path):
    work, arts = tmp_path / "app", tmp_path / "artifacts"
    work.mkdir()
    result = run_collect(work, tmp_path / "no-proc", arts, tmp_path / "no-tmp", name="round-1")
    assert result.returncode == 0, result.stderr
    out = arts / "round-1"
    assert (out / "killed.txt").read_text() == ""
    assert not (out / "harness").exists()
    assert (out / "project-files.txt").read_text() == ""
    assert (out / "tmp-ls.txt").is_file()


# ---- prompts ---------------------------------------------------------------------------------

def test_write_prompt_writes_the_arm_text_for_its_minutes(tmp_path):
    control = copies.write_prompt(tmp_path / "prompts" / "theme_demo__control.md", "control", 30)
    horizon = copies.write_prompt(tmp_path / "prompts" / "theme_demo__horizon.md", "horizon", 60)
    assert control == tmp_path / "prompts" / "theme_demo__control.md"
    assert control.read_text() == config.prompt_text("control", 30) + "\n"
    assert horizon.read_text() == config.prompt_text("horizon", 60) + "\n"
    assert "30 minutes" in control.read_text() and "horizon" not in control.read_text()
    assert "60 minutes" in horizon.read_text() and "horizon skill" in horizon.read_text()
    with pytest.raises(ValueError):
        copies.write_prompt(tmp_path / "prompts" / "x__ablation.md", "ablation", 30)


def test_collect_lists_the_processes_that_survive_into_the_next_round(tmp_path):
    procs = {key: subprocess.Popen(["sleep", "300"]) for key in ("claude", "server", "hook")}
    pid = {key: p.pid for key, p in procs.items()}
    proc = tmp_path / "proc"
    fake_proc(proc, pid["claude"], 1, ["claude", "--print"], "/root/.local/share/claude/versions/2.1.293")
    fake_proc(proc, pid["server"], 1, ["python3", "-m", "http.server", "8000"], "/usr/bin/python3.10")
    fake_proc(proc, pid["hook"], 0, ["bash", "-c", copies.COLLECT_COMMAND("round-2")], "/usr/bin/bash")
    work = tmp_path / "app"
    work.mkdir()
    try:
        result = run_collect(work, proc, tmp_path / "artifacts", tmp_path / "tmp")
        assert result.returncode == 0, result.stderr
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.kill()
            p.wait()
    survivors = (tmp_path / "artifacts" / "round-2" / copies.SURVIVORS_FILE).read_text().splitlines()
    assert survivors == [f"{pid['server']} python3 -m http.server 8000"]


def test_a_bundled_go_tarball_is_replaced_in_the_copy_and_recorded(tmp_path, monkeypatch):
    import hashlib
    import json

    arm64 = b"arm64 toolchain"
    fetched = []

    def fetch(url, dest=None):
        fetched.append(url)
        if dest is None:
            return [{"files": [{"filename": "go1.21.0.linux-arm64.tar.gz", "sha256": hashlib.sha256(arm64).hexdigest()}]}]
        dest.write_bytes(arm64)

    monkeypatch.setattr(patch, "_fetch", fetch)
    src = make_task(tmp_path / "src", dockerfile="FROM ubuntu:22.04\nCOPY go1.21.0.linux-amd64.tar.gz /tmp/\n"
                                                 "RUN tar -C /usr/local -xzf /tmp/go1.21.0.linux-amd64.tar.gz\n")
    (src / "environment" / "go1.21.0.linux-amd64.tar.gz").write_bytes(b"amd64 toolchain")
    before = tree_digest(src)
    dest = tmp_path / "copy" / "theme_demo"
    copies.make_copy(src, dest, kind="agent", image_tag=TAG)
    assert tree_digest(src) == before
    assert sorted(p.name for p in (dest / "environment").iterdir()) == ["Dockerfile", "go1.21.0.linux-arm64.tar.gz"]
    assert "amd64" not in (dest / "environment" / "Dockerfile").read_text()
    record = json.loads((dest / copies.ARM_PATCH_FILE).read_text())
    assert record["artifacts"][0]["sha256"] == hashlib.sha256(arm64).hexdigest()
    assert [c.split(":", 1)[0] for c in record["changed"]] == ["3"]
    assert fetched == ["https://go.dev/dl/?mode=json&include=all", "https://go.dev/dl/go1.21.0.linux-arm64.tar.gz"]
