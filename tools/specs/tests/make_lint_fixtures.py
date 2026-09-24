"""Regenerate tests/fixtures/lint/L0NN-{pass,fail}/ from the workflow example spec.

Run from anywhere: `python3 tools/specs/tests/make_lint_fixtures.py`. Every fixture is the example
spec with one change, so each failing fixture trips exactly one rule. Rerun after changing the
example spec, and review the diff.

Layout of a fixture:
  head/<spec-dir>/...    the spec as linted (copied to <repo>/specs/)
  base/<spec-dir>/...    optional: the spec at --base (committed first)
  config.yml             optional: overrides the default config
  expected.json          fail fixtures only: {"rule", "path", "line"}
"""

import json
import shutil
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL))
from sdlc_specs.new import TEMPLATES, render_body, render_frontmatter  # noqa: E402
from sdlc_specs.snapshot import intent_sha256  # noqa: E402

FIXTURES = TOOL / "tests" / "fixtures"
EXAMPLE = FIXTURES / "specs/123-prorate-plan-changes"
OUT = FIXTURES / "lint"
NAME = EXAMPLE.name
SPEC = (EXAMPLE / "spec.md").read_text()
SNAPSHOT = (EXAMPLE / "ticket.snapshot.md").read_text()


def replace(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def line_of(text: str, needle: str) -> int:
    hits = [i + 1 for i, line in enumerate(text.split("\n")) if needle in line]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


def write_spec_dir(target: Path, spec: str, name: str = NAME, snapshot: str | None = SNAPSHOT, drop=()):
    d = target / name
    d.mkdir(parents=True)
    for f in EXAMPLE.iterdir():
        if f.name not in ("spec.md", "ticket.snapshot.md") and f.name not in drop:
            shutil.copy(f, d / f.name)
    (d / "spec.md").write_text(spec)
    if snapshot is not None:
        (d / "ticket.snapshot.md").write_text(snapshot)


def fixture(
    fixture_name, spec, *, rule=None, needle=None, line=None, path=None, base=None, config=None, **kw
):
    target = OUT / fixture_name
    write_spec_dir(target / "head", spec, **kw)
    if base is not None:
        write_spec_dir(target / "base", base, **kw)
    if config is not None:
        (target / "config.yml").write_text(config)
    if rule:
        if line is None and needle is not None:
            line = line_of(spec, needle)
        dir_name = kw.get("name", NAME)
        (target / "expected.json").write_text(
            json.dumps({"rule": rule, "path": path or f"specs/{dir_name}/spec.md", "line": line}, indent=2)
            + "\n"
        )


def bump(spec: str, revision: int, note: str) -> str:
    spec = replace(spec, "revision: 2 ", f"revision: {revision} ")
    return replace(spec, "## Revisions\n", f"## Revisions\n- **r{revision}** (2026-09-27, jdoe): {note}\n")


if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()

# L001
fixture("L001-pass", SPEC)
bad = replace(SPEC, "title: Prorate plan changes mid-cycle\n", "title: [unclosed\n")
fixture("L001-fail", bad, rule="L001", line=4)

# L002: every optional field used, then a forbidden one
fixture("L002-pass", SPEC)
fixture(
    "L002-fail",
    replace(SPEC, "state: active", "approved: true\nstate: active"),
    rule="L002",
    needle="approved: true",
)

# L003: an other-project ticket keeps its prefix; then an id that doesn't match the directory
other = "acme-api-123-prorate-plan-changes"
other_spec = replace(
    replace(SPEC, f"id: {NAME}", f"id: {other}"), "ref: billing/api#123 ", "ref: acme/api#123   "
)
title = "Prorate plan changes mid-cycle"
other_snapshot = SNAPSHOT.replace("ticket: billing/api#123 ", "ticket: acme/api#123 ")
fixture("L003-pass", other_spec, name=other, snapshot=other_snapshot)
fixture(
    "L003-fail",
    replace(SPEC, f"id: {NAME}", "id: 123-another-name"),
    rule="L003",
    needle="id: 123-another-name",
)

# L004: a Linear spec under a Linear config passes; a spec naming another system fails
LINEAR = """tracker:
  system: linear
  team_key: ENG
code_host:
  system: github
"""
linear_name = "eng-123-prorate-plan-changes"
linear_spec = replace(SPEC, f"id: {NAME}", f"id: {linear_name}")
linear_spec = replace(linear_spec, "system: gitlab ", "system: linear ")
linear_spec = replace(linear_spec, "ref: billing/api#123 ", "ref: ENG-123         ")
linear_snapshot = SNAPSHOT.replace("ticket: billing/api#123 ", "ticket: ENG-123 ")
fixture("L004-pass", linear_spec, config=LINEAR, name=linear_name, snapshot=linear_snapshot)
fixture(
    "L004-fail", replace(SPEC, "system: gitlab ", "system: github "), rule="L004", needle="system: github"
)

# L005: sections in another order pass; a missing one fails
moved = replace(SPEC, "## Design\n", "## DESIGN-PLACEHOLDER\n")
moved = replace(moved, "## Context\n", "## Design\nMoved first on purpose.\n\n## Context\n")
moved = replace(moved, "## DESIGN-PLACEHOLDER\n", "## Notes\n")
fixture("L005-pass", moved)
fixture(
    "L005-fail", replace(SPEC, "## Rollout and migration\n", ""), rule="L005", line=22
)  # the closing --- of the frontmatter

# L006: a struck criterion is fine; a duplicate is not
struck = replace(
    SPEC,
    "- **AC-2** Downgrading mid-cycle issues a credit applied to the next invoice.",
    "- ~~**AC-2** Downgrading mid-cycle issues a credit applied to the next invoice.~~ Moved to #130.",
)
fixture("L006-pass", struck)
dup = replace(SPEC, "- **AC-3** Proration", "- **AC-2** Duplicate number.\n- **AC-3** Proration")
fixture("L006-fail", dup, rule="L006", needle="- **AC-2** Duplicate number.")

# L007: striking against base passes; deleting fails
fixture("L007-pass", bump(struck, 3, "Struck AC-2."), base=SPEC)
removed = replace(SPEC, "- **AC-2** Downgrading mid-cycle issues a credit applied to the next invoice.\n", "")
removed = bump(removed, 3, "Removed a criterion.")
fixture("L007-fail", removed, base=SPEC, rule="L007", needle="## Acceptance criteria")

# L008: "None." is no question; a list item is one (lint runs with --ready)
none = replace(
    SPEC,
    "Each one names who must answer it. The spec is not approvable with open questions left.\n",
    "None.\n",
)
fixture("L008-pass", none)
question = replace(none, "None.\n", "- Do credits expire? (PM)\n")
fixture("L008-fail", question, rule="L008", needle="- Do credits expire?")

# L009
fixture("L009-pass", SPEC)
fixture("L009-fail", SPEC, drop=("sequence.png",), rule="L009", needle="attachments:")

# L010: a hand edit to the snapshot body
fixture("L010-pass", SPEC)
edited = SNAPSHOT.replace("never refund", "always refund")
assert edited != SNAPSHOT
fixture("L010-fail", SPEC, snapshot=edited, rule="L010", line=3, path=f"specs/{NAME}/ticket.snapshot.md")

# L011: a body change with a bump and entry passes; without a bump fails
changed = replace(SPEC, "What exists today and why", "What exists today, and why")
fixture("L011-pass", bump(changed, 3, "Reworded context."), base=SPEC)
fixture("L011-fail", changed, base=SPEC, rule="L011", needle="revision: 2")

# L012
superseded = replace(
    replace(SPEC, "state: active ", "state: superseded "),
    "superseded_by: null ",
    "superseded_by: 200-plan-changes-v2",
)
fixture("L012-pass", superseded)
fixture(
    "L012-fail",
    replace(SPEC, "state: active ", "state: superseded "),
    rule="L012",
    needle="state: superseded",
)

# L013: the example already mentions AC-3 mid-sentence in a revision; a bare "AC-4:" line warns
fixture("L013-pass", SPEC)
fixture(
    "L013-fail",
    replace(SPEC, "- **AC-3** Proration", "AC-4: something\n- **AC-3** Proration"),
    rule="L013",
    needle="AC-4: something",
)

# Intent specs: the base is what `specs new` writes, with fixed dates and author.
INTENT_NAME = "2026-09-23-webhook-retries"
INTENT_TEXT = render_body((TEMPLATES / "intent.md").read_text(), "Webhook retries", "", "2026-09-23", "jdoe")
INTENT_SPEC = render_frontmatter(
    INTENT_NAME,
    "Webhook retries",
    intent={
        "file": "intent.md",
        "content_sha256": intent_sha256(INTENT_TEXT),
        "recorded_at": "2026-09-23T11:02:00Z",
        "recorded_by": "jdoe",
    },
) + render_body(
    (TEMPLATES / "spec.md").read_text(), "Webhook retries", "[intent.md](intent.md)", "2026-09-23", "jdoe"
)


def intent_fixture(fixture_name, spec, *, rule=None, needle=None, line=None, intent=INTENT_TEXT):
    target = OUT / fixture_name / "head" / INTENT_NAME
    target.mkdir(parents=True)
    (target / "spec.md").write_text(spec)
    if intent is not None:
        (target / "intent.md").write_text(intent)
    if rule:
        if line is None:
            line = line_of(spec, needle)
        (OUT / fixture_name / "expected.json").write_text(
            json.dumps({"rule": rule, "path": f"specs/{INTENT_NAME}/spec.md", "line": line}, indent=2) + "\n"
        )


# L014: an intent spec passes; a spec with neither intent nor ticket fails (reported at the id)
intent_fixture("L014-pass", INTENT_SPEC)
start = INTENT_SPEC.index("intent:\n")
end = INTENT_SPEC.index("revision: 1")
intent_fixture("L014-fail", INTENT_SPEC[:start] + INTENT_SPEC[end:], rule="L014", needle="id: ")

# L015: the intent file must exist
intent_fixture("L015-pass", INTENT_SPEC)
intent_fixture("L015-fail", INTENT_SPEC, intent=None, rule="L015", needle="file: intent.md")

print("\n".join(sorted(p.name for p in OUT.iterdir())))
