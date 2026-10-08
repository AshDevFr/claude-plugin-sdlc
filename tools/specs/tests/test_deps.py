import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.deps import Graph

from tests.base import OfflineTestCase

CONFIG = "tracker:\n  system: github\ncode_host:\n  system: github\n"
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "jdoe",
    "GIT_AUTHOR_EMAIL": "jdoe@example.com",
    "GIT_COMMITTER_NAME": "jdoe",
    "GIT_COMMITTER_EMAIL": "jdoe@example.com",
}
LOG = "2026-09-20-delivery-log"
RETRIES = "2026-09-23-webhook-retries"
ALERTS = "2026-09-25-failure-alerts"


class DepsTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "jdoe")
        self.specs_dir = self.root / "specs"
        self.specs_dir.mkdir()
        (self.specs_dir / "config.yml").write_text(CONFIG)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def specs(self, *args: str):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def new(self, spec_id: str, status: str = "draft", depends_on: tuple[str, ...] = ()) -> Path:
        date, slug = spec_id[:10], spec_id[11:]
        result = self.specs("new", "--date", date, "--title", slug, "--slug", slug)
        self.assertEqual(result.returncode, 0, result.stderr)
        spec_dir = self.specs_dir / spec_id
        self.set_status(spec_id, status)
        if depends_on:
            spec = spec_dir / "spec.md"
            line = "depends_on: [" + ", ".join(depends_on) + "]\n"
            spec.write_text(spec.read_text().replace("superseded_by: null\n", "superseded_by: null\n" + line))
        return spec_dir

    def fill(self, spec_dir: Path) -> None:
        """Real content where the template has guidance, so `--ready` has nothing else to say."""
        spec = spec_dir / "spec.md"
        text = spec.read_text()
        for heading in ("## Context\n", "## Design\n", "## Risks and security\n"):
            start = text.index(heading) + len(heading)
            end = text.index("\n## ", start) + 1
            text = text[:start] + "Real content.\n\n" + text[end:]
        start = text.index("- **AC-1**")
        text = (
            text[:start]
            + "- **AC-1** Given a 503, then it is retried.\n"
            + text[text.index("\n", start) + 1 :]
        )
        spec.write_text(text)

    def set_status(self, spec_id: str, status: str) -> None:
        intent = self.specs_dir / spec_id / "intent.md"
        text = intent.read_text()
        start = text.index("status: ")
        intent.write_text(text[:start] + f"status: {status}" + text[text.index("   #", start) :])

    def ticket_spec(self) -> str:
        result = self.specs("new", "--key", "42", "--title", "Partner portal")
        self.assertEqual(result.returncode, 0, result.stderr)
        return "42-partner-portal"


