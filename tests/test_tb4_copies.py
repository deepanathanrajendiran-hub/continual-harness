import os
import tomllib

import pytest

from bench.tb4 import copies, config

PLAIN = """schema_version = "1.0"
artifacts = ["/app/"]

[task]
name = "terminal-bench/demo"

[verifier]
timeout_sec = 900.0
environment_mode = "separate"

[agent]
timeout_sec = 28800.0

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 8192
storage_mb = 10240
gpus = 0
mcp_servers = []

[verifier.env]

[solution.env]
"""

WITH_VERIFIER_ENV = PLAIN.replace("[verifier.env]", "[verifier.environment]\ncpus = 4\nmemory_mb = 4096\n\n[verifier.env]")
INSTRUCTION = "<!-- harbor-canary GUID x -->\n\nFix the thing.\n\nYou have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.\n"


def make_task(root, toml=PLAIN, instruction=INSTRUCTION):
    d = root / "demo"
    for sub in ("environment", "tests", "solution"):
        (d / sub).mkdir(parents=True)
    (d / "task.toml").write_text(toml)
    (d / "instruction.md").write_text(instruction)
    (d / "environment" / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (d / "tests" / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (d / "solution" / "solve.sh").write_text("#!/bin/bash\necho solved > /app/out\n")
    return d


def test_pin_toml_appends_a_full_verifier_environment():
    data = tomllib.loads(copies.pin_toml(PLAIN, "a:tag", "v:tag"))
    assert data["environment"]["docker_image"] == "a:tag"
    ve = data["verifier"]["environment"]
    assert ve["docker_image"] == "v:tag"
    for key in ("build_timeout_sec", "cpus", "memory_mb", "storage_mb", "gpus", "mcp_servers"):
        assert ve[key] == data["environment"][key]
    assert data["verifier"]["environment_mode"] == "separate"


def test_pin_toml_keeps_an_existing_verifier_environment():
    data = tomllib.loads(copies.pin_toml(WITH_VERIFIER_ENV, "a:tag", "v:tag"))
    assert data["verifier"]["environment"] == {"docker_image": "v:tag", "cpus": 4, "memory_mb": 4096}


def test_pin_toml_refuses_a_preset_image_and_nonempty_subtables():
    with pytest.raises(ValueError):
        copies.pin_toml(PLAIN.replace("cpus = 2", 'cpus = 2\ndocker_image = "x"'), "a", "v")
    with pytest.raises(ValueError):
        copies.pin_toml(PLAIN + '\n[environment.env]\nFOO = "1"\n', "a", "v")


def test_pin_task_removes_only_the_deadline_sentence(tmp_path):
    src = make_task(tmp_path / "src")
    digest = copies.pin_task(src, tmp_path / "copy" / "demo", "demo")
    text = (tmp_path / "copy" / "demo" / "instruction.md").read_text()
    assert "28800 seconds" not in text
    assert "Do not cheat by using online solutions" in text and "Fix the thing." in text
    data = tomllib.loads((tmp_path / "copy" / "demo" / "task.toml").read_text())
    assert data["environment"]["docker_image"] == config.agent_tag("demo")
    assert data["verifier"]["environment"]["docker_image"] == config.verifier_tag("demo")
    assert len(digest) == 64
    assert (src / "instruction.md").read_text() == INSTRUCTION


def test_pin_task_requires_exactly_one_deadline_sentence(tmp_path):
    src = make_task(tmp_path / "src", instruction="No deadline here.\n")
    with pytest.raises(ValueError):
        copies.pin_task(src, tmp_path / "copy" / "demo", "demo")


def test_pin_task_refuses_an_existing_destination(tmp_path):
    src = make_task(tmp_path / "src")
    (tmp_path / "copy" / "demo").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        copies.pin_task(src, tmp_path / "copy" / "demo", "demo")


def test_digest_is_stable_and_content_sensitive(tmp_path):
    a = make_task(tmp_path / "a")
    b = make_task(tmp_path / "b")
    assert copies.tree_digest(a) == copies.tree_digest(b)
    (b / "instruction.md").write_text("changed\n")
    assert copies.tree_digest(a) != copies.tree_digest(b)


def test_ledger_check_copy_plants_the_ledger_before_the_real_solution(tmp_path):
    pinned = tmp_path / "pinned"
    copies.pin_task(make_task(tmp_path / "src"), pinned, "demo")
    ledger = tmp_path / "ledger"
    (ledger / "goals").mkdir(parents=True)
    (ledger / "goals" / "g.json").write_text("{}")
    dest = tmp_path / "check"
    copies.ledger_check_copy(pinned, dest, "/app/sglang", ledger)
    solution = dest / "solution"
    assert (solution / "solve.orig.sh").read_text() == "#!/bin/bash\necho solved > /app/out\n"
    assert (solution / "horizon-ledger" / "goals" / "g.json").is_file()
    wrapper = (solution / "solve.sh").read_text()
    assert "mkdir -p /app/sglang/.claude/harness" in wrapper
    assert "cp -R /solution/horizon-ledger/. /app/sglang/.claude/harness/" in wrapper
    assert wrapper.rstrip().endswith('exec bash /solution/solve.orig.sh "$@"')
    assert os.access(solution / "solve.sh", os.X_OK)
