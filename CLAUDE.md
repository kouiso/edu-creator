## Codex Cloud
**ENV_ID**: `69f339214d408191b596286f9291849e`  — `codex cloud exec --env 69f339214d408191b596286f9291849e "<task>"`

## 参照情報の取り扱い（最重要）

外部案件・顧客・他リポジトリの参照情報（固有名・ローカル絶対パス・社名）は絶対に commit / push しない。clone 後は `scripts/setup-hooks.sh` を実行し、`--no-verify` は使わない。詳細は AGENTS.md。
