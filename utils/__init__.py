"""
=============================================================================
Utils Package (ユーティリティパッケージ)
6つの柱の実装を提供

柱1: プロンプト構造化 → prompt/task/write.py
柱2: CoT（思考制御） → cot_parser.py
柱3: タスク分解 → （main.pyに統合）
柱4: RAG（前章参照） → chapter_context.py
柱5: 評価エンジニアリング → llm_judge.py, tests/ai/golden_dataset.py
柱6: デバッグ・可観測性 → structured_logger.py, debugger.py
=============================================================================
"""

from .structured_logger import AILogEntry, StructuredLogger
from .cot_parser import (
    ParsedResponse,
    parse_cot_response,
    parse_section_response,
    extract_tag_content,
    extract_json_from_tag,
    validate_metadata,
    extract_thinking_insights,
    CoTResponseBuilder,
)
from .chapter_context import (
    ChapterSummary,
    ChapterContext,
    build_context_for_chapter,
    format_context_for_prompt,
    get_consistency_rules,
    extract_explained_terms,
    extract_metaphor,
    extract_files,
    extract_commands,
)
from .debugger import (
    DiagnosisResult,
    QualityDebugger,
    diagnose_quality_failure,
    print_diagnosis_report,
    generate_fix_prompt,
)
from .integration import (
    EnhancedPipeline,
    create_enhanced_pipeline,
    measure_time,
    evaluate_chapter_with_llm,
    get_structured_write_prompt,
)

__all__ = [
    # 構造化ログ（柱6）
    "AILogEntry",
    "StructuredLogger",
    # CoTパーサー（柱2）
    "ParsedResponse",
    "parse_cot_response",
    "parse_section_response",
    "extract_tag_content",
    "extract_json_from_tag",
    "validate_metadata",
    "extract_thinking_insights",
    "CoTResponseBuilder",
    # 前章コンテキスト（柱4）
    "ChapterSummary",
    "ChapterContext",
    "build_context_for_chapter",
    "format_context_for_prompt",
    "get_consistency_rules",
    "extract_explained_terms",
    "extract_metaphor",
    "extract_files",
    "extract_commands",
    # デバッガー（柱6）
    "DiagnosisResult",
    "QualityDebugger",
    "diagnose_quality_failure",
    "print_diagnosis_report",
    "generate_fix_prompt",
    # 統合モジュール
    "EnhancedPipeline",
    "create_enhanced_pipeline",
    "measure_time",
    "evaluate_chapter_with_llm",
    "get_structured_write_prompt",
]
