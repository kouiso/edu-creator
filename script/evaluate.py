#!/usr/bin/env python3
"""
=============================================================================
教材評価スクリプト
LLM-as-Judgeとゴールデンデータセットを使用した品質評価

柱5: 評価エンジニアリング
- 単一ファイルの評価
- 全教材の回帰テスト
- ゴールデンデータセットによる検証
=============================================================================

使用方法:
    # 単一ファイル評価
    python script/evaluate.py material/30days-curriculum/day01_*.md

    # 全教材評価
    python script/evaluate.py --all --output report.json

    # ゴールデンテスト実行
    python script/evaluate.py --golden-test

    # 標準入力から評価
    echo "テスト内容" | python script/evaluate.py --stdin
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.llm_judge import (
    LLMJudge,
    AsyncLLMJudge,
    EvaluationResult,
    print_evaluation_report,
)
from tests.ai.golden_dataset import (
    ALL_TEST_CASES,
    GOOD_EXAMPLES,
    BAD_EXAMPLES,
    GoldenTestCase,
    validate_test_case_result,
)


def evaluate_single_file(file_path: Path, model: str = "gpt-4o") -> EvaluationResult:
    """単一ファイルを評価

    Args:
        file_path: 評価対象ファイルのパス
        model: 使用するモデル

    Returns:
        EvaluationResult: 評価結果
    """
    judge = LLMJudge(model=model)
    return judge.evaluate_file(file_path)


async def evaluate_multiple_files(
    file_paths: list[Path],
    model: str = "gpt-4o",
) -> list[tuple[Path, EvaluationResult]]:
    """複数ファイルを並列評価

    Args:
        file_paths: 評価対象ファイルのリスト
        model: 使用するモデル

    Returns:
        list: (ファイルパス, 評価結果) のリスト
    """
    judge = AsyncLLMJudge(model=model)

    async def evaluate_one(path: Path) -> tuple[Path, EvaluationResult]:
        result = await judge.evaluate_file(path)
        return (path, result)

    tasks = [evaluate_one(path) for path in file_paths]
    results = await asyncio.gather(*tasks)

    return list(results)


def run_golden_tests(model: str = "gpt-4o") -> dict:
    """ゴールデンテストを実行

    Args:
        model: 使用するモデル

    Returns:
        dict: テスト結果サマリー
    """
    judge = LLMJudge(model=model)

    results = {
        "total": len(ALL_TEST_CASES),
        "passed": 0,
        "failed": 0,
        "details": [],
    }

    print("\n" + "=" * 60)
    print("🧪 ゴールデンテスト実行")
    print("=" * 60)

    for test_case in ALL_TEST_CASES:
        print(f"\n📋 {test_case.id}: {test_case.description}")

        # コンテンツを取得
        if test_case.content:
            content = test_case.content
        elif test_case.content_path:
            content_path = PROJECT_ROOT / test_case.content_path
            if not content_path.exists():
                print(f"  ⚠️ ファイルが見つかりません: {test_case.content_path}")
                results["failed"] += 1
                results["details"].append({
                    "id": test_case.id,
                    "passed": False,
                    "reason": f"File not found: {test_case.content_path}",
                })
                continue
            content = content_path.read_text(encoding="utf-8")
        else:
            print(f"  ⚠️ コンテンツが指定されていません")
            results["failed"] += 1
            continue

        # 評価実行
        eval_result = judge.evaluate(content)

        if eval_result.error:
            print(f"  ❌ 評価エラー: {eval_result.error}")
            results["failed"] += 1
            results["details"].append({
                "id": test_case.id,
                "passed": False,
                "reason": f"Evaluation error: {eval_result.error}",
            })
            continue

        # 結果検証
        actual_scores = {
            "clarity": eval_result.clarity.score,
            "accessibility": eval_result.accessibility.score,
            "engagement": eval_result.engagement.score,
            "actionability": eval_result.actionability.score,
            "self_containment": eval_result.self_containment.score,
        }

        passed, failures = validate_test_case_result(
            test_case,
            eval_result.overall_score,
            actual_scores,
        )

        if passed:
            print(f"  ✅ PASSED (score: {eval_result.overall_score:.1f})")
            results["passed"] += 1
        else:
            print(f"  ❌ FAILED (score: {eval_result.overall_score:.1f})")
            for failure in failures:
                print(f"     - {failure}")
            results["failed"] += 1

        results["details"].append({
            "id": test_case.id,
            "passed": passed,
            "actual_score": eval_result.overall_score,
            "actual_scores": actual_scores,
            "failures": failures if not passed else [],
        })

    # サマリー
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    print(f"  合計: {results['total']}")
    print(f"  成功: {results['passed']} ✅")
    print(f"  失敗: {results['failed']} ❌")
    print(f"  合格率: {results['passed'] / results['total'] * 100:.1f}%")
    print("=" * 60 + "\n")

    return results


def generate_report(
    results: list[tuple[Path, EvaluationResult]],
    output_path: Path | None = None,
) -> dict:
    """評価レポートを生成

    Args:
        results: 評価結果のリスト
        output_path: 出力ファイルパス（省略時はコンソール出力のみ）

    Returns:
        dict: レポートデータ
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(results),
        "passed": 0,
        "failed": 0,
        "average_score": 0.0,
        "files": [],
    }

    total_score = 0.0

    for file_path, result in results:
        file_data = {
            "path": str(file_path),
            "overall_score": result.overall_score,
            "passed": result.passed,
            "scores": {
                "clarity": result.clarity.score,
                "accessibility": result.accessibility.score,
                "engagement": result.engagement.score,
                "actionability": result.actionability.score,
                "self_containment": result.self_containment.score,
            },
            "critical_issues": result.critical_issues,
            "improvement_suggestions": result.improvement_suggestions,
            "error": result.error,
        }

        if result.passed:
            report["passed"] += 1
        else:
            report["failed"] += 1

        if not result.error:
            total_score += result.overall_score

        report["files"].append(file_data)

    if report["total_files"] > 0:
        report["average_score"] = round(total_score / report["total_files"], 2)

    # 出力
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📄 レポートを保存しました: {output_path}")

    return report


