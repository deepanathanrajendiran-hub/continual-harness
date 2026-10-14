import json
import os

import pytest

from bench.swepro import bundle


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def state(tmp_path):
    s = tmp_path / "state"
    write(s / "app" / "CLAUDE.md", "Run tests with bin/ansible-test units.\n")
    write(s / "app" / ".claude" / "skills" / "ansible-tests" / "SKILL.md", "skill")
    write(s / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "the refine snapshot")
    write(s / "app" / ".claude" / "skills" / "horizon" / "SKILL.md", "never exported")
    write(s / "app" / ".claude" / "agents" / "reviewer.md", "agent")
    write(s / "app" / ".claude" / "harness" / "refine-log.jsonl", "{}")
    write(s / "memory" / "MEMORY.md", "- [Units](units.md) — how to run units\n")
    write(s / "memory" / "units.md", "note")
    return s


def files(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_export_keeps_only_the_four_note_layers(state, tmp_path):
    m = bundle.export(state, tmp_path / "b")
    assert files(tmp_path / "b") == [
        ".claude/CLAUDE.md", ".claude/agents/reviewer.md", ".claude/skills/ansible-tests/SKILL.md",
        "manifest.json", "memory/MEMORY.md", "memory/units.md"]
    assert (tmp_path / "b" / ".claude" / "CLAUDE.md").read_text().startswith("Run tests")
    assert set(m["files"]) == set(files(tmp_path / "b")) - {"manifest.json"}


def test_export_of_an_empty_state_is_an_empty_bundle_with_a_hash(tmp_path):
    m = bundle.export(tmp_path / "nothing", tmp_path / "b")
    assert m["files"] == {} and len(m["hash"]) == 64
    assert files(tmp_path / "b") == ["manifest.json"]


def test_export_replaces_an_old_bundle(state, tmp_path):
    write(tmp_path / "b" / "memory" / "stale.md")
    bundle.export(state, tmp_path / "b")
    assert not (tmp_path / "b" / "memory" / "stale.md").exists()


def test_export_refuses_a_second_claude_md(state, tmp_path):
    write(state / "app" / ".claude" / "CLAUDE.md", "two homes for rho")
    with pytest.raises(bundle.BundleError, match="CLAUDE.md"):
        bundle.export(state, tmp_path / "b")


def test_export_refuses_a_symlink_in_the_state(state, tmp_path):
    os.symlink("/etc/passwd", state / "memory" / "leak.md")
    with pytest.raises(bundle.BundleError, match="symlink"):
        bundle.export(state, tmp_path / "b")


def test_the_hash_changes_with_any_byte_and_verify_catches_edits(state, tmp_path):
    h1 = bundle.export(state, tmp_path / "b")["hash"]
    assert bundle.verify(tmp_path / "b") == h1
    write(tmp_path / "b" / "memory" / "units.md", "edited")
    with pytest.raises(bundle.BundleError, match="manifest"):
        bundle.verify(tmp_path / "b")
    write(state / "memory" / "units.md", "edited")
    assert bundle.export(state, tmp_path / "c")["hash"] != h1


def test_the_hash_ignores_where_the_bundle_lives(state, tmp_path):
    assert bundle.export(state, tmp_path / "b")["hash"] == bundle.export(state, tmp_path / "c")["hash"]


def test_snapshot_refine_resolves_symlinks_and_bundles_the_harness(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "harness" / "cli.py", "cli")
    write(repo / "harness" / "refine_log.py", "log")
    write(repo / "harness" / "paths.py", "paths")
    skill = repo / ".claude" / "skills" / "refine"
    write(skill / "SKILL.md", "skill text")
    write(skill / "references" / "commands.md", "refs")
    (skill / "scripts").mkdir()
    os.symlink("../../../../harness/cli.py", skill / "scripts" / "harness.py")
    m = bundle.snapshot_refine(skill, repo / "harness", tmp_path / "snap")
    snap = tmp_path / "snap"
    assert files(snap) == ["SKILL.md", "manifest.json", "references/commands.md", "scripts/harness.py",
                           "scripts/paths.py", "scripts/refine_log.py"]
    assert (snap / "scripts" / "harness.py").read_text() == "cli"
    assert not any(p.is_symlink() for p in snap.rglob("*"))
    assert json.loads((snap / "manifest.json").read_text()) == m
