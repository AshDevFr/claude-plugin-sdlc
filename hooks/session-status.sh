#!/bin/sh
# One status line for the current branch's spec at session start. Silent outside a repository
# set up for sdlc, and silent whenever the helper can't run: a status line must never get in
# the way of starting work.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -f "$root/specs/config.yml" ] || [ -f "$root/.specs/config.yml" ] || exit 0

helper="${CLAUDE_PLUGIN_ROOT:-}/tools/specs/specs"
[ -x "$helper" ] || exit 0

line=$(cd "$root" && "$helper" status 2>/dev/null) || exit 0
[ -n "$line" ] && printf 'sdlc: %s\n' "$line"
exit 0
