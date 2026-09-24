# Adopting the `sdlc` plugin

For a team that wants to try spec-driven development in a repository it already works in. The
plugin enforces nothing: it advises, drafts and checks, and people decide. So adoption is a
matter of habits, not of rolling out gates, and a team can stop at any time by uninstalling it.

## Before you start

- **Agree on what gets a spec.** Substantial changes do: new behaviour, a changed contract, a
  migration, anything crossing a trust boundary. A one-line fix doesn't. Write the line down
  where the team will see it.
- **Agree on who reviews specs.** One group to start (a tech lead and a product person, say);
  per-area routing can come later.
- **Each engineer needs** Claude Code, Python 3.10 or later and PyYAML on their machine. The
  plugin makes no network calls and needs no credentials.

## Install

Once per machine:

```sh
claude plugin marketplace add <path-or-url-of-the-plugin-repository>
claude plugin install sdlc@sdlc
```

Once per repository, from a session in it:

```
/sdlc:init
```

It writes `specs/config.yml`, the spec and intent templates under `specs/templates/` (edit them
to suit the team), a `.gitignore` rule for local working files, and a short section in
`CLAUDE.md`. It commits nothing, and prints two things to apply by hand on the code host:

- the `CODEOWNERS` entry that routes `specs/` to the spec reviewers;
- the branch settings for requirements R1 to R4 in `docs/workflow.md` section 4 (spec approval,
  what resets it, trailers surviving a squash), with the GitLab and GitHub specifics in
  section 10.2.

Commit what `/sdlc:init` wrote, and point the team at `docs/workflow.md`: it is the model the
commands follow.

## Your first change

Pick something real but modest, with a request someone else wrote. If it isn't written down
yet, whoever has the problem can write it with **`/sdlc:intent`** first: an interview in their
words that produces the intent file, under the id the spec will keep.

1. **`/sdlc:start`** with the request: an `intent.md`, a file, or the text pasted in. It points
   out the gaps in the request and offers to fill them with you (or to go ahead as it is), then
   drafts the spec.
2. **`/sdlc:clarify`** works the spec's open questions down to recorded decisions.
3. **`/sdlc:propose`** says whether the spec is ready for review and writes the spec commit
   message and the draft PR text. Commit, push, open the draft PR; reviewers approve the spec.
4. **`/sdlc:plan`** writes your working plan, `plan.local.md`, which git ignores.
5. **`/sdlc:implement`** works through it, test first, a commit per step with the spec's
   trailers. If the spec turns out wrong, it stops and `/sdlc:sync` amends the spec on purpose.
6. **`/sdlc:check`** before committing spec changes, and at the end: lint, criteria no test
   cites, whether the intent moved.
7. **`/sdlc:converge`** before marking the PR ready: a verdict per criterion and any change no
   criterion explains.
8. **`/sdlc:pr-msg`** for the PR description; then review and merge. The merged spec is the
   frozen record of what shipped.

Along the way: `/sdlc:analyze` for a deeper read of a spec against its intent, `/sdlc:sync`
when the intent changes, `/sdlc:commit-msg` for any commit, `/sdlc:handoff` to pause a session
and resume it later, `/sdlc:bug` for a bug. The session status line at startup says which spec
the branch is on and whether anything needs attention.

## Is it working?

Nothing is collected automatically. A team that wants to know reads these by hand from `git log`
and the code host's PR history, over a few weeks of changes. Each is one of the workflow's
signals (`docs/workflow.md` section 12).

| Signal | How to read it |
|---|---|
| **Intent changes after the spec was written** | `git log --format='%h %ad %(trailers:key=Spec-Change,valueonly)' -- specs/<id>/` per spec: `acknowledge` and `amend` commits after the first commit whose `Implements` trailer names that spec |
| **Changed intents caught before merge** | For each `intent.md` edit on a branch (`git log -- specs/<id>/intent.md`), whether an `acknowledge` or `amend` commit follows before the merge commit |
| **Spec-first rate** | In each spec PR's timeline on the code host: the spec reviewer's approval, and the first commit whose `Implements` trailer isn't empty. Approval first counts as spec-first |
| **Converge findings at review time** | The converge summary line in each PR description (`/sdlc:pr-msg` carries it): the `MISSING` and `UNJUSTIFIED` counts, change by change |
| **Ceremony cost** | The code host's PR timeline: draft PR opened to spec approval. A median over a day means the process is too heavy |

Two more worth asking the engineers directly: whether they ran `/sdlc:check` and `/sdlc:sync`
without being told to, and where the plugin got in the way. The friction is the finding; the
templates, the team's conventions and `docs/workflow.md` are all meant to be adjusted.

## When it isn't working

- **Specs arrive after the code.** Review the spec first as a convention, and look at the
  spec-first rate; tooling can't fix the habit.
- **Spec review takes days.** Smaller specs, fewer reviewers, or specs only for changes that
  really need one.
- **Intents keep changing mid-change.** That's what `/sdlc:sync` is for; if it happens on most
  changes, the requests need more time before a spec starts.
