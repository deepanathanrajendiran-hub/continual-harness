import json
import subprocess

import pytest

from bench.swepro import config, probe

GOOD = """=== NETWORK PROBE (agent phase, python) ===
NET https://api.github.com blocked URLError <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]
NET https://raw.githubusercontent.com/ansible/ansible/devel/README.md blocked URLError x
NET https://pypi.org/simple/ blocked URLError x
NET https://www.google.com blocked URLError x
NET https://api.anthropic.com/v1/models http_error 401
"""


def test_parse_reads_each_url_outcome():
    out = probe.parse(GOOD)
    assert out["https://api.anthropic.com/v1/models"] == "http_error"
    assert out["https://pypi.org/simple/"] == "blocked"
    assert len(out) == 5


def test_good_output_passes():
    assert probe.passed(probe.parse(GOOD))


@pytest.mark.parametrize("text", [
    GOOD.replace("NET https://pypi.org/simple/ blocked", "NET https://pypi.org/simple/ status"),
    GOOD.replace("http_error 401", "blocked URLError"),
    GOOD.replace("NET https://www.google.com blocked URLError x\n", ""),
    "",
])
def test_any_open_host_a_closed_model_endpoint_or_a_missing_line_fails(text):
    assert not probe.passed(probe.parse(text))


def test_make_probe_task_replaces_only_the_solution(tmp_path):
    src = tmp_path / "src"
    (src / "solution").mkdir(parents=True)
    (src / "solution" / "solve.sh").write_text("gold")
    (src / "task.toml").write_text("[agent]\nnetwork_mode = \"no-network\"\n")
    out = probe.make_probe_task(src, tmp_path / "probe")
    assert (out / "solution" / "solve.sh").read_text() == probe.PROBE_SCRIPT
    assert (out / "task.toml").read_text() == (src / "task.toml").read_text()
    assert (src / "solution" / "solve.sh").read_text() == "gold"


def test_run_probe_records_and_raises_on_failure(tmp_path):
    task = tmp_path / "tasks" / config.SMOKE_TASK
    (task / "solution").mkdir(parents=True)
    (task / "task.toml").write_text('[environment]\ndocker_image = "img:smoke"\n')
    outputs = [GOOD, GOOD.replace("http_error 401", "blocked x")]

    def run(cmd, **kw):
        if cmd[0] == "docker":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        assert "--allow-agent-host" in cmd
        name = cmd[cmd.index("--job-name") + 1]
        t = tmp_path / "runs" / "jobs" / name / "trial__x"
        (t / "agent").mkdir(parents=True)
        (t / "agent" / "oracle.txt").write_text(outputs.pop(0))
        (t / "result.json").write_text(json.dumps({"task_name": config.SMOKE_TASK, "exception_info": None,
                                                   "verifier_result": {"rewards": {"reward": 0.0}}}))
        return subprocess.CompletedProcess(cmd, 0)

    rec = probe.run_probe(tmp_path / "runs", tmp_path / "tasks", "start of practice", run=run)
    assert rec["passed"] and rec["label"] == "start of practice"
    with pytest.raises(probe.ProbeFailed):
        probe.run_probe(tmp_path / "runs", tmp_path / "tasks", "after 10 tasks", run=run)
    saved = sorted((tmp_path / "runs" / "probes").glob("*.json"))
    assert [json.loads(p.read_text())["passed"] for p in saved] == [True, False]
