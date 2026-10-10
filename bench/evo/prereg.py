"""Freeze the EvoCode first look: build the Horizon bundle, write the pre-registration, check the freeze tag."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from bench.evo import config, copies, dataset, validate
from bench.evo import order as evo_order
from bench.evo import run as evo_run
from bench.tb4 import bundle as tb4_bundle, copies as tb4_copies

SPEC = "docs/superpowers/specs/2026-10-09-evocode-horizon-design.md"
JUDGE_RUBRIC = "docs/evaluations/tb4-horizon-pilot/prompts/judge.md"
DOCS_REL = config.DOCS.relative_to(config.REPO_ROOT).as_posix()
PREREG_JSON = f"{DOCS_REL}/prereg.json"
PREREG_MD = f"{DOCS_REL}/prereg.md"
REPORT = f"{DOCS_REL}/report.md"
CODE_PATHS = ("bench/evo", "bench/tb4")
# What the main run, scoring, the judge and the report read: the code, the record, its rendering, the rubric, the spec.
FROZEN_PATHS = (*CODE_PATHS, PREREG_JSON, JUDGE_RUBRIC, SPEC, PREREG_MD)
# Task 7's Harbor check jobs, by job name without the attempt; the probe is recorded, not asserted.
PILOT_JOBS = ("check__dummy__oracle", "check__dummy-vtimeout__oracle", "check__dummy__control",
              "check__dummy-probe__control", "canary__dummy__horizon")
RECORDED_ONLY = ("check__dummy-probe__control",)
_ATTEMPT = re.compile(r"^(?P<job>.+)__a(?P<attempt>\d+)$")
ANALYSIS = "exact sign-flip permutation, two-sided, alpha 0.05"
OUTCOMES = {
    "primary": (
        "Per-task fraction of rounds passed: a round passes when its verifier reward is at least 1.0, and a missing, "
        "aborted or timed-out round counts as failed. Each task's difference is d = horizon - control. Reported: "
        "the mean d with a 95% interval from inverting the exact sign-flip test over shifts in steps of 0.01 "
        "within [-1, 1], the two-sided permutation p over all 2^N sign assignments, and the tasks won, lost and tied."
    ),
    "secondary": [
        "Case score: the mean per-round share of hidden test cases passed, from the pass/total counts on the "
        "verifier's CASE_SUMMARY line; rounds without counts are excluded and counted.",
        "False done rate: the share of failed rounds whose final message the TB4 blind judge labels claims_complete.",
        "Under-claim rate: the share of passed rounds whose final message the judge labels reports_incomplete.",
        "Cost: median and mean agent minutes per round; tokens and the cost Claude Code reports, which exist only for "
        "rounds with a final result, so they cover those rounds and their count is shown beside them; and "
        "subscription usage consumed. Rounds that timed out, and rounds ended by another Harbor exception, are "
        "reported per arm.",
        "Horizon start rate in Horizon rounds, Horizon calls in control rounds, and extra result records.",
    ],
    "validity": [
        "Horizon was started in at least 90% of Horizon rounds.",
        "Control never invoked Horizon.",
        "Each round has exactly one result record; any extra record is flagged.",
        "No agent read /tests or /logs/verifier.",
        "The leftover-file audit shows what survives a round.",
    ],
    "running": (
        "One attempt per arm per task; a task's two arms run back to back in its seeded arm order. An invalid run "
        "(usage limit, API error, infrastructure failure, host sleep or interruption) is rerun once; a second "
        "invalid run drops the task, logged in deviations.md. After the freeze a task is replaced only for an "
        "infrastructure failure, never because of its results: a main task dropped for an infrastructure failure "
        "is replaced by the next unused reserve in order; with no reserve left a drop stays a drop."
    ),
}

# The user's decisions before the freeze, one sentence each; prereg.json and prereg.md both carry them.
DECISIONS = (
    "Task copies add python3 to the image for both arms when the image lacks it, so the Horizon CLI can run "
    "(user decision, 2026-10-09; tasks theme_d10_w4 and theme_d1_w11 had no python3).",
    "The ARM patcher leaves the x86_64/amd64 arms of an architecture case statement in a RUN instruction "
    "unchanged when the same statement also has an aarch64/arm64 arm, and patches the rest of the statement as "
    "usual (user decision, 2026-10-09; task theme_d12_w1).",
    "theme_d5_w9 was swapped out at validation: its oracle passes only round 1, and the same happens without the "
    "round hooks, so the failure is the task's, not the runner's (diagnosed 2026-10-09).",
    "The runner keeps TB4's usage pacing rates (0.098 five-hour and 0.0127 seven-day utilization per "
    "agent-hour), although the timing dry run measured about 0.15 to 0.19 five-hour utilization per agent-hour "
    "while other work shared the account; a job that hits a usage limit is invalid and is rerun, never scored "
    "(user decision, 2026-10-10).",
)


class FreezeError(RuntimeError):
    """The inputs do not support a freeze: fix them before the freeze, or stop and ask the user."""


class BundleMismatch(FreezeError):
    """RUNS/bundle differs from the bundle built at BUNDLE_COMMIT."""


class NotFrozen(RuntimeError):
    """Main-phase runs need the evo-prereg tag in HEAD and the frozen paths unchanged since it."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def tree_files(root: Path) -> dict:
    """{relative path: sha256} for every file under root; a symlink is listed as 'symlink'."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[rel] = "symlink"
        elif path.is_file():
            found[rel] = sha256_file(path)
    return found


def _write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _read_json(path: Path, what: str):
    if not path.is_file():
        raise FreezeError(f"missing {path}: {what}")
    return json.loads(path.read_text())


def build_bundle(runs=config.RUNS, *, build=tb4_bundle.build) -> dict:
    """Build RUNS/bundle at BUNDLE_COMMIT, or verify the one already there; write RUNS/bundle-manifest.json."""
    runs = Path(runs)
    runs.mkdir(parents=True, exist_ok=True)
    out = runs / "bundle"
    if out.exists() and any(out.iterdir()):
        with tempfile.TemporaryDirectory() as tmp:
            files = build(config.REPO_ROOT, config.BUNDLE_COMMIT, Path(tmp) / "bundle", modules=config.BUNDLE_MODULES)
        found = tree_files(out)
        differ = sorted(k for k in set(found) | set(files) if found.get(k) != files.get(k))
        if differ:
            raise BundleMismatch(f"{out} differs from commit {config.BUNDLE_COMMIT[:7]} in {differ}")
    else:
        files = build(config.REPO_ROOT, config.BUNDLE_COMMIT, out, modules=config.BUNDLE_MODULES)
    manifest = {"commit": config.BUNDLE_COMMIT, "modules": list(config.BUNDLE_MODULES), "files": files}
    _write_text(runs / "bundle-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def n_from_timing(dry_timing: dict) -> int:
    """N from the dry run's minutes per round, by the pre-registered N rule."""
    m_control, m_horizon = dry_timing.get("m_control"), dry_timing.get("m_horizon")
    if m_control is None or m_horizon is None:
        raise FreezeError(f"the dry run gave no minutes per round for an arm: {dry_timing}")
    n = evo_order.n_rule(m_control, m_horizon)
    if n is None:
        raise FreezeError(f"even N = 6 does not fit the budget (m_control {m_control:.1f}, m_horizon "
                          f"{m_horizon:.1f}): stop and report to the user before the freeze")
    return n


