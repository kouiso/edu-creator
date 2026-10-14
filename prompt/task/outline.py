"""
=============================================================================
Outline Task Prompts (Commander's Task)
アウトラインタスクプロンプト（Commanderのタスク）

Commander creates a detailed outline based on Scout's research.
CommanderがScoutの調査に基づいて詳細なアウトラインを作成する。
=============================================================================
"""


OUTLINE_TASK_TEMPLATE: str = """
【OUTLINE CREATION】
Based on Scout's research, create a detailed outline for:
Chapter: {chapter_title} {chapter_subtitle}

【CHAPTER BALANCE - VOLUME UNIFORMITY】

ページ数目標: 8-12ページ/章
文字数目標: 4,000-6,000文字/章

Day01の例外: 最大10ページ
（最初の章は軽めにして挫折を防ぐ）

コンテンツ密度ガイドライン:

| Day範囲 | コンテンツ種別 | 目標ページ |
|---------|--------------|-----------|
| Day 01-05 | セットアップ・基礎 | 8-10 |
| Day 06-15 | コア機能 | 10-12 |
| Day 16-25 | 応用機能 | 10-12 |
| Day 26-30 | 仕上げ・デプロイ | 8-10 |

章が薄い場合（6ページ未満）の対策:
1. 「なぜ」セクションを追加（なぜこの技術を使うのか）
2. トラブルシューティング表を追加（よくあるエラーと解決法）
3. 比較表を追加（似た概念の違い）
4. Mermaid図を追加（データフロー、コンポーネント関係）

章が厚い場合（12ページ超）の対策:
1. 2日に分割を検討
2. 高度な内容を別Day（上級者向け）に移動

Requirements:
1. Review Scout's findings
2. Select the best 2-3 code examples to use
3. Create section-by-section outline
4. Specify which metaphor to use for each concept

If Scout's findings are insufficient:
- Use FileReadTool to check files yourself
- Request Scout to search again (max {max_iterations} times)

Output format (in ENGLISH):
```
=== CHAPTER OUTLINE ===
SELECTED CODE EXAMPLES:
  1. [file path] - for explaining [concept]
  2. ...

SECTIONS:
  1. Introduction (Problem)
     - Hook: [what frustration does reader have?]

  2. Core Concept (Solution)
     - Metaphor: [exact metaphor from dictionary]
     - Key points: [bullet points]

  3. Hands-on (Code)
     - Code from: [file path]
     - Explanation approach: [how to walk through]

  4. Verification (tests)
     - How reader can test: [steps]

  5. Summary (key takeaway)
     - One-liner: [takeaway]
```

NO EMOJI: Do not use emojis in the outline or section titles.
"""
"""
【アウトライン作成】
Scoutの調査に基づいて、以下の詳細なアウトラインを作成：
チャプター: {chapter_title} {chapter_subtitle}

要件:
1. Scoutの発見をレビュー
2. 使用する最良の2-3個のコード例を選択
3. セクションごとのアウトラインを作成
4. 各概念に使用するメタファーを指定

Scoutの発見が不十分な場合:
- FileReadToolで自分でファイルを確認
- Scoutに再検索を依頼（最大{max_iterations}回）

出力フォーマット（英語）:
```
=== CHAPTER OUTLINE ===
SELECTED CODE EXAMPLES:
  1. [ファイルパス] - [概念]の説明用
  2. ...

SECTIONS:
  1. Introduction (Problem)
     - Hook: [読者はどんな不満を持っているか？]

  2. Core Concept (Solution)
     - Metaphor: [辞書からの正確なメタファー]
     - Key points: [箇条書き]

  3. Hands-on (Code)
     - Code from: [ファイルパス]
     - Explanation approach: [どう説明を進めるか]

  4. Verification (tests)
     - How reader can test: [手順]

  5. Summary (key takeaway)
     - One-liner: [まとめ]
```

絵文字禁止: アウトラインやセクション名に絵文字を使用しない。
"""


OUTLINE_EXPECTED_OUTPUT: str = "Detailed chapter outline in English"
"""
Expected output description for the outline task.

アウトラインタスクの期待される出力の説明。
詳細なチャプターアウトライン（英語）
"""
