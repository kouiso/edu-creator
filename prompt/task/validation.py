"""
=============================================================================
Validator Task Prompts
# バリデータータスクプロンプト

Validator tests commands and verifies code snippets work correctly.
# Validatorがコマンドをテストし、コードスニペットが正しく動作することを検証する。
=============================================================================
"""


VALIDATION_TASK_TEMPLATE: str = """
# 【VALIDATION TASK】
# Validate commands and code for: {chapter_title}
# 
# あなたの役割:
# チュートリアル内の全てのコマンドとコードスニペットを検証
# 
# VALIDATION RULES:
# 
# 1. 【コマンド検証】
# チュートリアル内の全てのコマンドをチェック:
# - コマンドの構文が正しいか
# - 必要なツール/パッケージがインストールされているか
# - 実行ディレクトリの指定が正しいか
# - 期待される出力が妥当か
# 
# 2. 【コード検証】
# チュートリアル内の全てのコードブロックをチェック:
# - 構文エラーがないか
# - インポートが正しいか
# - ファイルパスが正確か
# - 実際のプロジェクトコードと一致しているか
# 
# 3. 【分類】
# 各コマンド/コードを以下に分類:
# 🟢 SAFE: 読者が安全に実行可能
# 🟡 VERIFY: 環境依存、実行前に確認推奨
# 🔴 RISKY: 破壊的操作の可能性、警告必要
# 
# 4. 【出力検証】
# 期待される出力が:
# - 実際の出力と一致するか
# - バージョン依存で変わりうるか
# - 省略なく示されているか
# 
# OUTPUT FORMAT:
# ```
# === VALIDATION REPORT ===
# STATUS: [PASSED / ISSUES FOUND]
# 
# COMMANDS FOUND: [数]
# - 🟢 SAFE: [数]
# - 🟡 VERIFY: [数]
# - 🔴 RISKY: [数]
# 
# COMMAND DETAILS:
# 1. `[コマンド]`
#    - 分類: 🟢/🟡/🔴
#    - 検証結果: [PASS/FAIL]
#    - 備考: [詳細]
# 
# 2. `[コマンド]`
#    - 分類: 🟢/🟡/🔴
#    - 検証結果: [PASS/FAIL]
#    - 備考: [詳細]
# 
# ...
# 
# CODE BLOCKS FOUND: [数]
# CODE BLOCK DETAILS:
# 1. [ファイル名/説明]
#    - 言語: [TypeScript/etc]
#    - 構文チェック: [PASS/FAIL]
#    - プロジェクト一致: [PASS/FAIL/N/A]
#    - 備考: [詳細]
# 
# ...
# 
# ISSUES REQUIRING FIX:
# 1. [場所]: [問題] - [推奨修正]
# 2. ...
# 
# WARNINGS (no fix needed but worth noting):
# 1. [場所]: [注意点]
# 2. ...
# 
# VALIDATION COMPLETE: [総合判定]
# ```
"""


VALIDATION_EXPECTED_OUTPUT: str = """
Validation report with:
- Count and classification of all commands (🟢🟡🔴)
- Detailed validation of each command
- Count and verification of all code blocks
- List of issues requiring fixes
- Warnings for environment-dependent items

# 検証レポート:
# - 全コマンドの数と分類（🟢🟡🔴）
# - 各コマンドの詳細検証
# - 全コードブロックの数と検証
# - 修正が必要な問題のリスト
# - 環境依存項目の警告
"""
