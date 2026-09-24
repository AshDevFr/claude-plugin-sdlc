<!-- sdlc:begin -->
## Specs

This repository uses spec-driven development with the `sdlc` plugin. A change that deserves a
spec gets a directory under `$specs_dir/`:

- `intent.md` is the original request, in the words of whoever has the problem. It may be
  imperfect; improving it is offered, never required.
- `spec.md` is the contract: what the team reviews in the pull request, what the code is built
  against, and what tests cite as `<spec-id>:AC-<n>`.

Start a change with `/sdlc:start`. Run `/sdlc:check` before committing spec changes. When
`intent.md` changes after the spec was written, or the spec turns out to be wrong, run
`/sdlc:sync`.

Commits on a spec'd change end with these trailers:

```
Spec: <spec-id>@r<revision>
Implements: AC-1, AC-3
Spec-Change: <kind>        (only on commits that change the spec)
```
<!-- sdlc:end -->
