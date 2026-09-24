from pathlib import Path

from sdlc_specs.spec import SpecParseError, parse_spec, parse_spec_text

from tests.base import OfflineTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "specs"
TEMPLATE_SECTIONS = [
    "Context",
    "Goals",
    "Non-goals",
    "Acceptance criteria",
    "Design",
    "Risks and security",
    "Rollout and migration",
    "Open questions",
    "Decisions",
    "Revisions",
]

MINIMAL_FRONTMATTER = "---\nid: x\ntitle: Example\n---\n\n# Example\n\n"


def spec_with(sections: dict[str, str]) -> str:
    body = "".join(f"## {title}\n{text}\n" for title, text in sections.items())
    return MINIMAL_FRONTMATTER + body


class WorkflowExampleTest(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.spec = parse_spec(FIXTURES / "123-prorate-plan-changes" / "spec.md")

    def test_counts(self):
        self.assertEqual([c.number for c in self.spec.criteria], [1, 2, 3])
        self.assertEqual([r.number for r in self.spec.revisions], [2, 1])
        self.assertEqual(self.spec.open_questions, [])
        self.assertEqual(list(self.spec.sections), TEMPLATE_SECTIONS)
        self.assertEqual(self.spec.warnings, [])

    def test_title_and_frontmatter(self):
        self.assertEqual(self.spec.title, "Prorate plan changes mid-cycle")
        self.assertEqual(self.spec.frontmatter["id"], "123-prorate-plan-changes")
        self.assertEqual(self.spec.frontmatter["ticket"]["ref"], "billing/api#123")
        self.assertEqual(self.spec.frontmatter_end_line, 22)

    def test_key_lines(self):
        self.assertEqual(self.spec.key_lines["id"], 2)
        self.assertEqual(self.spec.key_lines["ticket"], 4)
        self.assertEqual(self.spec.key_lines["ticket.snapshot"], 8)
        self.assertEqual(self.spec.key_lines["ticket.snapshot.content_sha256"], 9)
        self.assertEqual(self.spec.key_lines["attachments"], 19)

    def test_criterion_details(self):
        first = self.spec.criteria[0]
        self.assertEqual(first.text, "Upgrading mid-cycle charges the prorated difference immediately.")
        self.assertFalse(first.struck)
        self.assertEqual(first.line, 36)

    def test_revision_details_include_continuation_lines(self):
        r2 = self.spec.revisions[0]
        self.assertEqual((r2.date, r2.author, r2.line), ("2026-09-26", "jdoe", 55))
        self.assertIn("Non-goals and AC-3 updated.", r2.text)

    def test_section_lines(self):
        section = self.spec.sections["Acceptance criteria"]
        self.assertEqual(section.start_line, 35)
        self.assertEqual(section.end_line, 39)


class CriteriaTest(OfflineTestCase):
    def test_struck_criterion_keeps_its_number(self):
        spec = parse_spec(FIXTURES / "struck-ac" / "spec.md")
        struck = [c for c in spec.criteria if c.struck]
        self.assertEqual(len(struck), 1)
        self.assertEqual(struck[0].number, 2)
        self.assertEqual(struck[0].line, 21)
        self.assertEqual(struck[0].text, "Downgrades issue a credit")
        self.assertEqual(struck[0].reason, "Dropped: annual plans only.")
        self.assertEqual([c.number for c in spec.criteria], [1, 2, 3])

    def test_noncanonical_lines_are_warnings_not_criteria(self):
        spec = parse_spec(FIXTURES / "noncanonical-ac" / "spec.md")
        self.assertEqual([c.number for c in spec.criteria], [1])
        self.assertEqual([w.line for w in spec.warnings], [21, 22, 25, 30])
        by_line = {w.line: w.message for w in spec.warnings}
        self.assertIn("AC-4", by_line[21])
        self.assertIn("Design", by_line[25])
        self.assertIn("code block", by_line[30])

    def test_mentions_of_an_ac_inside_prose_are_not_warnings(self):
        spec = parse_spec_text(
            spec_with(
                {
                    "Acceptance criteria": "- **AC-1** One.\n  Continues, like AC-2 would.\n",
                    "Design": "We satisfy AC-1 by charging once.\n- Uses the anchor (see AC-1).\n",
                }
            )
        )
        self.assertEqual(spec.warnings, [])
        self.assertEqual(spec.criteria[0].text, "One. Continues, like AC-2 would.")

    def test_duplicates_are_kept_for_the_linter(self):
        spec = parse_spec_text(spec_with({"Acceptance criteria": "- **AC-1** A.\n- **AC-1** B.\n"}))
        self.assertEqual([c.number for c in spec.criteria], [1, 1])

    def test_ac_like_heading_in_a_block_quote_warns(self):
        spec = parse_spec_text(spec_with({"Acceptance criteria": "> - **AC-9** quoted\n"}))
        self.assertEqual(len(spec.warnings), 1)
        self.assertEqual(spec.criteria, [])

    def test_headings_inside_fences_do_not_open_sections(self):
        spec = parse_spec_text(spec_with({"Design": "```md\n## Not a section\n```\n"}))
        self.assertNotIn("Not a section", spec.sections)


class OpenQuestionsTest(OfflineTestCase):
    def test_list_items_are_questions(self):
        spec = parse_spec_text(
            spec_with(
                {
                    "Open questions": (
                        "- Who approves annual plans? (PM)\n  More detail.\n* Credit expiry? (Finance)\n"
                    )
                }
            )
        )
        self.assertEqual(
            [q.text for q in spec.open_questions],
            ["Who approves annual plans? (PM) More detail.", "Credit expiry? (Finance)"],
        )

    def test_none_and_empty_and_prose_mean_no_questions(self):
        for text in ("None.\n", "", "Each one names who must answer it.\n"):
            with self.subTest(text=text):
                self.assertEqual(parse_spec_text(spec_with({"Open questions": text})).open_questions, [])

    def test_missing_section_means_no_questions(self):
        self.assertEqual(parse_spec_text(spec_with({"Context": "x\n"})).open_questions, [])


class FrontmatterErrorTest(OfflineTestCase):
    def test_no_frontmatter(self):
        with self.assertRaises(SpecParseError) as ctx:
            parse_spec(FIXTURES / "no-frontmatter" / "spec.md")
        self.assertEqual(ctx.exception.line, 1)
        self.assertTrue(
            str(ctx.exception).endswith(
                "no-frontmatter/spec.md:1: missing frontmatter (--- on the first line)"
            )
        )

    def test_invalid_yaml_reports_the_file_line(self):
        with self.assertRaises(SpecParseError) as ctx:
            parse_spec(FIXTURES / "bad-frontmatter" / "spec.md")
        self.assertEqual(ctx.exception.line, 5)

    def test_unterminated_frontmatter(self):
        with self.assertRaises(SpecParseError) as ctx:
            parse_spec_text("---\nid: x\n\n# Example\n")
        self.assertEqual(ctx.exception.line, 1)
        self.assertIn("unterminated", ctx.exception.message)

    def test_frontmatter_must_be_a_mapping(self):
        with self.assertRaises(SpecParseError) as ctx:
            parse_spec_text("---\n- a\n---\n")
        self.assertEqual(ctx.exception.line, 2)

    def test_crlf_files_parse(self):
        text = spec_with({"Acceptance criteria": "- **AC-1** One.\n"}).replace("\n", "\r\n")
        spec = parse_spec_text(text)
        self.assertEqual(spec.criteria[0].text, "One.")
