---
name: test-first
description: The failing-test-first loop tied to a spec's acceptance criteria, covering the order, what each step proves, the expected failure at every stage, how a test cites the criterion it checks, and the two ways the loop silently becomes worthless. Use when implementing a criterion or a fix, before writing implementation code, and when deciding whether a passing test proves anything.
---

# Test first

Failing test first, wherever the behaviour or the bug can be captured. This is the loop.

## Why the order is the whole thing

A test written after the code it tests is shaped by that code. It passes, it looks like evidence,
and it is indistinguishable afterwards from a test that would have caught the bug. The order is
what makes the difference, and it's the only part that can't be recovered later.

A spec's acceptance criteria are what the tests are written against. A test that could never
have failed satisfies the criterion on paper and proves nothing about it.

## Cite the criterion

Every test that checks an acceptance criterion names it as `<spec-id>:AC-n`, in the test's name
or a comment next to it. The spec id is the spec's directory name, `YYYY-MM-DD-<slug>`; it
qualifies the number because every spec has an AC-1.

```python
def test_503_is_retried_with_backoff():  # 2026-09-23-webhook-retries:AC-1
    ...


def test_400_is_final():  # 2026-09-23-webhook-retries:AC-2
    ...
```

`"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" coverage` lists the criteria no test cites yet. A
citation only proves a test names the criterion; the test still has to exercise what the
criterion says, all of it (a criterion about "backoff" needs a test that sees the delays).

## The loop

### 1. Write the test, and make it fail

Write the smallest test that captures the criterion, or the bug you're fixing. Run it.

**It must fail, and it must fail for the right reason.** This is the step that gets skipped, and
skipping it is what makes the rest theatre.

| What you see | What it means |
|---|---|
| The assertion fails, with your expected value against the actual one | Correct. Continue |
| `ImportError`, a name error, a syntax error | The test is broken, not the code. Fix the test |
| A path or fixture error | The harness is wrong. Fix that first |
| **It passes** | **Stop.** Either the behaviour already exists, or the test asserts nothing. Find out which before writing a line of implementation |

A test that passes before the code exists will pass after it too, whatever you write.

### 2. Write the smallest change that makes it pass

Not the design you have in mind: the smallest thing that turns this test green. The design
pressure arrives in step 3, where the tests are there to catch you. Run it, and the related
tests.

### 3. Tidy, with the tests still green

Rename, extract, collapse the duplication you just created. Run the tests after each change.
If a tidy turns something red, it was a behaviour change dressed as a refactor: undo it and
decide whether you meant it.

### 4. Repeat, and run the suite at the end

One behaviour at a time; the full suite before the work is called done.

## The two ways this becomes worthless

**Writing the test after the code.** The test then describes what the code does rather than what
the criterion says, including its bugs. It is green either way, and stays green through the
regression it was supposed to catch.

**Never watching it fail.** A test never seen red might assert nothing: a wrong path, a mock
that swallows the call, an assertion that's always true. It reports success forever.

Both produce a suite that is large, green, and evidence of nothing.

## When the test shows the spec is wrong

Sometimes writing the test shows the criterion can't be met as written, or contradicts another
one. Don't bend the test to make it pass, and don't quietly change the criterion: stop, and bring
it to `/sdlc:sync`, which amends the spec on purpose with a revision entry.

## Where the loop doesn't apply

- **A bug with no reproduction isn't ready for it.** `/sdlc:bug` gets a reproduction first.
- **Prose, configuration and documentation** have no failing test; use a checker where one
  exists.
- **A spike whose output is an answer** needs no test, because the code is thrown away. Say it's
  a spike rather than quietly skipping the loop.

Where it doesn't apply, say which of these it is. "Hard to test" isn't on the list; it's usually
a statement about the design.

---

The loop follows `superpowers:test-driven-development` (MIT, Copyright (c) 2025 Jesse Vincent).
This is a reimplementation, not a copy, tied to a spec's acceptance criteria and their citations.