class ReadinessTest(DepsTestCase):
    def test_ready_when_ready_for_code_and_every_dependency_done(self):
        self.new(LOG, "done")
        self.new(RETRIES, "ready-for-code", depends_on=(LOG,))
        readiness = Graph(self.specs_dir).readiness(RETRIES)
        self.assertEqual((readiness.verdict, readiness.ready_to_implement), ("ready", True))
        self.assertEqual(readiness.blocked_by, ())

    def test_a_dependency_not_done_blocks(self):
        for status in ("draft", "ready-for-spec", "ready-for-code", "dropped"):
            with self.subTest(status=status):
                self.setUp()
                self.new(LOG, status)
                self.new(RETRIES, "ready-for-code", depends_on=(LOG,))
                readiness = Graph(self.specs_dir).readiness(RETRIES)
                self.assertEqual(readiness.verdict, "blocked")
                self.assertFalse(readiness.ready_to_implement)
                self.assertEqual([(n.id, n.status) for n in readiness.blocked_by], [(LOG, status)])

    def test_only_dependencies_decide_its_own_status_does_not(self):
        # Whether work can start depends on what it builds on; the intent's status is shown, not
        # judged.
        for status in ("draft", "ready-for-spec", "ready-for-code"):
            with self.subTest(status=status):
                self.setUp()
                self.new(RETRIES, status)
                readiness = Graph(self.specs_dir).readiness(RETRIES)
                self.assertEqual((readiness.verdict, readiness.ready_to_implement), ("ready", True))

    def test_done_and_dropped_are_their_own_verdicts(self):
        self.new(LOG, "draft")
        self.new(RETRIES, "done", depends_on=(LOG,))
        self.new(ALERTS, "dropped")
        graph = Graph(self.specs_dir)
        self.assertEqual(graph.readiness(RETRIES).verdict, "done")
        self.assertEqual(graph.readiness(ALERTS).verdict, "dropped")

    def test_a_ticket_dependency_is_unknown_and_never_done(self):
        ticket = self.ticket_spec()
        self.new(RETRIES, "ready-for-code", depends_on=(ticket,))
        readiness = Graph(self.specs_dir).readiness(RETRIES)
        self.assertEqual([(n.id, n.status) for n in readiness.blocked_by], [(ticket, "unknown (tracker)")])

    def test_a_ticket_specs_own_status_is_not_held_against_it(self):
        # Its tracker knows; the helper doesn't read trackers, so only its dependencies count.
        ticket = self.ticket_spec()
        self.assertTrue(Graph(self.specs_dir).readiness(ticket).ready_to_implement)

    def test_an_intent_without_frontmatter_is_a_draft(self):
        spec_dir = self.new(RETRIES)
        intent = spec_dir / "intent.md"
        intent.write_text(intent.read_text().split("---\n", 2)[2])
        self.assertEqual(Graph(self.specs_dir).readiness(RETRIES).status, "draft")

    def test_a_missing_dependency_blocks(self):
        self.new(RETRIES, "ready-for-code", depends_on=("2026-01-01-nowhere",))
        readiness = Graph(self.specs_dir).readiness(RETRIES)
        self.assertEqual(
            [(n.id, n.status) for n in readiness.blocked_by], [("2026-01-01-nowhere", "missing")]
        )


class LintTest(DepsTestCase):
    def rules(self) -> list[str]:
        doc = json.loads(self.specs("--json", "lint").stdout)
        return sorted(f"{f['path'].split('/')[1]} {f['rule']}" for f in doc["findings"])

    def test_a_longer_cycle_is_reported_on_each_spec(self):
        self.new(LOG, depends_on=(ALERTS,))
        self.new(RETRIES, depends_on=(LOG,))
        self.new(ALERTS, depends_on=(RETRIES,))
        self.assertEqual(self.rules(), [f"{s} L020" for s in sorted((LOG, RETRIES, ALERTS))])
        message = json.loads(self.specs("--json", "lint", f"specs/{RETRIES}").stdout)["findings"][0][
            "message"
        ]
        self.assertIn(f"{RETRIES} -> {LOG} -> {ALERTS} -> {RETRIES}", message)

    def test_a_spec_downstream_of_a_cycle_is_not_on_it(self):
        self.new(LOG, depends_on=(ALERTS,))
        self.new(ALERTS, depends_on=(LOG,))
        self.new(RETRIES, depends_on=(LOG,))
        self.assertEqual(self.rules(), [f"{LOG} L020", f"{ALERTS} L020"])

    def test_a_dependency_on_an_intent_written_ahead_is_a_spec_directory(self):
        self.assertEqual(
            self.specs("intent", "new", "--date", "2026-09-20", "--title", "delivery log").returncode, 0
        )
        self.new(RETRIES, depends_on=(LOG,))
        self.assertEqual(self.rules(), [])

    def test_the_templates_directory_is_not_a_spec(self):
        (self.specs_dir / "templates").mkdir()
        self.new(RETRIES, depends_on=("templates",))
        self.assertEqual(self.rules(), [f"{RETRIES} L018"])


