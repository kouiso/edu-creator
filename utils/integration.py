"""
=============================================================================
Integration Module (統合モジュール)
6つの柱の機能をmain.pyに統合するためのヘルパー

新機能:
- 構造化ログ（柱6）
- CoTパース（柱2）
- LLM-as-Judge評価（柱5）
- 前章コンテキスト（柱4）
- 問題診断（柱6）
=============================================================================
"""

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from .cot_parser import ParsedResponse, parse_cot_response
from .structured_logger import AILogEntry, StructuredLogger
from .chapter_context import (
    ChapterContext,
    build_context_for_chapter,
    format_context_for_prompt,
)
from .debugger import (
    DiagnosisResult,
    diagnose_quality_failure,
    print_diagnosis_report,
)


class EnhancedPipeline:
    """6つの柱を統合した拡張パイプライン

    Usage:
        pipeline = EnhancedPipeline(log_dir=Path("logs/day01"))

        # ログ記録
        pipeline.log_request(
            agent_name="Scout",
            task_type="research",
            chapter_id="day01",
            ...
        )

        # CoTレスポンスのパース
        parsed = pipeline.parse_response(raw_response)

        # 前章コンテキストの取得
        context = pipeline.get_chapter_context(chapter_num=2, output_dir=Path("output"))

        # 品質問題の診断
        diagnosis = pipeline.diagnose_failure(chapter_id, errors)
    """

    def __init__(self, log_dir: Path):
        """
        Args:
            log_dir: ログディレクトリ
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = StructuredLogger(log_dir)
        self._request_id: str | None = None

    def start_request(self) -> str:
        """新しいリクエストを開始

        Returns:
            str: リクエストID
        """
        self._request_id = str(uuid.uuid4())[:8]
        return self._request_id

    def log_request(
        self,
        agent_name: str,
        task_type: str,
        chapter_id: str = "",
        input_prompt: str = "",
        input_context_summary: str = "",
        retrieval_query: str | None = None,
        retrieval_results: list[str] | None = None,
        retrieval_time_ms: int | None = None,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        response_time_ms: int = 0,
        thinking: str | None = None,
        output_summary: str = "",
        output_valid: bool = True,
        validation_errors: list[str] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """AI呼び出しをログに記録

        Args:
            agent_name: エージェント名（Scout, Scribe, Commander等）
            task_type: タスクタイプ（research, write, outline等）
            chapter_id: 章ID
            input_prompt: 入力プロンプト（ハッシュ化して保存）
            input_context_summary: 入力コンテキストの要約
            retrieval_query: 検索クエリ（RAG用）
            retrieval_results: 検索結果（RAG用）
            retrieval_time_ms: 検索時間（RAG用）
            model: 使用モデル
            prompt_tokens: プロンプトトークン数
            completion_tokens: 完了トークン数
            response_time_ms: レスポンス時間
            thinking: 思考過程（CoT用）
            output_summary: 出力の要約
            output_valid: 出力が有効か
            validation_errors: バリデーションエラー
            error_type: エラータイプ
            error_message: エラーメッセージ
        """
        # プロンプトをハッシュ化（全文保存を避ける）
        prompt_hash = hashlib.sha256(input_prompt.encode()).hexdigest()[:16] if input_prompt else ""

        entry = AILogEntry(
            request_id=self._request_id or str(uuid.uuid4())[:8],
            timestamp="",  # StructuredLoggerが設定
            agent_name=agent_name,
            task_type=task_type,
            chapter_id=chapter_id,
            input_prompt_hash=prompt_hash,
            input_context_summary=input_context_summary[:500] if input_context_summary else "",
            retrieval_query=retrieval_query,
            retrieval_results=retrieval_results,
            retrieval_time_ms=retrieval_time_ms,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            response_time_ms=response_time_ms,
            thinking=thinking[:2000] if thinking else None,  # 思考は2000文字まで
            output_summary=output_summary[:500] if output_summary else "",
            output_valid=output_valid,
            validation_errors=validation_errors,
            error_type=error_type,
            error_message=error_message,
        )

        self.logger.log(entry)

    def parse_response(self, raw_response: str) -> ParsedResponse:
        """CoTレスポンスをパース

        Args:
            raw_response: 生のAIレスポンス

        Returns:
            ParsedResponse: パースされたレスポンス
        """
        return parse_cot_response(raw_response)

    def get_chapter_context(
        self,
        chapter_num: int,
        output_dir: Path,
    ) -> ChapterContext:
        """前章コンテキストを取得

        Args:
            chapter_num: 章番号（1から開始）
            output_dir: 出力ディレクトリ

        Returns:
            ChapterContext: 章のコンテキスト
        """
        return build_context_for_chapter(chapter_num, output_dir)

    def format_context_for_prompt(self, context: ChapterContext) -> str:
        """コンテキストをプロンプト用にフォーマット

        Args:
            context: 章のコンテキスト

        Returns:
            str: フォーマットされたコンテキスト
        """
        return format_context_for_prompt(context)

    def diagnose_failure(
        self,
        chapter_id: str,
        validation_errors: list[str],
    ) -> DiagnosisResult:
        """品質問題を診断

        Args:
            chapter_id: 章ID
            validation_errors: バリデーションエラーのリスト

        Returns:
            DiagnosisResult: 診断結果
        """
        return diagnose_quality_failure(
            chapter_id=chapter_id,
            validation_errors=validation_errors,
            log_dir=self.log_dir,
        )

    def print_diagnosis(self, result: DiagnosisResult) -> None:
        """診断結果を出力

        Args:
            result: 診断結果
        """
        print_diagnosis_report(result)


def create_enhanced_pipeline(log_dir: Path | str) -> EnhancedPipeline:
    """拡張パイプラインを作成（便利関数）

    Args:
        log_dir: ログディレクトリ

    Returns:
        EnhancedPipeline: パイプラインインスタンス

    Example:
        pipeline = create_enhanced_pipeline("logs/day01")
        pipeline.start_request()
        pipeline.log_request(agent_name="Scout", ...)
    """
    return EnhancedPipeline(log_dir=Path(log_dir))


def measure_time(func):
    """実行時間を計測するデコレータ

    Usage:
        @measure_time
        def my_function():
            ...
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_ms = int((time.time() - start) * 1000)
        return result, elapsed_ms
    return wrapper


