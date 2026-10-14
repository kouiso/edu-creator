"""
=============================================================================
Product Owner Final Approval Task Prompts
# プロダクトオーナー最終承認タスクプロンプト

Product Owner makes the final approval decision based on all PM reviews.
# プロダクトオーナーが全PMレビューに基づいて最終承認を決定する。
=============================================================================
"""


PO_APPROVAL_TASK_TEMPLATE: str = """
# 【PRODUCT OWNER FINAL APPROVAL】
# Final decision for: {chapter_title}
# 
# あなたの権限:
# - 最終承認/却下の決定権
# - 全PMレビューの統合判断
# - 品質基準の門番
# 
# INPUT:
# - Content PMのレビュー結果
# - Quality PMのレビュー結果
# - BeginnerAdvocateのレビュー結果
# - Validatorの検証結果
# 
# APPROVAL CRITERIA:
# 全ての条件を満たす必要がある:
# 1. Content PM: 構成・フローが適切
# 2. Quality PM: 技術的に正確
# 3. BeginnerAdvocate: 初心者に優しい
# 4. Validator: コマンド・コードが検証済み
# 
# REJECTION TRIGGERS (一つでも該当すれば即却下):
# ❌ コードが実際のプロジェクトと不一致
# ❌ コマンドにエラーがある
# ❌ 初心者が😱評価のつまずきポイントがある
# ❌ 技術的な誤りがある
# ❌ 説明なしで専門用語を使用している
# 
# DECISION FLOW:
# 1. 全レビューを確認
# 2. 重大な問題があるか判定
# 3. 軽微な問題のみなら承認
# 4. 重大な問題があれば具体的な修正指示を出す
# 
# OUTPUT FORMAT:
# ```
# === PRODUCT OWNER DECISION ===
# 
# 📊 REVIEW SUMMARY:
# - Content PM: [APPROVED/ISSUES]
# - Quality PM: [APPROVED/ISSUES]
# - BeginnerAdvocate: [APPROVED/ISSUES]
# - Validator: [PASSED/ISSUES]
# 
# 🎯 FINAL DECISION: [✅ APPROVED / ❌ REJECTED / ⚠️ CONDITIONAL]
# 
# RATIONALE:
# [判断理由を簡潔に]
# 
# CRITICAL ISSUES (if rejected):
# 1. [深刻な問題]
# 2. ...
# 
# REQUIRED FIXES (if conditional):
# 1. [必須の修正]
# 2. ...
# 
# MINOR NOTES (for future reference):
# 1. [軽微な改善点]
# 2. ...
# 
# APPROVAL TIMESTAMP: [日時]
# APPROVED BY: Product Owner
# ```
"""


PO_APPROVAL_EXPECTED_OUTPUT: str = """
Product Owner final decision with:
- Summary of all PM reviews
- Clear APPROVED / REJECTED / CONDITIONAL decision
- Rationale for the decision
- List of critical issues (if rejected)
- Required fixes (if conditional approval)
- Minor notes for future improvement

# プロダクトオーナー最終決定:
# - 全PMレビューのサマリー
# - 明確な承認/却下/条件付き承認の決定
# - 判断理由
# - 深刻な問題のリスト（却下の場合）
# - 必須の修正（条件付き承認の場合）
# - 将来の改善に向けた軽微なメモ
"""
