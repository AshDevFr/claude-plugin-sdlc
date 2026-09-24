import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

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
# Real content for the sections the template fills with guidance.
FILLED = {
    "## Context\n": "Deliveries are sent once and dropped on any error.\n",
    "## Design\n": "Failed deliveries go to a retry queue per partner, with the existing backoff.\n",
    "## Risks and security\n": "Retries make delivery at-least-once; partners dedupe on the event id.\n",
}


class CheckTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)

    def git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            check=True,
            capture_output=True,
        )

    def specs(self, *args):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def new(self, slug="retries", fill=True) -> str:
        result = self.specs("new", "--date", "2026-09-23", "--title", slug, "--slug", slug)
        self.assertEqual(result.returncode, 0, result.stderr)
        spec_id = f"2026-09-23-{slug}"
        if fill:
            self.fill(spec_id)
        return spec_id

    def spec_path(self, spec_id: str) -> Path:
        return self.root / "specs" / spec_id / "spec.md"

    def fill(self, spec_id: str) -> None:
        path = self.spec_path(spec_id)
        text = path.read_text()
        for heading, body in FILLED.items():
            start = text.index(heading) + len(heading)
            end = text.index("\n## ", start) + 1
            text = text[:start] + body + "\n" + text[end:]
        start = text.index("- **AC-1**")
        text = (
            text[:start]
            + "- **AC-1** Given a 503, when delivering, then the delivery is retried.\n"
            + text[text.index("\n", start) + 1 :]
        )
        path.write_text(text)

    def cite(self, spec_id: str, *acs: str) -> None:
        tests = self.root / "tests"
        tests.mkdir(exist_ok=True)
        (tests / "test_retries.py").write_text("".join(f"# {spec_id}:{ac}\n" for ac in acs))

    def check(self, *args):
        result = self.specs("--json", "check", *args)
        return result.returncode, json.loads(result.stdout) if result.stdout.strip() else None, result


class CheckTest(CheckTestCase):
    def test_changed_intent_is_reported_with_the_rest(self):
        spec_id = self.new()
        self.git("switch", "-q", "-c", spec_id)
        intent = self.root / "specs" / spec_id / "intent.md"
        intent.write_text(intent.read_text() + "\nOne more thing.\n")
        code, doc, _ = self.check()
        self.assertEqual(code, 1)
        report = doc["specs"][0]
        self.assertEqual(report["spec"], spec_id)
        self.assertEqual(report["intent"], "changed")
        self.assertIn("L016", [f["rule"] for f in report["lint"]])
        self.assertEqual(report["uncited"], ["AC-1"])

    def test_clean_spec_with_citations_has_nothing_to_report(self):
        spec_id = self.new()
        self.cite(spec_id, "AC-1")
        code, doc, _ = self.check(f"specs/{spec_id}")
        self.assertEqual(code, 0, doc)
        self.assertEqual(
            (doc["specs"][0]["lint"], doc["specs"][0]["uncited"], doc["specs"][0]["intent"]),
            ([], [], "unchanged"),
        )

    def test_all_covers_every_spec(self):
        self.new("one")
        self.new("two")
        _, doc, _ = self.check("--all")
        self.assertEqual([s["spec"] for s in doc["specs"]], ["2026-09-23-one", "2026-09-23-two"])

    def test_no_spec_for_the_branch_is_a_usage_error(self):
        self.new()
        code, doc, result = self.check()
        self.assertEqual(code, 2)
        self.assertIn("--all", doc["error"]["message"])


class ReadyTest(CheckTestCase):
    def test_an_open_question_means_not_ready(self):
        spec_id = self.new()
        path = self.spec_path(spec_id)
        text = path.read_text()
        start = text.index("## Open questions\n") + len("## Open questions\n")
        end = text.index("\n## ", start) + 1
        path.write_text(text[:start] + "- How many retries? (integrations lead)\n\n" + text[end:])
        code, doc, _ = self.check("--ready", f"specs/{spec_id}")
        self.assertEqual(code, 1)
        self.assertIs(doc["specs"][0]["ready"], False)
        self.assertIn("open questions", doc["specs"][0]["reasons"])

    def test_ready_spec(self):
        spec_id = self.new()
        code, doc, _ = self.check("--ready", f"specs/{spec_id}")
        self.assertEqual(code, 0, doc)
        self.assertIs(doc["specs"][0]["ready"], True)
        self.assertEqual(doc["specs"][0]["reasons"], [])

    def test_uncited_criteria_dont_block_readiness(self):
        # Spec review comes before code, so no test cites anything yet.
        spec_id = self.new()
        _, doc, _ = self.check("--ready", f"specs/{spec_id}")
        self.assertEqual(doc["specs"][0]["uncited"], ["AC-1"])
        self.assertIs(doc["specs"][0]["ready"], True)

    def test_changed_intent_means_not_ready(self):
        spec_id = self.new()
        intent = self.root / "specs" / spec_id / "intent.md"
        intent.write_text(intent.read_text() + "\nMore.\n")
        _, doc, _ = self.check("--ready", f"specs/{spec_id}")
        self.assertIn("intent changed", doc["specs"][0]["reasons"])

    def test_template_text_means_not_ready(self):
        spec_id = self.new(fill=False)
        _, doc, _ = self.check("--ready", f"specs/{spec_id}")
        self.assertIn("template text", doc["specs"][0]["reasons"])


class TemplateTextRuleTest(CheckTestCase):
    def findings(self, spec_id: str, *flags: str) -> list[dict]:
        result = self.specs("--json", "lint", *flags, f"specs/{spec_id}")
        return json.loads(result.stdout)["findings"]

    def test_guidance_left_in_place_is_reported_only_when_ready(self):
        spec_id = self.new(fill=False)
        ready = [f for f in self.findings(spec_id, "--ready") if f["rule"] == "L017"]
        named = " ".join(f["message"] for f in ready)
        for section in ("Context", "Acceptance criteria", "Design", "Risks and security"):
            self.assertIn(section, named)
        self.assertNotIn("Open questions", named)
        self.assertEqual([f for f in self.findings(spec_id) if f["rule"] == "L017"], [])

    def test_filled_sections_pass(self):
        spec_id = self.new()
        self.assertEqual([f for f in self.findings(spec_id, "--ready") if f["rule"] == "L017"], [])

    def test_the_teams_template_is_the_reference(self):
        templates = self.root / "specs" / "templates"
        templates.mkdir()
        spec_template = (
            Path(__file__).resolve().parent.parent / "sdlc_specs" / "templates" / "spec.md"
        ).read_text()
        (templates / "spec.md").write_text(
            spec_template.replace(
                "Approach, data model changes, API changes, alternatives considered and why rejected.",
                "Our own design guidance.",
            )
        )
        spec_id = self.new(fill=True)
        path = self.spec_path(spec_id)
        text = path.read_text()
        start = text.index("## Design\n") + len("## Design\n")
        end = text.index("\n## ", start) + 1
        path.write_text(text[:start] + "Our own design guidance.\n\n" + text[end:])
        messages = [f["message"] for f in self.findings(spec_id, "--ready") if f["rule"] == "L017"]
        self.assertEqual(len(messages), 1)
        self.assertIn("Design", messages[0])
