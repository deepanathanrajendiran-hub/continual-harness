"""Stage 1 tables and the three-condition decision rule (spec: Stage 1 analysis and decision rule)."""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from bench.tb4 import config, draw, score


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def valid_pairs(rows) -> dict:
    pairs = {}
    for task, (status, attempt) in score.statuses(rows).items():
        if status == "valid":
            pairs[task] = {r["arm"]: r for r in rows if r["task"] == task and r["attempt"] == attempt}
    return pairs


def decision(rows, n_planned: int = config.N_MEASURED) -> dict:
    pairs = valid_pairs(rows)
    control_passes = sum(1 for p in pairs.values() if p["control"]["passed"])
    latest = {}
    for r in rows:
        latest[r["task"]] = max(latest.get(r["task"], 0), r["attempt"])
    horizon = [r for r in rows if r["arm"] == "horizon" and r["valid"] and r["attempt"] == latest[r["task"]]]
    started = sum(1 for r in horizon if r["horizon_started"])
    leaked = sorted({r["task"] for r in rows if r["arm"] == "control" and (r["horizon_started"] or r["horizon_calls"])})
    c1 = len(pairs) >= n_planned - 1
    c2 = 2 <= control_passes <= 8
    c3 = bool(horizon) and started >= 0.9 * len(horizon) and not leaked
    return {"planned_pairs": n_planned, "valid_pairs": len(pairs), "control_passes": control_passes,
            "horizon_trials": len(horizon), "horizon_started": started, "control_invoked_horizon": leaked,
            "condition_1": c1, "condition_2": c2, "condition_3": c3, "proceed": c1 and c2 and c3}


def _rate(rows, key):
    return sum(bool(r.get(key)) for r in rows) / len(rows) if rows else None


def arm_summary(rows) -> dict:
    labeled_failures = [r for r in rows if not r["passed"] and r.get("final_message") and r.get("label")]
    wall = _median([config.HARD_LIMIT_SEC if r["timed_out"] else r["wall_s"] for r in rows])
    return {
        "n": len(rows), "passes": sum(r["passed"] for r in rows), "timeouts": sum(r["timed_out"] for r in rows),
        "false_done": sum(bool(r.get("false_done")) for r in rows),
        "honest_stop": sum(bool(r.get("honest_stop")) for r in rows),
        "labeled_failures": len(labeled_failures),
        "false_done_rate": _rate(labeled_failures, "false_done"),
        "honest_stop_rate": _rate(labeled_failures, "honest_stop"),
        "tokens_median": _median([r["tokens"] for r in rows]), "tokens_n": sum(r["tokens"] is not None for r in rows),
        "cost_median": _median([r["cost_usd"] for r in rows]), "cost_n": sum(r["cost_usd"] is not None for r in rows),
        "wall_median_s": wall, "wall_censored": wall is not None and wall >= config.HARD_LIMIT_SEC,
        "horizon_started": sum(bool(r["horizon_started"]) for r in rows),
        "horizon_reviewed": sum(bool(r.get("horizon_reviewed")) for r in rows),
        "horizon_end": dict(sorted(Counter(r["horizon_end"] for r in rows).items())),
        "subagents_dispatched": sum(r["subagents_dispatched"] for r in rows),
    }


def summarize(rows) -> dict:
    pairs = valid_pairs(rows)
    flagged = sorted(t for t, p in pairs.items() if any(r["audit_flags"] for r in p.values()))
    first = {}
    for task in sorted({r["task"] for r in rows}):
        arms = {r["arm"]: r for r in rows if r["task"] == task and r["attempt"] == 1}
        if set(arms) == set(config.ARMS) and all(r["valid"] for r in arms.values()):
            first[task] = arms

    def per_arm(selected):
        return {arm: arm_summary([p[arm] for p in selected.values()]) for arm in config.ARMS}

    return {
        "pairs": [{"task": t, "control": p["control"]["passed"], "horizon": p["horizon"]["passed"],
                   "discordant": p["control"]["passed"] != p["horizon"]["passed"], "flagged": t in flagged}
                  for t, p in sorted(pairs.items())],
        "arms": per_arm(pairs),
        "arms_without_flagged": per_arm({t: p for t, p in pairs.items() if t not in flagged}),
        "first_attempt_arms": per_arm(first),
        "invalid_by_arm": dict(Counter(r["arm"] for r in rows if not r["valid"])),
        "invalid_reasons": dict(Counter(reason for r in rows for reason in r["invalid_reasons"])),
        "statuses": {t: s for t, (s, _) in score.statuses(rows).items()},
        "flagged": flagged,
    }


