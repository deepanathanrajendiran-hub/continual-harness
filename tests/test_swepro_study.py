"""SWEPRO_STUDY picks the repository; ansible stays the default with its original paths and tag."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("STUDY", "REPO_PREFIX", "EXCLUDED", "RUNS", "DOCS", "FREEZE_TAG", "REPO_LABEL", "MODEL",
          "MODEL_NAME", "PILOT", "ALLOW_HOST", "BASE_URL", "PROVIDER_KEYCHAIN")


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
    assert c["MODEL"] == "anthropic/claude-sonnet-5-5" and c["MODEL_NAME"] == "Sonnet 5.5"


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


def test_the_ansible_haiku_study_reuses_the_ansible_pool_with_haiku():
    c = json.loads(load("ansible-haiku").stdout)
    a = json.loads(load(None).stdout)
    assert c["MODEL"] == "anthropic/claude-haiku-5-5" and c["MODEL_NAME"] == "Haiku 5.5"
    assert (c["REPO_LABEL"], c["REPO_PREFIX"], c["EXCLUDED"]) == ("ansible", a["REPO_PREFIX"], a["EXCLUDED"])
    assert c["RUNS"] == str(Path.home() / "swepro-runs-ansible-haiku")
    assert c["DOCS"] == str(ROOT / "docs" / "evaluations" / "swepro-refine-ansible-haiku")
    assert c["FREEZE_TAG"] == "swepro-prereg-ansible-haiku"
    practice = json.loads((ROOT / "docs" / "evaluations" / "swepro-refine" / "split.json").read_text())["practice"]
    assert len(set(c["PILOT"])) == 8 and set(c["PILOT"]) <= set(practice)


def test_the_report_limits_name_the_study_model():
    env = {**os.environ, "SWEPRO_STUDY": "ansible-haiku"}
    code = "from bench.swepro import analysis; print(analysis.LIMITS[0])"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout
    assert "(ansible) and one model (Haiku 5.5)" in out


def test_the_openlibrary_haiku_study_reuses_the_openlibrary_pool_with_haiku():
    c = json.loads(load("openlibrary-haiku").stdout)
    o = json.loads(load("openlibrary").stdout)
    assert c["MODEL"] == "anthropic/claude-haiku-5-5" and c["MODEL_NAME"] == "Haiku 5.5"
    assert (c["REPO_LABEL"], c["REPO_PREFIX"], c["EXCLUDED"], c["PILOT"]) == (
        "openlibrary", o["REPO_PREFIX"], o["EXCLUDED"], o["PILOT"])
    assert c["RUNS"] == str(Path.home() / "swepro-runs-openlibrary-haiku")
    assert c["FREEZE_TAG"] == "swepro-prereg-openlibrary-haiku"


def test_ansible_talks_to_anthropic_with_the_subscription():
    c = json.loads(load(None).stdout)
    assert (c["ALLOW_HOST"], c["BASE_URL"], c["PROVIDER_KEYCHAIN"]) == ("api.anthropic.com", None, None)


def test_the_openlibrary_deepseek_study_points_claude_code_at_deepseek():
    c = json.loads(load("openlibrary-deepseek").stdout)
    o = json.loads(load("openlibrary").stdout)
    assert (c["MODEL"], c["MODEL_NAME"]) == ("deepseek-v4-flash", "DeepSeek V4 Flash")
    assert (c["ALLOW_HOST"], c["BASE_URL"]) == ("api.deepseek.com", "https://api.deepseek.com/anthropic")
    assert c["PROVIDER_KEYCHAIN"] == "swepro-deepseek-key"
    assert (c["REPO_PREFIX"], c["EXCLUDED"], c["PILOT"]) == (o["REPO_PREFIX"], o["EXCLUDED"], o["PILOT"])
    assert c["RUNS"] == str(Path.home() / "swepro-runs-openlibrary-deepseek")


def test_a_provider_studys_network_probe_needs_the_provider_open_and_anthropic_closed():
    env = {**os.environ, "SWEPRO_STUDY": "openlibrary-deepseek"}
    code = "import json; from bench.swepro import probe; print(json.dumps([probe.MODEL_URL, probe.BLOCKED_URLS]))"
    model_url, blocked = json.loads(subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                                   capture_output=True, text=True).stdout)
    assert model_url == "https://api.deepseek.com/v1/models"
    assert "https://api.anthropic.com/v1/models" in blocked


def test_the_ansible_network_probe_is_unchanged():
    from bench.swepro import probe
    assert probe.MODEL_URL == "https://api.anthropic.com/v1/models" and len(probe.BLOCKED_URLS) == 4
