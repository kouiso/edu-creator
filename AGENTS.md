# AGENTS.md

## Overview
edu-creator - kouiso プロジェクト

## Development

### Language & Frameworks
- (auto-detect required)

### Setup
```bash
# See project documentation
```

### Code Style
- 日本語でコメント・ドキュメントを記述
- 既存コードスタイルに従う

### Testing
```bash
# See project documentation
```

## 参照情報の取り扱い（最重要・AI含む全員）

- 外部案件・顧客・他リポジトリの参照情報（固有名、ローカルの絶対パス、社名、案件名）は**絶対に commit / push しない**。
- 参照ファイルはローカル専用（`.git/info/exclude` か `/reference-local/`）に置く。
- clone したら最初に `scripts/setup-hooks.sh` を実行する。pre-commit / commit-msg / pre-push フックが禁止語と秘密（gitleaks）を検知すると拒否する。
- フックを `--no-verify` で回避しない。CI でも同じチェックが走る。
- 同じ内容を issue・PR・コメントの題や本文にも書かない（公開リポなので誰でも読める）。
- 自動で見張るのは、秘密の値・秘密の名前・データベースの接続情報・個人のメールアドレスだけ。弱点や攻め方の手順、顧客の名前と金額は自動では検査しない。書く人が自分で確かめ、投稿しない。

## GitHub Project での作業管理

- この repo のボードの設定は `.github/scrum-board.yml` にある
- 手順は global skill `scrum-board` に従う

## 旧 CLAUDE.md から移行した指示

## Codex Cloud
**ENV_ID**: `69f339214d408191b596286f9291849e`  — `codex cloud exec --env 69f339214d408191b596286f9291849e "<task>"`

## 参照情報の取り扱い（最重要）

外部案件・顧客・他リポジトリの参照情報（固有名・ローカル絶対パス・社名）は絶対に commit / push しない。clone 後は `scripts/setup-hooks.sh` を実行し、`--no-verify` は使わない。issue・PR・コメントの本文にも書かない。弱点や攻め方の手順、顧客の名前と金額は自動検査の対象外なので、書く人が投稿しない。詳細は AGENTS.md。