def validation_holds(record: dict, rounds: int) -> bool:
    """Task 6's rule (validate.failures), re-applied to the saved per-round rewards, plus arch and round count."""
    lists = [record.get(kind) or [] for kind in ("oracle", "nop", "planted")]
    if record.get("arch") != "arm64" or record.get("rounds") != rounds or any(len(x) != rounds for x in lists):
        return False
    return not validate.failures(record)


def select_tasks(n: int, order_list, validations: dict, task_infos: dict) -> tuple:
    """The first n tasks of the order whose validation is ok, and the tasks passed over, with their reasons."""
    selected, replaced = [], []
    for task in order_list:
        if len(selected) == n:
            break
        record = validations.get(task)
        if record is None:
            raise FreezeError(f"{task} has no validation record; validate in order before the freeze")
        if record.get("ok") is not True:
            replaced.append({"task": task, "reason": record.get("reason")})
            continue
        if not validation_holds(record, task_infos[task]["rounds"]):
            raise FreezeError(f"{task}: its validation record says ok, but its rewards or arch break the rule")
        if record.get("code") != validate.CODE_DIGEST:
            raise FreezeError(f"{task}: validated by other copy code; rerun python3 -m bench.evo.validate --n 10")
        selected.append(task)
    if len(selected) < n:
        raise FreezeError(f"N = {n} needs {n} validated tasks; the order has {len(selected)}")
    return selected, replaced


