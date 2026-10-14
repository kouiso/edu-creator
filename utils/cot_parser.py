"""
=============================================================================
Chain of Thought Parser (CoTパーサー)
AIの思考過程と出力を分離してパース

柱2: 思考プロセス制御（Chain of Thought）
- 思考過程がログに保存されてデバッグ可能
- 品質問題発生時に「なぜそう書いたか」を追跡可能
=============================================================================
"""

import re
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedResponse:
    """パースされたAIレスポンス"""

    # 思考過程（デバッグ用）
    thinking: str = ""

    # 実際の出力（チュートリアル本文）
    tutorial: str = ""

    # メタデータ（JSON形式）
    metadata: dict[str, Any] = field(default_factory=dict)

    # パース成功フラグ
    parse_success: bool = True

    # パースエラー（失敗時）
    parse_errors: list[str] = field(default_factory=list)

    # 生のレスポンス（フォールバック用）
    raw_response: str = ""


def extract_tag_content(text: str, tag_name: str) -> str | None:
    """XMLタグの内容を抽出

    Args:
        text: 検索対象のテキスト
        tag_name: タグ名（例: "thinking", "tutorial"）

    Returns:
        str | None: タグの内容（見つからない場合はNone）
    """
    # マルチライン対応の正規表現
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None


def extract_json_from_tag(text: str, tag_name: str) -> dict[str, Any] | None:
    """XMLタグ内のJSONを抽出してパース

    Args:
        text: 検索対象のテキスト
        tag_name: タグ名

    Returns:
        dict | None: パースされたJSON（失敗時はNone）
    """
    content = extract_tag_content(text, tag_name)
    if content is None:
        return None

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # JSONが不正な場合、コードブロック内のJSONを試す
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        return None


def parse_cot_response(response: str) -> ParsedResponse:
    """CoTレスポンスをパース

    期待される構造:
    <thinking>
    [AIの分析・判断理由]
    </thinking>

    <tutorial>
    [実際のMarkdownチュートリアル]
    </tutorial>

    <metadata>
    {"word_count": 1234, ...}
    </metadata>

    Args:
        response: AIからの生レスポンス

    Returns:
        ParsedResponse: パースされたレスポンス
    """
    result = ParsedResponse(raw_response=response)
    errors = []

    # 思考過程を抽出
    thinking = extract_tag_content(response, "thinking")
    if thinking:
        result.thinking = thinking
    else:
        # thinkingタグがない場合は警告（必須ではない）
        errors.append("Warning: <thinking> tag not found")

    # チュートリアル本文を抽出
    tutorial = extract_tag_content(response, "tutorial")
    if tutorial:
        result.tutorial = tutorial
    else:
        # tutorialタグがない場合、outputタグを試す
        tutorial = extract_tag_content(response, "output")
        if tutorial:
            result.tutorial = tutorial
        else:
            # タグがない場合、レスポンス全体をチュートリアルとして扱う
            # （後方互換性のため）
            errors.append("Warning: <tutorial> or <output> tag not found, using raw response")
            result.tutorial = response

    # メタデータを抽出
    metadata = extract_json_from_tag(response, "metadata")
    if metadata:
        result.metadata = metadata
    else:
        errors.append("Warning: <metadata> tag not found or invalid JSON")

    # パース結果の判定
    result.parse_errors = errors
    result.parse_success = bool(result.tutorial)

    return result


def parse_section_response(response: str) -> dict[str, Any]:
    """セクション単位のレスポンスをパース

    期待される構造:
    <thinking>...</thinking>
    <section>
    {
      "heading": "見出し",
      "content": "本文",
      "code_blocks": [...],
      "verification_point": "確認ポイント"
    }
    </section>

    Args:
        response: AIからの生レスポンス

    Returns:
        dict: パースされたセクション情報
    """
    result = {
        "thinking": "",
        "section": {},
        "parse_success": True,
        "parse_errors": [],
        "raw_response": response,
    }

    # 思考過程を抽出
    thinking = extract_tag_content(response, "thinking")
    if thinking:
        result["thinking"] = thinking

    # セクションを抽出
    section = extract_json_from_tag(response, "section")
    if section:
        result["section"] = section
    else:
        # sectionタグがない場合、output_schemaを試す
        section = extract_json_from_tag(response, "output")
        if section:
            result["section"] = section
        else:
            result["parse_success"] = False
            result["parse_errors"].append("Error: <section> tag not found or invalid JSON")

    return result


