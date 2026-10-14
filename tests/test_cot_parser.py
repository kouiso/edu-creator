"""
CoT Parser のテスト

Chain of Thought レスポンスのパース機能を検証する。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cot_parser import (
    CoTResponseBuilder,
    ParsedResponse,
    extract_json_from_tag,
    extract_tag_content,
    extract_thinking_insights,
    parse_cot_response,
    parse_section_response,
    validate_metadata,
)


class TestExtractTagContent:
    """extract_tag_content() のテスト"""

    def test_basic(self):
        """基本的なタグ抽出"""
        result = extract_tag_content("<tag>hello</tag>", "tag")
        assert result == "hello"

    def test_multiline(self):
        """マルチラインタグ抽出"""
        text = "<thinking>\nline1\nline2\nline3\n</thinking>"
        result = extract_tag_content(text, "thinking")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_not_found(self):
        """タグが見つからない場合"""
        result = extract_tag_content("<a>hello</a>", "b")
        assert result is None

    def test_empty_content(self):
        """空のコンテンツ"""
        result = extract_tag_content("<tag></tag>", "tag")
        assert result == ""

    def test_nested_content(self):
        """ネストしたコンテンツ（内部タグはそのまま）"""
        text = "<outer><inner>content</inner></outer>"
        result = extract_tag_content(text, "outer")
        assert result == "<inner>content</inner>"

    def test_with_surrounding_text(self):
        """周囲にテキストがある場合"""
        text = "prefix <tag>content</tag> suffix"
        result = extract_tag_content(text, "tag")
        assert result == "content"

    def test_whitespace_preserved(self):
        """空白が保持される（ただしstripされる）"""
        text = "<tag>  content  </tag>"
        result = extract_tag_content(text, "tag")
        assert result == "content"


class TestExtractJsonFromTag:
    """extract_json_from_tag() のテスト"""

    def test_valid_json(self):
        """有効なJSON"""
        text = '<metadata>{"key": "value", "count": 42}</metadata>'
        result = extract_json_from_tag(text, "metadata")
        assert result == {"key": "value", "count": 42}

    def test_json_in_code_block(self):
        """コードブロック内のJSON"""
        text = """<metadata>
```json
{"key": "value"}
```
</metadata>"""
        result = extract_json_from_tag(text, "metadata")
        assert result == {"key": "value"}

    def test_invalid_json(self):
        """無効なJSON"""
        text = "<metadata>not valid json</metadata>"
        result = extract_json_from_tag(text, "metadata")
        assert result is None

    def test_tag_not_found(self):
        """タグが見つからない場合"""
        text = "<other>content</other>"
        result = extract_json_from_tag(text, "metadata")
        assert result is None

    def test_complex_json(self):
        """複雑なJSON"""
        data = {
            "word_count": 1000,
            "tables_count": 5,
            "nested": {"a": 1, "b": 2},
            "list": [1, 2, 3],
        }
        text = f"<data>{json.dumps(data)}</data>"
        result = extract_json_from_tag(text, "data")
        assert result == data


class TestParseCoTResponse:
    """parse_cot_response() のテスト"""

    def test_complete_response(self):
        """完全なCoTレスポンスのパース"""
        response = """
<thinking>
This is my analysis.
I will write a tutorial.
</thinking>

<tutorial>
# Tutorial Title

Content here.
</tutorial>

<metadata>
{"word_count": 100, "tables_count": 5}
</metadata>
"""
        result = parse_cot_response(response)
        assert result.parse_success is True
        assert "analysis" in result.thinking
        assert "Tutorial Title" in result.tutorial
        assert result.metadata.get("word_count") == 100

    def test_missing_thinking_tag(self):
        """thinkingタグ欠落時（警告のみ、成功する）"""
        response = """
<tutorial>
Content here.
</tutorial>
"""
        result = parse_cot_response(response)
        assert result.parse_success is True
        assert result.thinking == ""
        assert "Content" in result.tutorial
        assert any("thinking" in err.lower() for err in result.parse_errors)

    def test_missing_tutorial_tag(self):
        """tutorialタグ欠落時（outputタグを試す）"""
        response = """
