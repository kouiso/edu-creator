"""
=============================================================================
🎯 Relevance Scorer - コード関連性スコアリングエンジン
=============================================================================

Scout が検索したコードを全て Scribe に渡すのではなく、
LLM が関連性を点数付けし TOP-K だけを渡す。

トークンコスト 20-30% 削減 + 品質維持

実務の RAG パターンから学んだベストプラクティス。
"""

import logging
from typing import Any
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CodeRelevance(BaseModel):
    """コードの関連性スコア"""
    
    file_path: str = Field(description="ファイルパス")
    relevance_score: float = Field(ge=0.0, le=1.0, description="関連性スコア（0.0-1.0）")
    reason: str = Field(description="スコアリングの理由")
    code_snippet: str = Field(description="コードスニペット（最初の50行程度）")


class RelevanceScoringResult(BaseModel):
    """スコアリング結果"""
    
    files: list[CodeRelevance] = Field(description="スコア順にソートされたファイルリスト")
    total_files: int = Field(description="総ファイル数")
    selected_files: int = Field(description="選択されたファイル数")
    avg_score: float = Field(description="平均スコア")


def score_code_relevance(
    file_path: str,
    code_content: str,
    chapter_topics: list[str],
    chapter_title: str,
    llm_callable: Any,
    max_snippet_lines: int = 50,
) -> CodeRelevance:
    """
    コードの関連性をスコアリング
    
    Args:
        file_path: ファイルパス
        code_content: コード内容
        chapter_topics: 章のトピック一覧
        chapter_title: 章タイトル
        llm_callable: LLM呼び出し関数
        max_snippet_lines: スニペット最大行数
    
    Returns:
        CodeRelevance オブジェクト
    """
    # コードスニペット（最初のN行）
    lines = code_content.split('\n')
    snippet = '\n'.join(lines[:max_snippet_lines])
    if len(lines) > max_snippet_lines:
        snippet += f"\n... ({len(lines) - max_snippet_lines} more lines)"
    
    # スコアリングプロンプト
    prompt = f"""
Evaluate the relevance of this code file to the tutorial chapter.

**Chapter**: {chapter_title}
**Topics**: {', '.join(chapter_topics)}

**File**: {file_path}
**Code Snippet**:
```
{snippet}
```

Rate the relevance on a scale of 0.0 to 1.0:
- 1.0: Highly relevant (core concepts, main implementation)
- 0.7-0.9: Relevant (supporting code, related features)
- 0.4-0.6: Somewhat relevant (tangentially related)
- 0.0-0.3: Not relevant (unrelated code)

Respond in JSON format:
{{
  "relevance_score": 0.85,
  "reason": "This file implements the main authentication logic mentioned in the chapter topics."
}}
"""
    
    try:
        # LLM呼び出し（JSON応答を期待）
        response = llm_callable(prompt)
        
        # JSON解析（簡易実装）
        import json
        import re
        json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return CodeRelevance(
                file_path=file_path,
                relevance_score=result.get("relevance_score", 0.5),
                reason=result.get("reason", "No reason provided"),
                code_snippet=snippet,
            )
        else:
            # JSON解析失敗時はデフォルトスコア
            logger.warning(f"Failed to parse JSON from LLM response: {response[:100]}")
            return CodeRelevance(
                file_path=file_path,
                relevance_score=0.5,
                reason="Failed to parse LLM response",
                code_snippet=snippet,
            )
    
    except Exception as e:
        logger.error(f"Error scoring relevance for {file_path}: {e}")
        return CodeRelevance(
            file_path=file_path,
            relevance_score=0.5,
            reason=f"Error: {str(e)}",
            code_snippet=snippet,
        )


def filter_top_k_files(
    files_with_content: dict[str, str],
    chapter_topics: list[str],
    chapter_title: str,
    llm_callable: Any,
    top_k: int = 10,
) -> RelevanceScoringResult:
    """
    ファイルを関連性でスコアリングし、TOP-K を選択
    
    Args:
        files_with_content: {file_path: code_content} の辞書
        chapter_topics: 章のトピック一覧
        chapter_title: 章タイトル
        llm_callable: LLM呼び出し関数
        top_k: 選択するファイル数
    
    Returns:
        RelevanceScoringResult オブジェクト
    """
    logger.info(f"📊 Scoring relevance for {len(files_with_content)} files...")
    
    # 全ファイルをスコアリング
    scored_files: list[CodeRelevance] = []
    for file_path, code_content in files_with_content.items():
        score = score_code_relevance(
            file_path,
            code_content,
            chapter_topics,
            chapter_title,
            llm_callable,
        )
        scored_files.append(score)
    
    # スコア順にソート
    scored_files.sort(key=lambda x: x.relevance_score, reverse=True)
    
    # TOP-K を選択
    selected_files = scored_files[:top_k]
    
    # 平均スコア計算
    avg_score = sum(f.relevance_score for f in selected_files) / len(selected_files) if selected_files else 0.0
    
    logger.info(
        f"✅ Selected top {len(selected_files)} files "
        f"(avg relevance: {avg_score:.2f})"
    )
    
    return RelevanceScoringResult(
        files=selected_files,
        total_files=len(files_with_content),
        selected_files=len(selected_files),
        avg_score=avg_score,
    )


def format_filtered_context(result: RelevanceScoringResult) -> str:
    """
    フィルタリング結果を Scribe 用のコンテキストにフォーマット
    
    Args:
        result: RelevanceScoringResult オブジェクト
    
    Returns:
        フォーマット済みコンテキスト文字列
    """
    context_parts = [
        f"📊 Code Context (Top {result.selected_files}/{result.total_files} files, avg relevance: {result.avg_score:.2f})",
        "",
    ]
    
    for idx, file in enumerate(result.files, 1):
        context_parts.append(f"## File {idx}: {file.file_path} (relevance: {file.relevance_score:.2f})")
        context_parts.append(f"**Why relevant**: {file.reason}")
        context_parts.append("")
        context_parts.append("```")
        context_parts.append(file.code_snippet)
        context_parts.append("```")
        context_parts.append("")
    
    return "\n".join(context_parts)
