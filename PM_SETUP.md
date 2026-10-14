# PM Architecture Setup Guide

## 概要

新しいPM体制では、以下の役割分担で教材を生成します：

```
Claude Code (Worker)
  ↓ ドラフト作成
PM A (Gemini 3 Pro) - 論理性・技術的正確性レビュー
PM B (ChatGPT 5.2) - わかりやすさ・読みやすさレビュー
  ↓ 独立レビュー
PO (ChatGPT 5.2) - 最終判断（approve/revise）
  ↓ 修正指示
Claude Code (Worker) - 修正実装
  ↓ 最大3ラウンド
完成 or 最大ラウンド到達
```

## 環境変数設定

### 必須

```bash
# Gemini API (PM A用)
export GEMINI_API_KEY="your_gemini_api_key_here"

# OpenAI API (PM B & PO用)
export OPENAI_API_KEY="your_openai_api_key_here"
```

### オプション

```bash
# モデル指定（デフォルト値あり）
export CLAUDE_CODE_MODEL="claude-opus-4-5-20251101"
export GEMINI_MODEL="gemini-3-pro"
export CHATGPT_MODEL="gpt-5.2"

# 最大修正ラウンド数（デフォルト: 3）
export MAX_REVISION_ROUNDS=3

# Claude Codeタイムアウト（秒、デフォルト: 300）
export CLAUDE_CODE_TIMEOUT=300
```

## APIキー取得方法

### 1. Gemini API Key

1. https://makersuite.google.com/app/apikey にアクセス
2. Googleアカウントでログイン
3. "Get API Key" をクリック
4. APIキーをコピー

### 2. OpenAI API Key

1. https://platform.openai.com/api-keys にアクセス
2. OpenAIアカウントでログイン
3. "Create new secret key" をクリック
4. 名前を入力（例: "edu-creator-pm"）
5. APIキーをコピー（**一度しか表示されないので注意**）

### 3. Claude Code CLI

月額課金ユーザーは追加のAPIキー設定は不要です。
Claude Code CLIが自動的に認証情報を使用します。

## 使用方法

### 基本

```bash
# 単一章を生成
python edu-creator/main_pm.py --config edu-config.yaml --chapters 1

# 範囲指定
python edu-creator/main_pm.py --config edu-config.yaml --chapters 1-5

# 複数章を個別指定
python edu-creator/main_pm.py --config edu-config.yaml --chapters 1,3,5

# 全章生成
python edu-creator/main_pm.py --config edu-config.yaml
```

### ログレベル指定

```bash
# デバッグモード
python edu-creator/main_pm.py --config edu-config.yaml --chapters 1 --log-level DEBUG

# 警告のみ
python edu-creator/main_pm.py --config edu-config.yaml --chapters 1-5 --log-level WARNING
```

## ワークフロー詳細

### Step 1: Initial Draft Generation (Claude Code)

Claude Codeがリポジトリを調査して初期ドラフトを作成します。

**タスク内容:**
- コードベースの調査
- 関連ファイルの特定
- チュートリアル執筆（Markdown形式）

**使用モデル:** Claude Opus 4.5 (月額課金範囲内)

### Step 2: PM A Review (Gemini)

Gemini 3 Proが論理性・技術的正確性を重点的にレビューします。

**チェック項目:**
- コード例の動作確認
- 技術的な正確性
- 論理的な一貫性
- コマンドの安全性
- 概念の整合性

**出力形式:**
```json
{
  "approval": true/false,
  "review_comment": "全体的な評価",
  "issues": [
    {
      "severity": "critical",
      "category": "技術的誤り",
      "description": "問題の説明",
      "suggestion": "修正案"
    }
  ]
}
```

### Step 3: PM B Review (ChatGPT)

ChatGPT 5.2がわかりやすさ・読みやすさを重点的にレビューします。

**チェック項目:**
- 説明の明瞭性
- トーンの親しみやすさ
- 情報の構造化
- 例の適切性
- 完全性（欠落情報）
- モチベーション維持

**出力形式:** PM Aと同じJSON形式

### Step 4: PO Decision (ChatGPT)

ChatGPT 5.2が2つのPMレビューを統合して最終判断を下します。

**判断基準:**
- 両PM承認 → **APPROVE**
- 片方が重大な問題を指摘 → **REVISE**
- 両方が却下 → **REVISE**（重大度の高い順に優先対応）

**出力形式:**
```json
{
  "final_decision": "approve" or "revise",
  "decision_reason": "判断理由",
  "revision_instructions": "Claude Codeへの修正指示",
  "priority_issues": [
    {
      "source": "PM A",
      "severity": "critical",
      "category": "技術的誤り",
      "description": "問題の説明",
      "suggestion": "修正案"
    }
  ]
}
```

### Step 5: Revision (Claude Code)

REVISE判定の場合、Claude CodeがPOの指示に従って修正します。

**修正内容:**
- 優先度の高い問題から順に対応
- 品質ルールの維持
- 全体構造は保持（特に指示がない限り）

## コスト見積もり

### Claude Code (月額課金 = 無料)

- 全30章の調査・執筆・修正
- 月額サブスクリプション内で無制限使用

### Gemini 3 Pro (API従量課金)

- 30章 × 3ラウンド = 90レビュー
- 推定: ~$1-2

### ChatGPT 5.2 (API従量課金)

- PM B: 30章 × 3ラウンド = 90レビュー
- PO: 30章 × 3ラウンド = 90判断
- 推定: ~$2-3

**合計推定コスト: ~$3-5** (Claude Codeの月額料金除く)

## トラブルシューティング

### エラー: "GEMINI_API_KEY environment variable not set"

```bash
# .envファイルに設定
echo 'GEMINI_API_KEY="your_key_here"' >> .env

# または直接エクスポート
export GEMINI_API_KEY="your_key_here"
```

### エラー: "OPENAI_API_KEY environment variable not set"

```bash
echo 'OPENAI_API_KEY="your_key_here"' >> .env
export OPENAI_API_KEY="your_key_here"
```

### エラー: "Claude Code failed"

1. Claude Code CLIがインストールされているか確認
   ```bash
   claude --version
   ```

2. 認証情報が正しいか確認
   ```bash
   claude --help
   ```

3. 月額サブスクリプションが有効か確認

### PM/POのレビューが厳しすぎる場合

`MAX_REVISION_ROUNDS`を増やすか、品質ルールを調整してください。

```bash
export MAX_REVISION_ROUNDS=5
```

## ファイル構成

```
edu-creator/
├── main_pm.py              # メインワークフロー
├── agents/
│   ├── pm_gemini.py        # PM A (Gemini)
│   ├── pm_chatgpt.py       # PM B (ChatGPT)
│   └── po_chatgpt.py       # PO (ChatGPT)
├── tools/
│   └── claude_code_wrapper.py  # Claude Code CLI wrapper
├── prompt/
│   └── task/
│       └── quality_rules.py    # 品質ルール
└── PM_SETUP.md             # このファイル
```

## 今後の改善予定

- [ ] コンテキストファイルの動的選択
- [ ] レビュー履歴の保存
- [ ] コスト追跡機能
- [ ] 並列処理による高速化
- [ ] PDFバリデーション統合