class StatusLineTest(DepsTestCase):
    def status(self, branch: str) -> tuple[str, dict]:
        self.git("switch", "-q", "-c", branch)
        text = self.specs("status")
        self.assertEqual(text.returncode, 0, text.stderr)
        return text.stdout.strip(), json.loads(self.specs("--json", "status").stdout)

    def test_the_intent_status_shows(self):
        self.new(RETRIES, "ready-for-code")
        line, doc = self.status(RETRIES)
        self.assertEqual(line, f"{RETRIES} r1: 0 lint finding(s), intent unchanged, status ready-for-code")
        self.assertEqual(
            (doc["status"], doc["blocked_by"], doc["ready_to_implement"]), ("ready-for-code", [], True)
        )

    def test_blocked_by_names_the_dependencies_not_done(self):
        self.new(LOG, "ready-for-code")
        self.new(ALERTS, "done")
        self.new(RETRIES, "ready-for-code", depends_on=(LOG, ALERTS))
        line, doc = self.status(RETRIES)
        self.assertTrue(line.endswith(f"status ready-for-code, blocked by {LOG}"), line)
        self.assertEqual(doc["blocked_by"], [LOG])
        self.assertIs(doc["ready_to_implement"], False)

    def test_a_ticket_spec_shows_no_status(self):
        ticket = self.ticket_spec()
        line, doc = self.status("42-portal")
        self.assertNotIn("status", line)
        self.assertEqual(doc["status"], "unknown (tracker)")
        self.assertTrue(line.startswith(ticket))

    def test_an_intent_written_ahead_shows_its_status(self):
        self.assertEqual(
            self.specs("intent", "new", "--date", "2026-09-23", "--title", "webhook retries").returncode, 0
        )
        line, doc = self.status(RETRIES)
        self.assertEqual(line, f"{RETRIES}: intent only, no spec yet, status draft")
        self.assertEqual(doc["status"], "draft")


class CheckTest(DepsTestCase):
    def check(self, *args: str) -> tuple[int, dict]:
        result = self.specs("--json", "check", *args)
        return result.returncode, json.loads(result.stdout)

    def test_every_report_carries_status_and_blockers(self):
        self.new(LOG, "ready-for-spec")
        self.new(RETRIES, "ready-for-code", depends_on=(LOG,))
        _, doc = self.check(f"specs/{RETRIES}")
        report = doc["specs"][0]
        self.assertEqual(report["status"], "ready-for-code")
        self.assertEqual(report["blocked_by"], [{"spec": LOG, "status": "ready-for-spec"}])
        self.assertIs(report["ready_to_implement"], False)
        text = self.specs("check", f"specs/{RETRIES}").stdout
        self.assertIn(f"  blocked by: {LOG} (ready-for-spec)", text)

    def test_unmet_dependencies_dont_affect_review_readiness(self):
        # Whether a spec is ready for review has nothing to do with whether it can be built yet:
        # the blockers are reported, the verdict ignores them.
        self.new(LOG, "draft")
        spec_dir = self.new(RETRIES, "ready-for-code", depends_on=(LOG,))
        self.fill(spec_dir)
        code, doc = self.check("--ready", f"specs/{RETRIES}")
        report = doc["specs"][0]
        self.assertEqual((code, report["ready"], report["reasons"]), (0, True, []))
        self.assertEqual(report["blocked_by"], [{"spec": LOG, "status": "draft"}])
        self.assertIs(report["ready_to_implement"], False)


class DepsCommandTest(DepsTestCase):
    def test_every_spec_in_dependency_order_with_its_verdict(self):
        self.new(ALERTS, "draft", depends_on=(RETRIES,))
        self.new(RETRIES, "ready-for-code", depends_on=(LOG,))
        self.new(LOG, "done")
        result = self.specs("deps")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                f"{LOG}: done",
                f"{RETRIES}: ready-for-code, ready (after {LOG})",
                f"{ALERTS}: draft, blocked by {RETRIES} (ready-for-code)",
            ],
        )
        doc = json.loads(self.specs("--json", "deps").stdout)
        self.assertEqual([s["spec"] for s in doc["specs"]], [LOG, RETRIES, ALERTS])
        self.assertEqual(
            doc["specs"][2],
            {
                "spec": ALERTS,
                "status": "draft",
                "verdict": "blocked",
                "depends_on": [RETRIES],
                "blocked_by": [{"spec": RETRIES, "status": "ready-for-code"}],
            },
        )
        self.assertEqual(doc["cycles"], [])

    def test_a_cycle_is_listed_last_and_named(self):
        self.new(LOG, "draft", depends_on=(ALERTS,))
        self.new(ALERTS, "draft", depends_on=(LOG,))
        self.new(RETRIES, "draft")
        doc = json.loads(self.specs("--json", "deps").stdout)
        self.assertEqual([s["spec"] for s in doc["specs"]], [RETRIES, LOG, ALERTS])
        self.assertEqual(doc["cycles"], [LOG, ALERTS])
        self.assertIn("cycle", self.specs("deps").stdout)

    def test_no_specs(self):
        result = self.specs("--json", "deps")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"ok": True, "specs": [], "cycles": []})
