"""Harbor agents: Claude Code from the arm64-musl build, with an optional notes bundle, and the refine agent.

Use with `PYTHONPATH=<worktree> harbor run -a bench.swepro.agent:ArmClaudeCode --ak tools_dir=... [--ak bundle_dir=...]`.
The container steps themselves live in bench.swepro.install.
"""
from __future__ import annotations

from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode, ClaudeCodeOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from bench.swepro import install, tools


class ArmClaudeCodeOptions(ClaudeCodeOptions):
    """Harbor checks every --ak against the agent's options model before a job starts."""
    tools_dir: str | None = None
    bundle_dir: str | None = None


class RefineClaudeCodeOptions(ArmClaudeCodeOptions):
    state_dir: str | None = None
    skill_dir: str | None = None
    inputs_dir: str | None = None
    out_dir: str | None = None


class ArmClaudeCode(ClaudeCode):
    options_model = ArmClaudeCodeOptions

    def __init__(self, logs_dir: Path, *args, tools_dir: str | None = None, bundle_dir: str | None = None,
                 **kwargs):
        self._tools = Path(tools_dir) if tools_dir else tools.TOOLS
        self._bundle = Path(bundle_dir) if bundle_dir else None
        if self._bundle is not None and (self._bundle / "memory").is_dir():
            kwargs["memory_dir"] = f"{install.NOTES}/memory"
        super().__init__(logs_dir, *args, **kwargs)

    @staticmethod
    def name() -> str:
        return "claude-code-arm"

    async def _apply(self, environment: BaseEnvironment, steps) -> None:
        for step in steps:
            if isinstance(step, install.Upload):
                if step.is_dir:
                    await environment.upload_dir(step.src, step.dst)
                else:
                    await environment.upload_file(step.src, step.dst)
                continue
            result = await environment.exec(command=step.command, user="root", timeout_sec=300)
            if step.check and result.return_code != 0:
                raise RuntimeError(f"install step failed ({result.return_code}): {step.command}")

    async def _install_claude(self, environment: BaseEnvironment) -> None:
        await self._apply(environment, install.claude_steps(self._tools))
        if not await self._installed_claude_satisfies_version(environment):
            raise RuntimeError(f"arm64 Claude Code does not report version {self._version}")

    async def install(self, environment: BaseEnvironment) -> None:
        await self._install_claude(environment)
        if self._bundle is not None:
            await self._apply(environment, install.bundle_steps(self._bundle))
        await self._apply(environment, [install.Exec(install.NOTES_REPORT, check=False)])

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            try:
                await environment.exec(command=install.CAPTURE, user="root", timeout_sec=300)
            except Exception as error:  # never mask the trial outcome
                self.logger.warning(f"patch capture failed: {error}")


class RefineClaudeCode(ArmClaudeCode):
    """A refine session: the notes state, refine snapshot and inputs go in; the state comes back out."""

    options_model = RefineClaudeCodeOptions

    def __init__(self, logs_dir: Path, *args, state_dir: str, skill_dir: str, inputs_dir: str, out_dir: str,
                 **kwargs):
        self._state, self._skill = Path(state_dir), Path(skill_dir)
        self._inputs, self._out = Path(inputs_dir), Path(out_dir)
        super().__init__(logs_dir, *args, **kwargs)

    @staticmethod
    def name() -> str:
        return "claude-code-refine"

    async def install(self, environment: BaseEnvironment) -> None:
        await self._install_claude(environment)
        await self._apply(environment, install.refine_steps(self._state, self._skill, self._inputs))

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        try:
            await ClaudeCode.run(self, instruction, environment, context)
        finally:
            await environment.exec(command=install.refine_history_command(), user="root", timeout_sec=300)
            self._out.mkdir(parents=True, exist_ok=True)
            await environment.download_dir("/app", self._out / "app")
            await environment.download_dir(install.REFINE_MEMORY, self._out / "memory")
