"""
=============================================================================
Quality PM Review Task Prompts
# 品質PMレビュータスクプロンプト

Quality PM reviews the tutorial for technical accuracy and code verification.
# 品質PMが技術的正確性とコード検証をレビューする。
=============================================================================
"""


QUALITY_REVIEW_TASK_TEMPLATE: str = """
# 【QUALITY PM REVIEW】
# Review technical accuracy for: {chapter_title}
# 
# あなたの専門:
# - 技術的正確性
# - コードの検証
# - ドキュメントとの整合性
# 
# TECHNICAL ACCURACY CHECKLIST:
# □ 技術用語が正確に使われている
# □ 説明が技術的に正しい（誤解を招く表現がない）
# □ バージョン情報が明記されている（必要な場合）
# □ 非推奨の方法を推奨していない
# 
# CODE VERIFICATION CHECKLIST:
# □ コードブロックが実際のプロジェクトコードと一致
# □ ファイルパスが正確
# □ インポート文が正しい
# □ コードが実行可能（構文エラーがない）
# □ 省略部分に「// ... 略 ...」等の明示がある
# 
# CROSS-REFERENCE CHECKLIST:
# □ Scoutの調査結果と矛盾していない
# □ 他のチャプターとの整合性がある
# □ プロジェクトの実際の構成と一致
# 
# COMMAND VERIFICATION CHECKLIST:
# □ コマンドが正確（タイポがない）
# □ 実行環境が明記されている（どのディレクトリで実行するか）
# □ 期待される出力が正確
# 
# OUTPUT FORMAT:
# ```
# === QUALITY PM REVIEW ===
# STATUS: [APPROVED / NEEDS REVISION]
# 
# TECHNICAL ACCURACY:
# - 用語の正確さ: [PASS/FAIL] [詳細]
# - 説明の正しさ: [PASS/FAIL] [詳細]
# - バージョン情報: [PASS/FAIL] [詳細]
# - 推奨方法の妥当性: [PASS/FAIL] [詳細]
# 
# CODE VERIFICATION:
# - コードの一致: [PASS/FAIL] [詳細]
# - ファイルパス: [PASS/FAIL] [詳細]
# - インポート文: [PASS/FAIL] [詳細]
# - 構文の正しさ: [PASS/FAIL] [詳細]
# - 省略の明示: [PASS/FAIL] [詳細]
# 
# CROSS-REFERENCE:
# - Scout調査との整合: [PASS/FAIL] [詳細]
# - 他チャプターとの整合: [PASS/FAIL] [詳細]
# - プロジェクト構成との一致: [PASS/FAIL] [詳細]
# 
# COMMAND VERIFICATION:
# - コマンドの正確さ: [PASS/FAIL] [詳細]
# - 実行環境の明記: [PASS/FAIL] [詳細]
# - 期待出力の正確さ: [PASS/FAIL] [詳細]
# 
# ERRORS FOUND (if any):
# 1. [具体的な誤りと正しい内容]
# 2. ...
# 
# VERIFICATION NOTES:
# [検証時の詳細メモ]
# ```
"""


QUALITY_REVIEW_EXPECTED_OUTPUT: str = """
Quality PM review with:
- Technical accuracy evaluation (terminology, explanations, versions)
- Code verification (matching actual code, correct paths, syntax)
- Cross-reference checks (consistency with Scout's research)
- Command verification (correct commands, expected outputs)
- List of specific errors if found

# 品質PMレビュー:
# - 技術的正確性評価（用語、説明、バージョン）
# - コード検証（実際のコードとの一致、パス、構文）
# - クロスリファレンスチェック（Scout調査との整合性）
# - コマンド検証（正確なコマンド、期待出力）
# - 発見した具体的な誤りのリスト
"""