def public_reason(reason):
    """A validation reason as the committed record states it. RUNS/validation/<task>.json keeps the full text.
    A copy or build failure keeps only what failed: its text can hold a docker command line with the absolute RUNS
    path, or the path of a file under the task's tests/. That covers every `... copy failed:` reason, the planted
    copy's included. Any other reason loses the host's RUNS and home paths."""
    if not isinstance(reason, str):
        return reason
    head = reason.split(":", 1)[0]
    if head.endswith("copy failed") or reason.startswith("build failed"):
        return head
    return reason.replace(str(config.RUNS), "$RUNS").replace(str(Path.home()), "~")


def reserve_tasks(order_list, tasks, validations: dict, task_infos: dict) -> list:
    """The pre-registered replacements: every task after the Nth selected one whose validation record passes the
    checks the selected tasks pass (ok, the saved rewards, the copy code digest, one agent timeout for all rounds).
    A task without a record, or failing a check, is skipped, never an error."""
    order_list = list(order_list)
    reserve = []
    for task in order_list[order_list.index(tasks[-1]) + 1:]:
        record = validations.get(task)
        if (record is not None and record.get("ok") is True
                and validation_holds(record, task_infos[task]["rounds"])
                and record.get("code") == validate.CODE_DIGEST
                and task_infos[task].get("uniform_agent_timeout") is not False):
            reserve.append(task)
    return reserve


def check_order(order: dict) -> None:
    seeded = evo_order.seeded_order(config.POOL, config.SEED, config.DOMAINS)
    if order.get("seed") != config.SEED or order.get("order") != seeded:
        raise FreezeError("order.json is not the seeded order of the pool; write it with python3 -m bench.evo.order")
    arm_orders = order.get("arm_orders") or {}
    for task in seeded:
        if list(arm_orders.get(task) or []) != list(evo_order.arm_order(task, config.SEED)):
            raise FreezeError(f"order.json has the wrong arm order for {task}")


def check_inputs(pin: dict, bundle: dict, observed: dict, pilot: dict) -> None:
    if pin.get("revision") != config.DATASET_REVISION or len(pin.get("sha256") or "") != 64 \
            or pin.get("sha256") != pin.get("lfs_oid"):
        raise FreezeError(f"PIN.json does not pin revision {config.DATASET_REVISION} to its LFS oid: {pin}")
    if bundle.get("commit") != config.BUNDLE_COMMIT or bundle.get("modules") != list(config.BUNDLE_MODULES) \
            or "horizon/scripts/reviewing.py" not in (bundle.get("files") or {}):
        raise FreezeError(f"the bundle is not the v2 bundle at {config.BUNDLE_COMMIT[:7]}")
    if observed.get("harbor") != config.HARBOR_VERSION:
        raise FreezeError(f"harbor --version printed {observed.get('harbor')!r}, not {config.HARBOR_VERSION}")
    missing = [job for job in PILOT_JOBS if job not in pilot]
    if missing:
        raise FreezeError(f"Harbor check results missing: {missing}; run Task 7's checks first")
    failed = [f"{pilot[job]['job_name']}: {pilot[job]['failures']}" for job in PILOT_JOBS
              if job not in RECORDED_ONLY and pilot[job].get("ok") is not True]
    if failed:
        raise FreezeError(f"the latest attempt of a Harbor check failed: {failed}")
    # a probe is recorded, not asserted, but what it records must have been read: no trial, or a process list that
    # is missing or lacks the container's PID-1 line, is a failed probe
    probes = [f"{pilot[job]['job_name']}: {pilot[job]['failures']}" for job in RECORDED_ONLY
              if pilot[job].get("ok") is False or pilot[job].get("failures")]
    if probes:
        raise FreezeError(f"the latest attempt of the timeout probe failed: {probes}; rerun the probe with the next "
                          "--attempt")


