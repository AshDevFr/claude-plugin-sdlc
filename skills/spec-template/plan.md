# Plan: <spec title>

Spec: `<spec-id>` at r<n>. A local working plan: git ignores `plan.local.md`; rename it
`plan.md` only to commit it on purpose.

## Approach

<Two to five sentences: how the spec's Design gets built in this codebase as it is today, and
the order that makes each step testable.>

## Steps

### 1. <what this step delivers>

- **Criteria:** `<spec-id>:AC-1`
- **Test first:** <the failing test: its file, its name, what it asserts, and why it fails today>
- **Change:** <the files touched and what changes in each>
- **Done when:** <the test passes, and anything else observable>

### 2. <...>

## Criteria map

| Criterion | Steps |
|---|---|
| AC-1 | 1 |

Every criterion that isn't struck has at least one step.

## Risks and unknowns

<What reading the code showed that the spec doesn't cover. If it changes what a criterion
requires, that's for `/sdlc:sync`, not a quiet deviation in the plan.>
