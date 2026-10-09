"""Label final messages with the TB4 blind judge, score tasks, run the pre-registered permutation test, render the report."""
import argparse
import json
import statistics
import sys
from collections import Counter
from itertools import product
from pathlib import Path

from bench.evo import config, dataset, order
from bench.evo import run as evo_run
from bench.tb4 import judge
from bench.tb4 import run as runner

ANALYSIS = "exact sign-flip permutation, two-sided, alpha 0.05"
ALPHA = 0.05
TOL = 1e-9  # signed sums that differ by less than this are ties (float noise, e.g. 0.2 + 0.1 - 0.1)
GRID = tuple(k / 100 for k in range(-100, 101))  # shifts tried when inverting the test for the interval
NOT_REACHED = "not reached"
START_FLOOR = 0.9
RUBRIC = "docs/evaluations/tb4-horizon-pilot/prompts/judge.md"
LIMITS = (
    "Low power: {n} tasks, one attempt per arm. With 8 tasks and a paired SD near 0.30, the smallest reliably "
    "detectable difference is about 0.33 of a task's rounds.",
    "One model (Sonnet) through Claude Code only.",
    "The task images were patched from linux-amd64 to linux-arm64 and validated with oracle and no-op runs on every "
    "round. Scores are not comparable with the public leaderboard.",
    "No forced mid-round interruption, no ledger-wiped ablation arm and no continuous-session control.",
    "The TB4 tasks informed the Horizon v2 design. EvoCode material was seen during design; the walkthrough pair "
    "(theme_d11_w2_*) is excluded for that reason.",
    "The judge reads only the final message, but Horizon messages can reveal the arm.",
    "One operator ran the study.",
)


def read_rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path: Path, rows) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    tmp.replace(path)


def load_records(runs: Path, phase: str) -> list:
    records = [json.loads(p.read_text()) for p in sorted((runs / "records").glob("*.json"))]
    return [r for r in records if r.get("phase") == phase]


def label_rows(rows_path: Path, token: str, *, judge_fn=judge.judge, phase: str = "main", log=print) -> int:
    """Label each unlabeled final message of the phase. The judge sees the message text only; each label is saved."""
    rows = read_rows(rows_path)
    labeled = 0
    for row in rows:
        if row["phase"] == phase and row.get("final_message") and row.get("label") is None:
            row["label"] = judge_fn(row["final_message"], token)
            write_rows(rows_path, rows)
            labeled += 1
            log(f"labeled {row['job_name']} round {row['round_index']}: {row['label']}")
    return labeled


def _mean(values):
    return statistics.fmean(values) if values else None


def _ratio(count, n):
    return count / n if n else None


def _latest(rows) -> list:
    """Rows of the highest attempt of each (task, arm); rows of one phase."""
    top = {}
    for r in rows:
        top[(r["task"], r["arm"])] = max(top.get((r["task"], r["arm"]), 0), r["attempt"])
    return [r for r in rows if r["attempt"] == top[(r["task"], r["arm"])]]


def passed_rounds(rows) -> dict:
    """{(task, arm): number of distinct rounds passed} over the latest attempt of each (task, arm)."""
    passed = {}
    for r in _latest(rows):
        indices = passed.setdefault((r["task"], r["arm"]), set())
        if r["passed"]:
            indices.add(r["round_index"])
    return {key: len(indices) for key, indices in passed.items()}


def task_scores(rows, rounds_by_task) -> dict:
    """{task: {arm: passed / total rounds}}; a round without a passing row counts as failed; None without rows."""
    counts = passed_rounds(rows)
    scores = {}
    for task, total in rounds_by_task.items():
        scores[task] = {}
        for arm in config.ARMS:
            passed = counts.get((task, arm))
            if passed is not None and passed > total:
                raise ValueError(f"{task} {arm}: {passed} rounds passed but the task has {total}")
            scores[task][arm] = None if passed is None else passed / total
    return scores


def _p_value(sums, observed: float, n: int, delta: float) -> float:
    """Two-sided p of the sign-flip test that the diffs shifted by delta have mean zero."""
    target = abs(observed - delta * n)
    return sum(1 for a, b in sums if abs(a - delta * b) >= target - TOL) / len(sums)


