"""
=============================================================================
Content PM Review Task Prompts
# コンテンツPMレビュータスクプロンプト

Content PM reviews the tutorial for structure, flow, and storytelling.
# コンテンツPMが構成・フロー・ストーリーテリングをレビューする。
=============================================================================
"""


CONTENT_REVIEW_TASK_TEMPLATE: str = """
# 【CONTENT PM REVIEW】
# Review tutorial structure and flow for: {chapter_title}
# 
# あなたの専門:
# - 構成・フロー・ストーリーテリング
# - 読者体験の設計
# - 学習の段階設計
# 
# STRUCTURE CHECKLIST:
# □ 導入で「なぜこれを学ぶのか」が明確
# □ 各セクションの順序が論理的
# □ 前のセクションが次のセクションの土台になっている
# □ 最後に「できるようになったこと」のまとめがある
# 
# FLOW CHECKLIST:
# □ 説明 → 例示 → 実践 の流れが守られている
# □ 抽象的な説明の直後に具体例がある
# □ 「なぜ？」に対する答えが必ず書かれている
# □ 読者が「次は何？」と思う箇所で適切に誘導している
# 
# STORYTELLING CHECKLIST:
# □ 比喩が一貫している（途中で比喩を変えていない）
# □ 比喩が適切（技術概念を正しく表現している）
# □ 読者の感情に配慮している（「難しそう」→「できそう」への変化）
# □ 達成感を感じられるポイントがある
# 
# PACING CHECKLIST:
# □ 情報量が適切（1セクションに詰め込みすぎていない）
# □ 休憩ポイント（まとめ、確認問題など）がある
# □ 難易度の上昇が緩やか
# □ 「ここまでの振り返り」がある
# 
# OUTPUT FORMAT:
# ```
# === CONTENT PM REVIEW ===
# STATUS: [APPROVED / NEEDS REVISION]
# 
# STRUCTURE:
# - 導入の明確さ: [PASS/FAIL] [詳細]
# - セクション順序: [PASS/FAIL] [詳細]
# - 段階設計: [PASS/FAIL] [詳細]
# - まとめの存在: [PASS/FAIL] [詳細]
# 
# FLOW:
# - 説明→例示→実践: [PASS/FAIL] [詳細]
# - 具体例の配置: [PASS/FAIL] [詳細]
# - 「なぜ？」への回答: [PASS/FAIL] [詳細]
# - 誘導の適切さ: [PASS/FAIL] [詳細]
# 
# STORYTELLING:
# - 比喩の一貫性: [PASS/FAIL] [詳細]
# - 比喩の適切さ: [PASS/FAIL] [詳細]
# - 感情への配慮: [PASS/FAIL] [詳細]
# - 達成感ポイント: [PASS/FAIL] [詳細]
# 
# PACING:
# - 情報量: [PASS/FAIL] [詳細]
# - 休憩ポイント: [PASS/FAIL] [詳細]
# - 難易度上昇: [PASS/FAIL] [詳細]
# - 振り返り: [PASS/FAIL] [詳細]
# 
# ISSUES (if any):
# 1. [具体的な問題と場所]
# 2. ...
# 
# SUGGESTIONS:
# 1. [具体的な改善案]
# 2. ...
# ```
"""


CONTENT_REVIEW_EXPECTED_OUTPUT: str = """
Content PM review with:
- Structure evaluation (introduction, section order, gradual building, summary)
- Flow evaluation (explain→example→practice pattern)
- Storytelling evaluation (metaphor consistency, emotional journey)
- Pacing evaluation (information density, rest points, difficulty curve)
- Specific issues and suggestions

# コンテンツPMレビュー:
# - 構成評価（導入、セクション順序、段階設計、まとめ）
# - フロー評価（説明→例示→実践パターン）
# - ストーリーテリング評価（比喩の一貫性、感情の旅）
# - ペーシング評価（情報密度、休憩ポイント、難易度曲線）
# - 具体的な問題と改善案
"""
