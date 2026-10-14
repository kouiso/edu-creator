"""
=============================================================================
Structured Logger (構造化ログ)
AIインタラクションの構造化ログを提供

柱6: デバッグ・可観測性の強化
- 全てのAI呼び出しで構造化ログを保存
- リクエストIDでトレース可能
- 問題発生時に「検索/プロンプト/データ」の切り分けが可能
=============================================================================
"""

import json
import uuid
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


@dataclass
class AILogEntry:
    """AI呼び出しの構造化ログエントリ"""

    # 識別情報
    request_id: str
    timestamp: str
    agent_name: str
    task_type: str
    chapter_id: str = ""

    # 入力情報
    input_prompt_hash: str = ""  # プロンプト全文のハッシュ（全文は別ファイル）
    input_context_summary: str = ""  # コンテキストの要約

    # 検索情報（RAG/Scout用）
    retrieval_query: str | None = None
    retrieval_results: list[dict] | None = None
    retrieval_time_ms: int | None = None

    # 生成情報
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    response_time_ms: int = 0

    # 思考情報（CoT用）
    thinking: str | None = None

    # 出力情報
    output_summary: str = ""
    output_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    # エラー情報
    error_type: str | None = None
    error_message: str | None = None

    # メタデータ
    metadata: dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """構造化ログを管理するクラス"""

    def __init__(self, log_dir: Path, chapter_id: str = ""):
        """
        Args:
            log_dir: ログディレクトリのパス
            chapter_id: 章ID（例: "day01"）
        """
        self.log_dir = Path(log_dir)
        self.chapter_id = chapter_id
        self.log_file = self.log_dir / "ai_interactions.jsonl"
        self.prompt_dir = self.log_dir / "prompts"

        # ディレクトリを作成
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_dir.mkdir(parents=True, exist_ok=True)

    def create_entry(
        self,
        agent_name: str,
        task_type: str,
        **kwargs: Any,
    ) -> AILogEntry:
        """新しいログエントリを作成

        Args:
            agent_name: エージェント名（Scout, Scribe, Commander等）
            task_type: タスクタイプ（research, write, outline等）
            **kwargs: その他のフィールド

        Returns:
            AILogEntry: 新しいログエントリ
        """
        return AILogEntry(
            request_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            agent_name=agent_name,
            task_type=task_type,
            chapter_id=self.chapter_id,
            **kwargs,
        )

    def save_prompt(self, prompt: str, request_id: str) -> str:
        """プロンプト全文を別ファイルに保存し、ハッシュを返す

        Args:
            prompt: プロンプト全文
            request_id: リクエストID

        Returns:
            str: プロンプトのハッシュ値
        """
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        prompt_file = self.prompt_dir / f"{request_id}_{prompt_hash}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        return prompt_hash

    def log(self, entry: AILogEntry) -> None:
        """ログエントリをJSONLファイルに追記

        Args:
            entry: ログエントリ
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def log_interaction(
        self,
        agent_name: str,
        task_type: str,
        prompt: str,
        output: str,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        response_time_ms: int = 0,
        thinking: str | None = None,
        validation_errors: list[str] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AILogEntry:
        """AI呼び出しをログに記録（便利メソッド）

        Args:
            agent_name: エージェント名
            task_type: タスクタイプ
            prompt: プロンプト全文
            output: 出力
            model: 使用モデル
            prompt_tokens: プロンプトトークン数
            completion_tokens: 完了トークン数
            response_time_ms: レスポンス時間（ミリ秒）
            thinking: 思考過程（CoT）
            validation_errors: バリデーションエラー
            error_type: エラータイプ
            error_message: エラーメッセージ
            metadata: 追加メタデータ

        Returns:
            AILogEntry: 記録されたログエントリ
        """
        entry = self.create_entry(agent_name, task_type)

        # プロンプトを保存
        entry.input_prompt_hash = self.save_prompt(prompt, entry.request_id)
        entry.input_context_summary = prompt[:200] + "..." if len(prompt) > 200 else prompt

        # 生成情報
        entry.model = model
        entry.prompt_tokens = prompt_tokens
        entry.completion_tokens = completion_tokens
        entry.response_time_ms = response_time_ms

        # 思考情報
        entry.thinking = thinking

        # 出力情報
        entry.output_summary = output[:500] + "..." if len(output) > 500 else output
        entry.output_valid = not validation_errors
        entry.validation_errors = validation_errors or []

        # エラー情報
        entry.error_type = error_type
        entry.error_message = error_message

        # メタデータ
        entry.metadata = metadata or {}

        # ログに記録
        self.log(entry)

        return entry

    def log_retrieval(
        self,
        agent_name: str,
        query: str,
        results: list[dict],
        retrieval_time_ms: int,
        metadata: dict[str, Any] | None = None,
    ) -> AILogEntry:
        """検索（RAG/Scout）をログに記録

        Args:
            agent_name: エージェント名
            query: 検索クエリ
            results: 検索結果
            retrieval_time_ms: 検索時間（ミリ秒）
            metadata: 追加メタデータ

        Returns:
            AILogEntry: 記録されたログエントリ
        """
        entry = self.create_entry(agent_name, "retrieval")
        entry.retrieval_query = query
        entry.retrieval_results = results
        entry.retrieval_time_ms = retrieval_time_ms
        entry.metadata = metadata or {}

        self.log(entry)
        return entry

    def load_logs(self, filter_agent: str | None = None) -> list[AILogEntry]:
        """ログを読み込む

        Args:
            filter_agent: 特定のエージェントでフィルタ（オプション）

        Returns:
            list[AILogEntry]: ログエントリのリスト
        """
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if filter_agent is None or data.get("agent_name") == filter_agent:
                        entries.append(AILogEntry(**data))

        return entries

    def get_summary(self) -> dict[str, Any]:
        """ログのサマリーを取得

        Returns:
            dict: サマリー情報
        """
        entries = self.load_logs()

        if not entries:
            return {"total_entries": 0}

        agents = {}
        total_tokens = 0
        total_time_ms = 0
        errors = []

        for entry in entries:
            # エージェント別カウント
            if entry.agent_name not in agents:
                agents[entry.agent_name] = {"count": 0, "errors": 0}
            agents[entry.agent_name]["count"] += 1
            if entry.error_type:
                agents[entry.agent_name]["errors"] += 1
                errors.append({
                    "request_id": entry.request_id,
                    "agent": entry.agent_name,
                    "error": entry.error_message,
                })

            # トークン・時間集計
            total_tokens += entry.prompt_tokens + entry.completion_tokens
            total_time_ms += entry.response_time_ms

        return {
            "total_entries": len(entries),
            "agents": agents,
            "total_tokens": total_tokens,
            "total_time_ms": total_time_ms,
            "errors": errors,
        }


def get_logger(log_dir: Path | str, chapter_id: str = "") -> StructuredLogger:
    """StructuredLoggerのインスタンスを取得

    Args:
        log_dir: ログディレクトリのパス
        chapter_id: 章ID

    Returns:
        StructuredLogger: ロガーインスタンス
    """
    return StructuredLogger(Path(log_dir), chapter_id)


# グローバルロガー（シングルトン的に使用する場合）
_global_logger: StructuredLogger | None = None


def init_global_logger(log_dir: Path | str, chapter_id: str = "") -> StructuredLogger:
    """グローバルロガーを初期化

    Args:
        log_dir: ログディレクトリのパス
        chapter_id: 章ID

    Returns:
        StructuredLogger: ロガーインスタンス
    """
    global _global_logger
    _global_logger = get_logger(log_dir, chapter_id)
    return _global_logger


def get_global_logger() -> StructuredLogger | None:
    """グローバルロガーを取得

    Returns:
        StructuredLogger | None: ロガーインスタンス（未初期化の場合はNone）
    """
    return _global_logger
