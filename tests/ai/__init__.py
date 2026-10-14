"""
=============================================================================
AI Tests Package (AIテストパッケージ)
LLM-as-Judge評価とゴールデンデータセット

柱5: 評価エンジニアリング
- ゴールデンテストケース
- 回帰テスト用データセット
=============================================================================
"""

from .golden_dataset import (
    GoldenTestCase,
    GOOD_EXAMPLES,
    BAD_EXAMPLES,
    EDGE_CASES,
    ALL_TEST_CASES,
    get_test_cases,
    get_positive_cases,
    get_negative_cases,
    validate_test_case_result,
)

__all__ = [
    "GoldenTestCase",
    "GOOD_EXAMPLES",
    "BAD_EXAMPLES",
    "EDGE_CASES",
    "ALL_TEST_CASES",
    "get_test_cases",
    "get_positive_cases",
    "get_negative_cases",
    "validate_test_case_result",
]
