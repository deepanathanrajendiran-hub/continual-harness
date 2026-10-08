"""Build the self-contained Horizon skill bundle from a fixed commit (spec: Horizon bundle)."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bench.tb4 import config

MODULES = ("filelock", "gate", "goal", "paths", "refine_log", "steps", "task_state", "tree_hash")
LAYOUT = {
    "horizon/SKILL.md": ".claude/skills/horizon/SKILL.md",
    "horizon/scripts/harness.py": "harness/cli.py",
    "horizon/references/commands.md": "docs/harness-cli.md",
    **{f"horizon/scripts/{m}.py": f"harness/{m}.py" for m in MODULES},
}


def _git_show(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"],
                          check=True, capture_output=True).stdout


def build(repo: Path, commit: str, out_root: Path) -> dict:
    """Write LAYOUT from the Git object store; return {bundle path: sha256}."""
    if out_root.exists() and any(out_root.iterdir()):
        raise FileExistsError(f"{out_root} is not empty")
    manifest = {}
    for rel, src in sorted(LAYOUT.items()):
        data = _git_show(repo, commit, src)
        dest = out_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest[rel] = hashlib.sha256(data).hexdigest()
    links = [p for p in out_root.rglob("*") if p.is_symlink()]
    if links:
        raise RuntimeError(f"bundle contains symlinks: {links}")
    return manifest


def representative_ledger(skill_dir: Path, out_dir: Path) -> str:
    """Run the bundle once in a scratch project and copy its .claude/harness to out_dir."""
    with tempfile.TemporaryDirectory() as tmp:
        project, home = Path(tmp) / "project", Path(tmp) / "home"
        project.mkdir()
        home.mkdir()
        cli = [sys.executable, str(skill_dir / "scripts" / "harness.py"),
               "--runtime", "claude", "--project", str(project)]
        env = {**os.environ, "HOME": str(home)}
        start = subprocess.run(
            [*cli, "start", "Representative ledger", "--gate", "true",
             "--review", "The output matches the task requirements.",
             "--max-turns", "200", "--max-minutes", "100"],
            capture_output=True, text=True, env=env, check=True)
        slug = json.loads(start.stdout)["slug"]
        subprocess.run([*cli, "check", slug, "--did", "planted for reference check 3",
                        "--next", "independent review"],
                       capture_output=True, text=True, env=env, check=True)
        shutil.copytree(project / ".claude" / "harness", out_dir)
    return slug


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args(argv)
    files = build(config.REPO_ROOT, config.BUNDLE_COMMIT, args.out)
    args.manifest.write_text(json.dumps({"commit": config.BUNDLE_COMMIT, "files": files}, indent=2) + "\n")
    report = {"skill": str(args.out / "horizon"), "files": len(files)}
    if args.ledger:
        report["ledger_slug"] = representative_ledger(args.out / "horizon", args.ledger)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
