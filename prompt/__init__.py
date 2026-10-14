"""
=============================================================================
📝 Prompt Library for Educational Material Generator
=============================================================================
All prompts are written in English for optimal AI performance.
Each prompt includes Japanese translations in comments for maintainability.

Usage:
    from prompt import TEACHING_METHODOLOGY
    from prompt.agent import COMMANDER_BACKSTORY_TEMPLATE, SCOUT_BACKSTORY_TEMPLATE, SCRIBE_BACKSTORY_TEMPLATE
    from prompt.task import RESEARCH_TASK_TEMPLATE, OUTLINE_TASK_TEMPLATE, WRITE_TASK_TEMPLATE, REVIEW_TASK_TEMPLATE

Hover over any constant in VS Code to see its docstring (including Japanese translation).

プロンプトライブラリ
==================
AIへの指示は全て英語で記述（パフォーマンス最適化のため）。
各プロンプトには日本語訳をコメントで付与。
VS Codeで定数にhoverするとdocstring（日本語訳含む）が表示されます。
=============================================================================
"""

from prompt.teaching import TEACHING_METHODOLOGY

__all__ = [
    "TEACHING_METHODOLOGY",
]
