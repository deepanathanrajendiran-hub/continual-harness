"""Seeded domain round-robin order of the task pool, per-task arm order, and the N rule."""
import argparse
import json
import random
import re
import sys
from pathlib import Path

from bench.evo import config

ALGORITHM = (
    "for each domain d in DOMAINS: members = sorted pool tasks whose name starts theme_<d>_; "
    "random.Random(f'{seed}:{d}').shuffle(members); then take round-robin over DOMAINS in that "
    "order, skipping exhausted domains, until every task is taken. Arm order: positions 2k and 2k+1 of that "
    "order (from 0) form pair k; arms = ['control', 'horizon']; random.Random(f'{seed}:arms:pair{k}').shuffle(arms); "
    "position 2k runs arms in that order and position 2k+1 in the reverse order. A task outside the pool "
    "(the walkthrough): random.Random(f'{seed}:arms:{task}').shuffle(arms)."
)
_DOMAIN = re.compile(r"^theme_(d\d+)_")


def domain(task: str) -> str:
    match = _DOMAIN.match(task)
    if not match:
        raise ValueError(f"not a theme_d<k>_ task name: {task!r}")
    return match.group(1)


def seeded_order(pool, seed: int, domains) -> list:
    names = list(pool)
    if len(set(names)) != len(names):
        raise ValueError("pool has duplicate tasks")
    outside = sorted(t for t in names if domain(t) not in domains)
    if outside:
        raise ValueError(f"tasks outside the listed domains: {outside}")
    queues = []
    for d in domains:
        members = sorted(t for t in names if domain(t) == d)
        random.Random(f"{seed}:{d}").shuffle(members)
        queues.append(members)
    order = []
    while len(order) < len(names):
        for queue in queues:
            if queue:
                order.append(queue.pop(0))
    return order


def arm_order(task: str, seed: int) -> tuple:
    """Consecutive pool tasks in the seeded order get opposite arm orders, so every even prefix of the order
    runs each arm first equally often; a task outside the pool gets its own seeded coin."""
    ranked = seeded_order(config.POOL, seed, config.DOMAINS)
    arms = list(config.ARMS)
    if task in ranked:
        position = ranked.index(task)
        random.Random(f"{seed}:arms:pair{position // 2}").shuffle(arms)
        if position % 2:
            arms.reverse()
    else:
        random.Random(f"{seed}:arms:{task}").shuffle(arms)
    return tuple(arms)


def n_rule(m_control: float, m_horizon: float, *, choices=config.N_CHOICES,
           rounds=config.ROUNDS_PER_TASK_PLAN, budget=config.BUDGET_AGENT_HOURS):
    if not (m_control >= 0 and m_horizon >= 0):
        raise ValueError(f"minutes per round must be non-negative numbers: {m_control!r}, {m_horizon!r}")
    for n in sorted(choices, reverse=True):
        if n * rounds * (m_control + m_horizon) <= budget * 60:
            return n
    return None


def write_order(path: Path, *, pool=config.POOL, seed=config.SEED, domains=config.DOMAINS) -> dict:
    tasks = seeded_order(pool, seed, domains)
    payload = {"seed": seed, "algorithm": ALGORITHM, "order": tasks,
               "arm_orders": {t: list(arm_order(t, seed)) for t in tasks}}
    text = json.dumps(payload, indent=2) + "\n"
    path = Path(path)
    if path.exists() and path.read_text() != text:
        raise FileExistsError(f"{path} holds a different order; it is fixed once written")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=config.RUNS / "order.json")
    args = parser.parse_args(argv)
    print(json.dumps(write_order(args.out), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
