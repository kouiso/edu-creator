"""
=============================================================================
👨‍⚖️ Multi-Judge Evaluation Engine - 複数Judge評価エンジン
=============================================================================

GPT-4o + Gemini + Claude で並行評価し、複数エージェントの consensus を取る。

評価バイアス削減 + 説得力向上

実務の 品質評価システムから学んだベストプラクティス。
"""

import logging
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class JudgeName(str, Enum):
    """Judge の種類"""
    GPT4O = "gpt-4o"
    GEMINI = "gemini-2.0-flash"
    CLAUDE = "claude-3-5-sonnet"


class JudgeScore(BaseModel):
    """個別Judge の評価スコア"""
    
    judge_name: JudgeName = Field(description="Judge名")
    clarity: float = Field(ge=1.0, le=5.0, description="明確さ（1-5）")
    accessibility: float = Field(ge=1.0, le=5.0, description="アクセシビリティ（1-5）")
    engagement: float = Field(ge=1.0, le=5.0, description="引き込み（1-5）")
    actionability: float = Field(ge=1.0, le=5.0, description="実行可能性（1-5）")
    self_containment: float = Field(ge=1.0, le=5.0, description="自己完結性（1-5）")
    overall: float = Field(ge=1.0, le=5.0, description="総合評価（1-5）")
    comments: str = Field(description="コメント")
    
    @property
    def average(self) -> float:
        """平均スコア"""
        return (
            self.clarity +
            self.accessibility +
            self.engagement +
            self.actionability +
            self.self_containment
        ) / 5.0


class ConsensusResult(BaseModel):
    """Consensus 評価結果"""
    
    gpt4o_score: JudgeScore | None = Field(default=None, description="GPT-4o 評価")
    gemini_score: JudgeScore | None = Field(default=None, description="Gemini 評価")
    claude_score: JudgeScore | None = Field(default=None, description="Claude 評価")
    
    consensus_score: float = Field(description="Consensus スコア（全Judge の平均）")
    agreement_level: str = Field(description="一致度（high/medium/low）")
    disagreement_areas: list[str] = Field(default_factory=list, description="意見が分かれた項目")
    recommendation: str = Field(description="推奨アクション")
    
    @classmethod
    def from_scores(cls, scores: list[JudgeScore]) -> "ConsensusResult":
        """
        複数Judge のスコアから Consensus を計算
        
        Args:
            scores: JudgeScore のリスト
        
        Returns:
            ConsensusResult オブジェクト
        """
        if not scores:
            raise ValueError("At least one judge score is required")
        
        # 各Judge のスコアを格納
        result_dict: dict[str, Any] = {}
        for score in scores:
            if score.judge_name == JudgeName.GPT4O:
                result_dict["gpt4o_score"] = score
            elif score.judge_name == JudgeName.GEMINI:
                result_dict["gemini_score"] = score
            elif score.judge_name == JudgeName.CLAUDE:
                result_dict["claude_score"] = score
        
        # Consensus スコア（全Judge の平均）
        consensus = sum(s.average for s in scores) / len(scores)
        result_dict["consensus_score"] = consensus
        
        # 一致度を計算（標準偏差ベース）
        import statistics
        averages = [s.average for s in scores]
        if len(averages) > 1:
            std_dev = statistics.stdev(averages)
            if std_dev < 0.3:
                agreement = "high"
            elif std_dev < 0.6:
                agreement = "medium"
            else:
                agreement = "low"
        else:
            agreement = "high"  # 1つしかない場合は一致
        
        result_dict["agreement_level"] = agreement
        
        # 意見が分かれた項目を検出
        disagreement_areas = []
        if len(scores) > 1:
            for criterion in ["clarity", "accessibility", "engagement", "actionability", "self_containment"]:
                values = [getattr(s, criterion) for s in scores]
                if max(values) - min(values) > 1.0:  # 1.0以上の差がある場合
                    disagreement_areas.append(criterion)
        
        result_dict["disagreement_areas"] = disagreement_areas
        
        # 推奨アクション
        if consensus >= 4.5:
            recommendation = "APPROVE - 高品質です"
        elif consensus >= 4.0:
            recommendation = "APPROVE - 良好です"
        elif consensus >= 3.5:
            if disagreement_areas:
                recommendation = f"REVIEW - 以下の項目を改善してください: {', '.join(disagreement_areas)}"
            else:
                recommendation = "MINOR_REVISE - 軽微な修正が必要です"
        else:
            recommendation = "REVISE - 大幅な修正が必要です"
        
        result_dict["recommendation"] = recommendation
        
        return cls(**result_dict)


