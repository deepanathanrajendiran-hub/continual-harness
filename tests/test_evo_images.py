import json
import subprocess

from bench.evo import images


class FakeRun:
    def __init__(self, stdout=""):
        self.calls, self.stdout = [], stdout

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        return subprocess.CompletedProcess(cmd, 0, self.stdout, "")


def test_build_uses_the_copy_environment_and_arm64(tmp_path):
    fake, log = FakeRun(), object()
    images.build(tmp_path / "copy", "evo-local/demo:9fcae3e5539d", log, run=fake)
    (cmd, kwargs), = fake.calls
    assert cmd == ["docker", "build", "--platform", "linux/arm64", "-t", "evo-local/demo:9fcae3e5539d",
                   str(tmp_path / "copy" / "environment")]
    assert kwargs == {"check": True, "stdout": log, "stderr": subprocess.STDOUT, "timeout": 3600}


def test_inspect_returns_id_arch_workdir_and_user():
    payload = [{"Id": "sha256:abc", "Architecture": "arm64", "Config": {"WorkingDir": "/app", "User": ""}}]
    fake = FakeRun(json.dumps(payload))
    assert images.inspect("evo-local/demo:9fcae3e5539d", run=fake) == {
        "id": "sha256:abc", "arch": "arm64", "workdir": "/app", "user": "root"}
    assert fake.calls[0][0] == ["docker", "image", "inspect", "evo-local/demo:9fcae3e5539d"]


def test_remove_forces_the_tag_out():
    fake = FakeRun()
    images.remove("evo-local/demo:9fcae3e5539d", run=fake)
    assert fake.calls[0][0] == ["docker", "image", "rm", "-f", "evo-local/demo:9fcae3e5539d"]
