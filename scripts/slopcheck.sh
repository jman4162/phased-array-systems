#!/usr/bin/env bash
# slopcheck.sh — pre-publish AI-slop linter for phased-array-systems prose.
#
# Runs two local, no-network slop linters over Markdown files:
#   - slopscore-lint (https://github.com/jman4162/slopscore)   -> 0-100 SlopScore
#   - slopless       (https://github.com/seochecks-ai/slopless) -> rule findings
#
# Advisory by default: review findings by hand and ignore deliberate
# house style. With --strict, exits non-zero on high-severity
# slopscore findings (for CI).
#
# Known domain false positive: slopscore flags "dynamic" as a
# sophistication adjective; here it is almost always "dynamic range".
#
# Usage:
#   scripts/slopcheck.sh                       # default doc set
#   scripts/slopcheck.sh README.md docs/*.md   # explicit files
#   scripts/slopcheck.sh --strict README.md
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

STRICT=0
if [ "${1:-}" = "--strict" ]; then
  STRICT=1
  shift
fi

if [ $# -gt 0 ]; then
  files=("$@")
else
  files=("$ROOT/README.md" "$ROOT/CHANGELOG.md")
  while IFS= read -r f; do
    files+=("$f")
  done < <(find "$ROOT/docs" -name "*.md" -not -path "*/node_modules/*" 2>/dev/null | sort)
fi

missing=0
for f in "${files[@]}"; do
  if [ ! -f "$f" ]; then
    echo "[slopcheck] not found: $f" >&2
    missing=1
  fi
done
[ "$missing" -eq 1 ] && exit 2

echo "===== slopscore-lint (jman4162) ====="
venv="$ROOT/scripts/.slopvenv"
if [ ! -x "$venv/bin/slopscore-lint" ]; then
  echo "[slopcheck] installing slopscore-lint into $venv ..." >&2
  python3 -m venv "$venv" >/dev/null 2>&1 && "$venv/bin/pip" install -q slopscore-lint >/dev/null 2>&1
fi
slopscore_rc=0
if [ -x "$venv/bin/slopscore-lint" ]; then
  if [ "$STRICT" -eq 1 ]; then
    "$venv/bin/slopscore-lint" scan "${files[@]}" --profile technical --fail-on high || slopscore_rc=$?
  else
    "$venv/bin/slopscore-lint" scan "${files[@]}" --profile technical || true
  fi
else
  echo "[slopcheck] slopscore-lint unavailable (install failed); skipping." >&2
fi

echo
echo "===== slopless (seochecks-ai) ====="
if command -v npx >/dev/null 2>&1; then
  npx -y slopless "${files[@]}" 2>/dev/null | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
except Exception:
    print("[slopcheck] slopless produced no parseable output."); sys.exit(0)
# Markdown-formatting and readability rules that fight deliberate doc
# style are hidden; readability scores are meaningless for changelogs
# and API docs full of code identifiers.
ignore = {"slopless/word-repetition", "slopless/paragraph-length",
          "slopless/smart-quotes", "slopless/sentence-case",
          "slopless/coleman-liau", "slopless/flesch-kincaid",
          "slopless/gunning-fog"}
shown = hidden = 0
for result in data or []:
    path = result.get("filePath", "?")
    for m in result.get("messages", []):
        if m.get("ruleId") in ignore:
            hidden += 1
            continue
        shown += 1
        print("  " + str(path) + ":" + str(m.get("line", "?")) + " "
              + str(m.get("ruleId")) + ": " + str(m.get("message")))
print("[slopcheck] slopless: " + str(shown) + " substantive finding(s); "
      + str(hidden) + " style/readability rule(s) hidden.")
' || true
else
  echo "[slopcheck] npx not found; skipping slopless." >&2
fi

echo
if [ "$STRICT" -eq 1 ]; then
  exit "$slopscore_rc"
fi
echo "[slopcheck] Advisory only. Review findings; ignore deliberate house style."
