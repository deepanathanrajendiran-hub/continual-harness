from collections import Counter

import pytest

from bench.tb4 import draw

POOL = ([{"name": f"sw{i}", "category": "Software", "estimate_h": 4.0} for i in range(6)]
        + [{"name": f"ml{i}", "category": "ML", "estimate_h": 2.0} for i in range(5)]
        + [{"name": "ops0", "category": "Operations", "estimate_h": 8.0}]
        + [{"name": f"sci{i}", "category": "Science", "estimate_h": 5.0} for i in range(4)])


def test_draw_is_deterministic():
    assert draw.draw(POOL, 20261007, 10) == draw.draw(list(reversed(POOL)), 20261007, 10)


def test_setup_is_excluded_and_tasks_are_distinct():
    d = draw.draw(POOL, 20261007, 10)
    names = [m["task"] for m in d["measured"]]
    assert len(names) == 10 == len(set(names))
    assert d["setup"] not in names
    assert [m["order"] for m in d["measured"]] == list(range(1, 11))


def test_first_arms_are_balanced():
    d = draw.draw(POOL, 20261007, 10)
    assert Counter(m["first_arm"] for m in d["measured"]) == {"control": 5, "horizon": 5}


def test_round_robin_only_skips_exhausted_categories():
    d = draw.draw(POOL, 20261007, 10)
    category = {t["name"]: t["category"] for t in POOL}
    available = Counter(t["category"] for t in POOL if t["name"] != d["setup"])
    picked = Counter(category[m["task"]] for m in d["measured"])
    for a in available:
        for b in available:
            if picked[a] >= picked[b] + 2:
                assert picked[b] == available[b]


def test_too_small_a_pool_is_an_error():
    with pytest.raises(ValueError):
        draw.draw(POOL[:10], 1, 10)


def test_manifest_round_trip(tmp_path):
    d = draw.draw(POOL, 20261007, 10)
    validated = {t["name"]: {"category": t["category"], "estimate_h": t["estimate_h"], "workdir": "/app",
                             "agent_image_id": f"sha256:a-{t['name']}", "verifier_image_id": f"sha256:v-{t['name']}",
                             "copy_digest": "d" * 64} for t in POOL}
    path = tmp_path / "manifest.csv"
    draw.write_manifest(path, d, validated)
    rows = draw.read_manifest(path)
    assert rows[0]["order"] == 0 and rows[0]["first_arm"] == "setup" and rows[0]["task"] == d["setup"]
    assert [r["task"] for r in rows[1:]] == [m["task"] for m in d["measured"]]
    assert isinstance(rows[1]["estimate_h"], float) and rows[1]["agent_image_id"].startswith("sha256:a-")
