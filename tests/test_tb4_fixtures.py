import json
from pathlib import Path

import pytest

from bench.tb4 import config, fixtures, score

ROOT = Path(__file__).parent / "fixtures" / "tb4"


@pytest.mark.parametrize("name,arm", [("setup-control", "control"), ("setup-horizon", "horizon")])
def test_real_setup_trials_score_as_observed(name, arm):
    row = score.score_trial(fixtures.load_fixture(ROOT / name))
    assert row["arm"] == arm and row["valid"], row["invalid_reasons"]
    assert row["claude_code_version"] == config.CLAUDE_CODE_VERSION
    assert row["skill_loaded"] is (arm == "horizon")
    assert row["horizon_started"] is (arm == "horizon")
    assert row["image_ids"] == json.loads((ROOT / name / "record.json").read_text())["image_ids_expected"]

def test_the_real_horizon_trial_reports_its_last_result_record():
    events_path = ROOT / "setup-horizon" / "trial" / "agent" / "claude-code.txt"
    results = [json.loads(line) for line in events_path.read_text().splitlines() if '"type": "result"' in line
               or '"type":"result"' in line]
    assert len(results) == 3
    row = score.score_trial(fixtures.load_fixture(ROOT / "setup-horizon"))
    assert row["final_message"] == results[-1]["result"]