def permutation(diffs) -> dict:
    """Exact sign-flip test over all 2^n assignments; 95% interval by inverting it over GRID."""
    diffs = [float(d) for d in diffs]
    n = len(diffs)
    wins, losses = sum(d > TOL for d in diffs), sum(d < -TOL for d in diffs)
    counts = {"wins": wins, "losses": losses, "ties": n - wins - losses}
    if not n:
        return {"n": 0, "mean": None, "ci95": (None, None), "p": None, **counts}
    # with signs s, the shifted signed sum is sum(s*d) - delta*sum(s): keep both parts per assignment
    sums = [(sum(s * d for s, d in zip(signs, diffs)), sum(signs)) for signs in product((1, -1), repeat=n)]
    total = sum(diffs)
    kept = [delta for delta in GRID if _p_value(sums, total, n, delta) >= ALPHA]
    return {"n": n, "mean": total / n, "ci95": (min(kept), max(kept)) if kept else (None, None),
            "p": _p_value(sums, total, n, 0.0), **counts}


def secondary(rows) -> dict:
    """Per-arm secondary outcomes over the given rows (one row per round)."""
    out = {}
    for arm in config.ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        reached = [r for r in mine if r.get("end_reason") != NOT_REACHED]
        counted = [r for r in mine if r.get("cases_total") and r.get("cases_passed") is not None]
        failed = [r for r in mine if not r["passed"] and r.get("label")]
        passed = [r for r in mine if r["passed"] and r.get("label")]
        minutes = [r["agent_sec"] / 60 for r in mine if r.get("agent_sec") is not None]
        tokens = [r["tokens_in"] + r["tokens_out"] for r in mine
                  if r.get("tokens_in") is not None and r.get("tokens_out") is not None]
        costs = [r["cost_usd"] for r in mine if r.get("cost_usd") is not None]
        false_done = sum(r["label"] == "claims_complete" for r in failed)
        under_claim = sum(r["label"] == "reports_incomplete" for r in passed)
        started = sum(bool(r.get("horizon_started")) for r in reached)
        out[arm] = {
            "rounds": len(mine), "reached": len(reached), "passed": sum(bool(r["passed"]) for r in mine),
            "case_score": _mean([r["cases_passed"] / r["cases_total"] for r in counted]),
            "case_rounds": len(counted), "case_missing": len(mine) - len(counted),
            "false_done": false_done, "labeled_failed": len(failed), "false_done_rate": _ratio(false_done, len(failed)),
            "under_claim": under_claim, "labeled_passed": len(passed),
            "under_claim_rate": _ratio(under_claim, len(passed)),
            "agent_minutes_median": statistics.median(minutes) if minutes else None,
            "tokens_total": sum(tokens) if tokens else None, "tokens_per_round": _mean(tokens),
            "token_rounds": len(tokens), "cost_usd_total": sum(costs) if costs else None,
            "horizon_started": started, "horizon_start_rate": _ratio(started, len(reached)),
            "horizon_calls": sum(r.get("horizon_calls") or 0 for r in mine),
            "extra_result_records": sum((r.get("result_records") or 0) > 1 for r in mine),
            "no_result_record": sum(r.get("result_records") == 0 for r in reached),
        }
    return out


def run_status(records, tasks, dropped=()) -> dict:
    """valid: both arms' latest runs are valid; dropped: the runner dropped it (`dropped`, from deviations.md) or
    an arm's rerun was invalid too; pending: anything else."""
    latest = {}
    for r in records:
        key = (r["task"], r["arm"])
        if key not in latest or r["attempt"] > latest[key]["attempt"]:
            latest[key] = r
    status = {}
    for task in tasks:
        arms = [latest.get((task, arm)) for arm in config.ARMS]
        if task in dropped or any(r and not r["valid"] and r["attempt"] >= 2 for r in arms):
            status[task] = "dropped"
        elif all(r and r["valid"] for r in arms):
            status[task] = "valid"
        else:
            status[task] = "pending"
    return status


def final_rows(rows, records) -> list:
    """Rows of each (task, arm)'s latest valid run."""
    attempt = {}
    for r in records:
        if r["valid"]:
            attempt[(r["task"], r["arm"])] = max(attempt.get((r["task"], r["arm"]), 0), r["attempt"])
    return [r for r in rows if r["attempt"] == attempt.get((r["task"], r["arm"]))]


def problems(rows, records, tasks, dropped=()) -> dict:
    """Everything that must be fixed before the report is final; empty when it can be rendered."""
    statuses = run_status(records, tasks, dropped)
    kept = final_rows(rows, records)
    scored = {(r["task"], r["arm"]) for r in kept}
    found = {
        "pending": sorted(t for t, s in statuses.items() if s == "pending"),
        "not_scored": sorted(t for t, s in statuses.items()
                             if s == "valid" and any((t, arm) not in scored for arm in config.ARMS)),
        "unlabeled": sorted(f"{r['job_name']} round {r['round_index']}" for r in kept
                            if r.get("final_message") and r.get("label") is None),
        "not_planned": sorted({r["task"] for r in rows} - set(tasks)),
    }
    return {key: value for key, value in found.items() if value}


