"""The freeze: export the bundle, pin everything the test phase depends on, and check the tag later."""
import argparse
import json
import subprocess
from pathlib import Path

from bench.swepro import bundle, config, tools

DOCS_REL = config.DOCS.relative_to(config.REPO_ROOT).as_posix()
FROZEN_PATHS = ("bench/swepro", config.SPEC, f"{DOCS_REL}/split.json", f"{DOCS_REL}/prereg.json",
                f"{DOCS_REL}/prereg.md")
ANALYSIS = {
    "unit": "test task; y = passes / 3 per arm, scored by the pristine-image re-grade",
    "primary": "mean of d = y_refined - y_plain",
    "test": "two-sided sign-flip permutation, Monte Carlo",
    "draws": config.PERM_DRAWS,
    "seed": config.PERM_SEED,
    "alpha": 0.05,
    "interval": "95% by test inversion over shifts in steps of 0.01",
}


class FreezeError(RuntimeError):
    pass


class NotFrozen(RuntimeError):
    pass


def export_bundle(runs: Path = config.RUNS) -> dict:
    return bundle.export(runs / "refine" / "state", runs / "bundle")


def _read(path: Path):
    return json.loads(path.read_text())


def pins() -> dict:
    return {"scale_commit": config.SCALE_COMMIT, "replay_sha256": config.REPLAY_SHA256,
            "harbor": config.HARBOR_VERSION, "claude_code": config.CLAUDE_CODE_VERSION,
            "claude_arm_sha256": config.CLAUDE_ARM_SHA256, "model": config.MODEL, "effort": config.EFFORT,
            "max_output_tokens": config.MAX_OUTPUT_TOKENS, "allow_host": config.ALLOW_HOST,
            "attempts": config.ATTEMPTS, "excluded": list(config.EXCLUDED), "infra_reruns": config.INFRA_RERUNS,
            "probe_every": config.PROBE_EVERY}


def collect(runs: Path, docs: Path, *, versions: dict) -> dict:
    digest = bundle.verify(runs / "bundle")
    skill = bundle.manifest(runs / "refine" / "skill")
    if skill != _read(runs / "refine" / "skill" / "manifest.json"):
        raise FreezeError("the refine snapshot no longer matches its manifest")
    stored_tools = _read(runs / "tools" / "manifest.json")
    if stored_tools != {rel: tools.sha256_file(runs / "tools" / rel) for rel in stored_tools}:
        raise FreezeError("the tools no longer match tools/manifest.json")
    gate = _read(runs / "practice" / "gate.json")
    if gate.get("decision", "").startswith("stop"):
        raise FreezeError(f"the practice gate said {gate['decision']}; the test phase needs the user's decision")
    split = _read(docs / "split.json")
    return {"spec": config.SPEC, "pins": pins(), "versions": versions, "split": split,
            "bundle": {"hash": digest, "files": _read(runs / "bundle" / "manifest.json")["files"]},
            "refine_snapshot": skill, "tools": stored_tools, "gate": gate, "analysis": ANALYSIS}


def render(p: dict) -> str:
    lines = [
        "# SWE-bench Pro refine study: pre-registration", "",
        f"Spec: `{p['spec']}`", "",
        "## Pins", "",
        *[f"- {k}: `{v}`" for k, v in p["pins"].items()], "",
        "## Observed versions", "",
        *[f"- {k}: `{v}`" for k, v in p["versions"].items()], "",
        "## Tasks", "",
        f"- Practice: {len(p['split']['practice'])} tasks; test: {len(p['split']['test'])} tasks "
        f"(split seed {p['split']['seed']}); invalid: {len(p['split'].get('invalid', {}))}.",
        f"- Test order (seed {config.ORDER_SEED}): " + ", ".join(f"`{t}`" for t in p["split"]["test_order"]), "",
        "## Frozen notes", "",
        f"- Bundle hash: `{p['bundle']['hash']}`",
        *[f"  - `{rel}` `{h[:12]}`" for rel, h in sorted(p["bundle"]["files"].items())],
        f"- Refine snapshot hash: `{p['refine_snapshot']['hash']}`",
        *[f"- Tool `{rel}`: `{h}`" for rel, h in sorted(p["tools"].items())], "",
        "## Practice gate", "",
        *[f"- {k}: {v}" for k, v in sorted(p["gate"].items())], "",
        "## Analysis", "",
        *[f"- {k}: {v}" for k, v in p["analysis"].items()], "",
    ]
    return "\n".join(lines)


def write(p: dict, docs: Path = config.DOCS) -> tuple:
    docs.mkdir(parents=True, exist_ok=True)
    json_path, md_path = docs / "prereg.json", docs / "prereg.md"
    json_path.write_text(json.dumps(p, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render(p))
    return json_path, md_path


def _git(run, repo, *args):
    return run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def require_freeze(run=subprocess.run, *, repo=config.REPO_ROOT) -> str:
    """The tagged commit, if the tag exists and no frozen path changed since it (committed or not)."""
    tagged = _git(run, repo, "rev-list", "-n", "1", config.FREEZE_TAG)
    commit = (tagged.stdout or "").strip()
    if tagged.returncode != 0 or not commit:
        raise NotFrozen(f"no {config.FREEZE_TAG} tag: freeze first")
    if _git(run, repo, "diff", "--quiet", commit, "--", *FROZEN_PATHS).returncode != 0:
        raise NotFrozen(f"frozen paths changed since {config.FREEZE_TAG}")
    if (_git(run, repo, "status", "--porcelain", "--", *FROZEN_PATHS).stdout or "").strip():
        raise NotFrozen("frozen paths have uncommitted changes")
    return commit


def check_runtime(p: dict, runs: Path = config.RUNS) -> None:
    """The bundle and tools on disk are the frozen ones."""
    if bundle.verify(runs / "bundle") != p["bundle"]["hash"]:
        raise bundle.BundleError("the bundle on disk is not the frozen bundle")
    for rel, digest in p["tools"].items():
        if tools.sha256_file(runs / "tools" / rel) != digest:
            raise FreezeError(f"tool {rel} differs from the frozen one")


def observed_versions(run=subprocess.run) -> dict:
    out = {}
    for name, cmd in (("harbor", ["harbor", "--version"]), ("colima", ["colima", "version"]),
                      ("docker_server", ["docker", "version", "--format", "{{.Server.Version}}"])):
        proc = run(cmd, capture_output=True, text=True)
        out[name] = (proc.stdout or "").strip().splitlines()[0] if proc.returncode == 0 and proc.stdout else None
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the SWE-bench Pro refine study.")
    parser.add_argument("action", choices=("export-bundle", "write", "check"))
    parser.add_argument("--runs", type=Path, default=config.RUNS)
    parser.add_argument("--docs", type=Path, default=config.DOCS)
    args = parser.parse_args(argv)
    if args.action == "export-bundle":
        m = export_bundle(args.runs)
        print(f"bundle {m['hash']}: {len(m['files'])} files in {args.runs / 'bundle'}")
    elif args.action == "write":
        paths = write(collect(args.runs, args.docs, versions=observed_versions()), args.docs)
        print("\n".join(str(p) for p in paths))
    else:
        commit = require_freeze()
        check_runtime(_read(args.docs / "prereg.json"), args.runs)
        print(f"frozen at {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
