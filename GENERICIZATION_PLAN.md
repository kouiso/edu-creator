# edu-creator 汎用化計画

ステータス: ドラフト（オーナーレビュー待ち）
起点: 別リポジトリの教材（連載の第1弾）を
edu-creatorで作れるようにするため。ただし今回は 別教材 専用の応急対応ではなく、
シリーズ内の今後の教材（デスクトップ版/CLI/ブラウザ拡張/RN/リアルタイム
ダッシュボード、計6本予定）すべてで使い回せる形へ汎用化する。

## 1. 現状（調査結果の要約）

edu-creatorは現在 `task-app`（Next.js + tRPC + Prisma + shadcn/ui）専用に
べったり作られている。具体的には:

| 箇所 | 何がハードコードされているか |
|---|---|
| `main_pm.py`（実際に動いているPM方式パイプライン） | ドラフト生成・レビュープロンプトに「Next.js 15 / tRPC / Prisma / shadcn/ui」という文言を直書き |
| `reviewer.py`（Technical Reviewer） | `@/component/`の単数形importルール、react-hook-form+zod必須、`??`優先、`TASK_STATUS`定数名等、task-app固有の規約を直書き |
| `script/check_tech_stack.py`（品質ゲート5本のうち1本） | MUI/emotion禁止・shadcn/ui必須等、パターンが100% task-app固有 |
| `QualityGate`全般 | `check_code_completeness.py`を**対象リポジトリ側**（task-app/script/）から読む前提。別教材には同等のファイルがまだ無い |
| `_get_context_files`（章執筆時に読み込む参考ファイル） | `src/server/api/routers`というtRPC固有のパスをハードコード |
| `edu-config.yaml`の`chapters` | 30件すべてtask-appの機能（認証/プロジェクト/タスク/コメント等） |
| README.mdのアーキテクチャ説明 | CrewAI+GPT-5.2+Geminiという**実態と食い違う古い情報**（実際はmain_pm.pyがClaude Code自身をworker/leadに使う方式） |

一方、テンプレート（`templates/prompts/*.jinja2`）と`skills/*/SKILL.md`は
比較的汎用的に書かれており、`tech_stack`等の変数を外から注入する作りに
既になっている。ここは汎用化の土台として活かせる。

## 2. 汎用化の方針

**「コードを書き換えなくても、`edu-config.yaml`側の設定だけで別スタック・
別リポジトリに対応できる」を到達目標にする。**

### 2.1 新設定ブロック: `stack_profile`

`edu-config.yaml`に、対象リポジトリのスタック固有情報をまとめた
`stack_profile`ブロックを新設する。現在Pythonコード内にベタ書きされている
文言・ルールは、すべてここから注入する形に置き換える。

```yaml
stack_profile:
  description: |
    React 19 + Vite + TypeScript（素のSPA）、NestJSバックエンド、
    PostgreSQL + Prisma、Capacitorでモバイル配信。
  context_globs:          # 章執筆時に参考として読み込むファイルパターン
    - "material/*.md"
    - "src/modules/**/*.controller.ts"
  coding_conventions:      # レビュー時にチェックする規約（自然言語の箇条書き）
    - "import は @/ エイリアス、名前付きimportのみ"
    - "フォームは react-hook-form + zod"
    - "?? を || より優先"
  lint_rules:              # check_tech_stack.py が読む機械的ルール
    forbidden_imports: ["@mui/*", "@emotion/*"]
    required_libraries: ["@tanstack/react-query"]
  curriculum_approach: "self-contained"   # or "scaffold-script" 等、明示的に選ぶ
```

### 2.2 各ファイルの変更点

| ファイル | 変更内容 |
|---|---|
| `main_pm.py` | `_generate_initial_draft` / `_get_codebase_context` のハードコード文字列を`stack_profile.description`から注入するよう置き換え |
| `reviewer.py` | Technical Reviewerのプロンプトを`stack_profile.coding_conventions`から動的生成 |
| `script/check_tech_stack.py` | Python定数のforbidden/requiredリストを`stack_profile.lint_rules`読み込みに置き換え。スタックが変わってもコード変更不要にする |
| `_get_context_files` | `stack_profile.context_globs`からglobで解決する形に一般化 |
| `check_code_completeness.py` の扱い | edu-creator側に**汎用デフォルト実装**を1つ同梱し、対象リポジトリが独自版を持たない場合はそれにフォールバックする（現状はファイルが無いと`FileNotFoundError`で落ちる） |
| README.md | 実態（main_pm.pyのPM方式：Claude Code sonnet worker + opus lead + reviewer backend抽象化）に合わせて全面改訂。CrewAI/GPT-5.2/Gemini の記述は「旧設計・現在未使用」と明記するか削除 |
| `curriculum_approach` | 「自己完結型か、scaffoldスクリプト配布か」を`stack_profile`で明示選択制にする（現状は設定と実際の生成内容が食い違うバグがある） |

### 2.3 別教材向け `stack_profile` の初期案

上記スキーマに沿って、別教材用の値は以下を想定（`02_技術選定書.md`と
`05_DB設計書.md`から起こす）。実際の投入はedu-config.yaml新規作成時に行う。

```yaml
stack_profile:
  description: |
    React 19 + Vite + TypeScript（素のSPA、フルスタックフレームワークは不使用）、
    NestJSバックエンド、PostgreSQL + Prisma、Capacitorで iOS/Android 配信、
    リアルタイム通知はNestJS WebSocket Gateway、キャッシュ/レート制限はRedis、
    非同期ジョブはBullMQ。
  context_globs:
    - "material/*.md"
  coding_conventions:
    - "ルーティングはReact Router v7（ライブラリモード、SSR等のフレームワーク機能は不使用）"
  lint_rules:
    forbidden_imports: []   # 詳細設計確定後に追記
    required_libraries: []
  curriculum_approach: "self-contained"
```

## 3. 「3回推敲済み」表記の扱い

現状は「PO承認まで最大3ラウンド試行し、承認が出なくても警告付きでそのまま保存」
というベストエフォート実装。汎用化と直接の依存関係はないため、本計画では
**表記を実態に合わせて正直にする**（例:「最大3回の推敲プロセスを経て作成」）
に留め、承認ループの強化自体は別課題として切り出す。

## 4. 実装の進め方

本計画（設計判断）はClaude副長が担当したが、実際のコード変更
（`main_pm.py` / `reviewer.py` / `check_tech_stack.py` / README改訂等）は
Codexに委譲する（オーナー指示の「Claude=思考、Codex=実行」の原則）。

1. 本計画にオーナー承認
2. Codexへ実装委譲（`stack_profile`スキーマ追加 → 各ファイルの注入先置き換え →
   `check_code_completeness.py`汎用デフォルト実装 → README改訂）
3. task-appの既存30日教材で**回帰確認**（stack_profileにtask-appの値を入れて
   再生成し、既存の日次記事と実質的に同内容が生成されることを確認）
4. 別教材向け`stack_profile`を投入し、章1本を試験生成してレビューが通ることを確認

## 5. 未決定事項（オーナー判断）

- `check_code_completeness.py`の汎用デフォルト実装の中身（何を機械チェックするか）
  はスタック非依存にできる範囲でどこまで作り込むか
- README全面改訂のタイミング（汎用化の実装と同時 or 別PR）
