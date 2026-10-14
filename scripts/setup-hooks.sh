#!/usr/bin/env bash
# clone ごとに1回実行: フック有効化 + ローカル専用除外の設定
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/* scripts/guard/*.sh
INFO="$(git rev-parse --git-common-dir)/info"; mkdir -p "$INFO"
touch "$INFO/exclude"
for p in '/reference-local/' '*.reference.md'; do
  grep -qxF "$p" "$INFO/exclude" || echo "$p" >> "$INFO/exclude"
done
[ -s "$INFO/forbidden-patterns" ] || echo "⚠ $INFO/forbidden-patterns を配置してください（1行1正規表現・非公開）" >&2
echo "✔ hooks: $(git config core.hooksPath)"
