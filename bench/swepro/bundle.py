"""The notes bundle refine builds, and the frozen refine snapshot that builds it.

A refine state is a directory with two parts:
- `app/`: the project as refine sees it at /app (CLAUDE.md, .claude/skills, .claude/agents, .claude/harness);
- `memory/`: the project memory directory (~/.claude/projects/-app/memory in the refine container).

A bundle holds only the four note layers, laid out for installing into a task container:
- `.claude/CLAUDE.md` (rho; refine writes /app/CLAUDE.md, the bundle installs it under .claude/ so it
  stays out of the repo's own files), `.claude/skills/*`, `.claude/agents/*`, and `memory/*`;
- `manifest.json`: sha256 of every file and one overall `hash`.
"""
import hashlib
import json
import shutil
from pathlib import Path

NOT_EXPORTED_SKILLS = ("refine", "horizon")
MANIFEST = "manifest.json"


class BundleError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refuse_symlinks(root: Path) -> None:
    if root.exists():
        for p in root.rglob("*"):
            if p.is_symlink():
                raise BundleError(f"symlink in refine state: {p}")


def manifest(root: Path) -> dict:
    """sha256 of every file under root except manifest.json, and one hash over the sorted list."""
    found = {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*"))
             if p.is_file() and p.relative_to(root).as_posix() != MANIFEST}
    joined = "".join(f"{rel}\0{digest}\n" for rel, digest in sorted(found.items()))
    return {"files": found, "hash": hashlib.sha256(joined.encode()).hexdigest()}


def _write_manifest(root: Path) -> dict:
    m = manifest(root)
    (root / MANIFEST).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    return m


def _copy_tree(src: Path, dst: Path, skip=()) -> None:
    if not src.is_dir():
        return
    for child in sorted(src.iterdir()):
        if child.name in skip:
            continue
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(child, target)


def export(state: Path, dest: Path) -> dict:
    """Write the bundle for `state` to `dest` (replacing it) and return its manifest."""
    app = state / "app"
    _refuse_symlinks(app / ".claude")
    _refuse_symlinks(state / "memory")
    if (app / "CLAUDE.md").is_symlink():
        raise BundleError(f"symlink in refine state: {app / 'CLAUDE.md'}")
    if (app / ".claude" / "CLAUDE.md").exists():
        raise BundleError("refine state has both CLAUDE.md and .claude/CLAUDE.md")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if (app / "CLAUDE.md").is_file():
        (dest / ".claude").mkdir()
        shutil.copyfile(app / "CLAUDE.md", dest / ".claude" / "CLAUDE.md")
    _copy_tree(app / ".claude" / "skills", dest / ".claude" / "skills", skip=NOT_EXPORTED_SKILLS)
    _copy_tree(app / ".claude" / "agents", dest / ".claude" / "agents")
    _copy_tree(state / "memory", dest / "memory")
    return _write_manifest(dest)


def verify(bundle_dir: Path) -> str:
    """Return the bundle's hash if every file still matches manifest.json."""
    stored = json.loads((bundle_dir / MANIFEST).read_text())
    if manifest(bundle_dir) != stored:
        raise BundleError(f"{bundle_dir} no longer matches its manifest")
    return stored["hash"]


def snapshot_refine(skill_src: Path, harness_src: Path, dest: Path) -> dict:
    """Copy the refine skill with its CLI made self-contained: scripts/harness.py is harness/cli.py and
    every harness/*.py sits beside it (the CLI puts its own directory on sys.path)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copyfile(skill_src / "SKILL.md", dest / "SKILL.md")
    if (skill_src / "references").is_dir():
        shutil.copytree(skill_src / "references", dest / "references", symlinks=False)
    scripts = dest / "scripts"
    scripts.mkdir()
    for module in sorted(harness_src.glob("*.py")):
        shutil.copyfile(module, scripts / ("harness.py" if module.name == "cli.py" else module.name))
    return _write_manifest(dest)