<thinking>Analysis</thinking>
<output>
Output content.
</output>
"""
        result = parse_cot_response(response)
        assert result.parse_success is True
        assert "Output content" in result.tutorial

    def test_no_tags_fallback(self):
        """タグがない場合（全体をtutorialとして扱う）"""
        response = "Just plain text without any tags."
        result = parse_cot_response(response)
        assert result.parse_success is True
        assert result.tutorial == response

    def test_missing_metadata(self):
        """metadataタグ欠落時"""
        response = """
<tutorial>Content</tutorial>
"""
        result = parse_cot_response(response)
        assert result.parse_success is True
        assert result.metadata == {}
        assert any("metadata" in err.lower() for err in result.parse_errors)

    def test_raw_response_preserved(self):
        """生のレスポンスが保存される"""
        response = "<tutorial>test</tutorial>"
        result = parse_cot_response(response)
        assert result.raw_response == response


class TestParseSectionResponse:
    """parse_section_response() のテスト"""

    def test_valid_section(self):
        """有効なセクションレスポンス"""
        response = """
<thinking>Analyzing the section...</thinking>
<section>
{
    "heading": "Introduction",
    "content": "This is the introduction.",
    "code_blocks": ["print('hello')"],
    "verification_point": "Check the output"
}
</section>
"""
        result = parse_section_response(response)
        assert result["parse_success"] is True
        assert "Analyzing" in result["thinking"]
        assert result["section"]["heading"] == "Introduction"

    def test_missing_section_tag(self):
        """sectionタグ欠落時"""
        response = """
<thinking>Analysis</thinking>
"""
        result = parse_section_response(response)
        assert result["parse_success"] is False
        assert len(result["parse_errors"]) > 0

    def test_output_tag_fallback(self):
        """outputタグへのフォールバック"""
        response = """