def prompt_file_digest(arm: str, minutes: int, *, write=copies.write_prompt) -> str:
    """sha256 of the prompt file copies.write_prompt makes, written in a scratch directory."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(write(Path(tmp) / "prompt.md", arm, minutes)).read_bytes()
    if data.decode().strip() != config.prompt_text(arm, minutes):
        raise FreezeError(f"write_prompt({arm!r}, {minutes}) does not write the configured text")
    return sha256_bytes(data)


def prompt_facts(minutes_used) -> dict:
    keys = [(arm, m) for m in sorted(set(minutes_used)) for arm in config.ARMS]
    texts = {f"{arm}@{m}": config.prompt_text(arm, m) for arm, m in keys}
    return {"texts": texts,
            "text_sha256": {key: sha256_bytes(text.encode()) for key, text in texts.items()},
            "file_sha256": {f"{arm}@{m}": prompt_file_digest(arm, m) for arm, m in keys}}


def versions() -> dict:
    return {"harbor": config.HARBOR_VERSION, "claude_code": config.CLAUDE_CODE_VERSION, "model": config.MODEL,
            "effort": config.EFFORT, "max_output_tokens": config.MAX_OUTPUT_TOKENS,
            "agent_timeout_multiplier": config.AGENT_TIMEOUT_MULTIPLIER,
            "agent_setup_timeout_multiplier": config.AGENT_SETUP_TIMEOUT_MULTIPLIER,
            "disable_web_search": True, "resume_trajectory": False,
            "weekly_ceiling": config.WEEKLY_CEILING, "five_hour_ceiling": config.FIVE_HOUR_CEILING,
            "probe_model": config.PROBE_MODEL, "judge_model": config.JUDGE_MODEL}


def collect(n, order, validations, dry_timing, *, task_infos, bundle, pin, observed, code, pilot) -> dict:
    """The pre-registration: everything the main run and the analysis are held to."""
    check_order(order)
    missing = [t for t in order["order"] if t not in task_infos]
    if missing:
        raise FreezeError(f"the dataset has no task.toml for {missing}")
    if n != n_from_timing(dry_timing):
        raise FreezeError(f"N = {n}, but the N rule gives {n_from_timing(dry_timing)}")
    check_inputs(pin, bundle, observed, pilot)
    tasks, replaced = select_tasks(n, order["order"], validations, task_infos)
    replaced = [{**item, "reason": public_reason(item["reason"])} for item in replaced]
    mixed = [t for t in tasks if task_infos[t].get("uniform_agent_timeout") is False]
    if mixed:
        raise FreezeError(f"rounds of {mixed} have different agent timeouts, so one M per task is wrong: "
                          "stop and ask the user")
    reserve = reserve_tasks(order["order"], tasks, validations, task_infos)
    details = {}
    for task in tasks + reserve:
        info, record = task_infos[task], validations[task]
        details[task] = {"order": order["order"].index(task) + 1, "rounds": info["rounds"],
                         "minutes": dataset.minutes(info), "agent_timeout_sec": info["agent_timeout_sec"],
                         "verifier_timeout_sec": info["verifier_timeout_sec"],
                         "arm_order": list(order["arm_orders"][task]), "image_tag": config.image_tag(task),
                         "image_id": record["image_id"], "copy_digest": record["copy_digest"]}
    return {
        "study": "EvoCode-Bench first look: Horizon v2 against plain Claude Code",
        "spec": {"path": SPEC, "sha256": sha256_file(config.REPO_ROOT / SPEC)},
        "freeze_tag": config.FREEZE_TAG,
        "n": n,
        "n_rule": {"choices": list(config.N_CHOICES), "rounds_per_task_plan": config.ROUNDS_PER_TASK_PLAN,
                   "budget_agent_hours": config.BUDGET_AGENT_HOURS, "m_control": dry_timing["m_control"],
                   "m_horizon": dry_timing["m_horizon"], "dry_rounds": dry_timing.get("rounds"),
                   "dry_task": config.WALKTHROUGH, "n": n},
        "tasks": tasks,
        "replaced": replaced,
        "reserve": reserve,
        "decisions": list(DECISIONS),
        "task_details": details,
        "arms": list(config.ARMS),
        "arm_orders": {t: list(order["arm_orders"][t]) for t in tasks},
        "draw": {"seed": config.SEED, "domains": list(config.DOMAINS), "pool": list(config.POOL),
                 "excluded_prefix": config.EXCLUDED_PREFIX, "walkthrough": config.WALKTHROUGH,
                 "algorithm": order.get("algorithm"), "order": list(order["order"])},
        "prompts": prompt_facts(d["minutes"] for d in details.values()),
        "bundle": bundle,
        "versions": versions(),
        "observed": observed,
        "dataset": {"repo": config.DATASET_REPO, "revision": config.DATASET_REVISION,
                    "archive": config.ARCHIVE_PATH, "pin": pin},
        "evocode_code": {"url": config.EVO_CODE_URL, "commit": config.EVO_CODE_COMMIT},
        "judge": {"model": config.JUDGE_MODEL, "rubric": JUDGE_RUBRIC,
                  "sha256": sha256_file(config.REPO_ROOT / JUDGE_RUBRIC)},
        "analysis": ANALYSIS,
        "outcomes": OUTCOMES,
        "pilot": pilot,
        "code": code,
    }


def _table(header, rows) -> list:
    return ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |",
            *("| " + " | ".join(str(c) for c in row) + " |" for row in rows)]


def _task_table(p: dict, tasks) -> list:
    details = p["task_details"]
    return _table(["#", "Task", "Rounds", "Minutes", "Arm order", "Image ID", "Agent copy digest"],
                  [(details[t]["order"], f"`{t}`", details[t]["rounds"], details[t]["minutes"],
                    " then ".join(details[t]["arm_order"]), f"`{details[t]['image_id']}`",
                    f"`{details[t]['copy_digest']}`") for t in tasks])


def render(p: dict) -> str:
    """prereg.md: the human-readable form of prereg.json."""
    rule = p["n_rule"]
    lines = [
        "# EvoCode-Bench first look: pre-registration", "",
        f"Frozen at Git tag `{p['freeze_tag']}`. Design: [spec](../../superpowers/specs/{Path(p['spec']['path']).name}) "
        f"(sha256 `{p['spec']['sha256']}`). Every value here is also in [prereg.json](prereg.json). After the tag, "
        "every change goes to `deviations.md` with its date, its reason and the runs it affects.", "",
        "## Question", "",
        "On EvoCode-Bench's multi-round coding tasks, does Claude Code with Horizon v2 pass more rounds than plain "
        "Claude Code?", "",
        f"## Tasks (N = {p['n']})", "",
        f"The pool is {len(p['draw']['pool'])} tasks; the walkthrough pair `{p['draw']['excluded_prefix']}*` is "
        f"excluded. Seed {p['draw']['seed']} orders the pool by a round-robin over the domains "
        f"{', '.join(p['draw']['domains'])}. The measured tasks are the first N in that order that passed "
        "validation (arm64 build; oracle and planted-ledger oracle reward 1 on every round; nop reward below 1 on "
        "round 1 and on every later round it reached, since a step's min_reward may stop the nop chain early).", "",
        *_task_table(p, p["tasks"]),
        "",
    ]
    if p["replaced"]:
        lines += ["Passed over because they failed validation:", ""]
        lines += [f"- `{r['task']}`: {r['reason']}" for r in p["replaced"]]
    else:
        lines += ["None of the tasks before them failed validation."]
    reserve = p.get("reserve") or []
    lines += ["", "### Reserve", "",
              "Pre-registered replacements, used as the Running section says: the tasks after the Nth measured "
              "task in the order whose validation passes the same checks.", ""]
    lines += (_task_table(p, reserve) if reserve
              else ["No reserve: validation stopped at the Nth passing task, or no later task passed it."])
    lines += ["", "## Decisions made before the freeze", ""] + [f"- {x}" for x in p["decisions"]]
    lines += [
        "", "## N rule", "",
        f"The timing dry run on `{rule['dry_task']}` gave m_control = {rule['m_control']:.2f} and m_horizon = "
        f"{rule['m_horizon']:.2f} agent minutes per round. N is the largest of {rule['choices']} with "
        f"N x {rule['rounds_per_task_plan']} x (m_control + m_horizon) / 60 <= {rule['budget_agent_hours']} "
        f"agent-hours: N = {p['n']}.", "",
        "## Arms and prompts", "",
        f"Both arms: {p['versions']['model']} at effort {p['versions']['effort']}, Claude Code "
        f"{p['versions']['claude_code']}, Harbor {p['versions']['harbor']}, a fresh session every round, the same "
        "patched images and task copies. Control appends the shared paragraph to every round; Horizon also installs "
        f"the Horizon v2 bundle and appends the Horizon sentence. M is 30, or 60 for 3,600-s tasks.", "",
    ]
    for key, text in p["prompts"]["texts"].items():
        lines += [f"**{key}** (text sha256 `{p['prompts']['text_sha256'][key]}`, file sha256 "
                  f"`{p['prompts']['file_sha256'][key]}`)", ""]
        lines += [f"> {line}" if line else ">" for line in text.split("\n")] + [""]
    lines += ["## Analysis", "", OUTCOMES["primary"], "", f"Test: {p['analysis']}.", "",
              "## Running", "", OUTCOMES["running"], "",
              "## Secondary outcomes", ""] + [f"- {x}" for x in p["outcomes"]["secondary"]]
    lines += ["", "## Validity checks", ""] + [f"- {x}" for x in p["outcomes"]["validity"]]
    lines += ["", "## Settings and versions", "",
              *_table(["Setting", "Value"], [(k, f"`{v}`") for k, v in p["versions"].items()]), "",
              *_table(["Observed on the host", "Value"], [(k, f"`{v}`") for k, v in p["observed"].items()]), "",
              "## Horizon bundle", "",
              f"Commit `{p['bundle']['commit']}`, modules {', '.join(p['bundle']['modules'])}.", "",
              *_table(["File", "SHA-256"], [(f"`{f}`", f"`{d}`") for f, d in sorted(p["bundle"]["files"].items())]),
              "", "## Dataset", "",
              f"`{p['dataset']['repo']}` at revision `{p['dataset']['revision']}`, archive "
              f"`{p['dataset']['archive']}`, sha256 `{p['dataset']['pin']['sha256']}` (equal to its LFS oid). "
              f"EvoCode code reference: {p['evocode_code']['url']} at `{p['evocode_code']['commit']}`.", "",
              "## Judge", "",
              f"`{p['judge']['model']}` with the TB4 rubric `{p['judge']['rubric']}` (sha256 `{p['judge']['sha256']}`), "
              "blind to task and arm.", "",
              "## Pilot checks", ""]
    verdict = {True: "passed", False: "failed", None: "recorded only"}
    lines += ["The latest attempt of each Harbor behaviour check (Task 7), with the digest of its findings.json.", "",
              *_table(["Job", "Result", "Failures", "findings.json sha256"],
                      [(f"`{c['job_name']}`", verdict[c["ok"]], len(c["failures"]), f"`{c['sha256']}`")
                       for _, c in sorted(p["pilot"].items())]), ""]
    for _, check in sorted(p["pilot"].items()):
        if "recorded" in check:
            lines += [f"Recorded by `{check['job_name']}`:", "", "```json",
                      json.dumps(check["recorded"], indent=2, sort_keys=True), "```", ""]
    lines += ["## Code", "",
              f"{len(p['code'])} tracked files under `bench/evo` and `bench/tb4`; their sha256 digests are in "
              "prereg.json. `python3 -m bench.evo.prereg check` refuses main-phase runs once they change."]
    return "\n".join(lines) + "\n"


def write(prereg: dict, docs_dir=config.DOCS) -> tuple:
    """Write prereg.json and prereg.md; return their paths. The markdown renders the stored JSON, not the dict
    that was passed: sorting the keys reorders some tables, and the freeze pin renders the stored record again."""
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = docs_dir / "prereg.json", docs_dir / "prereg.md"
    text = json.dumps(prereg, indent=2, sort_keys=True) + "\n"
    _write_text(json_path, text)
    _write_text(md_path, render(json.loads(text)))
    return json_path, md_path


def observed_versions(run=subprocess.run) -> dict:
    def out(*cmd) -> str:
        try:
            return run(list(cmd), capture_output=True, text=True).stdout.strip()
        except OSError as error:
            return f"unavailable: {error}"

    return {"harbor": out("harbor", "--version"), "claude (host)": out("claude", "--version"),
            "docker server": out("docker", "version", "--format", "{{.Server.Version}}"),
            "docker arch": out("docker", "info", "--format", "{{.Architecture}}"),
            "python (host)": sys.version.split()[0]}


def code_digests(repo=config.REPO_ROOT, run=subprocess.run) -> dict:
    """sha256 of every tracked file under bench/evo and bench/tb4; refuses uncommitted or untracked changes."""
    def git(*args) -> str:
        return run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout

    dirty = git("status", "--porcelain", "--untracked-files=all", "--", *CODE_PATHS).strip()
    if dirty:
        raise FreezeError(f"commit the code before the freeze:\n{dirty}")
    names = [name for name in git("ls-files", "-z", "--", *CODE_PATHS).split("\0") if name]
    return {name: sha256_file(Path(repo) / name) for name in sorted(names)}


def read_pilot(checks_dir: Path) -> dict:
    """The latest attempt of every Harbor check job: verdict, failures, probe record and findings digest."""
    latest = {}
    for path in sorted(Path(checks_dir).glob("*/findings.json")):
        data = json.loads(path.read_text())
        match = _ATTEMPT.match(str(data.get("job_name") or ""))
        if not match:
            continue
        job, attempt = match["job"], int(match["attempt"])
        if job in latest and latest[job]["attempt"] > attempt:
            continue
        latest[job] = {"job_name": data["job_name"], "attempt": attempt, "ok": data.get("ok"),
                       "failures": data.get("failures") or [], "sha256": sha256_file(path)}
        if "recorded" in data:
            latest[job]["recorded"] = data["recorded"]
    return latest


def collect_from_runs(runs=config.RUNS) -> dict:
    """Read every input from the run directory, then collect."""
    runs = Path(runs)
    base = runs / "dataset" / config.DATASET_REVISION
    order = _read_json(runs / "order.json", "write the order first")
    timing = _read_json(runs / "timing.json", "save the dry run's analysis timing output there first")
    pin = _read_json(base / "PIN.json", "fetch the dataset first")
    task_infos = {info["task"]: info for info in dataset.list_tasks(base / "tasks")}
    validations = {}
    for task in order.get("order") or []:
        path = runs / "validation" / f"{task}.json"
        if path.is_file():
            validations[task] = json.loads(path.read_text())
    return collect(n_from_timing(timing), order, validations, timing, task_infos=task_infos,
                   bundle=build_bundle(runs), pin=pin, observed=observed_versions(), code=code_digests(),
                   pilot=read_pilot(runs / "checks"))


def frozen_commit(run=subprocess.run, repo=config.REPO_ROOT):
    """The commit the evo-prereg tag points at, or None."""
    proc = run(["git", "-C", str(repo), "rev-parse", "-q", "--verify", f"refs/tags/{config.FREEZE_TAG}^{{commit}}"],
               capture_output=True, text=True)
    commit = (proc.stdout or "").strip()
    return commit if proc.returncode == 0 and commit else None


def require_freeze(run=subprocess.run, *, repo=config.REPO_ROOT) -> str:
    """Return the freeze commit; HEAD may move past it only with the frozen paths unchanged."""
    def git(*args):
        return run(["git", "-C", str(repo), *args], capture_output=True, text=True)

    tag = frozen_commit(run, repo)
    if tag is None:
        raise NotFrozen(f"tag {config.FREEZE_TAG} is missing")
    if git("cat-file", "-e", f"{tag}:{PREREG_JSON}").returncode != 0:
        raise NotFrozen(f"{config.FREEZE_TAG} has no {PREREG_JSON}")
    if git("merge-base", "--is-ancestor", tag, "HEAD").returncode != 0:
        raise NotFrozen(f"HEAD does not contain {config.FREEZE_TAG}")
    if git("diff", "--quiet", tag, "HEAD", "--", *FROZEN_PATHS).returncode != 0:
        raise NotFrozen(f"frozen paths changed since {config.FREEZE_TAG}: {', '.join(FROZEN_PATHS)}")
    dirty = (git("status", "--porcelain", "--untracked-files=all", "--", *FROZEN_PATHS).stdout or "").strip()
    if dirty:
        raise NotFrozen(f"uncommitted changes in frozen paths:\n{dirty}")
    if git("ls-files", "--error-unmatch", "--", REPORT).returncode == 0:
        raise NotFrozen(f"{REPORT} is committed: the main run is closed")
    return tag


def require_frozen_record(path, run=subprocess.run, *, repo=config.REPO_ROOT) -> dict:
    """The parsed prereg.json at the freeze tag, once `path` holds exactly its bytes. A main run, the judge and the
    report plan from this record; a prereg file that is not the frozen one would change the task list unnoticed."""
    tag = frozen_commit(run, repo)
    if tag is None:
        raise NotFrozen(f"tag {config.FREEZE_TAG} is missing")
    proc = run(["git", "-C", str(repo), "show", f"{tag}:{PREREG_JSON}"], capture_output=True)
    if proc.returncode != 0:
        raise NotFrozen(f"{config.FREEZE_TAG} has no {PREREG_JSON}")
    try:
        found = Path(path).read_bytes()
    except OSError as error:
        raise NotFrozen(f"cannot read {path}: {error}") from error
    if found != proc.stdout:
        raise NotFrozen(f"{path} differs from {PREREG_JSON} at {config.FREEZE_TAG}")
    return json.loads(proc.stdout)


def verify_runs(prereg: dict, runs, tasks) -> None:
    """Before a main run, hold RUNS to the record: the Horizon bundle, every prompt file that exists and every agent
    copy for the tasks in play must be what prereg.json pins. A missing prompt file is skipped, since run.prepare
    writes it again from the pinned text; a missing agent copy is refused, since validation wrote it and prepare
    would build an unpinned one. Raises NotFrozen naming the first mismatch."""
    runs = Path(runs)
    try:
        built = build_bundle(runs)
    except BundleMismatch as error:
        raise NotFrozen(str(error)) from error
    if built != prereg["bundle"]:
        pinned = prereg["bundle"].get("files") or {}
        differ = sorted(k for k in set(built["files"]) | set(pinned) if built["files"].get(k) != pinned.get(k))
        raise NotFrozen(f"{runs / 'bundle'} is not the bundle prereg.json pins; it differs in "
                        f"{differ or 'its commit or modules'}")
    paths = evo_run.Paths(runs)
    for task in tasks:
        details = (prereg.get("task_details") or {}).get(task)
        if details is None:
            raise NotFrozen(f"{task} is not pre-registered in prereg.json")
        for arm in config.ARMS:
            prompt, key = paths.prompt(task, arm), f"{arm}@{details['minutes']}"
            if prompt.is_file() and sha256_file(prompt) != prereg["prompts"]["file_sha256"].get(key):
                raise NotFrozen(f"{prompt} differs from the {key} prompt file prereg.json pins")
        copy = paths.copy(task)
        if not copy.exists():
            raise NotFrozen(f"{copy}: the agent copy prereg.json pins for {task} is missing")
        if tb4_copies.tree_digest(copy) != details["copy_digest"]:
            raise NotFrozen(f"{copy} differs from the agent copy prereg.json pins for {task}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bundle", "write", "check"))
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            print(json.dumps({"frozen": require_freeze()}))
        elif args.action == "bundle":
            manifest = build_bundle(args.runs)
            print(json.dumps({"commit": manifest["commit"], "files": len(manifest["files"]),
                              "skill": str(args.runs / "bundle" / "horizon")}))
        else:
            tag = frozen_commit()
            if tag:
                raise FreezeError(f"already frozen at {tag}; record any change in deviations.md")
            prereg = collect_from_runs(args.runs)
            json_path, md_path = write(prereg, args.docs)
            print(json.dumps({"n": prereg["n"], "tasks": prereg["tasks"], "replaced": prereg["replaced"],
                              "reserve": prereg["reserve"], "json": str(json_path), "md": str(md_path)}))
    except (FreezeError, NotFrozen) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
