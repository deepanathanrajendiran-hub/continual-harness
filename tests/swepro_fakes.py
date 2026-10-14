"""A fake `run` for subprocess calls the swepro runner makes: docker, and harbor jobs of every phase."""
import json
import subprocess
from pathlib import Path

from bench.swepro import config


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class FakeHarbor:
    """`reward(phase, task, arm, attempt) -> float | str` decides each job: a float is the reward, a str is
    the Harbor exception type. Every call is recorded in `calls` (job names, or the docker argv)."""

    def __init__(self, runs: Path, reward=None, cost=0.5, entries=("e1",)):
        self.runs, self.cost, self.entries = runs, cost, list(entries)
        self.reward = reward or (lambda phase, task, arm, attempt: 1.0)
        self.calls = []
        self.kwargs = {}

    def __call__(self, cmd, **kw):
        if cmd[0] == "docker":
            self.calls.append(tuple(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        name = cmd[cmd.index("--job-name") + 1]
        self.calls.append(name)
        args = dict(cmd[i + 1].split("=", 1) for i, a in enumerate(cmd) if a == "--ak")
        self.kwargs[name] = args
        phase, task, arm, attempt = config.parse_job_name(name.split("-rerun")[0])
        value = self.reward(phase, task, arm, attempt)
        exc = value if isinstance(value, str) else None
        trial = self.runs / "jobs" / name / "trial__x"
        write(trial / "result.json", json.dumps({
            "task_name": f"swebench-pro/{task}", "exception_info": {"exception_type": exc} if exc else None,
            "verifier_result": None if exc else {"rewards": {"reward": value}},
            "agent_execution": {"started_at": "2026-10-14T00:00:00Z", "finished_at": "2026-10-14T00:01:00Z"}}))
        events = [{"type": "system", "subtype": "init", "claude_code_version": config.CLAUDE_CODE_VERSION,
                   "model": "claude-sonnet-5-5"},
                  {"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "Skill", "input": {"skill": "refine"}}]}},
                  {"type": "result", "is_error": False, "total_cost_usd": self.cost,
                   "modelUsage": {"m": {"inputTokens": 100, "outputTokens": 10}}}]
        write(trial / "agent" / "claude-code.txt", "".join(json.dumps(e) + "\n" for e in events))
        write(trial / "agent" / "sessions" / "projects" / "-app" / "s.jsonl", '{"session": 1}\n')
        bundle = args.get("bundle_dir")
        notes_hash = json.loads((Path(bundle) / "manifest.json").read_text())["hash"] if bundle else ""
        write(trial / "agent" / "notes.json", json.dumps({"hash": notes_hash, "claude_dir": bool(bundle),
                                                          "memory_files": 0}))
        write(trial / "agent" / "model.patch", "diff --git a/x b/x\n")
        if not exc:
            write(trial / "verifier" / "reward.txt", f"{int(value)}\n")
            write(trial / "verifier" / "output.json", json.dumps({"tests": [
                {"name": "t1", "status": "PASSED" if value >= 1 else "FAILED"}, {"name": "t2", "status": "PASSED"}]}))
        if phase == "refine" and not exc:
            write(trial / "agent" / "refine-history.json", json.dumps(
                {"entries": [{"id": f"{task[-4:]}-{e}"} for e in self.entries]}))
            out = Path(args["out_dir"])
            write(out / "app" / "CLAUDE.md", f"lesson from {task}\n")
            write(out / "app" / ".claude" / "skills" / "refine" / "SKILL.md", "snapshot")
            write(out / "memory" / "MEMORY.md", f"- [{task[-4:]}](n.md) — note\n")
        return subprocess.CompletedProcess(cmd, 0)


def make_tasks(root: Path, names) -> Path:
    for name in names:
        write(root / name / "task.toml", f'[environment]\ndocker_image = "img:{name}"\n')
        write(root / name / "instruction.md", f"statement for {name}")
        write(root / name / "tests" / "config.json", json.dumps({"fail_to_pass": '["t1"]', "pass_to_pass": '["t2"]'}))
        write(root / name / "solution" / "solve.sh", "gold")
    return root