def _where(r) -> str:
    return f"{r['task']} {r['arm']} round {r['round_index']}"


def validity(records, statuses, rows) -> dict:
    runs = {arm: {"valid": 0, "invalid": 0} for arm in config.ARMS}
    for r in records:
        runs[r["arm"]]["valid" if r["valid"] else "invalid"] += 1
    audited = [r for r in rows if "audit_flags" in r]
    return {
        "runs": runs,
        "invalid_reasons": dict(sorted(Counter(r["invalid_reason"] for r in records if not r["valid"]).items())),
        "retried": sorted(r["job_name"] for r in records if r["attempt"] >= 2),
        "dropped": sorted(t for t, s in statuses.items() if s == "dropped"),
        "control_horizon": sorted(_where(r) for r in rows
                                  if r["arm"] == "control" and (r.get("horizon_started") or r.get("horizon_calls"))),
        "extra_result_records": sorted(_where(r) for r in rows if (r.get("result_records") or 0) > 1),
        "audit": sorted(f"{_where(r)}: {', '.join(r['audit_flags'])}" for r in audited if r["audit_flags"])
                 if audited else None,
        "freezes": sorted({r["freeze"] for r in records if r.get("freeze")}),
        "leftovers": {
            "audited": sum(1 for r in rows if r.get("leftovers")),
            "killed": sum(1 for r in rows if (r.get("leftovers") or {}).get("killed")),
            "survivors": sum(1 for r in rows if (r.get("leftovers") or {}).get("survivors")),
            "tmp": sum(1 for r in rows if (r.get("leftovers") or {}).get("tmp_entries")),
            "reached": sum(1 for r in rows if r.get("end_reason") != NOT_REACHED)},
    }


def usage_consumed(records, tasks) -> dict:
    """Per arm, seven-day utilization consumed by the valid main jobs of `tasks` (usage_after - usage_before).
    Account-wide figures; a job whose two readings straddle a weekly reset is counted, not summed."""
    out = {arm: {"seven_day": 0.0, "jobs": 0, "straddled": 0} for arm in config.ARMS}
    for r in records:
        if not r.get("valid") or r["task"] not in tasks:
            continue
        before, after = r.get("usage_before") or {}, r.get("usage_after") or {}
        if before.get("seven_day") is None or after.get("seven_day") is None:
            continue
        if before.get("seven_day_resets_at") != after.get("seven_day_resets_at") or after["seven_day"] < before["seven_day"]:
            out[r["arm"]]["straddled"] += 1
            continue
        out[r["arm"]]["seven_day"] += after["seven_day"] - before["seven_day"]
        out[r["arm"]]["jobs"] += 1
    return out


def summarize(rows, records, tasks, rounds_by_task, dropped=()) -> dict:
    statuses = run_status(records, tasks, dropped)
    kept = final_rows(rows, records)
    counts = passed_rounds(kept)
    scores = task_scores(kept, {t: rounds_by_task[t] for t in tasks})
    paired = [t for t in tasks if statuses[t] == "valid" and None not in scores[t].values()]
    per_task = [{"task": t, "status": statuses[t], "rounds": rounds_by_task[t],
                 "passed": {arm: counts.get((t, arm)) for arm in config.ARMS}, "score": scores[t],
                 "d": scores[t]["horizon"] - scores[t]["control"] if t in paired else None} for t in tasks]
    paired_rows = [r for r in kept if r["task"] in paired]
    return {"planned": len(tasks), "tasks": per_task,
            "primary": permutation([t["d"] for t in per_task if t["d"] is not None]),
            "secondary": secondary(paired_rows), "validity": validity(records, statuses, paired_rows),
            "usage": usage_consumed(records, paired)}


def _num(value, spec=".2f") -> str:
    return "n/a" if value is None else format(value, spec)


def _share(passed, total) -> str:
    return "n/a" if passed is None else f"{passed}/{total} ({passed / total:.2f})"


def _rate(count, n, rate) -> str:
    return "n/a" if rate is None else f"{rate:.2f} ({count}/{n})"


def _met(ok: bool, detail: str = "") -> str:
    return "met" if ok else f"not met{': ' + detail if detail else ''}"


