"""
=============================================================================
📈 PDCA Monitor - 継続的品質改善ループ
=============================================================================

定期的（週1回）に全教材を LLM Judge で評価。
スコア推移をグラフ化。
低下トレンド検知時は自動アラート＋手動調査。

品質の安定的維持。

実務の 品質管理から学んだベストプラクティス。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QualitySnapshot(BaseModel):
    """品質スナップショット（ある時点の評価）"""
    
    chapter_id: str = Field(description="章ID")
    timestamp: str = Field(description="評価日時")
    score: float = Field(description="スコア")
    evaluator: str = Field(description="評価者（judge名）")


class QualityTrend(BaseModel):
    """品質トレンド"""
    
    chapter_id: str = Field(description="章ID")
    snapshots: list[QualitySnapshot] = Field(description="スナップショット一覧")
    current_score: float = Field(description="現在のスコア")
    previous_score: float | None = Field(default=None, description="前回のスコア")
    trend: str = Field(description="トレンド（improving/stable/declining）")
    alert_level: str = Field(description="アラートレベル（none/warning/critical）")


class PDCAReport(BaseModel):
    """PDCA レポート"""
    
    report_date: str = Field(description="レポート日")
    total_chapters: int = Field(description="総章数")
    avg_score: float = Field(description="平均スコア")
    trends: list[QualityTrend] = Field(description="トレンド一覧")
    alerts: list[str] = Field(default_factory=list, description="アラート")
    recommendations: list[str] = Field(default_factory=list, description="推奨アクション")


def evaluate_all_chapters(
    chapters_dir: Path,
    evaluate_func: Any,
) -> list[QualitySnapshot]:
    """
    全章を評価
    
    Args:
        chapters_dir: 章ディレクトリ
        evaluate_func: 評価関数（content -> float スコア）
    
    Returns:
        QualitySnapshot のリスト
    """
    logger.info("📊 Evaluating all chapters...")
    
    snapshots: list[QualitySnapshot] = []
    timestamp = datetime.now().isoformat()
    
    # 全教材ファイルを取得
    for chapter_file in sorted(chapters_dir.glob("day*.md")):
        chapter_id = chapter_file.stem.split('_')[0]  # day01
        
        logger.info(f"  ▶️ Evaluating {chapter_id}...")
        
        content = chapter_file.read_text(encoding="utf-8")
        score = evaluate_func(content)
        
        snapshot = QualitySnapshot(
            chapter_id=chapter_id,
            timestamp=timestamp,
            score=score,
            evaluator="llm_judge",
        )
        
        snapshots.append(snapshot)
        
        logger.info(f"  ✅ {chapter_id}: {score:.2f}/5.0")
    
    return snapshots


def analyze_trend(snapshots: list[QualitySnapshot]) -> QualityTrend:
    """
    スナップショットからトレンドを分析
    
    Args:
        snapshots: 同じchapter_idのスナップショット一覧（時系列順）
    
    Returns:
        QualityTrend
    """
    if not snapshots:
        raise ValueError("No snapshots provided")
    
    chapter_id = snapshots[0].chapter_id
    current_score = snapshots[-1].score
    previous_score = snapshots[-2].score if len(snapshots) > 1 else None
    
    # トレンド判定
    if previous_score is None:
        trend = "stable"
        alert_level = "none"
    else:
        diff = current_score - previous_score
        
        if diff > 0.2:
            trend = "improving"
            alert_level = "none"
        elif diff < -0.2:
            trend = "declining"
            alert_level = "warning" if diff > -0.5 else "critical"
        else:
            trend = "stable"
            alert_level = "none"
    
    return QualityTrend(
        chapter_id=chapter_id,
        snapshots=snapshots,
        current_score=current_score,
        previous_score=previous_score,
        trend=trend,
        alert_level=alert_level,
    )


def generate_pdca_report(
    current_snapshots: list[QualitySnapshot],
    historical_snapshots: dict[str, list[QualitySnapshot]],
) -> PDCAReport:
    """
    PDCA レポートを生成
    
    Args:
        current_snapshots: 今回の評価結果
        historical_snapshots: {chapter_id: [過去のスナップショット]} の辞書
    
    Returns:
        PDCAReport
    """
    logger.info("📈 Generating PDCA report...")
    
    trends: list[QualityTrend] = []
    alerts: list[str] = []
    recommendations: list[str] = []
    
    for snapshot in current_snapshots:
        chapter_id = snapshot.chapter_id
        
        # 過去のスナップショットと結合
        all_snapshots = historical_snapshots.get(chapter_id, []) + [snapshot]
        
        # トレンド分析
        trend = analyze_trend(all_snapshots)
        trends.append(trend)
        
        # アラート
        if trend.alert_level == "warning":
            alerts.append(f"⚠️ {chapter_id}: 品質低下検知（{trend.current_score:.2f} → {trend.previous_score:.2f}）")
            recommendations.append(f"{chapter_id}: プロンプトまたはスキルを再確認")
        elif trend.alert_level == "critical":
            alerts.append(f"🚨 {chapter_id}: 重大な品質低下（{trend.current_score:.2f} → {trend.previous_score:.2f}）")
            recommendations.append(f"{chapter_id}: 即座に再生成または手動修正")
    
    # 平均スコア
    avg_score = sum(s.score for s in current_snapshots) / len(current_snapshots) if current_snapshots else 0.0
    
    report = PDCAReport(
        report_date=datetime.now().isoformat(),
        total_chapters=len(current_snapshots),
        avg_score=avg_score,
        trends=trends,
        alerts=alerts,
        recommendations=recommendations,
    )
    
    # レポート出力
    logger.info("=" * 70)
    logger.info(f"📊 PDCA Report - {report.report_date}")
    logger.info(f"  Total Chapters: {report.total_chapters}")
    logger.info(f"  Average Score: {report.avg_score:.2f}/5.0")
    logger.info(f"  Alerts: {len(report.alerts)}")
    
    if report.alerts:
        for alert in report.alerts:
            logger.warning(f"  {alert}")
    
    logger.info("=" * 70)
    
    return report


def save_snapshots_to_history(
    snapshots: list[QualitySnapshot],
    history_file: Path = Path("logs/quality_history.jsonl"),
) -> None:
    """
    スナップショットを履歴ファイルに保存（JSONL形式）
    
    Args:
        snapshots: 保存するスナップショット
        history_file: 履歴ファイルパス
    """
    import json
    
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(history_file, "a", encoding="utf-8") as f:
        for snapshot in snapshots:
            f.write(snapshot.model_dump_json() + "\n")
    
    logger.info(f"💾 Saved {len(snapshots)} snapshots to {history_file}")
