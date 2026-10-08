"""Render environment.md: the frozen record of versions, images, bundle files, and prompt digests."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from bench.tb4 import config, draw


def _out(run, cmd) -> str:
    return run(cmd, capture_output=True, text=True).stdout.strip()


def prompt_digests(prompts_dir: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(prompts_dir.glob("*.md"))}


def collect_facts(rows, bundle_manifest: dict, runs: Path, run=subprocess.run, prompts_dir=None) -> dict:
    return {
        "versions": {
            "harbor": _out(run, ["harbor", "--version"]),
            "claude (host)": _out(run, ["claude", "--version"]),
            "python (host)": sys.version.split()[0],
            "terminal-bench commit": _out(run, ["git", "-C", str(runs / "tb4"), "rev-parse", "HEAD"]),
            "repository commit": _out(run, ["git", "-C", str(config.REPO_ROOT), "rev-parse", "HEAD"]),
        },
        "docker": {
            "server": _out(run, ["docker", "version", "--format", "{{.Server.Version}}"]),
            "cpus and memory bytes": _out(run, ["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"]),
        },
        "bundle": bundle_manifest,
        "tasks": rows,
        "prompts": prompt_digests(prompts_dir or config.PROMPTS),
    }


def render(facts: dict) -> str:
    lines = ["# Environment record", "",
             "Written before the freeze. Every value here is part of the frozen protocol.", "",
             "## Versions", ""]
    lines += [f"- {k}: `{v}`" for k, v in facts["versions"].items()]
    lines += ["", "## Docker", ""] + [f"- {k}: `{v}`" for k, v in facts["docker"].items()]
    lines += ["", "## Horizon bundle", "", f"Commit `{facts['bundle']['commit']}`.", "",
              "| File | SHA-256 |", "| --- | --- |"]
    lines += [f"| `{f}` | `{d}` |" for f, d in sorted(facts["bundle"]["files"].items())]
    lines += ["", "## Tasks, images, and copies", "",
              "| Order | Task | Workdir | Agent image | Verifier image | Copy digest |",
              "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {t['order']} | {t['task']} | `{t['workdir']}` | `{t['agent_image_id']}` | "
              f"`{t['verifier_image_id']}` | `{t['copy_digest']}` |" for t in facts["tasks"]]
    lines += ["", "## Prompt files", "", "| File | SHA-256 |", "| --- | --- |"]
    lines += [f"| `{f}` | `{d}` |" for f, d in sorted(facts["prompts"].items())]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bundle-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    facts = collect_facts(draw.read_manifest(args.manifest), json.loads(args.bundle_manifest.read_text()),
                          config.RUNS)
    args.out.write_text(render(facts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