def evaluate_with_judge(
    content: str,
    judge_name: JudgeName,
    llm_callable: Any,
) -> JudgeScore:
    """
    単一Judge で評価
    
    Args:
        content: 評価対象のコンテンツ
        judge_name: Judge名
        llm_callable: LLM呼び出し関数
    
    Returns:
        JudgeScore オブジェクト
    """
    prompt = f"""
Evaluate this tutorial content on the following 5 criteria (1-5 scale):

1. **Clarity (明確さ)**: Are explanations clear and unambiguous?
2. **Accessibility (アクセシビリティ)**: Can beginners understand it?
3. **Engagement (引き込み)**: Are metaphors/examples effective?
4. **Actionability (実行可能性)**: Can readers take action?
5. **Self-Containment (自己完結性)**: Is it complete without external references?

**Content**:
{content[:3000]}... (truncated)

Respond in JSON format:
{{
  "clarity": 4.5,
  "accessibility": 4.0,
  "engagement": 4.2,
  "actionability": 4.3,
  "self_containment": 4.1,
  "overall": 4.2,
  "comments": "Good tutorial with clear examples. Consider adding more diagrams."
}}
"""
    
    try:
        response = llm_callable(prompt)
        
        # JSON解析
        import json
        import re
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return JudgeScore(
                judge_name=judge_name,
                clarity=result.get("clarity", 3.0),
                accessibility=result.get("accessibility", 3.0),
                engagement=result.get("engagement", 3.0),
                actionability=result.get("actionability", 3.0),
                self_containment=result.get("self_containment", 3.0),
                overall=result.get("overall", 3.0),
                comments=result.get("comments", "No comments"),
            )
        else:
            logger.warning(f"Failed to parse JSON from {judge_name}")
            return JudgeScore(
                judge_name=judge_name,
                clarity=3.0,
                accessibility=3.0,
                engagement=3.0,
                actionability=3.0,
                self_containment=3.0,
                overall=3.0,
                comments="Failed to parse response",
            )
    
    except Exception as e:
        logger.error(f"Error evaluating with {judge_name}: {e}")
        return JudgeScore(
            judge_name=judge_name,
            clarity=3.0,
            accessibility=3.0,
            engagement=3.0,
            actionability=3.0,
            self_containment=3.0,
            overall=3.0,
            comments=f"Error: {str(e)}",
        )


def evaluate_with_multi_judges(
    content: str,
    judges: list[JudgeName],
    llm_callables: dict[JudgeName, Any],
) -> ConsensusResult:
    """
    複数Judge で評価し、Consensus を取る
    
    Args:
        content: 評価対象のコンテンツ
        judges: 使用するJudgeのリスト
        llm_callables: {JudgeName: llm_callable} の辞書
    
    Returns:
        ConsensusResult オブジェクト
    
    Example:
        judges = [JudgeName.GPT4O, JudgeName.GEMINI, JudgeName.CLAUDE]
        llm_callables = {
            JudgeName.GPT4O: gpt4o_llm.call,
            JudgeName.GEMINI: gemini_llm.call,
            JudgeName.CLAUDE: claude_llm.call,
        }
        consensus = evaluate_with_multi_judges(content, judges, llm_callables)
        print(f"Consensus: {consensus.consensus_score:.2f}")
        print(f"Recommendation: {consensus.recommendation}")
    """
    logger.info(f"📊 Evaluating with {len(judges)} judges...")
    
    scores: list[JudgeScore] = []
    for judge in judges:
        if judge not in llm_callables:
            logger.warning(f"⚠️ No LLM callable for {judge}, skipping")
            continue
        
        logger.info(f"  ▶️ Evaluating with {judge}...")
        score = evaluate_with_judge(content, judge, llm_callables[judge])
        scores.append(score)
        logger.info(f"  ✅ {judge}: {score.average:.2f}/5.0")
    
    if not scores:
        raise ValueError("No judges were able to evaluate the content")
    
    consensus = ConsensusResult.from_scores(scores)
    
    logger.info(
        f"✅ Consensus: {consensus.consensus_score:.2f}/5.0 "
        f"(agreement: {consensus.agreement_level})"
    )
    if consensus.disagreement_areas:
        logger.warning(f"⚠️ Disagreement areas: {', '.join(consensus.disagreement_areas)}")
    
    return consensus
