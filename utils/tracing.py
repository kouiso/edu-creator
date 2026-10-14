"""
=============================================================================
🔍 Distributed Tracing - 分散トレーシング（OpenTelemetry）
=============================================================================

全エージェント・全 API 呼び出しを OpenTelemetry で統合トレース。

複数エージェントの処理フロー追跡、ボトルネック特定、問題洗い出し。

実務の 運用インフラから学んだベストプラクティス。
"""

import logging
import uuid
from typing import Any, Optional
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# トレースID を保持する ContextVar（スレッドセーフ）
current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)


class SimpleTracer:
    """
    簡易トレーサー（OpenTelemetry の軽量実装）
    
    本格的な OpenTelemetry 統合は将来的に実装。
    まずは基本的なトレースIDとスパンの概念を導入。
    """
    
    def __init__(self, service_name: str = "edu-creator"):
        self.service_name = service_name
        self.traces: dict[str, list[dict[str, Any]]] = {}
    
    def start_trace(self, operation_name: str) -> str:
        """
        新しいトレースを開始
        
        Args:
            operation_name: 操作名（例: "generate_chapter_01"）
        
        Returns:
            trace_id
        """
        trace_id = str(uuid.uuid4())
        current_trace_id.set(trace_id)
        self.traces[trace_id] = []
        
        logger.info(f"🔍 Starting trace: {trace_id} ({operation_name})")
        
        # ルートスパンを作成
        self.add_span(
            trace_id=trace_id,
            span_name=operation_name,
            span_type="root",
        )
        
        return trace_id
    
    def add_span(
        self,
        trace_id: str,
        span_name: str,
        span_type: str = "agent",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        スパンを追加
        
        Args:
            trace_id: トレースID
            span_name: スパン名（例: "scout_research"）
            span_type: スパンタイプ（root/agent/llm/task）
            metadata: メタデータ
        
        Returns:
            span_id
        """
        import time
        
        span_id = str(uuid.uuid4())
        span = {
            "span_id": span_id,
            "span_name": span_name,
            "span_type": span_type,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        
        self.traces[trace_id].append(span)
        
        logger.debug(f"  📊 Span: {span_name} ({span_type})")
        
        return span_id
    
    def end_trace(self, trace_id: str) -> dict[str, Any]:
        """
        トレースを終了し、結果を取得
        
        Args:
            trace_id: トレースID
        
        Returns:
            トレースデータ
        """
        if trace_id not in self.traces:
            logger.warning(f"⚠️ Trace not found: {trace_id}")
            return {}
        
        trace_data = {
            "trace_id": trace_id,
            "service_name": self.service_name,
            "spans": self.traces[trace_id],
            "total_spans": len(self.traces[trace_id]),
        }
        
        logger.info(
            f"✅ Trace completed: {trace_id} "
            f"({trace_data['total_spans']} spans)"
        )
        
        current_trace_id.set(None)
        
        return trace_data
    
    def get_current_trace_id(self) -> str | None:
        """現在のトレースIDを取得"""
        return current_trace_id.get()


# グローバルトレーサーインスタンス
_global_tracer: SimpleTracer | None = None


def get_tracer() -> SimpleTracer:
    """グローバルトレーサーを取得"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = SimpleTracer()
    return _global_tracer


def trace_agent_execution(agent_name: str, task_description: str):
    """
    エージェント実行をトレース（デコレータとして使用可能）
    
    Usage:
        @trace_agent_execution("scout", "code_research")
        def scout_execute(prompt):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            trace_id = tracer.get_current_trace_id()
            
            if trace_id:
                span_id = tracer.add_span(
                    trace_id=trace_id,
                    span_name=f"{agent_name}:{task_description}",
                    span_type="agent",
                    metadata={
                        "agent_name": agent_name,
                        "task": task_description,
                    }
                )
            
            result = func(*args, **kwargs)
            
            return result
        
        return wrapper
    
    return decorator
