import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("harbor")

from bench.swepro import agent, bundle, install  # noqa: E402


class FakeEnv:
    def __init__(self, fail_on=None, version="2.1.293 (Claude Code)"):
        self.calls = []
        self.fail_on = fail_on
        self.version = version

    async def upload_file(self, source_path, target_path):
        self.calls.append(("upload_file", Path(source_path), target_path))

    async def upload_dir(self, source_dir, target_dir):
        self.calls.append(("upload_dir", Path(source_dir), target_dir))

    async def download_dir(self, source_dir, target_dir):
        self.calls.append(("download_dir", source_dir, Path(target_dir)))

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.calls.append(("exec", command, user))
        rc = 1 if self.fail_on and self.fail_on in command else 0
        out = self.version if "--version" in command else ""
        return SimpleNamespace(return_code=rc, stdout=out, stderr="")


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make(tmp_path, cls=agent.ArmClaudeCode, **kw):
    return cls(logs_dir=tmp_path / "logs", model_name="anthropic/claude-sonnet-5-5", version="2.1.293",
               tools_dir=str(tmp_path / "tools"), **kw)


def test_install_without_a_bundle_puts_claude_in_and_reports_no_notes(tmp_path):
    env = FakeEnv()
    asyncio.run(make(tmp_path).install(env))
    uploads = [c[2] for c in env.calls if c[0] == "upload_file"]
    assert uploads == ["/lib/ld-musl-aarch64.so.1", "/usr/local/bin/claude"]
    assert any(c[0] == "exec" and c[1] == install.NOTES_REPORT for c in env.calls)
    assert not any(c[0] == "upload_dir" for c in env.calls)


def test_install_with_a_bundle_uploads_it_and_points_harbor_memory_at_it(tmp_path):
    write(tmp_path / "state" / "memory" / "MEMORY.md", "- [a](a.md)")
    write(tmp_path / "state" / "app" / "CLAUDE.md", "rule")
    bundle.export(tmp_path / "state", tmp_path / "bundle")
    a = make(tmp_path, bundle_dir=str(tmp_path / "bundle"))
    assert a.options.memory_dir == f"{install.NOTES}/memory"
    env = FakeEnv()
    asyncio.run(a.install(env))
    dirs = [c[2] for c in env.calls if c[0] == "upload_dir"]
    assert dirs == ["/app/.claude", f"{install.NOTES}/memory"]
    report = [i for i, c in enumerate(env.calls) if c[0] == "exec" and c[1] == install.NOTES_REPORT]
    assert report and report[0] == len(env.calls) - 1


def test_a_bundle_without_memory_leaves_harbor_memory_unset(tmp_path):
    write(tmp_path / "state" / "app" / "CLAUDE.md", "rule")
    bundle.export(tmp_path / "state", tmp_path / "bundle")
    assert make(tmp_path, bundle_dir=str(tmp_path / "bundle")).options.memory_dir is None


def test_a_failed_check_stops_the_install(tmp_path):
    bundle.export(tmp_path / "nothing", tmp_path / "bundle")
    env = FakeEnv(fail_on="test ! -e /app/.claude")
    with pytest.raises(RuntimeError, match="/app/.claude"):
        asyncio.run(make(tmp_path, bundle_dir=str(tmp_path / "bundle")).install(env))


def test_a_wrong_claude_version_stops_the_install(tmp_path):
    with pytest.raises(RuntimeError, match="version"):
        asyncio.run(make(tmp_path).install(FakeEnv(version="2.1.299 (Claude Code)")))


def test_run_captures_the_patch_even_when_claude_fails(tmp_path, monkeypatch):
    async def boom(self, instruction, environment, context):
        raise RuntimeError("agent died")

    monkeypatch.setattr(agent.ClaudeCode, "run", boom)
    env = FakeEnv()
    with pytest.raises(RuntimeError, match="agent died"):
        asyncio.run(make(tmp_path).run("do it", env, SimpleNamespace()))
    assert env.calls[-1] == ("exec", install.CAPTURE, "root")


