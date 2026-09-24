#!/bin/sh
# After Claude edits a spec.md, remind once when its body changed since the version reviewers can
# already see (the branch's upstream) and the revision wasn't bumped. Advice only: always exits 0,
# and says nothing whenever it can't tell (no upstream, spec not pushed, helper unavailable).

input=$(cat)
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

file=$(printf '%s' "$input" | python3 -c '
import json, sys
print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
' 2>/dev/null) || exit 0

# Only <specs_dir>/<spec-id>/spec.md, never the templates; everything else leaves before the helper.
spec_dir=
for dir in specs .specs; do
    [ -f "$root/$dir/config.yml" ] || continue
    case "$file" in
        "$root/$dir/templates/"*) ;;
        "$root/$dir/"*/spec.md)
            id=${file#"$root/$dir/"}
            id=${id%/spec.md}
            case "$id" in */*) ;; *) spec_dir="$dir/$id" ;; esac
            ;;
    esac
done
[ -n "$spec_dir" ] || exit 0

helper="${CLAUDE_PLUGIN_ROOT:-}/tools/specs/specs"
[ -x "$helper" ] || exit 0
upstream=$(git -C "$root" rev-parse --verify -q '@{upstream}') || exit 0
git -C "$root" cat-file -e "$upstream:$spec_dir/spec.md" 2>/dev/null || exit 0

(cd "$root" && "$helper" lint --only L011 --base "$upstream" "$spec_dir") >/dev/null 2>&1
[ $? -eq 1 ] || exit 0

message="sdlc: ${spec_dir##*/} changed since the pushed version without a revision bump: bump 'revision' and add a '## Revisions' entry saying what changed and why."
printf '{"systemMessage": "%s", "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "%s"}}\n' \
    "$message" "$message"
exit 0