# =============================================================================
# LLM-as-Judge統合（オプショナル - OpenAI APIキーが必要）
# =============================================================================

def evaluate_chapter_with_llm(
    chapter_path: Path,
    model: str = "gpt-4o",
) -> dict[str, Any] | None:
    """LLM-as-Judgeで章を評価（オプショナル）

    Note:
        この関数はOpenAI APIキーが設定されている場合のみ動作します。
        設定されていない場合はNoneを返します。

    Args:
        chapter_path: 章ファイルのパス
        model: 使用するモデル

    Returns:
        dict | None: 評価結果（API利用不可の場合はNone）
    """
    try:
        from .llm_judge import LLMJudge
        judge = LLMJudge(model=model)
        result = judge.evaluate_file(chapter_path)
        return result.to_dict()
    except ImportError:
        print("⚠️ OpenAI package not installed. Skipping LLM-as-Judge evaluation.")
        return None
    except Exception as e:
        print(f"⚠️ LLM-as-Judge evaluation failed: {e}")
        return None


# =============================================================================
# プロンプト統合ヘルパー
# =============================================================================

def get_structured_write_prompt(
    chapter_title: str,
    chapter_subtitle: str,
    day_number: int,
    quality_rules: str,
    outline: str,
    research_results: str,
    previous_chapter_context: str = "",
    user_notes: str = "",
) -> str:
    """構造化された執筆プロンプトを取得

    Args:
        chapter_title: 章タイトル
        chapter_subtitle: 章サブタイトル
        day_number: 日数
        quality_rules: 品質ルール
        outline: アウトライン
        research_results: 調査結果
        previous_chapter_context: 前章コンテキスト
        user_notes: ユーザーメモ

    Returns:
        str: 構造化されたプロンプト
    """
    from prompt.task.write import get_structured_prompt
    return get_structured_prompt(
        chapter_title=chapter_title,
        chapter_subtitle=chapter_subtitle,
        day_number=day_number,
        quality_rules=quality_rules,
        outline=outline,
        research_results=research_results,
        previous_chapter_context=previous_chapter_context,
        user_notes=user_notes,
    )
