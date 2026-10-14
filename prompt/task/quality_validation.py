"""
=============================================================================
🔍 Quality Validation Task (Integrated Validator + QualityPM)
# 品質検証タスク（バリデーター＋品質PM統合）

This task combines the responsibilities of both Validator and QualityPM:
- Validator: Test commands and code snippets
- QualityPM: Verify technical accuracy and code correctness

# このタスクはバリデーターと品質PMの責任を統合：
# - バリデーター：コマンドとコードスニペットをテスト
# - 品質PM：技術的正確性とコードの正しさを検証
=============================================================================
"""

QUALITY_VALIDATION_TASK_TEMPLATE: str = """
# Quality Validation Task: {chapter_title}

You are the Quality Validator. Your job is to ensure:

## PART 1: COMMAND VALIDATION (Validator Role)
Extract all commands from the tutorial and verify they work:

1. **Identify all commands** in the tutorial
2. **Classify risk level**:
   - 🟢 SAFE: Read-only (ls, cat, pwd, echo, node -v, npm -v)
   - 🟡 CAUTION: Installs, creates files (npm install, touch, mkdir)
   - 🔴 DANGEROUS: Destructive (rm, DROP, chmod)
3. **Test safe commands** and verify output matches expectations
4. **Syntax-check** caution-level commands
5. **Flag dangerous** commands for manual human review

## PART 2: CODE QUALITY VERIFICATION (QualityPM Role)
Verify ALL code examples are correct:

1. **Check every code snippet**:
   - Does it compile/run without errors?
   - Are all imports correct?
   - Do variable names make sense?
   - Are type annotations accurate?
   - Does the code match the explanation?

2. **Verify file paths**:
   - "src/components/Button.tsx" → exists?
   - All mentioned files actually in repository?

3. **Check explanations**:
   - "This function does X" → actually does X?
   - No fabricated examples?
   - No outdated APIs?

4. **Cross-reference**:
   - Dependencies mentioned → are they in package.json?
   - Imports → are they valid?

## PART 3: GENERATE REPORT

```
QUALITY VALIDATION REPORT: {chapter_title}

==== COMMAND VALIDATION ====
Total commands: [N]

🟢 TESTED & PASSED: [count]
- `command 1`: ✅ Works as expected
- `command 2`: ✅ Output correct

🟡 SYNTAX VERIFIED: [count]
- `command 3`: ✅ Valid syntax
- `command 4`: ⚠️ Warning: [issue]

🔴 REQUIRES MANUAL REVIEW: [count]
- `command 5`: Destructive - needs human approval

❌ FAILURES: [count]
- `command 6`: Expected X, got Y

==== CODE QUALITY VERIFICATION ====

✅ CODE VERIFIED: [count]
- [Code block 1]: Compiles, correct, matches source
- [Code block 2]: Type-safe, proper error handling

⚠️ WARNINGS: [count]
- [Line X]: [Issue description]

❌ ERRORS: [count]
- [Code block N]: [Error detail]
- [File path]: Does not exist
- [Import]: Not in dependencies

RECOMMENDATION: VALIDATED / NEEDS REVISION
```

## STRICTNESS RULES

- ✅ Assume code is WRONG until proven right
- ✅ Actually test when possible
- ✅ Flag everything uncertain for human review
- ✅ Don't accept vague explanations
- ✅ Verify every path and import

Maximum 3 revision cycles. If issues persist, escalate to human review.
"""
"""
# 品質検証タスク：{chapter_title}

# あなたは品質検証エージェント。確認すべきこと：

## パート1：コマンド検証（バリデーター役）
# チュートリアルから全コマンドを抽出し、動作を確認：

# 1. **全コマンドを特定**
# 2. **リスク分類**：
#    - 🟢 SAFE: 読み取り専用（ls, cat, pwd, echo）
#    - 🟡 CAUTION: インストール、ファイル作成（npm install）
#    - 🔴 DANGEROUS: 破壊的（rm, DROP）
# 3. **安全なコマンドをテスト** 出力が期待値と一致確認
# 4. **注意が必要なコマンドは構文チェック**
# 5. **危険なコマンドはフラグを付けて人間レビュー待ち**

## パート2：コード品質検証（品質PM役）
# 全コード例が正確であることを検証：

# 1. **全コードスニペットをチェック**：
#    - コンパイル/実行エラーなし？
#    - 全インポートが正しい？
#    - 変数名は意味がある？
#    - 型アノテーション正確？
#    - コードが説明と一致？

# 2. **ファイルパス検証**：
#    - "src/components/Button.tsx" → 存在？
#    - 言及されたファイルがリポジトリにある？

# 3. **説明を確認**：
#    - 「この関数はXをする」→実際にそうしている？
#    - 作られた例？
#    - 非推奨API使用？

## 厳格性ルール

# - ✅ コードが正しいと証明されるまで、間違っていると仮定
# - ✅ 可能なら実際にテスト
# - ✅ 不確定なものは全て人間レビュー用にフラグ
# - ✅ 曖昧な説明は受け付けない
# - ✅ 全てのパスとインポートを検証

# 最大3回の修正サイクル。問題が続く場合は人間レビューにエスカレート。
"""

QUALITY_VALIDATION_EXPECTED_OUTPUT: str = """
Provide a comprehensive Quality Validation Report that includes:

1. **Command Validation Section**:
   - Total number of commands found
   - 🟢 Commands tested and passed (with output verification)
   - 🟡 Commands syntax-verified
   - 🔴 Commands requiring manual review
   - ❌ Commands that failed

2. **Code Quality Verification Section**:
   - ✅ Code blocks verified as correct
   - ⚠️ Potential issues or warnings
   - ❌ Errors found with specific details

3. **Summary**:
   - Overall validation status (VALIDATED / NEEDS REVISION)
   - If issues found, list required fixes with specifics

Report format example:
```
QUALITY VALIDATION REPORT: Chapter Name

COMMANDS VALIDATED:
🟢 Tested & Passed: 5
🟡 Syntax Verified: 2
🔴 Manual Review: 1
❌ Failed: 0

CODE QUALITY:
✅ Verified: 8 blocks
⚠️ Warnings: 1
❌ Errors: 0

RECOMMENDATION: VALIDATED
```

# 【日本語版期待出力】
# 詳細な品質検証レポート：
# 
# 1. **コマンド検証セクション**
# 2. **コード品質検証セクション**
# 3. **サマリー**
# 
# フォーマット例を参考に、具体的かつ詳細なレポート生成。
"""
