"""
=============================================================================
🔧 LLM Wrapper with Advanced Retry Strategy
=============================================================================

CrewAI の LLM クラスをラップし、高度なリトライ戦略を適用します。

実務の ベストプラクティス:
- Exponential Backoff + Jitter
- Model Fallback (Gemini → Claude → GPT)
- レート制限エラーの自動検知と待機
"""

import logging
from typing import Any

from crewai import LLM

from utils.retry_strategy import RetryConfig, retry_with_fallback

logger = logging.getLogger(__name__)


class ResilientLLM:
    """
    リトライ戦略を適用したLLMラッパー
    
    CrewAI の LLM クラスをラップし、API障害時に自動リトライします。
    
    Usage:
        llm = create_worker_llm(config)
        resilient_llm = ResilientLLM(llm, retry_config)
        
        # CrewAI Agent で使用
        agent = Agent(
            role="...",
            llm=resilient_llm.llm,  # 内部のLLMを渡す
            ...
        )
    """
    
    def __init__(
        self,
        llm: LLM,
        retry_config: RetryConfig | None = None,
    ):
        """
        Args:
            llm: CrewAI の LLM インスタンス
            retry_config: リトライ設定（Noneの場合はデフォルト）
        """
        self.llm = llm
        self.retry_config = retry_config or RetryConfig(
            max_retries=3,
            initial_wait=1.0,
            max_wait=60.0,
            jitter=True,
        )
    
    def call_with_retry(self, prompt: str, **kwargs: Any) -> str:
        """
        プロンプトを実行（リトライ付き）
        
        Args:
            prompt: プロンプト文字列
            **kwargs: LLM.call() に渡す引数
        
        Returns:
            LLMの応答
        
        Raises:
            最後のリトライが失敗した場合は例外を再発生
        """
        def _call() -> str:
            # CrewAI の LLM.call() は通常このようなインターフェース
            # （実際の実装は CrewAI のバージョンによって異なる可能性があります）
            return self.llm.call(prompt, **kwargs)
        
        return retry_with_fallback(
            _call,
            self.retry_config,
            current_model=self.llm.model,
        )


def create_resilient_llm(
    llm: LLM,
    max_retries: int = 3,
    model_fallback: list[str] | None = None,
) -> ResilientLLM:
    """
    リトライ戦略を適用したLLMを作成
    
    Args:
        llm: ベースとなる CrewAI LLM
        max_retries: 最大リトライ回数
        model_fallback: フォールバックモデルリスト（例: ["gemini-2.0-flash", "claude-3-5-sonnet"]）
    
    Returns:
        ResilientLLM インスタンス
    
    Usage:
        llm = create_worker_llm(config)
        resilient_llm = create_resilient_llm(
            llm,
            max_retries=3,
            model_fallback=["gemini-2.0-flash", "claude-3-5-sonnet", "gpt-4o"]
        )
    """
    retry_config = RetryConfig(
        max_retries=max_retries,
        initial_wait=1.0,
        max_wait=60.0,
        jitter=True,
        model_fallback=model_fallback,
    )
    
    return ResilientLLM(llm, retry_config)
