"""
=============================================================================
🔄 Advanced Retry Strategy (Exponential Backoff + Jitter + Model Fallback)
=============================================================================

高度なリトライ戦略の実装。API障害時の自動回復率を向上させます。

特徴:
1. Exponential Backoff: 指数関数的にリトライ間隔を延ばす（1s → 2s → 4s → 8s）
2. Jitter: ランダムなブレを追加し、サンダリングハード問題を回避
3. Model Fallback: 異なるモデルを順次試行（Gemini → Claude → GPT）

実務の ベストプラクティスから学んだパターン。
"""

import random
import time
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """リトライ設定"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_wait: float = 1.0,
        max_wait: float = 60.0,
        exponential_base: int = 2,
        jitter: bool = True,
        model_fallback: list[str] | None = None,
    ):
        self.max_retries = max_retries
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.model_fallback = model_fallback or []


def exponential_backoff_with_jitter(
    attempt: int,
    initial_wait: float = 1.0,
    exponential_base: int = 2,
    max_wait: float = 60.0,
    jitter: bool = True,
) -> float:
    """
    Exponential Backoff + Jitter を計算
    
    Args:
        attempt: 試行回数（1から始まる）
        initial_wait: 初期待機時間（秒）
        exponential_base: 指数関数のベース（通常は2）
        max_wait: 最大待機時間（秒）
        jitter: ランダムなブレを追加するか
    
    Returns:
        待機時間（秒）
    
    Example:
        attempt=1: 1s (+ jitter)
        attempt=2: 2s (+ jitter)
        attempt=3: 4s (+ jitter)
        attempt=4: 8s (+ jitter)
    """
    # Exponential Backoff: initial_wait * (base ^ (attempt - 1))
    wait_time = min(initial_wait * (exponential_base ** (attempt - 1)), max_wait)
    
    # Jitter: ランダムに 0.5x ~ 1.5x のブレを追加
    if jitter:
        wait_time *= random.uniform(0.5, 1.5)
    
    return wait_time


def retry_with_fallback(
    func: Callable[..., T],
    retry_config: RetryConfig,
    current_model: str | None = None,
    **kwargs: Any,
) -> T:
    """
    Exponential Backoff + Model Fallback でリトライ実行
    
    Args:
        func: 実行する関数
        retry_config: リトライ設定
        current_model: 現在のモデル名（Noneの場合はモデル切り替えなし）
        **kwargs: func に渡す引数
    
    Returns:
        func の実行結果
    
    Raises:
        最後の試行が失敗した場合は例外を再発生
    
    Usage:
        config = RetryConfig(
            max_retries=3,
            model_fallback=["gemini-2.0-flash", "claude-3-5-sonnet", "gpt-4o"]
        )
        
        result = retry_with_fallback(
            call_llm,
            retry_config=config,
            current_model="gemini-2.0-flash",
            prompt="Hello"
        )
    """
    models_to_try = retry_config.model_fallback if current_model and retry_config.model_fallback else [current_model]
    
    last_exception = None
    
    for model_idx, model in enumerate(models_to_try):
        for attempt in range(1, retry_config.max_retries + 1):
            try:
                # モデルを kwargs に注入（model パラメータがある場合）
                if model and "model" in kwargs:
                    kwargs["model"] = model
                
                logger.info(
                    f"🔄 Retry attempt {attempt}/{retry_config.max_retries} "
                    f"(model: {model or 'default'}, model_idx: {model_idx + 1}/{len(models_to_try)})"
                )
                
                # 関数実行
                result = func(**kwargs)
                
                # 成功
                if attempt > 1 or model_idx > 0:
                    logger.info(
                        f"✅ Retry succeeded on attempt {attempt} with model {model or 'default'}"
                    )
                
                return result
            
            except Exception as e:
                last_exception = e
                
                # 最後の試行 + 最後のモデル → 例外を再発生
                if attempt == retry_config.max_retries and model_idx == len(models_to_try) - 1:
                    logger.error(
                        f"❌ All retry attempts exhausted. Last error: {type(e).__name__}: {e}"
                    )
                    raise
                
                # Exponential Backoff + Jitter で待機
                wait_time = exponential_backoff_with_jitter(
                    attempt,
                    initial_wait=retry_config.initial_wait,
                    exponential_base=retry_config.exponential_base,
                    max_wait=retry_config.max_wait,
                    jitter=retry_config.jitter,
                )
                
                logger.warning(
                    f"⚠️ Attempt {attempt} failed: {type(e).__name__}: {e}. "
                    f"Retrying in {wait_time:.2f}s..."
                )
                
                time.sleep(wait_time)
    
    # ここには到達しないはずだが、念のため
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry logic error")


def create_retry_decorator(retry_config: RetryConfig):
    """
    Tenacity ベースのリトライデコレータを生成
    
    Usage:
        config = RetryConfig(max_retries=3)
        retry_decorator = create_retry_decorator(config)
        
        @retry_decorator
        def call_api():
            ...
    """
    return retry(
        stop=stop_after_attempt(retry_config.max_retries),
        wait=wait_exponential(
            multiplier=retry_config.initial_wait,
            max=retry_config.max_wait,
        ),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
