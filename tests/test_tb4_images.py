import json
import subprocess
from pathlib import Path

from bench.tb4 import images


class FakeRun:
    def __init__(self, stdout="", returncode=0):
        self.calls, self.stdout, self.returncode = [], stdout, returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


def test_build_commands_pin_arm64_and_both_contexts(tmp_path):
    cmds = images.build_commands(tmp_path / "t", "demo")
    assert cmds[0] == ["docker", "build", "--platform", "linux/arm64", "-t",
                       "tb4-local/demo:v4.0.0", str(tmp_path / "t" / "environment")]
    assert cmds[1] == ["docker", "build", "--platform", "linux/arm64", "-t",
                       "tb4-local/demo-verifier:v4.0.0", str(tmp_path / "t" / "tests")]


def test_inspect_reads_id_workdir_and_user():
    payload = [{"Id": "sha256:abc", "Architecture": "arm64",
                "Config": {"WorkingDir": "/workspace", "User": "nobody"}}]
    info = images.inspect("tag", run=FakeRun(json.dumps(payload)))
    assert info == {"id": "sha256:abc", "arch": "arm64", "workdir": "/workspace", "user": "nobody"}


def test_inspect_defaults_for_unset_workdir_and_user():
    payload = [{"Id": "sha256:abc", "Architecture": "arm64", "Config": {"WorkingDir": "", "User": ""}}]
    info = images.inspect("tag", run=FakeRun(json.dumps(payload)))
    assert info["workdir"] == "/" and info["user"] == "root"


def test_python_probe_runs_offline_as_the_image_user():
    fake = FakeRun("3.12.4\n")
    ok, out = images.python_ok("tb4-local/demo:v4.0.0", run=fake)
    assert ok and out.strip() == "3.12.4"
    cmd = fake.calls[0]
    assert cmd[:2] == ["docker", "run"] and "--network" in cmd and "none" in cmd
    assert "--user" not in cmd
    assert "sys.version_info >= (3, 10)" in cmd[-1]


def test_bundle_probe_mounts_the_skill_read_only(tmp_path):
    fake = FakeRun("ok\n")
    ok, _ = images.bundle_ok("tb4-local/demo:v4.0.0", tmp_path / "horizon", run=fake)
    cmd = fake.calls[0]
    assert ok
    assert f"{tmp_path / 'horizon'}:/opt/horizon:ro" in cmd
    script = cmd[-1]
    for needed in ("doctor", "start smoke --gate true", "check", "status", ".claude/harness/goals"):
        assert needed in script


def test_failed_probe_reports_false():
    ok, _ = images.python_ok("tag", run=FakeRun("", returncode=1))
    assert not ok
