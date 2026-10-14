# 品質向上システム（6つの柱）

edu-creatorに適用された「AIフィーチャーリファクタリングの6つの柱」の実装ガイド。

## 概要

| 柱 | 機能 | ファイル |
|:---|:-----|:---------|
| 1 | プロンプト構造化 | `prompt/task/write.py` |
| 2 | CoT（思考制御） | `utils/cot_parser.py` |
| 3 | タスク分解 | `prompt/task/write.py` (セクション単位) |
| 4 | RAG（前章参照） | `utils/chapter_context.py` |
| 5 | 評価エンジニアリング | `utils/llm_judge.py`, `tests/ai/golden_dataset.py` |
| 6 | デバッグ・可観測性 | `utils/structured_logger.py`, `utils/debugger.py` |

---

## 使用方法

### 1. 構造化ログの使用

```python
from utils import EnhancedPipeline, create_enhanced_pipeline

# パイプラインを作成
pipeline = create_enhanced_pipeline("logs/day01")

# リクエスト開始
request_id = pipeline.start_request()

# AI呼び出しをログに記録
pipeline.log_request(
    agent_name="Scout",
    task_type="research",
    chapter_id="day01",
    model="gemini-2.0-flash",
    response_time_ms=1500,
    output_summary="5件のファイルを検索",
)
```

### 2. CoTレスポンスのパース

```python
from utils import parse_cot_response

# AIの生レスポンスをパース
raw_response = """
<thinking>
読者の疑問: なぜDockerが必要なのか？
メタファー: キッチン
</thinking>

<tutorial>
# Day 01: 環境構築
...
</tutorial>

<metadata>
{"word_count": 4500, "tables_count": 5}
</metadata>
"""

parsed = parse_cot_response(raw_response)
print(parsed.thinking)  # 思考過程（デバッグ用）
print(parsed.tutorial)  # 実際のチュートリアル
print(parsed.metadata)  # メタデータ
```

### 3. 前章コンテキストの取得

```python
from utils import build_context_for_chapter, format_context_for_prompt

# Day 02執筆時に、Day 01のコンテキストを取得
context = build_context_for_chapter(
    chapter_num=2,
    output_dir=Path("output")
)

# プロンプト用にフォーマット
context_str = format_context_for_prompt(context)
print(context_str)
# 出力:
# 【既に説明済みの用語（再説明不要）】
# Docker, npm, Node.js, ...
```

### 4. LLM-as-Judge評価（GPT-4o/5.2）

```bash
# 単一ファイル評価
python script/evaluate.py material/30days-curriculum/day01_*.md

# 全教材評価
python script/evaluate.py --all --output report.json

# ゴールデンテスト実行
python script/evaluate.py --golden-test
```

```python
from utils.llm_judge import LLMJudge

judge = LLMJudge(model="gpt-4o")
result = judge.evaluate_file(Path("day01.md"))

print(f"総合スコア: {result.overall_score}")
print(f"合格: {result.passed}")
print(f"問題点: {result.critical_issues}")
```

### 5. 品質問題の診断

```python
from utils import diagnose_quality_failure, print_diagnosis_report

# バリデーションエラーから原因を診断
errors = ["禁止ワード「同様に」が検出されました", "テーブルが3個しかありません"]

diagnosis = diagnose_quality_failure(
    chapter_id="day01",
    validation_errors=errors,
    log_dir=Path("logs/day01")
)

# 診断結果を表示
print_diagnosis_report(diagnosis)
# 出力:
# 原因カテゴリ: prompt
# 詳細: 思考過程にメタファーへの言及がありません
# 修正提案: プロンプトでメタファー使用の指示を強化してください
```

---

## ディレクトリ構造

```
edu-creator/
├── utils/
│   ├── __init__.py           # パッケージエクスポート
│   ├── structured_logger.py  # 柱6: 構造化ログ
│   ├── cot_parser.py         # 柱2: CoTパーサー
│   ├── chapter_context.py    # 柱4: 前章コンテキスト
│   ├── llm_judge.py          # 柱5: LLM-as-Judge
│   ├── debugger.py           # 柱6: 問題診断
│   └── integration.py        # 統合モジュール
├── tests/
│   └── ai/
│       ├── __init__.py
│       └── golden_dataset.py # 柱5: ゴールデンデータセット
├── script/
│   └── evaluate.py           # 柱5: 評価スクリプト
└── prompt/
    └── task/
        └── write.py          # 柱1,2,3: 構造化プロンプト
```

---

## 評価基準

LLM-as-Judgeは以下の5項目で評価:

| 項目 | 説明 | 合格基準 |
|:-----|:-----|:---------|
| clarity | 明確さ | ≥4 |
| accessibility | アクセシビリティ | ≥4 |
| engagement | 引き込み | ≥4 |
| actionability | 実行可能性 | ≥4 |
| self_containment | 自己完結性 | ≥4 |
| **overall_score** | **総合（平均）** | **≥4.0** |

---

## 検証コマンド

```bash
# 構文確認
python -c "from utils import *; print('✅ Import OK')"

# 単体テスト
python script/evaluate.py --golden-test

# 全教材評価
python script/evaluate.py --all --output report.json
```

---

## 注意事項

1. **OpenAI API**: LLM-as-JudgeにはOpenAI APIキーが必要
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **コスト**: GPT-4oで1章あたり約$0.05-0.10

3. **後方互換性**: 既存の`quality_checker.py`はそのまま使用可能

---

**最終更新: 2025-02-03**
