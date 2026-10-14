#!/usr/bin/env bash
# 参照情報・秘密の混入チェック。禁止語リストはリポジトリに含めない（ローカル or CI secret）。
# 使い方: check-forbidden.sh staged | range <base> <head> | commits <head>(リモート未到達の全commit) | tree
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
LIST="${EDU_GUARD_PATTERNS_FILE:-$(git rev-parse --git-common-dir)/info/forbidden-patterns}"
if [ ! -s "$LIST" ]; then
  echo "✖ 禁止語リストがありません: $LIST" >&2
  echo "  scripts/setup-hooks.sh を実行し、リストを配置してください（中身は公開しない）。" >&2
  exit 1
fi
PAT="$(grep -vE '^\s*(#|$)' "$LIST" | paste -sd'|' -)"
mode="${1:-staged}"; fail=0
scan() { # stdin=text, $1=label
  local hits; hits="$(grep -niE -- "$PAT" || true)"
  if [ -n "$hits" ]; then echo "✖ 禁止語を検出 ($1):" >&2; echo "$hits" | sed 's/^/    /' | head -20 >&2; fail=1; fi
}
case "$mode" in
  staged)
    scan "ファイル名" < <(git diff --cached --name-only --diff-filter=ACMR)
    scan "追加行" < <(git diff --cached -U0 --no-color | grep -E '^\+' | grep -vE '^\+\+\+ ')
    if command -v gitleaks >/dev/null; then gitleaks git --staged --no-banner --redact -l error "$ROOT" || fail=1
    else echo "⚠ gitleaks 未インストール（秘密検査をスキップ）" >&2; fi ;;
  range|commits)
    if [ "$mode" = range ]; then commits="$(git rev-list "$2..$3")"; logopt="$2..$3"
    else commits="$(git rev-list "$2" --not --remotes)"; logopt="$2 --not --remotes"; fi
    for c in $commits; do
      scan "commit $c メタ/ファイル名" < <(git show --format='%an <%ae>%n%B' --name-only "$c")
      scan "commit $c 追加行" < <(git show --format= -U0 --no-color "$c" | grep -E '^\+' | grep -vE '^\+\+\+ ')
    done
    if command -v gitleaks >/dev/null; then gitleaks git --log-opts="$logopt" --no-banner --redact -l error "$ROOT" || fail=1; fi ;;
  tree)
    scan "ファイル名" < <(git ls-files)
    git grep -niE -- "$PAT" >/dev/null 2>&1 && { git grep -niE -- "$PAT" | head -20 >&2; fail=1; } || true
    scan "全commitメタ" < <(git log --all --format='%an <%ae>%n%B') ;;
esac
[ $fail -eq 0 ] || { echo "✖ 拒否しました。参照情報はcommit/pushしないこと（AGENTS.md参照）。" >&2; exit 1; }
