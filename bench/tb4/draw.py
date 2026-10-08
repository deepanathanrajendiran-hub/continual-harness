"""Seeded draw of the setup task and the measured tasks; manifest read and write."""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

from bench.tb4 import config

ALGORITHM = (
    "rng = random.Random(seed); setup = rng.choice(sorted names); categories = rng.sample(sorted "
    "categories of the rest); each category's tasks = rng.sample(sorted names); take tasks round-robin "
    "over categories until n; first arms = n//2 control + (n - n//2) horizon, rng.shuffle."
)
FIELDS = ("order", "task", "category", "estimate_h", "first_arm", "workdir",
          "agent_image_id", "verifier_image_id", "copy_digest")


def draw(pool: list, seed: int, n: int) -> dict:
    by_name = {t["name"]: t for t in pool}
    names = sorted(by_name)
    if len(names) < n + 1:
        raise ValueError(f"need {n + 1} validated tasks, have {len(names)}")
    rng = random.Random(seed)
    setup = rng.choice(names)
    rest = [x for x in names if x != setup]
    categories = sorted({by_name[x]["category"] for x in rest})
    order = rng.sample(categories, len(categories))
    queues = {}
    for category in order:
        members = sorted(x for x in rest if by_name[x]["category"] == category)
        queues[category] = rng.sample(members, len(members))
    picked = []
    while len(picked) < n:
        for category in order:
            if queues[category] and len(picked) < n:
                picked.append(queues[category].pop(0))
    arms = ["control"] * (n // 2) + ["horizon"] * (n - n // 2)
    rng.shuffle(arms)
    return {"seed": seed, "algorithm": ALGORITHM, "setup": setup,
            "measured": [{"order": i + 1, "task": t, "first_arm": a}
                         for i, (t, a) in enumerate(zip(picked, arms))]}


def write_manifest(path: Path, drawn: dict, validated: dict) -> None:
    rows = [{"order": 0, "task": drawn["setup"], "first_arm": "setup"}] + drawn["measured"]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            v = validated[row["task"]]
            writer.writerow({"order": row["order"], "task": row["task"], "category": v["category"],
                             "estimate_h": v["estimate_h"], "first_arm": row["first_arm"],
                             "workdir": v["workdir"], "agent_image_id": v["agent_image_id"],
                             "verifier_image_id": v["verifier_image_id"], "copy_digest": v["copy_digest"]})


def read_manifest(path: Path) -> list:
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["order"] = int(row["order"])
        row["estimate_h"] = float(row["estimate_h"])
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    validation = json.loads(args.validation.read_text())
    passed = {t["task"]: t for t in validation["tasks"] if t["ok"]}
    pool = [{"name": name, "category": t["category"]} for name, t in passed.items()]
    drawn = draw(pool, config.SEED, config.N_MEASURED)
    write_manifest(args.out, drawn, passed)
    print(json.dumps(drawn, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
