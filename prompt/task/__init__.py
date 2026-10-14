"""
=============================================================================
📋 Task Prompts (Task Descriptions)
タスクプロンプト（タスク説明）
=============================================================================
"""

from prompt.task.outline import OUTLINE_EXPECTED_OUTPUT, OUTLINE_TASK_TEMPLATE
from prompt.task.research import (RESEARCH_EXPECTED_OUTPUT,
                                  RESEARCH_TASK_TEMPLATE)
from prompt.task.review import REVIEW_EXPECTED_OUTPUT, REVIEW_TASK_TEMPLATE
from prompt.task.write import WRITE_EXPECTED_OUTPUT, WRITE_TASK_TEMPLATE

__all__ = [
    # Research
    "RESEARCH_TASK_TEMPLATE",
    "RESEARCH_EXPECTED_OUTPUT",
    # Outline
    "OUTLINE_TASK_TEMPLATE",
    "OUTLINE_EXPECTED_OUTPUT",
    # Write
    "WRITE_TASK_TEMPLATE",
    "WRITE_EXPECTED_OUTPUT",
    # Review
    "REVIEW_TASK_TEMPLATE",
    "REVIEW_EXPECTED_OUTPUT",
]