def test_refine_agent_lays_out_state_and_downloads_it_after(tmp_path, monkeypatch):
    ran = []

    async def fake_run(self, instruction, environment, context):
        ran.append(instruction)

    monkeypatch.setattr(agent.ClaudeCode, "run", fake_run)
    write(tmp_path / "skill" / "SKILL.md")
    write(tmp_path / "inputs" / "result.txt", "passed")
    a = make(tmp_path, cls=agent.RefineClaudeCode, state_dir=str(tmp_path / "state"),
             skill_dir=str(tmp_path / "skill"), inputs_dir=str(tmp_path / "inputs"), out_dir=str(tmp_path / "out"))
    env = FakeEnv()
    asyncio.run(a.install(env))
    assert [c[2] for c in env.calls if c[0] == "upload_dir"] == ["/app/.claude/skills/refine", "/inputs"]
    env.calls.clear()
    asyncio.run(a.run("refine it", env, SimpleNamespace()))
    assert ran == ["refine it"]
    assert any(c[0] == "exec" and "refine-history" in c[1] for c in env.calls)
    assert ("download_dir", "/app", tmp_path / "out" / "app") in env.calls
    assert ("download_dir", install.REFINE_MEMORY, tmp_path / "out" / "memory") in env.calls
    assert not any(c[0] == "exec" and c[1] == install.CAPTURE for c in env.calls)


def test_harbor_preflight_accepts_the_arm_options():
    agent.ArmClaudeCode.parse_options({"version": "2.1.293", "tools_dir": "/t", "bundle_dir": "/b"})


def test_harbor_preflight_accepts_the_refine_options():
    agent.RefineClaudeCode.parse_options({"version": "2.1.293", "tools_dir": "/t", "state_dir": "/s",
                                          "skill_dir": "/k", "inputs_dir": "/i", "out_dir": "/o"})


def test_harbor_preflight_still_rejects_unknown_options():
    with pytest.raises(ValueError, match="nonsense"):
        agent.ArmClaudeCode.parse_options({"nonsense": "1"})


def make_mini(tmp_path, **kw):
    write(tmp_path / "tools" / "mini" / "mini.yaml", "agent:\n  system_template: |\n    You are helpful.\n  step_limit: 0\n")
    return agent.ArmMiniSweAgent(logs_dir=tmp_path / "logs", model_name="deepseek/deepseek-v4-flash",
                                 tools_dir=str(tmp_path / "tools"), **kw)


def test_a_plain_mini_agent_installs_offline_with_the_step_cap_and_no_notes(tmp_path):
    a = make_mini(tmp_path)
    assert "step_limit: 100" in a._config_yaml and "Notes from earlier" not in a._config_yaml
    env = FakeEnv()
    asyncio.run(a.install(env))
    assert [c[2] for c in env.calls if c[0] == "upload_file"] == ["/tmp/mswea.tgz"]
    assert any(c[0] == "exec" and c[1] == install.NOTES_REPORT for c in env.calls)
    assert not any(c[0] == "exec" and ("apt-get" in c[1] or "curl" in c[1]) for c in env.calls)


def test_a_refined_mini_agent_puts_the_notes_file_in_its_system_prompt_and_records_the_hash(tmp_path):
    write(tmp_path / "state" / "app" / "CLAUDE.md", "Run the solr tests first.")
    digest = bundle.export(tmp_path / "state", tmp_path / "bundle")["hash"]
    a = make_mini(tmp_path, bundle_dir=str(tmp_path / "bundle"))
    assert "Run the solr tests first." in a._config_yaml and "You are helpful." in a._config_yaml
    env = FakeEnv()
    asyncio.run(a.install(env))
    assert any(c[0] == "exec" and f"echo {digest} > {install.NOTES}/HASH" in c[1] for c in env.calls)


def test_a_mini_run_captures_the_patch_even_when_the_agent_fails(tmp_path, monkeypatch):
    async def boom(self, instruction, environment, context):
        raise RuntimeError("agent died")

    monkeypatch.setattr(agent.MiniSweAgent, "run", boom)
    env = FakeEnv()
    with pytest.raises(RuntimeError, match="agent died"):
        asyncio.run(make_mini(tmp_path).run("do it", env, SimpleNamespace()))
    assert env.calls[-1] == ("exec", install.CAPTURE, "root")


def test_harbor_preflight_accepts_the_mini_options():
    agent.ArmMiniSweAgent.parse_options({"tools_dir": "/t", "bundle_dir": "/b", "cost_limit": "0"})
