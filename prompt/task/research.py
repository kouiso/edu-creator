"""
=============================================================================
🔬 Research Task Prompts (Scout's Task)
リサーチタスクプロンプト（Scoutのタスク）

Scout searches the repository for beginner-friendly code examples.
Scoutがリポジトリから初心者向けのコード例を検索する。
=============================================================================
"""


RESEARCH_TASK_TEMPLATE: str = """
【RESEARCH MISSION】
Chapter: {chapter_title} {chapter_subtitle}
Topics to cover: {topics}
Priority directories: {target_dirs}

Your job:
1. Search the repository for code examples related to: {topics}
2. Find 3-5 beginner-friendly code snippets
3. Report each finding with: file path, line numbers, why it's good for beginners

IMPORTANT:
- Skip excluded directories (node_modules, .next, dist, etc.)
- Prioritize short, readable code (under 30 lines ideal)
- Report in ENGLISH

Expected output format:
```
=== RESEARCH REPORT ===
FINDING 1:
  FILE: src/...
  LINES: X-Y
  TOPIC: [which topic this covers]
  WHY GOOD: [why beginners will understand this]

FINDING 2:
  ...
```
"""
"""
【リサーチミッション】
チャプター: {chapter_title} {chapter_subtitle}
カバーするトピック: {topics}
優先ディレクトリ: {target_dirs}

あなたの仕事:
1. {topics}に関連するコード例をリポジトリから検索
2. 3-5個の初心者向けコードスニペットを見つける
3. 各発見について報告：ファイルパス、行番号、なぜ初心者に良いか

重要:
- 除外ディレクトリをスキップ（node_modules, .next, dist等）
- 短く読みやすいコードを優先（理想は30行以下）
- 英語で報告

期待される出力フォーマット:
```
=== RESEARCH REPORT ===
FINDING 1:
  FILE: src/...
  LINES: X-Y
  TOPIC: [どのトピックをカバーするか]
  WHY GOOD: [なぜ初心者が理解しやすいか]

FINDING 2:
  ...
```
"""


RESEARCH_EXPECTED_OUTPUT: str = "Research report with 3-5 code findings in English"
"""
Expected output description for the research task.

リサーチタスクの期待される出力の説明。
3-5個のコード発見を含むリサーチレポート（英語）
"""
