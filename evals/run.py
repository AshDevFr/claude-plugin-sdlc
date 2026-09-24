#!/usr/bin/env python3
"""Run the plugin's eval scenarios: build a sandbox, run the steps headless, check the result.

    python evals/run.py [scenario ...] [--model opus] [--jobs 4] [--dry-run] [--keep]

Each scenario prints PASS or FAIL with its failed checks. Transcripts of failed scenarios are kept
under evals/results/<timestamp>/. --dry-run builds every sandbox and runs every setup without
calling Claude, which is what the unit tests use. Exit 0 when every scenario passes.
"""

import argparse
import importlib.util
import json
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import Check, build, offline, run_step  # noqa: E402

EVALS = Path(__file__).resolve().parent
SCENARIOS = EVALS / "scenarios"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"scenarios.{name}", SCENARIOS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def names() -> list[str]:
    return sorted(p.stem for p in SCENARIOS.glob("*.py") if not p.stem.startswith("_"))


def evaluate(name: str, args, work: Path, results: Path) -> dict:
    scenario = load(name)
    started = time.monotonic()
    outcome = {"scenario": name, "failures": [], "cost_usd": 0.0}
    try:
        repo = build(scenario, work / name)
        if args.dry_run:
            outcome["seconds"] = round(time.monotonic() - started, 1)
            return outcome
        runs = []
        for step in scenario.STEPS:
            if step.before:
                step.before(repo)
            run = run_step(repo, step, args.model, args.timeout)
            runs.append(run)
            outcome["cost_usd"] += run.cost_usd
            if run.exit_code != 0:
                outcome["failures"].append(f"{step.prompt!r} exited {run.exit_code}")
                break
        c = Check()
        if not outcome["failures"]:
            offline(c, runs)
            scenario.check(c, repo, runs)
        outcome["failures"] += c.failures
    except Exception:  # a broken scenario is a failure, not a crash of the whole suite
        outcome["failures"].append(traceback.format_exc(limit=3))
        runs = locals().get("runs", [])
    outcome["seconds"] = round(time.monotonic() - started, 1)
    if outcome["failures"] and not args.dry_run:
        kept = results / name
        kept.mkdir(parents=True, exist_ok=True)
        for i, run in enumerate(runs, start=1):
            (kept / f"step-{i}.jsonl").write_text(run.transcript, encoding="utf-8")
            (kept / f"step-{i}.md").write_text(run.final, encoding="utf-8")
    return outcome


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("scenarios", nargs="*", help="default: all")
    parser.add_argument("--model", default="opus")
    parser.add_argument("--jobs", type=int, default=4, help="scenarios run at once")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds per step")
    parser.add_argument("--dry-run", action="store_true", help="build sandboxes and run setups only")
    parser.add_argument("--keep", action="store_true", help="keep the sandboxes")
    args = parser.parse_args(argv)
    chosen = args.scenarios or names()
    unknown = sorted(set(chosen) - set(names()))
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}; known: {', '.join(names())}", file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="sdlc-evals-"))
    results = EVALS / "results" / time.strftime("%Y%m%d-%H%M%S")
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        outcomes = list(pool.map(lambda n: evaluate(n, args, work, results), chosen))

    for o in outcomes:
        verdict = "FAIL" if o["failures"] else "PASS"
        cost = "" if args.dry_run else f"  ${o['cost_usd']:.2f}"
        print(f"{verdict}  {o['scenario']}  {o['seconds']}s{cost}")
        for failure in o["failures"]:
            print("      - " + failure.strip().replace("\n", "\n        "))
    failed = [o for o in outcomes if o["failures"]]
    if not args.dry_run:
        results.mkdir(parents=True, exist_ok=True)
        (results / "summary.json").write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
        total = sum(o["cost_usd"] for o in outcomes)
        print(f"{len(outcomes) - len(failed)}/{len(outcomes)} passed, ${total:.2f}; results in {results}")
    print(f"sandboxes in {work}" if args.keep else "", end="\n" if args.keep else "")
    if not args.keep:
        import shutil

        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
