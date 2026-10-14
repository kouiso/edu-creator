"""
=============================================================================
🧪 Retry Strategy Tests
=============================================================================

リトライ戦略の単体テスト
"""

import pytest
import time
from utils.retry_strategy import (
    RetryConfig,
    exponential_backoff_with_jitter,
    retry_with_fallback,
)


def test_exponential_backoff():
    """Exponential Backoff の計算をテスト"""
    # Jitterなしでテスト
    assert exponential_backoff_with_jitter(1, initial_wait=1.0, exponential_base=2, jitter=False) == 1.0
    assert exponential_backoff_with_jitter(2, initial_wait=1.0, exponential_base=2, jitter=False) == 2.0
    assert exponential_backoff_with_jitter(3, initial_wait=1.0, exponential_base=2, jitter=False) == 4.0
    assert exponential_backoff_with_jitter(4, initial_wait=1.0, exponential_base=2, jitter=False) == 8.0
    
    # Max wait のテスト
    assert exponential_backoff_with_jitter(10, initial_wait=1.0, exponential_base=2, max_wait=10.0, jitter=False) == 10.0


def test_exponential_backoff_with_jitter_range():
    """Jitter が正しい範囲にあることをテスト"""
    for _ in range(100):
        wait_time = exponential_backoff_with_jitter(2, initial_wait=1.0, exponential_base=2, jitter=True)
        # attempt=2 → base wait = 2.0
        # Jitter: 0.5x ~ 1.5x → 1.0 ~ 3.0
        assert 1.0 <= wait_time <= 3.0


def test_retry_with_fallback_success_first_attempt():
    """最初の試行で成功する場合"""
    call_count = 0
    
    def success_func():
        nonlocal call_count
        call_count += 1
        return "success"
    
    config = RetryConfig(max_retries=3)
    result = retry_with_fallback(success_func, config)
    
    assert result == "success"
    assert call_count == 1


def test_retry_with_fallback_success_after_retry():
    """リトライ後に成功する場合"""
    call_count = 0
    
    def retry_then_success():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary error")
        return "success"
    
    config = RetryConfig(max_retries=3, initial_wait=0.01)  # 高速化
    result = retry_with_fallback(retry_then_success, config)
    
    assert result == "success"
    assert call_count == 3


def test_retry_with_fallback_all_failed():
    """全てのリトライが失敗する場合"""
    call_count = 0
    
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("Permanent error")
    
    config = RetryConfig(max_retries=3, initial_wait=0.01)
    
    with pytest.raises(ValueError, match="Permanent error"):
        retry_with_fallback(always_fail, config)
    
    assert call_count == 3


def test_retry_timing():
    """リトライのタイミングをテスト"""
    call_times = []
    
    def record_time():
        call_times.append(time.time())
        if len(call_times) < 3:
            raise ValueError("Retry")
        return "success"
    
    config = RetryConfig(max_retries=3, initial_wait=0.1, jitter=False)
    retry_with_fallback(record_time, config)
    
    # 3回呼ばれることを確認
    assert len(call_times) == 3
    
    # 2回目は1回目から約0.1秒後
    assert 0.08 <= (call_times[1] - call_times[0]) <= 0.15
    
    # 3回目は2回目から約0.2秒後（exponential backoff）
    assert 0.18 <= (call_times[2] - call_times[1]) <= 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
