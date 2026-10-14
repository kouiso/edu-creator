"""
=============================================================================
🧠 CoT Analyzer - Chain of Thought 自動解析エンジン
=============================================================================

CoT パーサーで抽出した <thinking> セクションを NLP で解析。

「どのメタファーを選んだか」「どの用語を説明したか」を自動抽出し可視化。

AIの判断ミスを洗い出し、プロンプト改善につなげる。

実務の 分析基盤から学んだベストプラクティス。
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CoTInsight(BaseModel):
    """CoT 思考過程から抽出されたインサイト"""
    
    metaphor_chosen: str | None = Field(default=None, description="選択されたメタファー")
    terms_explained: list[str] = Field(default_factory=list, description="説明された用語")
    decision_points: list[str] = Field(default_factory=list, description="意思決定ポイント")
    concerns: list[str] = Field(default_factory=list, description="懸念事項")
    confidence_level: str = Field(default="unknown", description="信頼度（high/medium/low）")


class CoTAnalysisResult(BaseModel):
    """CoT 解析結果"""
    
    thinking_text: str = Field(description="元の思考テキスト")
    insights: CoTInsight = Field(description="抽出されたインサイト")
    quality_flags: list[str] = Field(default_factory=list, description="品質フラグ")
    recommendations: list[str] = Field(default_factory=list, description="改善提案")


def extract_metaphor(thinking_text: str) -> str | None:
    """
    思考テキストからメタファーを抽出
    
    Args:
        thinking_text: 思考テキスト
    
    Returns:
        メタファー（見つからない場合はNone）
    """
    # パターンマッチング
    patterns = [
        r"メタファー[：:]\s*(.+)",
        r"例え[：:]\s*(.+)",
        r"metaphor[：:]\s*(.+)",
        r"比喩[：:]\s*(.+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, thinking_text, re.IGNORECASE)
        if match:
            metaphor = match.group(1).strip()
            # 改行までを抽出
            metaphor = metaphor.split('\n')[0].strip()
            return metaphor
    
    return None


def extract_explained_terms(thinking_text: str) -> list[str]:
    """
    説明された用語を抽出
    
    Args:
        thinking_text: 思考テキスト
    
    Returns:
        用語リスト
    """
    terms = []
    
    # 「〜を説明」パターン
    patterns = [
        r"「([^」]+)」を説明",
        r"「([^」]+)」の説明",
        r"explain\s+[\"']([^\"']+)[\"']",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, thinking_text, re.IGNORECASE)
        terms.extend(matches)
    
    return list(set(terms))  # 重複除去


def extract_decision_points(thinking_text: str) -> list[str]:
    """
    意思決定ポイントを抽出
    
    Args:
        thinking_text: 思考テキスト
    
    Returns:
        意思決定ポイントのリスト
    """
    decision_points = []
    
    # 「〜にする」「〜を選ぶ」パターン
    patterns = [
        r"(?:選択|選ぶ|決定)[：:]\s*(.+)",
        r"(?:〜にする|〜を使う)[：:]\s*(.+)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, thinking_text)
        for match in matches:
            decision = match.strip().split('\n')[0].strip()
            if decision:
                decision_points.append(decision)
    
    return decision_points


def extract_concerns(thinking_text: str) -> list[str]:
    """
    懸念事項を抽出
    
    Args:
        thinking_text: 思考テキスト
    
    Returns:
        懸念事項のリスト
    """
    concerns = []
    
    # 「懸念」「問題」「注意」パターン
    patterns = [
        r"(?:懸念|問題|注意|課題)[：:]\s*(.+)",
        r"(?:concern|issue|problem)[：:]\s*(.+)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, thinking_text, re.IGNORECASE)
        for match in matches:
            concern = match.strip().split('\n')[0].strip()
            if concern:
                concerns.append(concern)
    
    return concerns


def analyze_confidence_level(thinking_text: str) -> str:
    """
    信頼度レベルを推定
    
    Args:
        thinking_text: 思考テキスト
    
    Returns:
        信頼度（high/medium/low）
    """
    # 不確実性を示すキーワードの数をカウント
    uncertainty_keywords = [
        "おそらく", "多分", "かもしれない", "〜だろう",
        "possibly", "maybe", "might", "probably",
    ]
    
    uncertainty_count = sum(
        1 for keyword in uncertainty_keywords
        if keyword in thinking_text.lower()
    )
    
    if uncertainty_count == 0:
        return "high"
    elif uncertainty_count <= 2:
        return "medium"
    else:
        return "low"


def analyze_cot(thinking_text: str) -> CoTAnalysisResult:
    """
    CoT 思考過程を解析
    
    Args:
        thinking_text: <thinking> タグ内のテキスト
    
    Returns:
        CoTAnalysisResult オブジェクト
    """
    logger.info("🧠 Analyzing CoT thinking process...")
    
    # インサイト抽出
    insights = CoTInsight(
        metaphor_chosen=extract_metaphor(thinking_text),
        terms_explained=extract_explained_terms(thinking_text),
        decision_points=extract_decision_points(thinking_text),
        concerns=extract_concerns(thinking_text),
        confidence_level=analyze_confidence_level(thinking_text),
    )
    
    # 品質フラグ
    quality_flags = []
    recommendations = []
    
    if not insights.metaphor_chosen:
        quality_flags.append("no_metaphor_detected")
        recommendations.append("プロンプトにメタファー選択の明示的な指示を追加")
    
    if len(insights.terms_explained) == 0:
        quality_flags.append("no_terms_explained")
        recommendations.append("専門用語の説明を促すプロンプトを強化")
    
    if insights.confidence_level == "low":
        quality_flags.append("low_confidence")
        recommendations.append("AIの不確実性が高い。より具体的な指示が必要")
    
    if len(insights.concerns) > 3:
        quality_flags.append("high_concerns")
        recommendations.append("懸念事項が多い。タスクを分解または簡略化を検討")
    
    logger.info(f"  ✅ Metaphor: {insights.metaphor_chosen or 'Not detected'}")
    logger.info(f"  ✅ Terms explained: {len(insights.terms_explained)}")
    logger.info(f"  ✅ Confidence: {insights.confidence_level}")
    
    if quality_flags:
        logger.warning(f"  ⚠️ Quality flags: {', '.join(quality_flags)}")
    
    return CoTAnalysisResult(
        thinking_text=thinking_text,
        insights=insights,
        quality_flags=quality_flags,
        recommendations=recommendations,
    )
