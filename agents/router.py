"""
=============================================================================
🎯 Router Agent - ルータエージェント
=============================================================================

タスクの種類に応じて最適なエージェント構成を動的に選択。

例:
- 簡単な章 → Scribe のみ
- 複雑な章 → Scout + PM層を追加

適応的な処理構成で効率とコストをバランス。

実務の複数プロジェクトから学んだベストプラクティス。
"""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """タスク複雑度"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class AgentConfiguration(BaseModel):
    """エージェント構成"""
    
    use_scout: bool = Field(default=True, description="Scout を使用するか")
    use_scribe: bool = Field(default=True, description="Scribe を使用するか（必須）")
    use_pm_layer: bool = Field(default=False, description="PM層を使用するか")
    use_validator: bool = Field(default=True, description="Validator を使用するか")
    
    estimated_cost: float = Field(default=0.0, description="推定コスト（USD）")
    estimated_time_minutes: int = Field(default=15, description="推定時間（分）")


class RoutingDecision(BaseModel):
    """ルーティング決定"""
    
    task_id: str = Field(description="タスクID")
    complexity: TaskComplexity = Field(description="判定された複雑度")
    configuration: AgentConfiguration = Field(description="選択されたエージェント構成")
    reasoning: str = Field(description="判定理由")


def assess_task_complexity(
    chapter_title: str,
    chapter_topics: list[str],
    target_dirs: list[str] | None = None,
) -> TaskComplexity:
    """
    タスクの複雑度を評価
    
    Args:
        chapter_title: 章タイトル
        chapter_topics: トピック一覧
        target_dirs: 対象ディレクトリ
    
    Returns:
        TaskComplexity
    """
    complexity_score = 0
    
    if len(chapter_topics) <= 2:
        complexity_score += 1
    elif len(chapter_topics) <= 4:
        complexity_score += 2
    else:
        complexity_score += 3
    
    if target_dirs:
        if len(target_dirs) <= 2:
            complexity_score += 1
        elif len(target_dirs) <= 5:
            complexity_score += 2
        else:
            complexity_score += 3
    
    # キーワードベースの評価
    simple_keywords = ["基礎", "入門", "はじめて", "first", "basic", "intro"]
    
    title_lower = chapter_title.lower()
    
    if any(keyword in title_lower for keyword in complex_keywords):
        complexity_score += 2
    
    if any(keyword in title_lower for keyword in simple_keywords):
        complexity_score -= 1
    
    if complexity_score <= 2:
        return TaskComplexity.SIMPLE
    elif complexity_score <= 4:
        return TaskComplexity.MEDIUM
    else:
        return TaskComplexity.COMPLEX


def select_agent_configuration(
    complexity: TaskComplexity,
    config: dict[str, Any] | None = None,
) -> AgentConfiguration:
    """
    複雑度に応じてエージェント構成を選択
    
    Args:
        complexity: タスク複雑度
        config: 設定（オプション）
    
    Returns:
        AgentConfiguration
    """
    if complexity == TaskComplexity.SIMPLE:
        return AgentConfiguration(
            use_scout=False,
            use_scribe=True,
            use_pm_layer=False,
            use_validator=True,
            estimated_cost=0.10,
            estimated_time_minutes=5,
        )
    
    elif complexity == TaskComplexity.MEDIUM:
        return AgentConfiguration(
            use_scout=True,
            use_scribe=True,
            use_pm_layer=False,
            use_validator=True,
            estimated_cost=0.25,
            estimated_time_minutes=10,
        )
    
    else:
        # 複雑な章: 全エージェント（Scout + Scribe + PM層 + Validator）
        return AgentConfiguration(
            use_scout=True,
            use_scribe=True,
            use_pm_layer=True,  # PM層を追加
            use_validator=True,
            estimated_cost=0.50,
            estimated_time_minutes=20,
        )


def route_task(
    task_id: str,
    chapter_title: str,
    chapter_topics: list[str],
    target_dirs: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> RoutingDecision:
    """
    タスクをルーティング
    
    Args:
        task_id: タスクID
        chapter_title: 章タイトル
        chapter_topics: トピック一覧
        target_dirs: 対象ディレクトリ
        config: 設定（オプション）
    
    Returns:
        RoutingDecision
    """
    logger.info(f"🎯 Routing task: {task_id}")
    
    # 複雑度評価
    complexity = assess_task_complexity(chapter_title, chapter_topics, target_dirs)
    
    # エージェント構成選択
    configuration = select_agent_configuration(complexity, config)
    
    # 判定理由
    reasoning_parts = [
        f"Complexity: {complexity.value}",
        f"Topics: {len(chapter_topics)}",
    ]
    
    if target_dirs:
        reasoning_parts.append(f"Target dirs: {len(target_dirs)}")
    
    reasoning_parts.append(
        f"Configuration: Scout={configuration.use_scout}, "
        f"PM Layer={configuration.use_pm_layer}"
    )
    
    reasoning = ", ".join(reasoning_parts)
    
    logger.info(f"  ✅ {reasoning}")
    logger.info(
        f"  💰 Estimated cost: ${configuration.estimated_cost:.2f}, "
        f"time: {configuration.estimated_time_minutes}min"
    )
    
    return RoutingDecision(
        task_id=task_id,
        complexity=complexity,
        configuration=configuration,
        reasoning=reasoning,
    )