SECONDARY = (
    ("Rounds (reached)", lambda a: f"{a['rounds']} ({a['reached']})"),
    ("Rounds passed", lambda a: str(a["passed"])),
    ("Case score (mean per-round share of cases passed)", lambda a: _num(a["case_score"])),
    ("Rounds with case counts / without", lambda a: f"{a['case_rounds']} / {a['case_missing']}"),
    ('False "done" rate (failed rounds labeled claims_complete)',
     lambda a: _rate(a["false_done"], a["labeled_failed"], a["false_done_rate"])),
    ("Under-claim rate (passed rounds labeled reports_incomplete)",
     lambda a: _rate(a["under_claim"], a["labeled_passed"], a["under_claim_rate"])),
    ("Median agent minutes per round", lambda a: _num(a["agent_minutes_median"], ".1f")),
    ("Tokens per round (mean, input + output)", lambda a: _num(a["tokens_per_round"], ",.0f")),
    ("Total tokens", lambda a: _num(a["tokens_total"], ",")),
    ("Cost reported by Claude Code (USD)", lambda a: _num(a["cost_usd_total"])),
    ("Horizon start rate (rounds reached)",
     lambda a: _rate(a["horizon_started"], a["reached"], a["horizon_start_rate"])),
    ("Horizon CLI calls", lambda a: str(a["horizon_calls"])),
    ("Rounds with more than one result record", lambda a: str(a["extra_result_records"])),
    ("Reached rounds with no result record", lambda a: str(a["no_result_record"])),
)


def render(summary: dict, deviations: str = "") -> str:
    p, sec, val = summary["primary"], summary["secondary"], summary["validity"]
    lo, hi = p["ci95"]
    start = sec["horizon"]["horizon_start_rate"]
    audit = ("not checked: the rows carry no audit flags" if val["audit"] is None
             else _met(not val["audit"], "; ".join(val["audit"])))
    lines = [
        "# EvoCode-Bench first look: Horizon v2 against plain Claude Code", "",
        f"This is a first look, not a definitive comparison: {p['n']} of {summary['planned']} planned tasks were "
        "analysed, with one attempt per arm. Every task's result is shown.", "",
        f"Setup: {config.MODEL} at effort {config.EFFORT}, Claude Code {config.CLAUDE_CODE_VERSION}, Harbor "
        f"{config.HARBOR_VERSION}, a fresh session every round. Both arms get the same time-budget paragraph; the "
        "Horizon arm also gets the Horizon v2 skill and one sentence asking it to use the skill.", "",
        "## Primary result", "",
        "Outcome: the share of a task's rounds passed (reward 1). A missing, aborted or timed-out round counts as "
        f"failed. Analysis: {ANALYSIS}, on d = Horizon - control per task.", "",
        f"- Tasks analysed: {p['n']}",
        f"- Mean d: {_num(p['mean'], '+.2f')}",
        f"- 95% interval (test inversion over shifts in steps of 0.01): [{_num(lo, '+.2f')}, {_num(hi, '+.2f')}]",
        f"- Two-sided permutation p: {_num(p['p'], '.4f')}",
        f"- Horizon won / lost / tied: {p['wins']} / {p['losses']} / {p['ties']}",
        "", "## Per-task results", "",
        "| Task | Rounds | Control | Horizon | d | Status |", "| --- | --- | --- | --- | --- | --- |",
    ]
    lines += [f"| {t['task']} | {t['rounds']} | {_share(t['passed']['control'], t['rounds'])} | "
              f"{_share(t['passed']['horizon'], t['rounds'])} | {_num(t['d'], '+.2f')} | {t['status']} |"
              for t in summary["tasks"]]
    lines += ["", "## Secondary outcomes (analysed tasks)", "", "| Outcome | Control | Horizon |", "| --- | --- | --- |"]
    lines += [f"| {name} | {cell(sec['control'])} | {cell(sec['horizon'])} |" for name, cell in SECONDARY]
    use = summary["usage"]
    lines.append("| Seven-day usage consumed (jobs summed; jobs across a reset) | " + " | ".join(
        f"{use[arm]['seven_day']:.3f} ({use[arm]['jobs']}; {use[arm]['straddled']})" for arm in config.ARMS) + " |")
    runs = "; ".join(f"{arm} {val['runs'][arm]['valid']} valid, {val['runs'][arm]['invalid']} invalid"
                     for arm in config.ARMS)
    lines += [
        "", "## Validity", "",
        f"- Main runs: {runs}",
        f"- Invalid reasons: {', '.join(f'{k} {v}' for k, v in val['invalid_reasons'].items()) or 'none'}",
        f"- Reruns: {', '.join(val['retried']) or 'none'}",
        f"- Dropped tasks: {', '.join(val['dropped']) or 'none'}",
        f"- Horizon started in at least 90% of reached Horizon rounds: "
        f"{_rate(sec['horizon']['horizon_started'], sec['horizon']['reached'], start)}, "
        f"{_met(start is not None and start >= START_FLOOR)}",
        f"- Control never invoked Horizon: {_met(not val['control_horizon'], ', '.join(val['control_horizon']))}",
        f"- No round has more than one result record: "
        f"{_met(not val['extra_result_records'], ', '.join(val['extra_result_records']))}",
        f"- No agent read /tests or /logs/verifier: {audit}",
        f"- Leftover audit (rounds audited {val['leftovers']['audited']} of {val['leftovers']['reached']} reached): "
        f"a claude process killed after {val['leftovers']['killed']}, other processes still running after "
        f"{val['leftovers']['survivors']}, files left in /tmp after {val['leftovers']['tmp']}. The listings stay in "
        "the run directory.",
        f"- Freeze: {', '.join(val['freezes']) or 'not recorded'}",
        f"- Final-message labels: the TB4 blind judge ({config.JUDGE_MODEL}) sees only the message text; "
        f"rubric {RUBRIC}.",
        "", "## Deviations", "", deviations.strip() or "None recorded.",
        "", "## Limits", "",
    ]
    lines += [f"- {limit.format(n=p['n'])}" for limit in LIMITS]
    lines += [
        "", "## Credit and license", "",
        f"EvoCode-Bench by UniPat-AI ({config.EVO_CODE_URL} at {config.EVO_CODE_COMMIT[:7]}); tasks from the Hugging "
        f"Face dataset {config.DATASET_REPO} at revision {config.DATASET_REVISION[:7]}, licensed CC-BY-NC-4.0. This "
        "report is non-commercial. It reproduces no hidden tests, per-case results, reference solutions, round "
        "instructions or transcripts.", "",
    ]
    return "\n".join(lines)


