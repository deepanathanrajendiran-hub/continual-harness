import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from bench.swepro import config, tools

BINARY = b"\x7fELF fake claude"


def pin(monkeypatch, data=BINARY):
    monkeypatch.setattr(config, "CLAUDE_ARM_SHA256", hashlib.sha256(data).hexdigest())


def test_fetch_claude_downloads_and_verifies(tmp_path, monkeypatch):
    pin(monkeypatch)
    urls = []

    def download(url, dest):
        urls.append(url)
        dest.write_bytes(BINARY)

    out = tools.fetch_claude(tmp_path, download=download)
    assert urls == [config.CLAUDE_ARM_URL]
    assert out == tmp_path / "claude-arm64-musl" / "claude"
    assert out.read_bytes() == BINARY and out.stat().st_mode & 0o111


def test_fetch_claude_reuses_a_verified_copy(tmp_path, monkeypatch):
    pin(monkeypatch)
    tools.fetch_claude(tmp_path, download=lambda url, dest: dest.write_bytes(BINARY))
    tools.fetch_claude(tmp_path, download=lambda url, dest: pytest.fail("downloaded again"))


def test_fetch_claude_refuses_and_deletes_a_bad_download(tmp_path, monkeypatch):
    pin(monkeypatch)
    with pytest.raises(tools.ToolError, match="sha256"):
        tools.fetch_claude(tmp_path, download=lambda url, dest: dest.write_bytes(b"other"))
    assert not (tmp_path / "claude-arm64-musl" / "claude").exists()


def test_fetch_loader_copies_it_out_of_the_pinned_alpine_image(tmp_path):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        (tmp_path / "musl" / "ld-musl-aarch64.so.1").write_bytes(b"loader")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    out = tools.fetch_loader(tmp_path, run=run)
    assert out.read_bytes() == b"loader"
    cmd = calls[0]
    assert cmd[:3] == ["docker", "run", "--rm"] and "--platform" in cmd and "linux/arm64" in cmd
    assert config.ALPINE_IMAGE in cmd


def test_fetch_loader_refuses_an_empty_result(tmp_path):
    def run(cmd, **kw):
        (tmp_path / "musl").mkdir(exist_ok=True)
        (tmp_path / "musl" / "ld-musl-aarch64.so.1").write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with pytest.raises(tools.ToolError):
        tools.fetch_loader(tmp_path, run=run)


def test_manifest_hashes_every_tool(tmp_path):
    for rel, data in ((tools.CLAUDE_REL, b"c"), (tools.LOADER_REL, b"l"), ("patch_replay.py", b"r")):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    m = tools.write_manifest(tmp_path)
    assert m[tools.LOADER_REL] == hashlib.sha256(b"l").hexdigest()
    assert json.loads((tmp_path / "manifest.json").read_text()) == m
    assert set(m) == {tools.CLAUDE_REL, tools.LOADER_REL, "patch_replay.py"}


def fake_python(monkeypatch, data=b"python"):
    monkeypatch.setattr(config, "MINI_PYTHON_SHA256", hashlib.sha256(data).hexdigest())
    return lambda url, dest: dest.write_bytes(data)


def builder(calls):
    def run(cmd, **kw):
        calls.append(cmd)
        out = Path(cmd[cmd.index("-v") + 1].split(":")[0])
        for rel in ("mswea.tgz", "mini.yaml", "freeze.txt"):
            (out / rel).write_text("x")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


def test_build_mini_packs_pinned_mini_swe_agent_into_the_checked_python(tmp_path, monkeypatch):
    calls = []
    tools.build_mini(tmp_path, download=fake_python(monkeypatch), run=builder(calls))
    script = " ".join(calls[0])
    assert calls[0][:5] == ["docker", "run", "--rm", "--platform", "linux/amd64"]
    for part in (f"mini-swe-agent=={config.MINI_VERSION}", f"--exclude-newer {config.MINI_EXCLUDE_NEWER}",
                 f"uv=={config.MINI_UV_VERSION}", config.REFINE_BASE_IMAGE, "/opt/mswea"):
        assert part in script, part
    assert all((tmp_path / rel).is_file() for rel in (tools.MINI_REL, tools.MINI_YAML_REL))


def test_build_mini_refuses_a_python_download_that_fails_its_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MINI_PYTHON_SHA256", "0" * 64)
    with pytest.raises(tools.ToolError, match="sha256"):
        tools.build_mini(tmp_path, download=lambda url, dest: dest.write_bytes(b"evil"),
                         run=lambda *a, **k: pytest.fail("built from an unchecked python"))


def test_build_mini_skips_a_finished_build(tmp_path, monkeypatch):
    calls = []
    tools.build_mini(tmp_path, download=fake_python(monkeypatch), run=builder(calls))
    tools.build_mini(tmp_path, download=fake_python(monkeypatch), run=builder(calls))
    assert len(calls) == 1
