"""
=============================================================================
🏆 Golden Test Set - ゴールデンテストセット
=============================================================================

手作業で「品質が高い教材」をゴールデンとして定義し、
新プロンプト/スキル導入時にリグレッション検知。

実務の テスト戦略から学んだベストプラクティス。
"""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GoldenExample(BaseModel):
    """ゴールデン教材の定義"""
    
    id: str = Field(description="教材ID（例: day01）")
    file_path: str = Field(description="ファイルパス")
    expected_min_score: float = Field(ge=1.0, le=5.0, description="期待最低スコア")
    description: str = Field(description="この教材が優れている理由")
    created_by: str = Field(description="作成者/選定者")
    created_at: str = Field(description="選定日")


class RegressionTestResult(BaseModel):
    """リグレッションテスト結果"""
    
    golden_id: str = Field(description="ゴールデンID")
    actual_score: float = Field(description="実際のスコア")
    expected_min_score: float = Field(description="期待最低スコア")
    passed: bool = Field(description="テスト合格したか")
    degradation: float = Field(description="劣化量（負の値は改善）")
    comments: str = Field(description="コメント")


class GoldenTestReport(BaseModel):
    """ゴールデンテスト全体のレポート"""
    
    total_tests: int = Field(description="総テスト数")
    passed_tests: int = Field(description="合格テスト数")
    failed_tests: int = Field(description="不合格テスト数")
    pass_rate: float = Field(description="合格率")
    results: list[RegressionTestResult] = Field(description="個別結果")
    overall_status: str = Field(description="全体ステータス（PASS/FAIL）")


# ============================================================================
# ゴールデンテストセットの定義
# ============================================================================

GOLDEN_TEST_SET: list[GoldenExample] = [
    GoldenExample(
        id="day01",
        file_path="material/30days-curriculum/day01_環境構築の第一歩.md",
        expected_min_score=4.0,
        description="初心者向けのメタファー（キッチン）が効果的。環境構築の説明が明確。",
        created_by="Uchida Yuki",
        created_at="2026-02-03",
    ),
    # 他のゴールデン教材はここに追加
]


def load_golden_test_set(config_path: Path | None = None) -> list[GoldenExample]:
    """
    ゴールデンテストセットを読み込む
    
    Args:
        config_path: カスタム設定ファイルのパス（Noneの場合はデフォルト）
    
    Returns:
        GoldenExample のリスト
    """
    if config_path and config_path.exists():
        # YAMLから読み込み
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [GoldenExample(**item) for item in data.get("golden_test_set", [])]
    else:
        # デフォルトのゴールデンテストセット
        return GOLDEN_TEST_SET


def run_regression_test(
    golden: GoldenExample,
    evaluate_func: Any,
) -> RegressionTestResult:
    """
    単一ゴールデン教材でリグレッションテスト
    
    Args:
        golden: GoldenExample オブジェクト
        evaluate_func: 評価関数（content -> float スコア）
    
    Returns:
        RegressionTestResult オブジェクト
    """
    logger.info(f"🧪 Testing golden example: {golden.id}")
    
    # ファイルを読み込み
    file_path = Path(golden.file_path)
    if not file_path.exists():
        logger.error(f"❌ File not found: {file_path}")
        return RegressionTestResult(
            golden_id=golden.id,
            actual_score=0.0,
            expected_min_score=golden.expected_min_score,
            passed=False,
            degradation=golden.expected_min_score,
            comments=f"File not found: {file_path}",
        )
    
    content = file_path.read_text(encoding="utf-8")
    
    # 評価実行
    try:
        actual_score = evaluate_func(content)
    except Exception as e:
        logger.error(f"❌ Evaluation failed for {golden.id}: {e}")
        return RegressionTestResult(
            golden_id=golden.id,
            actual_score=0.0,
            expected_min_score=golden.expected_min_score,
            passed=False,
            degradation=golden.expected_min_score,
            comments=f"Evaluation error: {str(e)}",
        )
    
    # 合格判定
    passed = actual_score >= golden.expected_min_score
    degradation = golden.expected_min_score - actual_score
    
    if passed:
        comments = f"✅ PASS - スコア {actual_score:.2f} は期待値 {golden.expected_min_score:.2f} 以上"
    else:
        comments = f"❌ FAIL - スコア {actual_score:.2f} は期待値 {golden.expected_min_score:.2f} 未満（劣化: {degradation:.2f}）"
    
    logger.info(f"  {comments}")
    
    return RegressionTestResult(
        golden_id=golden.id,
        actual_score=actual_score,
        expected_min_score=golden.expected_min_score,
        passed=passed,
        degradation=degradation,
        comments=comments,
    )


def run_golden_test_suite(
    golden_set: list[GoldenExample],
    evaluate_func: Any,
) -> GoldenTestReport:
    """
    ゴールデンテストスイート全体を実行
    
    Args:
        golden_set: GoldenExample のリスト
        evaluate_func: 評価関数（content -> float スコア）
    
    Returns:
        GoldenTestReport オブジェクト
    
    Example:
        golden_set = load_golden_test_set()
        report = run_golden_test_suite(golden_set, llm_judge_evaluate)
        
        if report.overall_status == "FAIL":
            print(f"⚠️ Regression detected! {report.failed_tests}/{report.total_tests} tests failed")
        else:
            print(f"✅ All tests passed! ({report.pass_rate * 100:.1f}%)")
    """
    logger.info(f"🧪 Running golden test suite ({len(golden_set)} tests)...")
    
    results: list[RegressionTestResult] = []
    for golden in golden_set:
        result = run_regression_test(golden, evaluate_func)
        results.append(result)
    
    # 統計計算
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total if total > 0 else 0.0
    overall_status = "PASS" if failed == 0 else "FAIL"
    
    report = GoldenTestReport(
        total_tests=total,
        passed_tests=passed,
        failed_tests=failed,
        pass_rate=pass_rate,
        results=results,
        overall_status=overall_status,
    )
    
    # レポート出力
    logger.info("=" * 70)
    logger.info(f"📊 Golden Test Report")
    logger.info(f"  Total: {total}")
    logger.info(f"  Passed: {passed}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Pass Rate: {pass_rate * 100:.1f}%")
    logger.info(f"  Overall: {overall_status}")
    logger.info("=" * 70)
    
    if failed > 0:
        logger.warning("⚠️ Regression detected! Failed tests:")
        for result in results:
            if not result.passed:
                logger.warning(f"  - {result.golden_id}: {result.comments}")
    
    return report
