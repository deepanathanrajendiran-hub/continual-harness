"""Read Terminal-Bench task metadata and apply the spec's static filter."""
import argparse
import json
import sys
import tomllib
from pathlib import Path

from bench.tb4 import config


def load_meta(task_dir: Path) -> dict:
    data = tomllib.loads((task_dir / "task.toml").read_text())
    env = data.get("environment", {})
    verifier_env = data.get("verifier", {}).get("environment", {})
    meta = data.get("metadata", {})
    return {
        "name": task_dir.name,
        "category": meta.get("category", ""),
        "estimate_h": float(meta.get("expert_time_estimate_hours", 0) or 0),
        "cpus": env.get("cpus"),
        "memory_mb": env.get("memory_mb"),
        "gpus": int(env.get("gpus") or 0),
        "compose": (task_dir / "environment" / "docker-compose.yaml").exists(),
        "verifier_allow_internet": verifier_env.get("allow_internet", True),
        "verifier_network_mode": verifier_env.get("network_mode", "public"),
        "skills_dir": env.get("skills_dir"),
        "artifacts": data.get("artifacts", []),
    }


def exclusion_reasons(meta: dict) -> list:
    reasons = []
    if meta["gpus"]:
        reasons.append(f"gpus={meta['gpus']}")
    if meta["cpus"] is not None and meta["cpus"] > config.MAX_CPUS:
        reasons.append(f"cpus={meta['cpus']}")
    if meta["memory_mb"] is not None and meta["memory_mb"] > config.MAX_MEMORY_MB:
        reasons.append(f"memory_mb={meta['memory_mb']}")
    if meta["compose"]:
        reasons.append("environment/docker-compose.yaml")
    if meta["verifier_allow_internet"] is False or meta["verifier_network_mode"] != "public":
        reasons.append("verifier network denied")
    if meta["name"] in config.AMD64_ONLY:
        reasons.append("amd64-only (terminal-bench #1802-#1806)")
    if meta["skills_dir"]:
        reasons.append(f"skills_dir={meta['skills_dir']}")
    return reasons


def in_band(meta: dict) -> bool:
    low, high = config.BAND_HOURS
    return low <= meta["estimate_h"] <= high


def survey(tb4_root: Path) -> dict:
    survivors, excluded = [], {}
    for task_dir in sorted(p.parent for p in (tb4_root / "tasks").glob("*/task.toml")):
        meta = load_meta(task_dir)
        reasons = exclusion_reasons(meta)
        if reasons:
            excluded[meta["name"]] = reasons
        else:
            survivors.append(meta)
    return {"survivors": survivors, "band": [m for m in survivors if in_band(m)], "excluded": excluded}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tb4", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = survey(args.tb4)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"survivors": len(result["survivors"]), "band": len(result["band"]),
                      "excluded": len(result["excluded"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
