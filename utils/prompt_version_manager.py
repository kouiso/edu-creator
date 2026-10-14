"""
=============================================================================
📦 Prompt Version Manager - プロンプトバージョン管理
=============================================================================

複数のプロンプトバージョンを並行テストし、LLM Judge スコアで比較。

プロンプト改善サイクルの科学的検証。

実務の 推奨ベストプラクティス。
"""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PromptVersion(BaseModel):
    """プロンプトバージョン"""
    
    version: str = Field(description="バージョン番号（例: v1.0, v1.1）")
    file_path: str = Field(description="プロンプトファイルパス")
    description: str = Field(description="このバージョンの変更内容")
    created_at: str = Field(description="作成日")
    author: str = Field(description="作成者")


class ABTestResult(BaseModel):
    """A/Bテスト結果"""
    
    version_a: str = Field(description="バージョンA")
    version_b: str = Field(description="バージョンB")
    score_a: float = Field(description="バージョンAのスコア")
    score_b: float = Field(description="バージョンBのスコア")
    winner: str = Field(description="勝者（version_a/version_b/tie）")
    improvement: float = Field(description="改善率（%）")
    recommendation: str = Field(description="推奨アクション")


def load_prompt_version(version: str, prompt_dir: Path = Path("prompt/task")) -> str:
    """
    指定されたバージョンのプロンプトを読み込む
    
    Args:
        version: バージョン番号（例: v1.0）
        prompt_dir: プロンプトディレクトリ
    
    Returns:
        プロンプトファイルの内容
    """
    # バージョンファイル名（例: write_v1.0.py）
    version_file = prompt_dir / f"write_{version}.py"
    
    if not version_file.exists():
        raise FileNotFoundError(f"Prompt version not found: {version_file}")
    
    return version_file.read_text(encoding="utf-8")


def ab_test_prompts(
    version_a: str,
    version_b: str,
    test_content: str,
    evaluate_func: Any,
    prompt_dir: Path = Path("prompt/task"),
) -> ABTestResult:
    """
    2つのプロンプトバージョンを A/B テスト
    
    Args:
        version_a: バージョンA（例: v1.0）
        version_b: バージョンB（例: v1.1）
        test_content: テスト用コンテンツ
        evaluate_func: 評価関数（content -> float スコア）
        prompt_dir: プロンプトディレクトリ
    
    Returns:
        ABTestResult オブジェクト
    """
    logger.info(f"🧪 A/B Testing: {version_a} vs {version_b}")
    
    # バージョンAで生成
    logger.info(f"  ▶️ Testing {version_a}...")
    prompt_a = load_prompt_version(version_a, prompt_dir)
    # （実際には prompt_a を使ってコンテンツを生成）
    score_a = evaluate_func(test_content)  # 簡略化
    logger.info(f"  ✅ {version_a}: {score_a:.2f}/5.0")
    
    # バージョンBで生成
    logger.info(f"  ▶️ Testing {version_b}...")
    prompt_b = load_prompt_version(version_b, prompt_dir)
    score_b = evaluate_func(test_content)  # 簡略化
    logger.info(f"  ✅ {version_b}: {score_b:.2f}/5.0")
    
    # 勝者判定
    if score_b > score_a + 0.1:  # 0.1以上の差で有意とする
        winner = "version_b"
        improvement = ((score_b - score_a) / score_a) * 100
        recommendation = f"ADOPT {version_b} - {improvement:.1f}% improvement"
    elif score_a > score_b + 0.1:
        winner = "version_a"
        improvement = ((score_a - score_b) / score_b) * 100
        recommendation = f"KEEP {version_a} - {version_b} performs worse"
    else:
        winner = "tie"
        improvement = 0.0
        recommendation = "TIE - No significant difference"
    
    logger.info(f"📊 Result: {recommendation}")
    
    return ABTestResult(
        version_a=version_a,
        version_b=version_b,
        score_a=score_a,
        score_b=score_b,
        winner=winner,
        improvement=improvement,
        recommendation=recommendation,
    )


# ============================================================================
# プロンプトバージョン管理のベストプラクティス
# ============================================================================

PROMPT_VERSIONS: list[PromptVersion] = [
    PromptVersion(
        version="v1.0",
        file_path="prompt/task/write_v1.0.py",
        description="初期バージョン（600行のプロンプト）",
        created_at="2026-01-01",
        author="Uchida Yuki",
    ),
    PromptVersion(
        version="v2.0",
        file_path="prompt/task/write_v2.0.py",
        description="短縮版（200行、品質スキーマ参照）",
        created_at="2026-02-03",
        author="Uchida Yuki",
    ),
]
