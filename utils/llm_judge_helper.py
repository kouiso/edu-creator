"""
=============================================================================
LLM Judge統合ヘルパー
main.pyからLLM-as-Judgeを簡単に使うためのヘルパー関数
=============================================================================
"""

from pathlib import Path
from typing import Any

from utils.llm_judge import OPENAI_AVAILABLE, LLMJudge, EvaluationResult


def run_llm_judge_evaluation(
    markdown_file: Path,
    model: str = "gpt-4o",
    min_passing_score: float = 4.0,
) -> tuple[bool, EvaluationResult | None, str]:
    """
    LLM Judgeで教材を評価

    Args:
        markdown_file: 評価対象のMarkdownファイル
        model: 使用するモデル（gpt-4o, gpt-5.2等）
        min_passing_score: 合格最低スコア（デフォルト4.0）

    Returns:
        tuple[bool, EvaluationResult | None, str]:
            - passed: 合格したか
            - result: 評価結果（失敗時はNone）
            - message: エラーメッセージ or 成功メッセージ
    """
    if not OPENAI_AVAILABLE:
        return (
            True,  # OpenAI未インストール時はスキップ扱いでPASS
            None,
            "⚠️  OpenAI未インストール。LLM Judge評価をスキップします。",
        )

    try:
        judge = LLMJudge(model=model)
        result = judge.evaluate_file(markdown_file)

        if result.error:
            return False, result, f"❌ 評価エラー: {result.error}"

        passed = result.overall_score >= min_passing_score
        status = "✅ 合格" if passed else "❌ 不合格"

        message = f"""
{status} (スコア: {result.overall_score:.1f}/{5.0})
- Clarity (明確さ): {result.clarity.score}/5
- Accessibility (アクセシビリティ): {result.accessibility.score}/5
- Engagement (引き込み): {result.engagement.score}/5
- Actionability (実行可能性): {result.actionability.score}/5
- Self-Containment (自己完結性): {result.self_containment.score}/5
"""

        if result.critical_issues:
            message += "\n【即座に修正すべき問題】:\n"
            for issue in result.critical_issues:
                message += f"  - {issue}\n"

        return passed, result, message

    except Exception as e:
        return False, None, f"❌ LLM Judge実行エラー: {e}"


def format_llm_judge_report(result: EvaluationResult) -> str:
    """
    LLM Judge評価結果を人間が読みやすい形式にフォーマット

    Args:
        result: 評価結果

    Returns:
        str: フォーマット済みレポート
    """
    report = []
    report.append("=" * 70)
    report.append("📊 LLM-as-Judge 評価レポート")
    report.append("=" * 70)
    report.append(f"総合スコア: {result.overall_score:.1f}/5.0")
    report.append(f"合格: {'✅ YES' if result.passed else '❌ NO'}")
    report.append("")

    # 各項目の詳細
    items = [
        ("Clarity (明確さ)", result.clarity),
        ("Accessibility (アクセシビリティ)", result.accessibility),
        ("Engagement (引き込み)", result.engagement),
        ("Actionability (実行可能性)", result.actionability),
        ("Self-Containment (自己完結性)", result.self_containment),
    ]

    for name, score_obj in items:
        report.append(f"【{name}】: {score_obj.score}/5")
        report.append(f"  理由: {score_obj.reason}")
        if score_obj.evidence:
            report.append(f"  証拠: 「{score_obj.evidence[:80]}...」")
        report.append("")

    # 重大な問題
    if result.critical_issues:
        report.append("【即座に修正すべき問題】:")
        for issue in result.critical_issues:
            report.append(f"  ❌ {issue}")
        report.append("")

    # 改善提案
    if result.improvement_suggestions:
        report.append("【改善提案】:")
        for suggestion in result.improvement_suggestions:
            report.append(f"  💡 {suggestion}")
        report.append("")

    report.append("=" * 70)
    return "\n".join(report)
