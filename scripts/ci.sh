#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
lint() {
  uv run ruff check . --select E9,F6,F7,F63,W6,PLE,T10,B006
}
tests() {
  uv run pytest --ignore=tests/test_quality_checker.py
}
case "${1:-full}" in
  fast|lint) lint ;;
  test) tests ;;
  full)
    bash scripts/guard/check-forbidden.sh tree
    gitleaks git --no-banner --redact .
    uv sync --extra dev
    lint
    tests
    ;;
  *) echo 'Usage: bash scripts/ci.sh {fast|lint|test|full}' >&2; exit 2 ;;
esac
