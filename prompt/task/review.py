"""
=============================================================================
Review Task Prompts (Commander's Final Check)
レビュータスクプロンプト（Commanderの最終チェック）

Commander reviews the final tutorial for quality assurance.
Commanderが最終チュートリアルの品質保証をレビューする。
=============================================================================
"""


REVIEW_TASK_TEMPLATE: str = """
【FINAL REVIEW】
Review Scribe's tutorial for: {chapter_title}

CRITICAL PRINCIPLE
"Readers should NEVER need to look at source code to understand this tutorial."
This is the PRIMARY quality metric.

QUALITY CHECKLIST:
□ Written in Japanese (日本語) with です・ます style
□ Metaphors used correctly (ONE metaphor, consistent throughout)
□ No unexplained technical jargon
□ Code examples are REAL (match what Scout found)
□ Structure follows: Problem → Metaphor → Code → Verify → Summary
□ Length is appropriate (3,000-5,000 characters)
□ No emoji is used anywhere in the tutorial
□ Paragraph length: MAX 3 sentences per paragraph
□ Code block length: MAX 25 lines per code block
□ Visual elements: MIN 4 tables + MIN 1 Mermaid diagram

SELF-CONTAINMENT CHECK (MOST IMPORTANT)
Readers must understand EVERYTHING from the markdown alone. NO source code lookup.

For EVERY code block:
  - Is there a detailed explanation AFTER the code showing what each line does?
  - Example good: 「3行目の "node": "25.x" は『このプロジェクトがNode.jsの25系で動く』」
  - Example bad: Code block with no explanation

For EVERY command:
  - Is the EXPECTED OUTPUT shown?
  - Example good:
    ```
    $ node -v
    v25.6.1
    ```
    「このように『v25.6.1』と表示されれば、正しいバージョンがインストールされています」
  - Example bad: Just show command, reader must guess what output means

For EVERY complex concept:
  - Are there screenshot location hints? 【スクリーンショット】[description]
  - Minimum 3-4 screenshot points per chapter?
  - Example bad: No screenshot hints = reader must open file and look around

VERIFICATION STEPS:
1. Read as a complete beginner with ZERO prior knowledge
2. Ask: "Can I understand this WITHOUT opening source code?"
3. Check each code block has explanation AFTER it
4. Check each command shows expected output
5. Check for screenshot location hints (minimum 3-4 per chapter)
6. Verify metaphor consistency (don't switch metaphors mid-chapter)

IF SELF-CONTAINMENT FAILS:
- This is CRITICAL, not optional
- Request Scribe to add explanations, expected outputs, screenshot hints
- Do NOT approve if code lacks explanation
- Do NOT approve if commands lack expected output

IF ISSUES FOUND:
- List specific problems
- Request Scribe to fix (max {max_iterations} revision cycles)
- Emphasize self-containment if that's the issue
- If still not fixed, note issues but consider approving only if self-contained

OUTPUT FORMAT:
```
=== REVIEW RESULT ===
STATUS: [APPROVED / NEEDS REVISION / APPROVED WITH WARNINGS]

CHECKLIST:
- Japanese です・ます style: [PASS/FAIL]
- Metaphors correct: [PASS/FAIL]
- No jargon: [PASS/FAIL]
- Real code: [PASS/FAIL]
- Structure correct: [PASS/FAIL]
- Length appropriate: [PASS/FAIL]
- Self-contained (NO source code lookup): [PASS/FAIL] (CRITICAL)
- No emoji used: [PASS/FAIL]

SELF-CONTAINMENT ISSUES (if any):
1. Code shown without explanation: [location]
2. Command without expected output: [location]
3. Missing screenshot hints: [location]
4. Metaphor inconsistency: [location]

OTHER ISSUES (if any):
1. [specific issue and location]
2. ...

FINAL NOTES:
[Overall assessment. Emphasize whether self-containment requirement is met.]
```
"""
"""
【最終レビュー】
Scribeのチュートリアルをレビュー: {chapter_title}

品質チェックリスト:
□ 日本語で書かれている（です・ます調）
□ メタファーが正しく使用されている（辞書から）
□ 説明されていない専門用語がない
□ コード例が実際のもの（Scoutの発見と一致）
□ 構造が正しい：問題→メタファー→コード→検証→まとめ
□ 長さが適切（3,000-5,000文字）
□ チュートリアル全体に絵文字がない

検証手順:
1. チュートリアル全体を通読
2. 各コードブロックをScoutの発見と照合
3. 専門用語が初出で説明されているか確認
4. 初心者視点で流れが論理的か確認
5. コード後に説明があるか、コマンド後に期待出力があるかを確認
6. スクリーンショット位置のヒントが十分か確認

問題が見つかった場合:
- 具体的な問題をリスト
- Scribeに修正を依頼（最大{max_iterations}回の修正サイクル）
- 自己完結性が満たされない場合は承認しない

出力フォーマット:
```
=== REVIEW RESULT ===
STATUS: [APPROVED / NEEDS REVISION / APPROVED WITH WARNINGS]

CHECKLIST:
- Japanese です・ます style: [PASS/FAIL]
- Metaphors correct: [PASS/FAIL]
- No jargon: [PASS/FAIL]
- Real code: [PASS/FAIL]
- Structure correct: [PASS/FAIL]
- Length appropriate: [PASS/FAIL]
- Self-contained: [PASS/FAIL]
- No emoji used: [PASS/FAIL]

ISSUES (if any):
1. [具体的な問題と場所]
2. ...

FINAL NOTES:
[追加フィードバック]
```
"""


REVIEW_EXPECTED_OUTPUT: str = "Review result with checklist (APPROVED/NEEDS REVISION/APPROVED WITH WARNINGS)"
"""
Expected output description for the review task.

レビュータスクの期待される出力の説明。
チェックリスト付きのレビュー結果（承認/要修正/警告付き承認）
"""
