"""Run a plugin command headless in a throwaway repository, then check what it left behind.

A scenario is a module under `evals/scenarios/` with:

- `COMMANDS`: the `/sdlc:` commands it exercises;
- `SANDBOX`: an `sdlc-sandbox` scenario name, `""` for a plain sandbox, or `None` for a bare
  repository with the app and no `/sdlc:init`;
- `setup(repo)` (optional): puts the repository in its starting state;
- `STEPS`: `Step`s, each one `claude -p` session in the same repository;
- `check(c, repo, runs)`: structural assertions through `c.that(...)`. Never prose quality.

Claude's `.claude` state and the user's settings aren't touched; git runs with no global config.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
HELPER = PLUGIN / "tools" / "specs" / "specs"
SANDBOX = PLUGIN / "bin" / "sdlc-sandbox"
APP = PLUGIN / "sandbox" / "app"
TOOLS = "Bash Read Write Edit Glob Grep"
UNATTENDED = (
    "You are being run unattended to test a plugin command in a throwaway repository. There is no "
    "engineer at the keyboard; the engineer's answers are given below. The engineer is Ana Silva. "
    "For any question not answered below, take your recommended answer. Do not ask anything else."
)
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Ana Silva",
    "GIT_AUTHOR_EMAIL": "ana@example.com",
    "GIT_COMMITTER_NAME": "Ana Silva",
    "GIT_COMMITTER_EMAIL": "ana@example.com",
}


def env() -> dict:
    # The helper's shim runs `python3`: put the interpreter running the evals (with PyYAML) first.
    return {**os.environ, **GIT_ENV, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"}


@dataclass
class Step:
    prompt: str
    answers: str = ""  # the engineer's answers, appended to the unattended preamble
    before: object = None  # optional callable(repo), run just before this step


@dataclass
class Run:
    """One step's session: its final message, the tools it used, and its cost."""

    step: Step
    exit_code: int
    final: str = ""
    tools: list = field(default_factory=list)  # (name, input) in call order
    cost_usd: float = 0.0
    transcript: str = ""


class Repo:
    def __init__(self, path: Path):
        self.path = path
        self.start_head = ""  # recorded once setup is done, for "changed nothing" checks
        self.start_porcelain = ""

    def unchanged(self) -> bool:
        return self.head() == self.start_head and self.porcelain() == self.start_porcelain

    def git(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.path), *args], env=env(), capture_output=True, text=True
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout

    def specs(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(HELPER), *args], cwd=self.path, env=env(), capture_output=True, text=True)

    def read(self, rel: str) -> str:
        return (self.path / rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def exists(self, rel: str) -> bool:
        return (self.path / rel).exists()

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def porcelain(self) -> str:
        return self.git("status", "--porcelain")

    def ignored(self, rel: str) -> bool:
        return (
            subprocess.run(["git", "-C", str(self.path), "check-ignore", "-q", rel], env=env()).returncode
            == 0
        )

    def trailers(self, base: str) -> list[dict]:
        """Per commit since base, oldest first: {'subject', 'Spec', 'Implements', 'Spec-Change'}."""
        fmt = (
            "%x1e%s%x1f%(trailers:key=Spec,valueonly)%x1f%(trailers:key=Implements,valueonly)"
            "%x1f%(trailers:key=Spec-Change,valueonly)"
        )
        out = self.git("log", "--reverse", f"--format={fmt}", f"{base}..HEAD")
        commits = []
        for record in out.split("\x1e")[1:]:
            subject, spec, implements, change = (part.strip() for part in record.split("\x1f"))
            commits.append(
                {"subject": subject, "Spec": spec, "Implements": implements, "Spec-Change": change}
            )
        return commits


class Check:
    def __init__(self):
        self.failures: list[str] = []

    def that(self, condition, message: str) -> bool:
        if not condition:
            self.failures.append(message)
        return bool(condition)


def fenced_blocks(text: str) -> list[str]:
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, flags=re.M | re.S)


def parse_trailers(message: str) -> str:
    return subprocess.run(
        ["git", "interpret-trailers", "--parse"], input=message, capture_output=True, text=True
    ).stdout


def fill_sections(repo: Repo, spec_dir: str, sections: dict) -> None:
    """Replace the body of each named section of a spec with real content."""
    path = f"{spec_dir}/spec.md"
    text = repo.read(path)
    for title, body in sections.items():
        start = text.index(f"## {title}\n") + len(f"## {title}\n")
        end = text.index("\n## ", start) + 1
        text = text[:start] + body.rstrip("\n") + "\n\n" + text[end:]
    repo.write(path, text)


def build(scenario, where: Path) -> Repo:
    where.parent.mkdir(parents=True, exist_ok=True)
    if scenario.SANDBOX is None:
        shutil.copytree(APP, where)
        repo = Repo(where)
        repo.git("init", "-q", "-b", "main")
        repo.commit("Initial commit: the webhooks app")
    else:
        argv = [sys.executable, str(SANDBOX), str(where)]
        if scenario.SANDBOX:
            argv += ["--scenario", scenario.SANDBOX]
        result = subprocess.run(argv, env=env(), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"sdlc-sandbox: {result.stderr.strip()}")
        repo = Repo(where)
    if hasattr(scenario, "setup"):
        scenario.setup(repo)
    repo.start_head, repo.start_porcelain = repo.head(), repo.porcelain()
    return repo


def run_step(repo: Repo, step: Step, model: str, timeout: int) -> Run:
    system = UNATTENDED + (" " + step.answers if step.answers else "")
    argv = [
        "claude", "-p", step.prompt,
        "--plugin-dir", str(PLUGIN),
        "--model", model,
        "--append-system-prompt", system,
        "--allowedTools", TOOLS,
        "--disallowedTools", "WebFetch WebSearch",
        "--output-format", "stream-json", "--verbose",
    ]  # fmt: skip
    try:
        result = subprocess.run(
            argv, cwd=repo.path, env=env(), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        return Run(
            step,
            exit_code=-1,
            transcript=(exc.stdout or b"").decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or ""),
        )
    run = Run(step, exit_code=result.returncode, transcript=result.stdout)
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    run.tools.append((block.get("name"), block.get("input", {})))
        elif event.get("type") == "result":
            run.final = event.get("result") or ""
            run.cost_usd = event.get("total_cost_usd") or 0.0
    return run


def offline(c: Check, runs: list[Run]) -> None:
    """No run may reach for the web: the plugin works from the repository alone."""
    for run in runs:
        used = {name for name, _ in run.tools}
        c.that(not used & {"WebFetch", "WebSearch"}, f"{run.step.prompt!r} used a web tool: {sorted(used)}")
