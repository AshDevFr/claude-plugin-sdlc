from sdlc_specs.intent_status import DEFAULT_STATUS, INVALID, STATUSES, split_frontmatter, status_of_text

from tests.base import OfflineTestCase

BODY = "# Intent: x\nAuthor: jdoe.\n\n## Problem\nIt hurts.\n"


class StatusTest(OfflineTestCase):
    def test_every_status(self):
        self.assertEqual(STATUSES, ("draft", "ready-for-spec", "ready-for-code", "done", "dropped"))
        for status in STATUSES:
            with self.subTest(status=status):
                found = status_of_text(f"---\nstatus: {status}   # a comment\n---\n{BODY}")
                self.assertEqual((found.value, found.problem), (status, None))

    def test_no_frontmatter_or_no_status_is_a_draft(self):
        # Intents written before the status existed keep working.
        for text in (BODY, f"---\n---\n{BODY}", f"---\nowner: pm\n---\n{BODY}", f"---\nstatus:\n---\n{BODY}"):
            with self.subTest(text=text[:20]):
                self.assertEqual(status_of_text(text).value, DEFAULT_STATUS)
                self.assertIsNone(status_of_text(text).problem)

    def test_invalid_values_are_reported(self):
        cases = {
            "status: approved": "approved",
            "status: 3": "3",
            "status: [draft]": "list",
            "status: [unclosed": "YAML",
            "- draft": "mapping",
        }
        for line, fragment in cases.items():
            with self.subTest(line=line):
                found = status_of_text(f"---\n{line}\n---\n{BODY}")
                self.assertEqual(found.value, INVALID)
                self.assertIn(fragment, found.problem)

    def test_split_crlf_and_unterminated(self):
        self.assertEqual(
            split_frontmatter("---\r\nstatus: done\r\n---\r\n# T\r\n"), ("status: done", ["# T", ""])
        )
        self.assertEqual(
            split_frontmatter("---\nstatus: done\n# T\n"), (None, ["---", "status: done", "# T", ""])
        )
