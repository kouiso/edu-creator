#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
mkdir -p "$FIXTURE/scripts/guard" "$FIXTURE/bin"
cp "$ROOT/scripts/ci.sh" "$FIXTURE/scripts/ci.sh"
cat > "$FIXTURE/bin/uv" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf 'uv %s\n' "$*" >> "$CI_CONTRACT_LOG"
[[ "${CI_CONTRACT_FAIL:-}" != "$*" ]]
MOCK
cat > "$FIXTURE/bin/gitleaks" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf 'gitleaks %s\n' "$*" >> "$CI_CONTRACT_LOG"
[[ "${CI_CONTRACT_FAIL:-}" != "gitleaks" ]]
MOCK
cat > "$FIXTURE/scripts/guard/check-forbidden.sh" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf 'guard %s\n' "$*" >> "$CI_CONTRACT_LOG"
[[ "${CI_CONTRACT_FAIL:-}" != "guard" ]]
MOCK
chmod +x "$FIXTURE/bin/uv" "$FIXTURE/bin/gitleaks" "$FIXTURE/scripts/guard/check-forbidden.sh"
export PATH="$FIXTURE/bin:$PATH" CI_CONTRACT_LOG="$FIXTURE/actual"
expected_full=$'guard tree\ngitleaks git --no-banner --redact .\nuv sync --extra dev\nuv run ruff check . --select E9,F6,F7,F63,W6,PLE,T10,B006\nuv run pytest --ignore=tests/test_quality_checker.py'
bash "$FIXTURE/scripts/ci.sh" full
[[ "$(cat "$CI_CONTRACT_LOG")" == "$expected_full" ]]
for failure in guard gitleaks 'sync --extra dev' 'run ruff check . --select E9,F6,F7,F63,W6,PLE,T10,B006' 'run pytest --ignore=tests/test_quality_checker.py'; do
  : > "$CI_CONTRACT_LOG"
  if CI_CONTRACT_FAIL="$failure" bash "$FIXTURE/scripts/ci.sh" full; then
    echo "failure was lost: $failure" >&2; exit 1
  fi
done
: > "$CI_CONTRACT_LOG"
bash "$FIXTURE/scripts/ci.sh" fast
[[ "$(cat "$CI_CONTRACT_LOG")" == 'uv run ruff check . --select E9,F6,F7,F63,W6,PLE,T10,B006' ]]
: > "$CI_CONTRACT_LOG"
if bash "$FIXTURE/scripts/ci.sh" unknown; then exit 1; fi
[[ ! -s "$CI_CONTRACT_LOG" ]]
printf 'PASS shared command closure, five failure boundaries, fast and unknown modes\n'
