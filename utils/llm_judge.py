"""
=============================================================================
LLM-as-Judge (LLM評価システム)
GPT-5.2を使用した教材品質の自動評価

柱5: 評価エンジニアリング
- 「読みやすさ」「初心者にわかりやすいか」を定量評価
- プロンプト変更時の回帰テストが可能
- 「なんとなく良くなった」→「スコアが3.2→4.1に改善」と定量化
=============================================================================
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# OpenAI APIを使用（インストールされていない場合はスキップ）
try:
    from openai import OpenAI, AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# 評価プロンプト
LLM_JUDGE_PROMPT = """
<instructions>
あなたは初心者向け技術教材の品質審査員です。
以下の教材を5つの観点から厳密に評価してください。

評価は客観的に、具体的な証拠（引用）に基づいて行ってください。
</instructions>

<tutorial_content>
{content}
</tutorial_content>

<evaluation_rubric>
各項目を1〜5点で採点してください：

1. **clarity（明確さ）**: 説明が曖昧でないか
   - 5点: 全ての説明が具体的で明確。曖昧な表現がない
   - 4点: ほぼ明確だが、1-2箇所改善の余地あり
   - 3点: 一部曖昧な表現がある（「同様に」「簡単です」等）
   - 2点: 複数の曖昧な表現があり、理解に支障
   - 1点: 「同様に」「以下略」「簡単です」等の手抜き表現が多い

2. **accessibility（アクセシビリティ）**: 初心者が理解できるか
   - 5点: 全ての専門用語に「用語（読み方：意味）」形式の説明がある
   - 4点: ほぼ全ての用語に説明があるが、1-2個不足
   - 3点: 一部用語の説明が不足（専門用語が説明なしで使用）
   - 2点: 多くの専門用語が説明なしで使われている
   - 1点: 初心者には理解不能なレベル

3. **engagement（引き込み）**: 読者の興味を引くか
   - 5点: 効果的なメタファー、具体例が豊富で一貫している
   - 4点: メタファーがあり効果的だが、一部改善の余地あり
   - 3点: メタファーはあるが一貫性がない、または説明が浅い
   - 2点: メタファーが少なく、説明が単調
   - 1点: 無味乾燥な説明のみ

4. **actionability（実行可能性）**: 読者が手を動かせるか
   - 5点: 全コマンドに期待出力があり、確認ポイントが明確
   - 4点: ほぼ全てのコマンドに出力があるが、一部不足
   - 3点: 一部コマンドの出力が不明、または確認方法が不明確
   - 2点: 多くのコマンドで出力や確認方法が不明
   - 1点: 何をすればいいかわからない

5. **self_containment（自己完結性）**: 他を参照せず完結するか
   - 5点: ソースコードを見る必要がない。全てが教材内で完結
   - 4点: ほぼ自己完結だが、1-2箇所外部参照を促している
   - 3点: 一部コードの説明が不足、または「ファイルを見て」がある
   - 2点: 複数箇所で外部参照が必要
   - 1点: 「ファイルを見てください」「詳細は〇〇を参照」が多い
</evaluation_rubric>

<output_format>
以下のJSON形式で出力してください。JSON以外は出力しないでください。

