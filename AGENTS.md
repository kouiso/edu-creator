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

## GitHub Project での作業管理

- この repo の作業は GitHub Project（`.github/scrum-board.yml` の番号）で管理する
- 次にやる物を決める・課題を起票する・Status を動かす・繰り越す時は、必ず先に `.agents/skills/scrum-board/SKILL.md`（`.claude/skills/scrum-board/`）を読んでから手を付ける
- 読めない・見つからない場合の要点: 次にやる物=盤の「今週の Iteration」で Wait 空の先頭（無ければ「無し」と答える・issue一覧や open PR から選ばない）・課題は題の頭に `[PBI]`/`[SBI]` を付け sub-issue と盤登録と項目（Iteration・Priority・Estimate・Size）までやる・繰り越しは `kouiso/.github` の `scripts/scrum_keeper/scrum_keeper.py --job carryover|okawari` を使う
- Status は Backlog / In progress / In review / Done の 4 つ。Todo は作らん
