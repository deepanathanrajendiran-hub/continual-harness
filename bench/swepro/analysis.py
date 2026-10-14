"""The pre-registered analysis and the report."""
import argparse
import json
import random
import statistics
from pathlib import Path

from bench.swepro import config, prereg, score

ALPHA = 0.05
TOL = 1e-9
GRID = tuple(k / 100 for k in range(-100, 101))
LIMITS = (
    f"One repository ({config.REPO_LABEL}) and one model (Sonnet 5.5) through Claude Code only.",
    "Plain against refined cannot separate useful lessons from any added notes; a placebo-notes arm would.",
    f"The {config.REPO_LABEL} fixes are public, so the model may have seen some of them; both arms share this.",
    "Edits were auto-approved and the daily cap lifted, which normal refine use does not do.",
    "The amd64 task images ran under Rosetta on Colima with an arm64 Claude Code; scores are not "
    "comparable with the public leaderboard.",
    "One operator ran the study.",
)


def task_scores(rows) -> tuple:
    """({task: {arm: passes / 3}} for tasks with every run, sorted list of incomplete tasks)."""
    by = {}
    for r in rows:
        by.setdefault(r["task"], {}).setdefault(r["arm"], {})[r["attempt"]] = r["score"]
    scores, incomplete = {}, []
    for task, arms in sorted(by.items()):
        if all(len(arms.get(arm, {})) == config.ATTEMPTS for arm in config.ARMS):
            scores[task] = {arm: sum(arms[arm].values()) / config.ATTEMPTS for arm in config.ARMS}
        else:
            incomplete.append(task)
    return scores, incomplete


def _p(pairs, observed: float, n: int, delta: float) -> float:
    target = abs(observed - delta * n)
    hits = sum(1 for a, b in pairs if abs(a - delta * b) >= target - TOL)
    return hits / len(pairs)


def permutation(diffs, *, draws: int = config.PERM_DRAWS, seed: int = config.PERM_SEED) -> dict:
    """Two-sided sign-flip test by Monte Carlo (the observed signs are one of the draws); 95% interval by
    inverting the test over GRID with the same draws."""
    diffs = [float(d) for d in diffs]
    n = len(diffs)
    wins, losses = sum(d > TOL for d in diffs), sum(d < -TOL for d in diffs)
    counts = {"wins": wins, "losses": losses, "ties": n - wins - losses}
    if not n:
        return {"n": 0, "mean": None, "ci95": (None, None), "p": None, "draws": draws, **counts}
    rng = random.Random(seed)
    pairs = [(sum(diffs), n)]  # with signs s: (sum s*d, sum s)
    for _ in range(draws):
        signs = [1 if rng.random() < 0.5 else -1 for _ in range(n)]
        pairs.append((sum(s * d for s, d in zip(signs, diffs)), sum(signs)))
    total = sum(diffs)
    kept = [delta for delta in GRID if _p(pairs, total, n, delta) >= ALPHA]
    return {"n": n, "mean": total / n, "ci95": (min(kept), max(kept)) if kept else (None, None),
            "p": _p(pairs, total, n, 0.0), "draws": draws, **counts}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def secondary(rows) -> dict:
    out = {}
    for arm in config.ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        out[arm] = {
            "runs": len(mine), "passes": sum(r["score"] for r in mine),
            "mean_graded_failed": _mean([r["graded_failed"] for r in mine]),
            "cost_usd": sum(r["cost_usd"] or 0 for r in mine),
            "mean_tokens": _mean([(r["tokens_in"] or 0) + (r["tokens_out"] or 0) for r in mine
                                  if r["tokens_in"] is not None]),
            "median_agent_min": statistics.median([r["agent_sec"] / 60 for r in mine if r["agent_sec"]])
            if any(r["agent_sec"] for r in mine) else None,
            "timeouts": sum(r["exception"] == "AgentTimeoutError" for r in mine),
            "nonzero_exits": sum(r["exception"] == "NonZeroAgentExitCodeError" for r in mine),
            "sandbox_regrade_disagree": sum(1 for r in mine if r["regrade_valid"]
                                            and (r["reward_sandbox"] or 0) != (r["reward_regrade"] or 0)),
            "reruns": sum(r["reruns"] for r in mine),
            "invalid_after_reruns": sum(not r["valid"] for r in mine),
        }
    return out


def validity(rows, *, probes, frozen_hash: str) -> list:
    """(check, ok, detail) for every integrity check in the spec."""
    def where(bad):
        return "; ".join(f"{r['task']} {r['arm']} a{r['attempt']}" for r in bad[:10]) or "none"

    refined = [r for r in rows if r["arm"] == "refined"]
    plain = [r for r in rows if r["arm"] == "plain"]
    checks = [
        ("Every refined run logged the frozen bundle hash", [r for r in refined if r["notes_hash"] != frozen_hash]),
        ("No plain run found notes", [r for r in plain if r["claude_dir"] or r["notes_hash"]]),
        (f"Every run reported Claude Code {config.CLAUDE_CODE_VERSION} and claude-sonnet-5-5",
         [r for r in rows if r["claude_version"] != config.CLAUDE_CODE_VERSION
          or r["model"] != config.MODEL.split("/")[-1]]),
        ("No transcript touched /tests, /solution or /logs/verifier", [r for r in rows if r["audit_tests"]]),
        ("Every run has a valid re-grade", [r for r in rows if not r["regrade_valid"]]),
    ]
    out = [(name, not bad, where(bad)) for name, bad in checks]
    failed_probes = [p for p in probes if not p.get("passed")]
    out.append((f"All {len(probes)} network probes passed", not failed_probes, f"{len(failed_probes)} failed"))
    return out