{{
  "clarity": {{
    "score": 1から5の整数,
    "evidence": "該当箇所の引用（最大100文字）",
    "reason": "採点理由（日本語で簡潔に）"
  }},
  "accessibility": {{
    "score": 1から5の整数,
    "evidence": "該当箇所の引用（最大100文字）",
    "reason": "採点理由（日本語で簡潔に）"
  }},
  "engagement": {{
    "score": 1から5の整数,
    "evidence": "該当箇所の引用（最大100文字）",
    "reason": "採点理由（日本語で簡潔に）"
  }},
  "actionability": {{
    "score": 1から5の整数,
    "evidence": "該当箇所の引用（最大100文字）",
    "reason": "採点理由（日本語で簡潔に）"
  }},
  "self_containment": {{
    "score": 1から5の整数,
    "evidence": "該当箇所の引用（最大100文字）",
    "reason": "採点理由（日本語で簡潔に）"
  }},
  "overall_score": 5項目の平均（小数点1桁）,
  "pass": true または false（overall_score >= 4.0 なら true）,
  "critical_issues": ["即座に修正すべき問題のリスト（最大3個）"],
  "improvement_suggestions": ["改善すれば良くなる点のリスト（最大3個）"]
}}
</output_format>
"""


@dataclass
class EvaluationScore:
    """個別評価スコア"""

    score: int
    evidence: str
    reason: str


@dataclass
class EvaluationResult:
    """評価結果"""

    clarity: EvaluationScore
    accessibility: EvaluationScore
    engagement: EvaluationScore
    actionability: EvaluationScore
    self_containment: EvaluationScore
    overall_score: float
    passed: bool
    critical_issues: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)

    # メタ情報
    model_used: str = ""
    evaluation_time_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換"""
        return {
            "clarity": {"score": self.clarity.score, "evidence": self.clarity.evidence, "reason": self.clarity.reason},
            "accessibility": {
                "score": self.accessibility.score,
                "evidence": self.accessibility.evidence,
                "reason": self.accessibility.reason,
            },
            "engagement": {
                "score": self.engagement.score,
                "evidence": self.engagement.evidence,
                "reason": self.engagement.reason,
            },
            "actionability": {
                "score": self.actionability.score,
                "evidence": self.actionability.evidence,
                "reason": self.actionability.reason,
            },
            "self_containment": {
                "score": self.self_containment.score,
                "evidence": self.self_containment.evidence,
                "reason": self.self_containment.reason,
            },
            "overall_score": self.overall_score,
            "pass": self.passed,
            "critical_issues": self.critical_issues,
            "improvement_suggestions": self.improvement_suggestions,
            "model_used": self.model_used,
            "evaluation_time_ms": self.evaluation_time_ms,
            "error": self.error,
        }


def _parse_score_dict(data: dict[str, Any]) -> EvaluationScore:
    """スコア辞書をEvaluationScoreに変換"""
    return EvaluationScore(
        score=int(data.get("score", 0)),
        evidence=str(data.get("evidence", "")),
        reason=str(data.get("reason", "")),
    )


def _parse_evaluation_response(response_json: dict[str, Any], model: str, time_ms: int) -> EvaluationResult:
    """APIレスポンスをEvaluationResultに変換"""
    return EvaluationResult(
        clarity=_parse_score_dict(response_json.get("clarity", {})),
        accessibility=_parse_score_dict(response_json.get("accessibility", {})),
        engagement=_parse_score_dict(response_json.get("engagement", {})),
        actionability=_parse_score_dict(response_json.get("actionability", {})),
        self_containment=_parse_score_dict(response_json.get("self_containment", {})),
        overall_score=float(response_json.get("overall_score", 0)),
        passed=bool(response_json.get("pass", False)),
        critical_issues=list(response_json.get("critical_issues", [])),
        improvement_suggestions=list(response_json.get("improvement_suggestions", [])),
        model_used=model,
        evaluation_time_ms=time_ms,
    )


