#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
lint() {
  uv run ruff check . --select E9,F6,F7,F63,W6,PLE,T10,B006
  # edu-creator 3.0（educreator/）は負債が無いので、最初から全ルールと型検査を強制する。
  # RUF001-003 は日本語の全角の括弧・句読点への誤検知なので外す
  uv run ruff check educreator tests/educreator --ignore RUF001,RUF002,RUF003
  uv run ruff format --check educreator tests/educreator
  uv run mypy educreator
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