def summarize(rows, *, probes, frozen_hash: str, draws: int = config.PERM_DRAWS) -> dict:
    scores, incomplete = task_scores(rows)
    diffs = [s["refined"] - s["plain"] for s in scores.values()]
    return {"primary": permutation(diffs, draws=draws), "scores": scores, "incomplete": incomplete,
            "secondary": secondary([r for r in rows if r["task"] in scores]),
            "validity": validity(rows, probes=probes, frozen_hash=frozen_hash)}


def _f(x, spec=".2f"):
    return "n/a" if x is None else format(x, spec)


def render(summary: dict, *, practice: dict, learned: str, deviations: str) -> str:
    p, s = summary["primary"], summary["secondary"]
    lo, hi = p["ci95"]
    lines = [
        "# SWE-bench Pro: does refine make Claude Code better on new tasks?", "",
        f"Refine learned from {practice.get('runs', 'n/a')} {config.REPO_LABEL} practice tasks; its notes were "
        f"frozen; plain Claude Code and Claude Code with the frozen notes then tried each of {p['n']} unseen "
        f"{config.REPO_LABEL} tasks {config.ATTEMPTS} times. Every run was scored by re-grading its patch on a pristine image.", "",
        f"Setup: {config.MODEL} at effort {config.EFFORT}, Claude Code {config.CLAUDE_CODE_VERSION} (arm64-musl "
        f"build), Harbor {config.HARBOR_VERSION}, SWE-bench Pro v2 at {config.SCALE_COMMIT[:12]}, agent offline "
        f"except {config.ALLOW_HOST}.", "",
        "## Primary result", "",
        f"Analysis: two-sided sign-flip permutation (Monte Carlo, {p['draws']} draws, seed {config.PERM_SEED}), "
        f"alpha {ALPHA}, on d = refined - plain pass share per task.", "",
        f"- Tasks analysed: {p['n']}" + (f" (incomplete, left out: {len(summary['incomplete'])})"
                                          if summary["incomplete"] else ""),
        f"- Mean d: {_f(p['mean'], '+.3f')}",
        f"- 95% interval: [{_f(lo, '+.2f')}, {_f(hi, '+.2f')}]",
        f"- Two-sided p: {_f(p['p'], '.4f')}",
        f"- Refined won / lost / tied: {p['wins']} / {p['losses']} / {p['ties']}", "",
        "## Per-task results", "",
        "| Task | Plain | Refined | d |", "| --- | --- | --- | --- |",
        *[f"| {t} | {v['plain']:.2f} | {v['refined']:.2f} | {v['refined'] - v['plain']:+.2f} |"
          for t, v in summary["scores"].items()], "",
        "## Secondary outcomes", "",
        "| Outcome | Plain | Refined |", "| --- | --- | --- |",
        *[f"| {label} | {_f(s['plain'][key], fmt)} | {_f(s['refined'][key], fmt)} |" for label, key, fmt in (
            ("Runs", "runs", "d"), ("Passes", "passes", "d"),
            ("Graded tests failed per run (mean)", "mean_graded_failed", ".2f"),
            ("Cost reported by Claude Code (USD)", "cost_usd", ".2f"), ("Tokens per run (mean)", "mean_tokens", ",.0f"),
            ("Agent minutes per run (median)", "median_agent_min", ".1f"), ("Agent timeouts", "timeouts", "d"),
            ("Non-zero agent exits", "nonzero_exits", "d"),
            ("In-sandbox vs re-grade disagreements", "sandbox_regrade_disagree", "d"),
            ("Reruns", "reruns", "d"), ("Invalid after reruns (scored 0)", "invalid_after_reruns", "d"))], "",
        "## Practice", "",
        *[f"- {k}: {v}" for k, v in sorted(practice.items())], "",
        "## What refine learned", "", learned.strip(), "",
        "## Validity", "",
        *[f"- {name}: {'met' if ok else 'not met: ' + detail}" for name, ok, detail in summary["validity"]], "",
        "## Deviations", "", deviations.strip() or "None.", "",
        "## Limits", "", *[f"- {line}" for line in LIMITS], "",
        "## Credit", "",
        f"SWE-bench Pro by Scale AI ({config.SCALE_URL.removesuffix('.git')} at {config.SCALE_COMMIT[:12]}). "
        "This report reproduces no hidden tests, reference patches, per-test results or transcripts.", "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyse the test phase and write the report.")
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    prereg.require_freeze()
    frozen = json.loads((args.docs / "prereg.json").read_text())
    rows = score.read_rows(args.runs / "rows.jsonl")
    probes = [json.loads(p.read_text()) for p in sorted((args.runs / "probes").glob("*.json"))]
    summary = summarize(rows, probes=probes, frozen_hash=frozen["bundle"]["hash"])
    gate = json.loads((args.runs / "practice" / "gate.json").read_text())
    learned = (args.docs / "learned.md").read_text() if (args.docs / "learned.md").exists() else "Not written."
    deviations = (args.runs / "deviations.md").read_text() if (args.runs / "deviations.md").exists() else ""
    (args.docs / "report.md").write_text(render(summary, practice=gate, learned=learned, deviations=deviations))
    (args.runs / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=list) + "\n")
    print(args.docs / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