def validate_metadata(metadata: dict[str, Any]) -> tuple[bool, list[str]]:
    """メタデータのバリデーション

    Args:
        metadata: メタデータ辞書

    Returns:
        tuple[bool, list[str]]: (バリデーション成功, エラーリスト)
    """
    errors = []
    required_fields = [
        "word_count",
        "tables_count",
        "code_blocks_count",
        "mermaid_count",
    ]

    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(metadata[field], (int, float)):
            errors.append(f"Field {field} must be a number")

    # 品質ルールに基づくバリデーション
    if metadata.get("tables_count", 0) < 4:
        errors.append(f"tables_count ({metadata.get('tables_count', 0)}) is below minimum (4)")

    if metadata.get("mermaid_count", 0) < 1:
        errors.append(f"mermaid_count ({metadata.get('mermaid_count', 0)}) is below minimum (1)")

    return len(errors) == 0, errors


def extract_thinking_insights(thinking: str) -> dict[str, Any]:
    """思考過程から洞察を抽出（デバッグ用）

    Args:
        thinking: 思考過程のテキスト

    Returns:
        dict: 抽出された洞察
    """
    insights = {
        "mentions_metaphor": False,
        "mentions_code_selection": False,
        "mentions_reader_questions": False,
        "key_decisions": [],
    }

    thinking_lower = thinking.lower()

    # メタファーへの言及
    if any(word in thinking_lower for word in ["metaphor", "メタファー", "例え", "キッチン"]):
        insights["mentions_metaphor"] = True

    # コード選定への言及
    if any(word in thinking_lower for word in ["code", "コード", "example", "例"]):
        insights["mentions_code_selection"] = True

    # 読者の疑問への言及
    if any(word in thinking_lower for word in ["reader", "読者", "question", "疑問", "なぜ"]):
        insights["mentions_reader_questions"] = True

    # キーとなる判断を抽出（箇条書きや番号付きリストから）
    decision_patterns = [
        r"(?:^|\n)\s*[-*]\s*(.+?)(?=\n|$)",  # 箇条書き
        r"(?:^|\n)\s*\d+\.\s*(.+?)(?=\n|$)",  # 番号付き
    ]
    for pattern in decision_patterns:
        matches = re.findall(pattern, thinking)
        insights["key_decisions"].extend(matches[:5])  # 最大5個

    return insights


class CoTResponseBuilder:
    """CoTレスポンスを構築するヘルパークラス"""

    def __init__(self):
        self.thinking = ""
        self.tutorial = ""
        self.metadata = {}

    def set_thinking(self, thinking: str) -> "CoTResponseBuilder":
        """思考過程を設定"""
        self.thinking = thinking
        return self

    def set_tutorial(self, tutorial: str) -> "CoTResponseBuilder":
        """チュートリアル本文を設定"""
        self.tutorial = tutorial
        return self

    def set_metadata(self, metadata: dict[str, Any]) -> "CoTResponseBuilder":
        """メタデータを設定"""
        self.metadata = metadata
        return self

    def build(self) -> str:
        """最終的なレスポンス文字列を構築"""
        parts = []

        if self.thinking:
            parts.append(f"<thinking>\n{self.thinking}\n</thinking>")

        if self.tutorial:
            parts.append(f"<tutorial>\n{self.tutorial}\n</tutorial>")

        if self.metadata:
            metadata_json = json.dumps(self.metadata, ensure_ascii=False, indent=2)
            parts.append(f"<metadata>\n{metadata_json}\n</metadata>")

        return "\n\n".join(parts)