def print_summary(report: dict) -> None:
    """サマリーを表示

    Args:
        report: レポートデータ
    """
    print("\n" + "=" * 60)
    print("📊 評価サマリー")
    print("=" * 60)
    print(f"  評価日時: {report['generated_at']}")
    print(f"  対象ファイル数: {report['total_files']}")
    print(f"  合格: {report['passed']} ✅")
    print(f"  不合格: {report['failed']} ❌")
    print(f"  平均スコア: {report['average_score']:.1f}/5.0")

    if report["failed"] > 0:
        print("\n⚠️ 不合格ファイル:")
        for file_data in report["files"]:
            if not file_data["passed"]:
                print(f"  - {file_data['path']}: {file_data['overall_score']:.1f}")
                if file_data["critical_issues"]:
                    for issue in file_data["critical_issues"][:2]:
                        print(f"    → {issue}")

    print("=" * 60 + "\n")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="教材品質評価ツール（LLM-as-Judge）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 単一ファイル評価
  python script/evaluate.py material/30days-curriculum/day01_*.md

  # 全教材評価
  python script/evaluate.py --all --output report.json

  # ゴールデンテスト実行
  python script/evaluate.py --golden-test

  # 標準入力から評価
  echo "テスト内容" | python script/evaluate.py --stdin
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="評価対象のファイルパス",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="material/30days-curriculum/内の全ファイルを評価",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="標準入力からコンテンツを読み取って評価",
    )
    parser.add_argument(
        "--golden-test",
        action="store_true",
        help="ゴールデンテストを実行",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="レポートの出力先ファイルパス（JSON）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="使用するモデル（デフォルト: gpt-4o）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細な出力を表示",
    )

    args = parser.parse_args()

    # ゴールデンテスト
    if args.golden_test:
        results = run_golden_tests(model=args.model)
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"📄 結果を保存しました: {output_path}")
        sys.exit(0 if results["failed"] == 0 else 1)

    # 標準入力から評価
    if args.stdin:
        content = sys.stdin.read()
        if not content.strip():
            print("❌ 標準入力が空です")
            sys.exit(1)

        judge = LLMJudge(model=args.model)
        result = judge.evaluate(content)
        print_evaluation_report(result)
        sys.exit(0 if result.passed else 1)

    # 全ファイル評価
    if args.all:
        curriculum_dir = PROJECT_ROOT / "material" / "30days-curriculum"
        if not curriculum_dir.exists():
            print(f"❌ ディレクトリが見つかりません: {curriculum_dir}")
            sys.exit(1)

        files = list(curriculum_dir.glob("day*.md"))
        if not files:
            print(f"❌ 評価対象ファイルが見つかりません: {curriculum_dir}")
            sys.exit(1)

        print(f"📚 {len(files)}件のファイルを評価中...")

        results = asyncio.run(evaluate_multiple_files(files, model=args.model))
        report = generate_report(
            results,
            output_path=Path(args.output) if args.output else None,
        )
        print_summary(report)

        if args.verbose:
            for file_path, result in results:
                print(f"\n--- {file_path.name} ---")
                print_evaluation_report(result)

        sys.exit(0 if report["failed"] == 0 else 1)

    # 指定ファイル評価
    if args.files:
        files = [Path(f) for f in args.files]

        # 存在確認
        for f in files:
            if not f.exists():
                print(f"❌ ファイルが見つかりません: {f}")
                sys.exit(1)

        if len(files) == 1:
            # 単一ファイル
            result = evaluate_single_file(files[0], model=args.model)
            print_evaluation_report(result)
            sys.exit(0 if result.passed else 1)
        else:
            # 複数ファイル
            print(f"📚 {len(files)}件のファイルを評価中...")
            results = asyncio.run(evaluate_multiple_files(files, model=args.model))
            report = generate_report(
                results,
                output_path=Path(args.output) if args.output else None,
            )
            print_summary(report)

            if args.verbose:
                for file_path, result in results:
                    print(f"\n--- {file_path.name} ---")
                    print_evaluation_report(result)

            sys.exit(0 if report["failed"] == 0 else 1)

    # 引数なし
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
