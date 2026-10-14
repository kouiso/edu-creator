"""
=============================================================================
Problem Debugger (問題診断ヘルパー)
品質失敗の原因を診断し、修正方法を提案

柱6: デバッグ・可観測性の強化
- 問題発生時に「検索/プロンプト/データ」を素早く切り分け
- 構造化ログを活用した原因特定
- 修正提案の自動生成
=============================================================================
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .structured_logger import AILogEntry, StructuredLogger


@dataclass
class DiagnosisResult:
    """診断結果"""

    chapter_id: str
    errors: list[str]

    # 原因カテゴリ
    root_cause: Literal["retrieval", "prompt", "data", "unknown"] | None = None

    # 原因の詳細
    root_cause_detail: str = ""

    # 修正提案
    suggested_fix: str = ""

    # 関連するログエントリ
    related_logs: list[dict[str, Any]] = field(default_factory=list)

    # 追加情報
    additional_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """辞書形式に変換"""
        return {
            "chapter_id": self.chapter_id,
            "errors": self.errors,
            "root_cause": self.root_cause,
            "root_cause_detail": self.root_cause_detail,
            "suggested_fix": self.suggested_fix,
            "related_logs": self.related_logs,
            "additional_info": self.additional_info,
        }


class QualityDebugger:
    """品質問題の診断クラス"""

    def __init__(self, log_dir: Path):
        """
        Args:
            log_dir: ログディレクトリのパス
        """
        self.log_dir = Path(log_dir)
        self.logger = StructuredLogger(log_dir)

    def diagnose(
        self,
        chapter_id: str,
        validation_errors: list[str],
    ) -> DiagnosisResult:
        """品質失敗の原因を診断

        診断フロー:
        1. 検索結果の確認（RAGの問題か？）
        2. プロンプトの確認（指示の問題か？）
        3. データの問題（入力設定の問題か？）

        Args:
            chapter_id: 章ID
            validation_errors: バリデーションエラーのリスト

        Returns:
            DiagnosisResult: 診断結果
        """
        result = DiagnosisResult(
            chapter_id=chapter_id,
            errors=validation_errors,
        )

        # ログを読み込む
        logs = self.logger.load_logs()
        chapter_logs = [log for log in logs if log.chapter_id == chapter_id]

        if not chapter_logs:
            result.root_cause = "unknown"
            result.root_cause_detail = "該当する章のログが見つかりません"
            result.suggested_fix = "ログディレクトリを確認してください"
            return result

        # エラーの種類を分類
        error_categories = self._categorize_errors(validation_errors)

        # Step 1: 検索結果の確認（Scoutの問題か？）
        scout_diagnosis = self._diagnose_retrieval(chapter_logs, error_categories)
        if scout_diagnosis:
            return self._merge_diagnosis(result, scout_diagnosis)

        # Step 2: プロンプト/思考の確認（Scribeの問題か？）
        prompt_diagnosis = self._diagnose_prompt(chapter_logs, error_categories)
        if prompt_diagnosis:
            return self._merge_diagnosis(result, prompt_diagnosis)

        # Step 3: データの問題（入力設定の問題か？）
        data_diagnosis = self._diagnose_data(chapter_logs, error_categories)
        if data_diagnosis:
            return self._merge_diagnosis(result, data_diagnosis)

        # 原因不明
        result.root_cause = "unknown"
        result.root_cause_detail = "自動診断では原因を特定できませんでした"
        result.suggested_fix = "ログを手動で確認してください"
        result.related_logs = [self._log_to_dict(log) for log in chapter_logs[-5:]]

        return result

    def _categorize_errors(self, errors: list[str]) -> dict[str, list[str]]:
        """エラーをカテゴリ別に分類"""
        categories: dict[str, list[str]] = {
            "forbidden_words": [],  # 禁止ワード
            "code_length": [],  # コード長超過
            "missing_visuals": [],  # ビジュアル要素不足
            "missing_terms": [],  # 用語説明不足
            "structure": [],  # 構造の問題
            "other": [],
        }

        for error in errors:
            error_lower = error.lower()

            if any(word in error_lower for word in ["禁止", "同様に", "以下略", "簡単です"]):
                categories["forbidden_words"].append(error)
            elif any(word in error_lower for word in ["行", "長さ", "超過", "line"]):
                categories["code_length"].append(error)
            elif any(word in error_lower for word in ["表", "table", "mermaid", "図"]):
                categories["missing_visuals"].append(error)
            elif any(word in error_lower for word in ["用語", "説明", "term"]):
                categories["missing_terms"].append(error)
            elif any(word in error_lower for word in ["構造", "セクション", "見出し"]):
                categories["structure"].append(error)
            else:
                categories["other"].append(error)

        return categories

    def _diagnose_retrieval(
        self,
        logs: list[AILogEntry],
        error_categories: dict[str, list[str]],
    ) -> DiagnosisResult | None:
        """検索（Scout）の問題を診断"""

        # Scoutのログを探す
        scout_logs = [log for log in logs if log.agent_name == "Scout"]

        if not scout_logs:
            return None

        scout_log = scout_logs[-1]  # 最新のScoutログ

        # 検索結果が空または少ない場合
        if scout_log.retrieval_results is not None:
            if len(scout_log.retrieval_results) == 0:
                return DiagnosisResult(
                    chapter_id="",
                    errors=[],
                    root_cause="retrieval",
                    root_cause_detail="Scoutの検索結果が空です",
                    suggested_fix="検索クエリを見直すか、対象ディレクトリを確認してください",
                    related_logs=[self._log_to_dict(scout_log)],
                )

            if len(scout_log.retrieval_results) < 3:
                return DiagnosisResult(
                    chapter_id="",
                    errors=[],
                    root_cause="retrieval",
                    root_cause_detail=f"Scoutの検索結果が少なすぎます（{len(scout_log.retrieval_results)}件）",
                    suggested_fix="検索クエリを広げるか、別のディレクトリを検索してください",
                    related_logs=[self._log_to_dict(scout_log)],
                )

        return None

    def _diagnose_prompt(
        self,
        logs: list[AILogEntry],
        error_categories: dict[str, list[str]],
    ) -> DiagnosisResult | None:
        """プロンプト（Scribe）の問題を診断"""

        # Scribeのログを探す
        scribe_logs = [log for log in logs if log.agent_name == "Scribe"]

        if not scribe_logs:
            return None

        scribe_log = scribe_logs[-1]  # 最新のScribeログ

        # 思考過程を分析
        if scribe_log.thinking:
            thinking_lower = scribe_log.thinking.lower()

            # 禁止ワードエラーがあるのにメタファーへの言及がない場合
            if error_categories["forbidden_words"] and "metaphor" not in thinking_lower and "メタファー" not in scribe_log.thinking:
                return DiagnosisResult(
                    chapter_id="",
                    errors=[],
                    root_cause="prompt",
                    root_cause_detail="思考過程にメタファーへの言及がありません",
                    suggested_fix="プロンプトでメタファー使用の指示を強化してください",
                    related_logs=[self._log_to_dict(scribe_log)],
                    additional_info={"thinking_excerpt": scribe_log.thinking[:500]},
                )

            # ビジュアル要素不足エラーがあるのに表・図への言及がない場合
            if error_categories["missing_visuals"]:
                if "table" not in thinking_lower and "表" not in scribe_log.thinking:
                    return DiagnosisResult(
                        chapter_id="",
                        errors=[],
                        root_cause="prompt",
                        root_cause_detail="思考過程に表・ビジュアル要素への言及がありません",
                        suggested_fix="プロンプトで表・図の使用を強調してください",
                        related_logs=[self._log_to_dict(scribe_log)],
                    )

        # バリデーションエラーがある場合
        if scribe_log.validation_errors:
            return DiagnosisResult(
                chapter_id="",
                errors=[],
                root_cause="prompt",
                root_cause_detail=f"Scribeの出力にバリデーションエラー: {scribe_log.validation_errors}",
                suggested_fix="品質ルールの指示を明確化してください",
                related_logs=[self._log_to_dict(scribe_log)],
            )

        return None

    def _diagnose_data(
        self,
        logs: list[AILogEntry],
        error_categories: dict[str, list[str]],
    ) -> DiagnosisResult | None:
        """データ（入力設定）の問題を診断"""

        # Commanderのログを探す
        commander_logs = [log for log in logs if log.agent_name == "Commander"]

        if commander_logs:
            commander_log = commander_logs[-1]

            # コンテキストサマリーを確認
            if commander_log.input_context_summary:
                context = commander_log.input_context_summary

                # 設定が不十分な場合
                if len(context) < 100:
                    return DiagnosisResult(
                        chapter_id="",
                        errors=[],
                        root_cause="data",
                        root_cause_detail="入力コンテキストが短すぎます",
                        suggested_fix="chapter_configの設定を充実させてください",
                        related_logs=[self._log_to_dict(commander_log)],
                    )

        return None

    def _merge_diagnosis(
        self,
        base: DiagnosisResult,
        specific: DiagnosisResult,
    ) -> DiagnosisResult:
        """診断結果をマージ"""
        base.root_cause = specific.root_cause
        base.root_cause_detail = specific.root_cause_detail
        base.suggested_fix = specific.suggested_fix
        base.related_logs = specific.related_logs
        base.additional_info = specific.additional_info
        return base

    def _log_to_dict(self, log: AILogEntry) -> dict[str, Any]:
        """AILogEntryを辞書に変換（デバッグ用）"""
        return {
            "request_id": log.request_id,
            "timestamp": log.timestamp,
            "agent_name": log.agent_name,
            "task_type": log.task_type,
            "model": log.model,
            "response_time_ms": log.response_time_ms,
            "output_valid": log.output_valid,
            "error_type": log.error_type,
            "error_message": log.error_message,
        }


def diagnose_quality_failure(
    chapter_id: str,
    validation_errors: list[str],
    log_dir: Path,
) -> DiagnosisResult:
    """品質失敗の原因を診断（便利関数）

    Args:
        chapter_id: 章ID
        validation_errors: バリデーションエラーのリスト
        log_dir: ログディレクトリのパス

    Returns:
        DiagnosisResult: 診断結果
    """
    debugger = QualityDebugger(log_dir)
    return debugger.diagnose(chapter_id, validation_errors)


def print_diagnosis_report(result: DiagnosisResult) -> None:
    """診断結果をコンソールに出力

    Args:
        result: 診断結果
    """
    print("\n" + "=" * 60)
    print("🔍 品質問題診断レポート")
    print("=" * 60)

    print(f"\n章ID: {result.chapter_id}")
    print(f"エラー数: {len(result.errors)}")

    if result.errors:
        print("\n📋 エラー一覧:")
        for i, error in enumerate(result.errors[:5], 1):  # 最大5個表示
            print(f"  {i}. {error}")
        if len(result.errors) > 5:
            print(f"  ... 他 {len(result.errors) - 5} 件")

    print("\n" + "-" * 60)

    # 原因カテゴリに応じたアイコン
    cause_icons = {
        "retrieval": "🔎",
        "prompt": "📝",
        "data": "📊",
        "unknown": "❓",
    }

    icon = cause_icons.get(result.root_cause or "unknown", "❓")
    print(f"\n{icon} 原因カテゴリ: {result.root_cause or 'unknown'}")
    print(f"   詳細: {result.root_cause_detail}")

    print(f"\n💡 修正提案:")
    print(f"   {result.suggested_fix}")

    if result.related_logs:
        print("\n📜 関連ログ:")
        for log in result.related_logs[:3]:  # 最大3件表示
            print(f"  - [{log.get('agent_name', 'unknown')}] {log.get('request_id', 'N/A')}")

    print("\n" + "=" * 60 + "\n")


def generate_fix_prompt(result: DiagnosisResult) -> str:
    """診断結果から修正用のプロンプトを生成

    Args:
        result: 診断結果

    Returns:
        str: 修正用プロンプト
    """
    prompt_parts = [
        "【品質問題の修正指示】",
        "",
        f"以下の問題が検出されました：",
    ]

    for error in result.errors[:5]:
        prompt_parts.append(f"- {error}")

    prompt_parts.extend([
        "",
        f"原因: {result.root_cause_detail}",
        "",
        f"修正方針: {result.suggested_fix}",
        "",
        "上記の問題を修正した新しいバージョンを生成してください。",
        "特に以下の点に注意してください：",
    ])

    # 原因カテゴリに応じた具体的な指示
    if result.root_cause == "retrieval":
        prompt_parts.extend([
            "- より適切なコード例を選択してください",
            "- 検索結果が不足している場合は、一般的な例を使用してください",
        ])
    elif result.root_cause == "prompt":
        prompt_parts.extend([
            "- 品質ルールを再確認し、全てのルールを遵守してください",
            "- 禁止ワードを使用しないでください",
            "- 表やMermaid図を必ず含めてください",
        ])
    elif result.root_cause == "data":
        prompt_parts.extend([
            "- 入力情報が不足している場合は、一般的な知識で補完してください",
            "- 章の目的を明確にして執筆してください",
        ])

    return "\n".join(prompt_parts)