def _fmt(value):
    if value is None:
        return "n/a"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def render(summary: dict, decision_: dict, agreement=None) -> str:
    yes = lambda ok: "met" if ok else "not met"
    lines = ["# Terminal-Bench 4.0 Horizon pilot — stage 1 report", "",
             f"Proceed to stage 2: **{'yes' if decision_['proceed'] else 'no'}**", "",
             f"- Condition 1 (at least {decision_['planned_pairs'] - 1} valid pairs): {decision_['valid_pairs']} — {yes(decision_['condition_1'])}",
             f"- Condition 2 (control passes 2–8 of valid pairs): {decision_['control_passes']} — {yes(decision_['condition_2'])}",
             f"- Condition 3 (Horizon started in ≥90% of Horizon trials; control never invoked it): "
             f"{decision_['horizon_started']}/{decision_['horizon_trials']}, control invocations "
             f"{decision_['control_invoked_horizon'] or 'none'} — {yes(decision_['condition_3'])}",
             "", "## Pass/fail by task (valid pairs)", "", "| Task | Control | Horizon | Discordant | Flagged |",
             "| --- | --- | --- | --- | --- |"]
    lines += [f"| {p['task']} | {'pass' if p['control'] else 'fail'} | {'pass' if p['horizon'] else 'fail'} | "
              f"{'yes' if p['discordant'] else ''} | {'yes' if p['flagged'] else ''} |" for p in summary["pairs"]]
    metrics = ("n", "passes", "timeouts", "false_done", "false_done_rate", "honest_stop", "honest_stop_rate",
               "labeled_failures", "tokens_median", "tokens_n", "cost_median", "cost_n", "wall_median_s",
               "wall_censored", "horizon_started", "horizon_reviewed", "subagents_dispatched", "horizon_end")
    for title, key in (("By arm (valid pairs)", "arms"), ("By arm, flagged pairs removed", "arms_without_flagged"),
                       ("By arm, first attempts only", "first_attempt_arms")):
        lines += ["", f"## {title}", "", "| Metric | Control | Horizon |", "| --- | --- | --- |"]
        lines += [f"| {m} | {_fmt(summary[key]['control'][m])} | {_fmt(summary[key]['horizon'][m])} |" for m in metrics]
    lines += ["", "## Validity", "", f"- Invalid trials by arm: {summary['invalid_by_arm'] or 'none'}",
              f"- Invalid reasons: {summary['invalid_reasons'] or 'none'}",
              f"- Pair statuses: {summary['statuses']}", f"- Flagged pairs: {summary['flagged'] or 'none'}"]
    if agreement:
        lines += [f"- Judge/controller agreement: {agreement['agree']}/{agreement['n']} ({_fmt(agreement['rate'])})"]
    lines += ["", "## Limits", "",
              "- Ten pairs with binary rewards: descriptive only; no significance claim.",
              "- The judge reads the final message only, but Horizon messages can reveal the arm.",
              "- Scores are not comparable with the public leaderboard (native arm64 images, 120-minute cap, "
              "explicit effort, modified instruction).", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path,
                        default=config.REPO_ROOT / "docs/evaluations/tb4-horizon-pilot/manifest.csv")
    parser.add_argument("--agreement", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = [json.loads(line) for line in args.results.read_text().splitlines() if line.strip()]
    pending = {t: s for t, (s, _) in score.statuses(rows).items() if s in ("incomplete", "rerun")}
    if pending:
        print(json.dumps({"error": "pairs are not final; finish runs and reruns first", "pending": pending}))
        return 2
    measured = {r["task"] for r in draw.read_manifest(args.manifest) if r["first_arm"] != "setup"}
    present = {r["task"] for r in rows}
    if present != measured:
        print(json.dumps({"error": "results do not cover exactly the manifest's measured tasks",
                          "never_ran": sorted(measured - present), "not_in_manifest": sorted(present - measured)}))
        return 2
    agreement = json.loads(args.agreement.read_text()) if args.agreement else None
    args.out.write_text(render(summarize(rows), decision(rows), agreement))
    print(json.dumps(decision(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
