"""The seeded practice/test split of the valid tasks, and the seeded test order."""
import argparse
import json
import random
from pathlib import Path

from bench.swepro import config


class SplitTooSmall(RuntimeError):
    pass


def split(valid) -> dict:
    names = sorted(valid)
    random.Random(config.SPLIT_SEED).shuffle(names)
    practice, test = names[:config.N_PRACTICE], names[config.N_PRACTICE:]
    if len(test) < config.MIN_TEST:
        raise SplitTooSmall(f"only {len(test)} test tasks; the spec needs {config.MIN_TEST} (ask the user)")
    return {"seed": config.SPLIT_SEED, "practice": practice, "test": test}


def test_order(test) -> list:
    names = sorted(test)
    random.Random(config.ORDER_SEED).shuffle(names)
    return names


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write the practice/test split from valid.json.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    valid = json.loads((args.runs / "valid.json").read_text())
    result = split(valid["valid"])
    result["test_order"] = test_order(result["test"])
    result["invalid"] = valid["invalid"]
    args.docs.mkdir(parents=True, exist_ok=True)
    (args.docs / "split.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"practice {len(result['practice'])}, test {len(result['test'])}, invalid {len(result['invalid'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
