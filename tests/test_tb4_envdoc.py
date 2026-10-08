import subprocess

from bench.tb4 import envdoc


def fake_run(cmd, **kwargs):
    outputs = {
        ("harbor", "--version"): "0.24.0\n",
        ("claude", "--version"): "2.1.293 (Claude Code)\n",
        ("docker", "version"): "28.4.0\n",
        ("docker", "info"): "8 12884901888\n",
        ("git", "-C"): "452bf305c6daa62fc59061d22133a7cbc7c1572e\n",
    }
    return subprocess.CompletedProcess(cmd, 0, outputs.get(tuple(cmd[:2]), ""), "")


def test_render_contains_every_recorded_value(tmp_path):
    (tmp_path / "control.md").write_text("c\n")
    rows = [{"order": 1, "task": "demo", "category": "ML", "estimate_h": 2.0, "first_arm": "control",
             "workdir": "/app", "agent_image_id": "sha256:aaa", "verifier_image_id": "sha256:vvv",
             "copy_digest": "d" * 64}]
    bundle = {"commit": "2f65f2a", "files": {"horizon/SKILL.md": "e" * 64}}
    facts = envdoc.collect_facts(rows, bundle, tmp_path, run=fake_run, prompts_dir=tmp_path)
    text = envdoc.render(facts)
    for needed in ("0.24.0", "2.1.293", "28.4.0", "452bf305c6daa62fc59061d22133a7cbc7c1572e",
                   "sha256:aaa", "sha256:vvv", "d" * 64, "e" * 64, "horizon/SKILL.md", "control.md"):
        assert needed in text