<output>
{"heading": "Test", "content": "Content"}
</output>
"""
        result = parse_section_response(response)
        assert result["parse_success"] is True
        assert result["section"]["heading"] == "Test"


class TestValidateMetadata:
    """validate_metadata() のテスト"""

    def test_valid_metadata(self):
        """有効なメタデータ"""
        metadata = {
            "word_count": 1000,
            "tables_count": 5,
            "code_blocks_count": 10,
            "mermaid_count": 2,
        }
        is_valid, errors = validate_metadata(metadata)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_required_field(self):
        """必須フィールドが欠落"""
        metadata = {
            "word_count": 1000,
            # tables_count missing
            "code_blocks_count": 10,
            "mermaid_count": 2,
        }
        is_valid, errors = validate_metadata(metadata)
        assert is_valid is False
        assert any("tables_count" in err for err in errors)

    def test_tables_below_minimum(self):
        """tables_count が最小値未満"""
        metadata = {
            "word_count": 1000,
            "tables_count": 2,  # 最小4
            "code_blocks_count": 10,
            "mermaid_count": 2,
        }
        is_valid, errors = validate_metadata(metadata)
        assert is_valid is False
        assert any("tables_count" in err and "below" in err for err in errors)

    def test_mermaid_below_minimum(self):
        """mermaid_count が最小値未満"""
        metadata = {
            "word_count": 1000,
            "tables_count": 5,
            "code_blocks_count": 10,
            "mermaid_count": 0,  # 最小1
        }
        is_valid, errors = validate_metadata(metadata)
        assert is_valid is False
        assert any("mermaid_count" in err for err in errors)

    def test_invalid_type(self):
        """フィールドの型が不正"""
        metadata = {
            "word_count": "not a number",
            "tables_count": 5,
            "code_blocks_count": 10,
            "mermaid_count": 2,
        }
        is_valid, errors = validate_metadata(metadata)
        assert is_valid is False
        assert any("must be a number" in err for err in errors)


class TestExtractThinkingInsights:
    """extract_thinking_insights() のテスト"""

    def test_mentions_metaphor(self):
        """メタファーへの言及を検出"""
        thinking = "I will use a kitchen metaphor to explain this concept."
        insights = extract_thinking_insights(thinking)
        assert insights["mentions_metaphor"] is True

    def test_mentions_code_selection(self):
        """コード選定への言及を検出"""
        thinking = "I need to select appropriate code examples for this tutorial."
        insights = extract_thinking_insights(thinking)
        assert insights["mentions_code_selection"] is True

    def test_mentions_reader_questions(self):
        """読者の疑問への言及を検出"""
        thinking = "The reader might have questions about why this is necessary."
        insights = extract_thinking_insights(thinking)
        assert insights["mentions_reader_questions"] is True

    def test_extracts_key_decisions(self):
        """キーとなる判断を抽出"""
        thinking = """
        Key decisions:
        - Use simple examples
        - Focus on practical applications
        - Include troubleshooting section
        """
        insights = extract_thinking_insights(thinking)
        assert len(insights["key_decisions"]) > 0
        assert any("simple" in d.lower() for d in insights["key_decisions"])

    def test_extracts_numbered_decisions(self):
        """番号付きリストから判断を抽出"""
        thinking = """
        1. First, explain the concept
        2. Then, show code examples
        3. Finally, verify the results
        """
        insights = extract_thinking_insights(thinking)
        assert len(insights["key_decisions"]) > 0

    def test_no_insights(self):
        """洞察がない場合"""
        thinking = "This is a generic thinking process."
        insights = extract_thinking_insights(thinking)
        assert insights["mentions_metaphor"] is False
        assert insights["mentions_code_selection"] is False
        assert insights["mentions_reader_questions"] is False


class TestCoTResponseBuilder:
    """CoTResponseBuilder のテスト"""

    def test_build_complete(self):
        """完全なレスポンスの構築"""
        result = (
            CoTResponseBuilder()
            .set_thinking("my thoughts")
            .set_tutorial("# Tutorial")
            .set_metadata({"word_count": 50})
            .build()
        )
        assert "<thinking>" in result
        assert "my thoughts" in result
        assert "</thinking>" in result
        assert "<tutorial>" in result
        assert "# Tutorial" in result
        assert "</tutorial>" in result
        assert "<metadata>" in result
        assert '"word_count": 50' in result
        assert "</metadata>" in result

    def test_build_partial(self):
        """部分的なレスポンスの構築"""
        result = CoTResponseBuilder().set_tutorial("Content only").build()
        assert "<tutorial>" in result
        assert "Content only" in result
        assert "<thinking>" not in result
        assert "<metadata>" not in result

    def test_method_chaining(self):
        """メソッドチェーンが正しく動作"""
        builder = CoTResponseBuilder()
        result = builder.set_thinking("thought")
        assert result is builder  # 同じインスタンスを返す

    def test_empty_build(self):
        """空のビルド"""
        result = CoTResponseBuilder().build()
        assert result == ""

    def test_roundtrip(self):
        """ビルドしたレスポンスをパースできる"""
        original_thinking = "Analysis here"
        original_tutorial = "# Tutorial\n\nContent"
        original_metadata = {"word_count": 100, "tables_count": 5}

        built = (
            CoTResponseBuilder()
            .set_thinking(original_thinking)
            .set_tutorial(original_tutorial)
            .set_metadata(original_metadata)
            .build()
        )

        parsed = parse_cot_response(built)
        assert parsed.thinking == original_thinking
        assert parsed.tutorial == original_tutorial
        assert parsed.metadata == original_metadata


class TestParsedResponseDataclass:
    """ParsedResponse データクラスのテスト"""

    def test_default_values(self):
        """デフォルト値"""
        response = ParsedResponse()
        assert response.thinking == ""
        assert response.tutorial == ""
        assert response.metadata == {}
        assert response.parse_success is True
        assert response.parse_errors == []
        assert response.raw_response == ""

    def test_custom_values(self):
        """カスタム値"""
        response = ParsedResponse(
            thinking="thought",
            tutorial="tutorial",
            metadata={"key": "value"},
            parse_success=False,
            parse_errors=["error1"],
            raw_response="raw",
        )
        assert response.thinking == "thought"
        assert response.tutorial == "tutorial"
        assert response.metadata == {"key": "value"}
        assert response.parse_success is False
        assert response.parse_errors == ["error1"]
        assert response.raw_response == "raw"