def timing(rows) -> dict:
    """Mean agent minutes per round in each arm from the dry run, and the N they allow."""
    dry = _latest([r for r in rows if r["phase"] == "dry"])
    minutes = {arm: [r["agent_sec"] / 60 for r in dry if r["arm"] == arm and r.get("agent_sec") is not None]
               for arm in config.ARMS}
    means = {arm: _mean(values) for arm, values in minutes.items()}
    n = None if None in means.values() else order.n_rule(means["control"], means["horizon"])
    return {"m_control": means["control"], "m_horizon": means["horizon"],
            "rounds": {arm: len(values) for arm, values in minutes.items()}, "n": n}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--runs", type=Path, default=config.RUNS)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("label", parents=[common], help="label main-phase final messages with the TB4 blind judge")
    report = sub.add_parser("report", parents=[common], help="render the report from main-phase rows")
    report.add_argument("--prereg", type=Path, default=config.DOCS / "prereg.json")
    report.add_argument("--out", type=Path, default=config.DOCS / "report.md")
    sub.add_parser("timing", parents=[common], help="m_control, m_horizon and the N rule from the dry run")
    args = parser.parse_args(argv)
    rows_path = args.runs / "rows.jsonl"
    if args.action == "label":
        print(label_rows(rows_path, runner.read_token(), judge_fn=judge.judge))
        return 0
    rows = read_rows(rows_path)
    if args.action == "timing":
        result = timing(rows)
        if result["n"] is None:
            result["error"] = "even N = 6 does not fit the budget: stop and report to the user before the freeze"
        print(json.dumps(result))
        return 0 if result["n"] is not None else 1
    # the planned tasks are the pre-registered ones plus the reserves the runner brought in for its drops
    dropped = evo_run.dropped_tasks(evo_run.Paths(args.runs), "main")
    tasks = evo_run.main_tasks(json.loads(args.prereg.read_text()), dropped)
    info = {t["task"]: t["rounds"] for t in dataset.list_tasks(args.runs / "dataset" / config.DATASET_REVISION / "tasks")}
    rounds_by_task = {t: info[t] for t in tasks}
    rows = [r for r in rows if r["phase"] == "main"]
    records = load_records(args.runs, "main")
    found = problems(rows, records, tasks, dropped)
    if found:
        print(json.dumps({"error": "the main phase is not final: finish runs, scoring and labels first", **found}))
        return 2
    deviations = args.runs / "deviations.md"
    summary = summarize(rows, records, tasks, rounds_by_task, dropped)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(summary, deviations.read_text() if deviations.exists() else ""))
    print(json.dumps({"primary": summary["primary"], "statuses": {t["task"]: t["status"] for t in summary["tasks"]}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
