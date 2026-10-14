"""SWEPRO_STUDY picks the repository; ansible stays the default with its original paths and tag."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("STUDY", "REPO_PREFIX", "EXCLUDED", "RUNS", "DOCS", "FREEZE_TAG", "REPO_LABEL")


def load(study):
    env = {k: v for k, v in os.environ.items() if k != "SWEPRO_STUDY"}
    if study is not None:
        env["SWEPRO_STUDY"] = study
    code = ("import json; from bench.swepro import config as c; "
            f"print(json.dumps({{k: getattr(c, k) for k in {FIELDS!r}}}, default=str))")
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    return proc


def test_ansible_is_the_default_and_keeps_its_paths():
    c = json.loads(load(None).stdout)
    assert c["STUDY"] == "ansible" and c["REPO_LABEL"] == "ansible"
    assert c["REPO_PREFIX"] == "instance_ansible__ansible-"
    assert c["RUNS"] == str(Path.home() / "swepro-runs")
    assert c["DOCS"] == str(ROOT / "docs" / "evaluations" / "swepro-refine")
    assert c["FREEZE_TAG"] == "swepro-prereg"
    assert len(c["EXCLUDED"]) == 2


@pytest.mark.parametrize("study,prefix", [("openlibrary", "instance_internetarchive__openlibrary-"),
                                          ("flipt", "instance_flipt-io__flipt-")])
def test_another_study_gets_its_own_prefix_paths_tag_and_excludes_its_pilot_tasks(study, prefix):
    c = json.loads(load(study).stdout)
    assert c["STUDY"] == study and c["REPO_LABEL"] == study and c["REPO_PREFIX"] == prefix
    assert c["RUNS"] == str(Path.home() / f"swepro-runs-{study}")
    assert c["DOCS"] == str(ROOT / "docs" / "evaluations" / f"swepro-refine-{study}")
    assert c["FREEZE_TAG"] == f"swepro-prereg-{study}"
    assert len(c["EXCLUDED"]) == 8 and len(set(c["EXCLUDED"])) == 8
    assert all(t.startswith(prefix) for t in c["EXCLUDED"])


def test_an_unknown_study_refuses_to_load():
    proc = load("nope")
    assert proc.returncode != 0 and "unknown SWEPRO_STUDY 'nope'" in proc.stderr


def test_the_report_limits_name_the_study_repository():
    env = {**os.environ, "SWEPRO_STUDY": "flipt"}
    code = "from bench.swepro import analysis; print(analysis.LIMITS[0]); print(analysis.LIMITS[2])"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout
    assert "(flipt)" in out and "The flipt fixes are public" in out and "ansible" not in out


def test_the_refine_prompt_names_the_study_repository():
    env = {**os.environ, "SWEPRO_STUDY": "flipt"}
    code = "from bench.swepro import refine; print(refine.PROMPT)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout
    assert "tasks in the flipt repository\n(github.com/flipt-io/flipt)" in out
    assert "holds no flipt code" in out and "future flipt\ntasks" in out and "ansible" not in out


def test_the_ansible_refine_prompt_is_unchanged():
    from bench.swepro import refine
    assert "tasks in the ansible repository\n(github.com/ansible/ansible)" in refine.PROMPT
    assert "holds no ansible code, only the notes the agent will have on future ansible\ntasks" in refine.PROMPT