class LLMJudge:
    """GPT-5.2を使用した品質評価クラス"""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        """
        Args:
            model: 使用するモデル（デフォルト: gpt-4o）
                   注: gpt-5.2が利用可能になったら変更
            api_key: OpenAI APIキー（省略時は環境変数から取得）
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is not installed. Run: pip install openai")

        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def evaluate(self, content: str) -> EvaluationResult:
        """教材コンテンツを評価（同期版）

        Args:
            content: 評価対象のMarkdownコンテンツ

        Returns:
            EvaluationResult: 評価結果
        """
        import time

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": LLM_JUDGE_PROMPT.format(content=content)}],
                response_format={"type": "json_object"},
                temperature=0.1,  # 一貫性のため低温度
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            response_json = json.loads(response.choices[0].message.content)

            return _parse_evaluation_response(response_json, self.model, elapsed_ms)

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return EvaluationResult(
                clarity=EvaluationScore(0, "", ""),
                accessibility=EvaluationScore(0, "", ""),
                engagement=EvaluationScore(0, "", ""),
                actionability=EvaluationScore(0, "", ""),
                self_containment=EvaluationScore(0, "", ""),
                overall_score=0.0,
                passed=False,
                model_used=self.model,
                evaluation_time_ms=elapsed_ms,
                error=str(e),
            )

    def evaluate_file(self, file_path: Path | str) -> EvaluationResult:
        """ファイルを評価

        Args:
            file_path: 評価対象のファイルパス

        Returns:
            EvaluationResult: 評価結果
        """
        path = Path(file_path)
        if not path.exists():
            return EvaluationResult(
                clarity=EvaluationScore(0, "", ""),
                accessibility=EvaluationScore(0, "", ""),
                engagement=EvaluationScore(0, "", ""),
                actionability=EvaluationScore(0, "", ""),
                self_containment=EvaluationScore(0, "", ""),
                overall_score=0.0,
                passed=False,
                error=f"File not found: {file_path}",
            )

        content = path.read_text(encoding="utf-8")
        return self.evaluate(content)


class AsyncLLMJudge:
    """GPT-5.2を使用した品質評価クラス（非同期版）"""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        """
        Args:
            model: 使用するモデル
            api_key: OpenAI APIキー
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is not installed. Run: pip install openai")

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    async def evaluate(self, content: str) -> EvaluationResult:
        """教材コンテンツを評価（非同期版）

        Args:
            content: 評価対象のMarkdownコンテンツ

        Returns:
            EvaluationResult: 評価結果
        """
        import time

        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": LLM_JUDGE_PROMPT.format(content=content)}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            response_json = json.loads(response.choices[0].message.content)

            return _parse_evaluation_response(response_json, self.model, elapsed_ms)

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return EvaluationResult(
                clarity=EvaluationScore(0, "", ""),
                accessibility=EvaluationScore(0, "", ""),
                engagement=EvaluationScore(0, "", ""),
                actionability=EvaluationScore(0, "", ""),
                self_containment=EvaluationScore(0, "", ""),
                overall_score=0.0,
                passed=False,
                model_used=self.model,
                evaluation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def evaluate_file(self, file_path: Path | str) -> EvaluationResult:
        """ファイルを評価（非同期版）"""
        path = Path(file_path)
        if not path.exists():
            return EvaluationResult(
                clarity=EvaluationScore(0, "", ""),
                accessibility=EvaluationScore(0, "", ""),
                engagement=EvaluationScore(0, "", ""),
                actionability=EvaluationScore(0, "", ""),
                self_containment=EvaluationScore(0, "", ""),
                overall_score=0.0,
                passed=False,
                error=f"File not found: {file_path}",
            )

        content = path.read_text(encoding="utf-8")
        return await self.evaluate(content)


def quick_evaluate(content: str, model: str = "gpt-4o") -> dict[str, Any]:
    """クイック評価（便利関数）

    Args:
        content: 評価対象のコンテンツ
        model: 使用するモデル

    Returns:
        dict: 評価結果の辞書
    """
    judge = LLMJudge(model=model)
    result = judge.evaluate(content)
    return result.to_dict()


def print_evaluation_report(result: EvaluationResult) -> None:
    """評価結果をコンソールに出力

    Args:
        result: 評価結果
    """
    print("\n" + "=" * 60)
    print("📊 LLM-as-Judge 評価レポート")
    print("=" * 60)

    if result.error:
        print(f"\n❌ エラー: {result.error}")
        return

    categories = [
        ("clarity", "明確さ", result.clarity),
        ("accessibility", "アクセシビリティ", result.accessibility),
        ("engagement", "引き込み", result.engagement),
        ("actionability", "実行可能性", result.actionability),
        ("self_containment", "自己完結性", result.self_containment),
    ]

    for _, name, score in categories:
        stars = "★" * score.score + "☆" * (5 - score.score)
        print(f"\n{name}: {stars} ({score.score}/5)")
        print(f"  理由: {score.reason}")
        if score.evidence:
            print(f"  証拠: 「{score.evidence[:50]}...」" if len(score.evidence) > 50 else f"  証拠: 「{score.evidence}」")

    print("\n" + "-" * 60)
    print(f"総合スコア: {result.overall_score:.1f}/5.0")
    print(f"合格: {'✅ PASS' if result.passed else '❌ FAIL'}")

    if result.critical_issues:
        print("\n⚠️ 重大な問題:")
        for issue in result.critical_issues:
            print(f"  • {issue}")

    if result.improvement_suggestions:
        print("\n💡 改善提案:")
        for suggestion in result.improvement_suggestions:
            print(f"  • {suggestion}")

    print("\n" + "=" * 60)
    print(f"モデル: {result.model_used} | 評価時間: {result.evaluation_time_ms}ms")
    print("=" * 60 + "\n")
