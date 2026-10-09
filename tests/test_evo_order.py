import json
import math

import pytest

from bench.evo import config, order

EXPECTED_ORDER = [
    "theme_d1_w5_code_build_integration_e2e_wiring",
    "theme_d5_w1_data_engineering_greenfield_implementation",
    "theme_d8_w5_cloud_devops_integration_e2e_wiring",
    "theme_d9_w11_security_automation_scripting",
    "theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234",
    "theme_d11_w9_scientific_numerical_reproducibility_verification",
    "theme_d12_w1_automation_productivity_greenfield_implementation",
    "theme_d1_w11_code_build_automation_scripting",
    "theme_d5_w9_data_engineering_reproducibility_verification",
    "theme_d10_w9_ml_ai_mlops_reproducibility_verification",
    "theme_d1_w2_code_build_brownfield_modification",
    "theme_d5_w5_data_engineering_integration_e2e_wiring",
    "theme_d10_w11_ml_ai_mlops_automation_scripting",
]
# Pair k of the seeded order (positions 2k, 2k+1) runs opposite arm orders: horizon first in 3 of the first 6.
HORIZON_FIRST = {"theme_d5_w1_data_engineering_greenfield_implementation",
                 "theme_d8_w5_cloud_devops_integration_e2e_wiring",
                 "theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234",
                 "theme_d1_w11_code_build_automation_scripting",
                 "theme_d10_w9_ml_ai_mlops_reproducibility_verification",
                 "theme_d5_w5_data_engineering_integration_e2e_wiring"}


def test_domain_parses_the_theme_prefix():
    assert order.domain("theme_d1_w2_code_build_brownfield_modification") == "d1"
    assert order.domain("theme_d10_w4_ml_ai_mlops_migration_upgrade__not_1234") == "d10"
    assert order.domain(config.WALKTHROUGH) == "d11"
    for bad in ("d1_w2_code", "theme_dx_w2", "theme_d1"):
        with pytest.raises(ValueError):
            order.domain(bad)


def test_order_is_deterministic_and_ignores_input_order():
    first = order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
    assert first == order.seeded_order(list(reversed(config.POOL)), config.SEED, config.DOMAINS)
    assert sorted(first) == sorted(config.POOL) and len(first) == 13
    assert order.seeded_order(config.POOL, config.SEED + 1, config.DOMAINS) != first


def test_order_for_the_registered_pool_and_seed_is_pinned():
    assert order.seeded_order(config.POOL, config.SEED, config.DOMAINS) == EXPECTED_ORDER


def test_order_alternates_domains_and_skips_exhausted_ones():
    got = [order.domain(t) for t in order.seeded_order(config.POOL, config.SEED, config.DOMAINS)]
    assert got == ["d1", "d5", "d8", "d9", "d10", "d11", "d12",
                   "d1", "d5", "d10",
                   "d1", "d5", "d10"]


def test_each_domains_internal_order_is_stable():
    full = order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
    for d in config.DOMAINS:
        members = [t for t in config.POOL if order.domain(t) == d]
        alone = order.seeded_order(members, config.SEED, config.DOMAINS)
        assert [t for t in full if order.domain(t) == d] == alone
    fewer = [t for t in config.POOL if order.domain(t) != "d5"]
    shrunk = order.seeded_order(fewer, config.SEED, config.DOMAINS)
    assert [t for t in shrunk if order.domain(t) == "d1"] == [t for t in full if order.domain(t) == "d1"]


def test_order_refuses_unknown_domains_and_duplicates():
    with pytest.raises(ValueError, match="outside"):
        order.seeded_order(list(config.POOL) + ["theme_d2_w1_other"], config.SEED, config.DOMAINS)
    with pytest.raises(ValueError, match="duplicate"):
        order.seeded_order(list(config.POOL) + [config.POOL[0]], config.SEED, config.DOMAINS)


def test_arm_order_is_seeded_per_task():
    for task in config.POOL:
        arms = order.arm_order(task, config.SEED)
        assert sorted(arms) == ["control", "horizon"] and isinstance(arms, tuple)
        assert arms == order.arm_order(task, config.SEED)
        assert arms[0] == ("horizon" if task in HORIZON_FIRST else "control")


def test_arm_order_pairs_consecutive_positions_with_opposite_orders():
    ranked = order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
    for k in range(len(ranked) // 2):
        first, second = ranked[2 * k], ranked[2 * k + 1]
        assert order.arm_order(second, config.SEED) == tuple(reversed(order.arm_order(first, config.SEED)))
    firsts = [order.arm_order(t, config.SEED)[0] for t in ranked]
    for prefix in (6, 8, 10, 12):
        assert firsts[:prefix].count("horizon") == prefix // 2


def test_arm_order_of_a_task_outside_the_pool_is_its_own_seeded_coin():
    assert order.arm_order(config.WALKTHROUGH, config.SEED) == ("horizon", "control")
    assert "{seed}:arms:{task}" in order.ALGORITHM and "{seed}:arms:pair{k}" in order.ALGORITHM


@pytest.mark.parametrize("m_control,m_horizon,expected", [
    (18.0, 18.0, 10),     # 10 * 10 * 36 / 60 == 60.0, an exact fit
    (18.0, 18.01, 8),     # just over for 10
    (22.5, 22.5, 8),      # 8 * 10 * 45 / 60 == 60.0, an exact fit
    (22.5, 22.51, 6),
    (30.0, 30.0, 6),      # 6 * 10 * 60 / 60 == 60.0, an exact fit
    (30.0, 30.01, None),  # even 6 does not fit: stop and report back
    (0.0, 0.0, 10),
])
def test_n_rule_boundaries(m_control, m_horizon, expected):
    assert order.n_rule(m_control, m_horizon) == expected


def test_n_rule_takes_its_parameters_as_keywords():
    assert order.n_rule(10.0, 20.0, choices=(4, 2), rounds=5, budget=10.0) == 4
    assert order.n_rule(10.0, 20.0, choices=(4, 2), rounds=5, budget=4.9) is None
    assert order.n_rule(10.0, 20.0, choices=(2, 4), rounds=5, budget=5.0) == 2


@pytest.mark.parametrize("bad", [-1.0, math.nan])
def test_n_rule_refuses_impossible_minutes(bad):
    with pytest.raises(ValueError):
        order.n_rule(bad, 20.0)
    with pytest.raises(ValueError):
        order.n_rule(20.0, bad)


def test_write_order_writes_the_registered_draw_once(tmp_path):
    path = tmp_path / "runs" / "order.json"
    payload = order.write_order(path)
    data = json.loads(path.read_text())
    assert data == payload
    assert set(data) == {"seed", "algorithm", "order", "arm_orders"}
    assert data["seed"] == config.SEED and data["algorithm"] == order.ALGORITHM
    assert data["order"] == EXPECTED_ORDER
    assert data["arm_orders"] == {t: list(order.arm_order(t, config.SEED)) for t in EXPECTED_ORDER}
    assert order.write_order(path) == payload
    with pytest.raises(FileExistsError):
        order.write_order(path, seed=config.SEED + 1)
    assert json.loads(path.read_text()) == payload


def test_main_writes_and_prints_the_order(tmp_path, capsys):
    path = tmp_path / "order.json"
    assert order.main(["--out", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["order"] == EXPECTED_ORDER
    assert json.loads(path.read_text())["order"] == EXPECTED_ORDER
