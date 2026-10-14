import json
import subprocess

import pytest

from bench.swepro import bundle, config, prereg, tools

T = [f"instance_ansible__ansible-{i:040d}-v" for i in range(80)]


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def frozen_inputs(tmp_path):
    runs, docs = tmp_path / "runs", tmp_path / "docs"
    write(runs / "refine" / "state" / "app" / "CLAUDE.md", "Use bin/ansible-test units.")
    write(runs / "refine" / "state" / "memory" / "MEMORY.md", "- [u](u.md)")
    write(runs / "refine" / "skill" / "SKILL.md", "refine")
    bundle._write_manifest(runs / "refine" / "skill")
    for rel in (tools.CLAUDE_REL, tools.LOADER_REL, "patch_replay.py"):
        write(runs / "tools" / rel, rel)
    tools.write_manifest(runs / "tools")
    split = {"seed": config.SPLIT_SEED, "practice": T[:30], "test": T[30:], "test_order": T[30:][::-1],
             "invalid": {}}
    write(docs / "split.json", json.dumps(split))
    write(runs / "practice" / "gate.json", json.dumps({"passes": 15, "decision": "ask_user"}))
    return runs, docs


def test_export_bundle_freezes_the_state(frozen_inputs):
    runs, _ = frozen_inputs
    m = prereg.export_bundle(runs)
    assert bundle.verify(runs / "bundle") == m["hash"]
    assert ".claude/CLAUDE.md" in m["files"]


def test_collect_pins_everything_the_test_phase_depends_on(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={"harbor": "0.24.0", "colima": "0.10.3"})
    assert p["bundle"]["hash"] == bundle.verify(runs / "bundle")
    assert p["refine_snapshot"]["hash"] == bundle.manifest(runs / "refine" / "skill")["hash"]
    assert p["tools"] == json.loads((runs / "tools" / "manifest.json").read_text())
    assert p["split"]["test_order"] == T[30:][::-1]
    assert p["pins"]["model"] == config.MODEL and p["pins"]["scale_commit"] == config.SCALE_COMMIT
    assert p["analysis"]["draws"] == config.PERM_DRAWS and p["analysis"]["seed"] == config.PERM_SEED
    assert p["gate"] == {"passes": 15, "decision": "ask_user"}


def test_collect_refuses_a_bundle_edited_after_export(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "bundle" / "memory" / "MEMORY.md", "edited")
    with pytest.raises(bundle.BundleError):
        prereg.collect(runs, docs, versions={})


def test_collect_refuses_a_gate_that_said_stop(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "practice" / "gate.json", json.dumps({"passes": 28, "decision": "stop_high"}))
    with pytest.raises(prereg.FreezeError, match="stop_high"):
        prereg.collect(runs, docs, versions={})


def test_collect_refuses_changed_tools(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    write(runs / "tools" / tools.LOADER_REL, "other loader")
    with pytest.raises(prereg.FreezeError, match="tools"):
        prereg.collect(runs, docs, versions={})


def test_write_renders_json_and_markdown(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={"harbor": "0.24.0"})
    json_path, md_path = prereg.write(p, docs)
    assert json.loads(json_path.read_text()) == p
    md = md_path.read_text()
    assert p["bundle"]["hash"] in md and "sign-flip" in md and str(len(T[30:])) in md


def git(responses):
    """Fake git: responses maps an argv tail (tuple) to (returncode, stdout)."""
    def run(cmd, **kw):
        for tail, (rc, out) in responses.items():
            if tuple(cmd[-len(tail):]) == tail:
                return subprocess.CompletedProcess(cmd, rc, out, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


def test_require_freeze_returns_the_tagged_commit():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc123\n")})
    assert prereg.require_freeze(run=run) == "abc123"


def test_require_freeze_refuses_without_the_tag():
    with pytest.raises(prereg.NotFrozen, match="tag"):
        prereg.require_freeze(run=git({("rev-list", "-n", "1", config.FREEZE_TAG): (128, "")}))


def test_require_freeze_refuses_frozen_files_changed_since_the_tag():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc\n"),
               ("diff", "--quiet", "abc", "--", *prereg.FROZEN_PATHS): (1, "")})
    with pytest.raises(prereg.NotFrozen, match="changed"):
        prereg.require_freeze(run=run)


def test_require_freeze_refuses_uncommitted_frozen_files():
    run = git({("rev-list", "-n", "1", config.FREEZE_TAG): (0, "abc\n"),
               ("status", "--porcelain", "--", *prereg.FROZEN_PATHS): (0, " M bench/swepro/run.py\n")})
    with pytest.raises(prereg.NotFrozen, match="uncommitted"):
        prereg.require_freeze(run=run)


def test_check_runtime_matches_bundle_and_tools(frozen_inputs):
    runs, docs = frozen_inputs
    prereg.export_bundle(runs)
    p = prereg.collect(runs, docs, versions={})
    prereg.check_runtime(p, runs)
    write(runs / "bundle" / "memory" / "MEMORY.md", "edited")
    with pytest.raises(bundle.BundleError):
        prereg.check_runtime(p, runs)
