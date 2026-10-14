"""What the agent classes do to a container, as plain data so it can be tested without Harbor.

An `Upload` copies a host file or directory in; an `Exec` runs a command as root. `check=True` steps
must exit 0 or the trial fails before the agent starts.
"""
from dataclasses import dataclass
from pathlib import Path

from bench.swepro import bundle, tools

NOTES = "/opt/swepro-notes"
REFINE_MEMORY = "/root/.claude/projects/-app/memory"
REFINE_HISTORY = "/logs/agent/refine-history.json"

# From Scale's v2/tooling/locked_claude_code.py: stage everything, save the diff, unstage.
CAPTURE = (
    "mkdir -p /logs/agent; "
    "repo=$(git -C /app rev-parse --show-toplevel 2>/dev/null || git -C /testbed rev-parse --show-toplevel 2>/dev/null || echo /app); "
    'cd "$repo" && git add -A 2>/dev/null; git diff --cached > /logs/agent/model.patch 2>/dev/null; git reset -q 2>/dev/null; '
    "wc -c < /logs/agent/model.patch; true"
)

NOTES_REPORT = (
    "mkdir -p /logs/agent; "
    f"h=$(cat {NOTES}/HASH 2>/dev/null || echo); "
    "d=$(test -e /app/.claude && echo true || echo false); "
    f"n=$(ls {NOTES}/memory 2>/dev/null | wc -l | tr -d ' '); "
    'printf \'{"hash": "%s", "claude_dir": %s, "memory_files": %s}\\n\' "$h" "$d" "$n" > /logs/agent/notes.json'
)


@dataclass(frozen=True)
class Upload:
    src: Path
    dst: str
    is_dir: bool = False


@dataclass(frozen=True)
class Exec:
    command: str
    check: bool = True


def claude_steps(tools_dir: Path) -> list:
    return [
        Upload(tools_dir / tools.LOADER_REL, "/lib/ld-musl-aarch64.so.1"),
        Upload(tools_dir / tools.CLAUDE_REL, "/usr/local/bin/claude"),
        Exec("chmod 755 /lib/ld-musl-aarch64.so.1 /usr/local/bin/claude && "
             "ln -sf /lib/ld-musl-aarch64.so.1 /lib/libc.musl-aarch64.so.1 && /usr/local/bin/claude --version"),
    ]


def bundle_steps(bundle_dir: Path) -> list:
    """Install a verified bundle: notes under /app/.claude (hidden from git), memory for Harbor's memory_dir."""
    digest = bundle.verify(bundle_dir)
    steps = [Exec("test -d /app/.git && test ! -e /app/.claude && test -z \"$(git -C /app ls-files .claude)\"")]
    if (bundle_dir / ".claude").is_dir():
        steps.append(Upload(bundle_dir / ".claude", "/app/.claude", is_dir=True))
    if (bundle_dir / "memory").is_dir():
        steps += [Exec(f"mkdir -p {NOTES}"), Upload(bundle_dir / "memory", f"{NOTES}/memory", is_dir=True)]
    steps += [
        Exec("mkdir -p /app/.git/info && printf '\\n.claude/\\n' >> /app/.git/info/exclude"),
        Exec(f"mkdir -p {NOTES} && echo {digest} > {NOTES}/HASH"),
    ]
    return steps


def refine_steps(state: Path, skill: Path, inputs: Path) -> list:
    """Lay out a refine container: the notes state at /app and in memory, the snapshot skill, the inputs."""
    steps = [Exec(f"mkdir -p /app/.claude/skills {REFINE_MEMORY} /inputs")]
    if (state / "app").is_dir():
        steps.append(Upload(state / "app", "/app", is_dir=True))
    if (state / "memory").is_dir():
        steps.append(Upload(state / "memory", REFINE_MEMORY, is_dir=True))
    steps += [Upload(skill, "/app/.claude/skills/refine", is_dir=True), Upload(inputs, "/inputs", is_dir=True)]
    return steps


def refine_history_command() -> str:
    return ("python3 /app/.claude/skills/refine/scripts/harness.py --runtime claude --project /app "
            f"refine-history > {REFINE_HISTORY} 2>/logs/agent/refine-history.err; true")
