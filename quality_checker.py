"""
=============================================================================
教材品質自動検証スクリプト
=============================================================================
「AI に判断させず、機械的にチェック」する仕組み

このモジュールは2つの使用方法を提供します：
1. スタンドアロン: python quality_checker.py <file>
2. CrewAI Tool: @tool デコレータで Validator エージェントに統合

使用例（CrewAI統合）:
    from quality_checker import validate_markdown_tool
    from crewai_tools import Tool

    validator.tools = [
        Tool.from_function(validate_markdown_tool)
    ]
"""

import re
from json import dumps
from pathlib import Path
from typing import Dict, List, Tuple

# 品質スキーマのインポート (一元管理)
from config.quality_schema import (
    QUALITY_SCHEMA,
    get_required_section_patterns,
    get_forbidden_words,
    get_code_block_limits,
    get_table_limits,
    get_mermaid_limits,
)

try:
    from crewai_tools import tool
except ImportError:
    # CrewAI未インストール時でも基本機能は動作
    def tool(func):
        return func


class TutorialQualityChecker:
    """教材の品質を機械的にチェック"""

    def __init__(self, markdown_content: str):
        self.content = markdown_content
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def check_all(self) -> Dict[str, any]:
        """全ての検証を実行"""
        return {
            "markdown_format": self.check_markdown_format(),
            "required_sections": self.check_required_sections(),
            "emoji_usage": self.check_emoji_usage(),
            "code_blocks": self.check_code_blocks(),
            "tables": self.check_tables(),
            "mermaid_diagrams": self.check_mermaid_diagrams(),
            "step_by_step": self.check_step_by_step(),
            "error_handling": self.check_error_handling(),
            "technical_terms": self.check_technical_terms(),
            "explanation_depth": self.check_explanation_depth(),
            "sentence_length": self.check_sentence_length(),
            "is_passed": len(self.issues) == 0,
        }

    def check_markdown_format(self) -> Dict[str, any]:
        """マークダウン形式が正しいか"""
        issues = []

        if self.content.strip().startswith("````"):
            issues.append("❌ マークダウンが ````（4個のバックティック）で始まっている。```（3個）にする")

        code_block_count = len(re.findall(r"```", self.content))
        if code_block_count % 2 != 0:
            issues.append(f"❌ コードブロック（```）が対になっていない（{code_block_count}個）")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_required_sections(self) -> Dict[str, any]:
        """必須セクションが揃っているか - 品質スキーマベース"""
        required_sections = get_required_section_patterns()

        issues = []
        for pattern, section_name in required_sections:
            if not re.search(pattern, self.content, re.IGNORECASE):
                issues.append(f"❌ 必須セクションなし: {section_name}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_emoji_usage(self) -> Dict[str, any]:
        """絵文字チェック - 無効化: 絵文字は不要"""
        return {
            "passed": True,
            "issues": [],
        }

    def check_code_blocks(self) -> Dict[str, any]:
        """コードブロックが適切か - 品質スキーマベース"""
        issues = []
        limits = get_code_block_limits()

        code_blocks = re.findall(r"```(.+?)```", self.content, re.DOTALL)
        min_count = limits['min_count']
        max_lines = limits['max_lines_per_block']
        
        if len(code_blocks) < min_count:
            issues.append(f"❌ コードブロックが少ない ({len(code_blocks)}個). 最低 {min_count} 個は必要")

        for i, code in enumerate(code_blocks, 1):
            lines = code.strip().split('\n')
            actual_lines = len(lines) - 1 if len(lines) > 0 else 0
            if actual_lines > max_lines:
                issues.append(
                    f"❌ コードブロック {i} が長すぎる ({actual_lines}行). "
                    f"最大 {max_lines} 行まで"
                )

        code_block_pattern = r"```[^`]*```"
        for i, match in enumerate(re.finditer(code_block_pattern, self.content)):
            code_end = match.end()
            next_100_chars = self.content[code_end : code_end + 100].strip()

            # 次の 100 文字が空白や見出しだけではないか
            if (
                not next_100_chars
                or next_100_chars.startswith("#")
                or len(next_100_chars) < 20
            ):
                issues.append(
                    f"⚠️  コードブロック {i + 1} の後に説明がない"
                )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_tables(self) -> Dict[str, any]:
        """テーブルが充実しているか - 品質スキーマベース"""
        issues = []
        limits = get_table_limits()
        min_tables = limits['min_count']

        # 完全なテーブルを検出 (ヘッダー + セパレーター + データ行)
        complete_table_pattern = (
            r'\|[^|]+\|[^\n]*\n\|[\s\-:]+\|[^\n]*\n'
            r'(\|[^|]+\|[^\n]*\n?)+'
        )
        complete_tables = re.findall(complete_table_pattern, self.content)
        table_sets = len(complete_tables)

        if table_sets < min_tables:
            issues.append(
                f"❌ テーブルが少ない ({table_sets}個). "
                f"最低 {min_tables} 個は必要 (参考テーブル・コマンド比較・トラブルシューティング等)"
            )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_mermaid_diagrams(self) -> Dict[str, any]:
        """Mermaid図が含まれているか - 品質スキーマベース"""
        issues = []
        limits = get_mermaid_limits()
        min_count = limits['min_count']

        mermaid_pattern = r"```mermaid[\s\S]*?```"
        mermaid_count = len(re.findall(mermaid_pattern, self.content))

        if mermaid_count < min_count:
            issues.append(
                f"❌ Mermaid図が不足 ({mermaid_count}個). "
                f"最低 {min_count} 個は必要 (アーキテクチャ図、フロー図等)"
            )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_step_by_step(self) -> Dict[str, any]:
        """ステップバイステップの説明が詳細か"""
        issues = []

        step_pattern = r"(### ステップ|#### ステップ|Step)[\s\S]*?(?=###|####|$)"
        steps = [match.group(0) for match in re.finditer(step_pattern, self.content)]

        if len(steps) < 3:
            issues.append(f"❌ ステップが少ない（{len(steps)}個）。最低 3 個は必要")

        for i, step in enumerate(steps, 1):
            if "```" not in step:
                issues.append(f"❌ ステップ {i} にコマンドが示されていない")

            if (
                "何をしているか" not in step
                and "役割" not in step
                and "説明" not in step.lower()
            ):
                issues.append(f"❌ ステップ {i} に「何をしているか」の説明がない")

            if "期待される出力" not in step and "出力" not in step:
                issues.append(f"⚠️  ステップ {i} に「期待される出力」がない")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_error_handling(self) -> Dict[str, any]:
        """エラーハンドリングが充実しているか"""
        issues = []

        error_keywords = [
            "エラー",
            "失敗",
            "問題",
            "トラブル",
            "原因",
            "対処",
            "解決策",
        ]
        has_error_section = any(
            keyword in self.content for keyword in error_keywords
        )

        if not has_error_section:
            issues.append(
                "❌ エラーハンドリングセクションがない。「よくあるエラー」「トラブルシューティング」等を追加"
            )

        # エラー対処が複数あるか
        error_count = len(re.findall(r"❌|エラー|失敗", self.content))
        if error_count < 2:
            issues.append(f"❌ エラー対処が少ない（{error_count}個）。最低 2-3 個のエラーパターンを示す")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_technical_terms(self) -> Dict[str, any]:
        """専門用語が説明されているか + 禁止ワードチェック"""
        issues = []

        forbidden_words = get_forbidden_words()
        for word in forbidden_words:
            if word in self.content:
                issues.append(f"❌ 禁止ワード使用: '{word}' - より具体的な表現に置き換えてください")

        technical_terms = [
            ("Node.js", "ノード"),
            ("npm", "エヌピーエム"),
            ("Docker", "ドッカー"),
            ("PostgreSQL", "ポストグレス"),
            ("Taskfile", "タスクファイル"),
        ]

        for term, reading in technical_terms:
            if term in self.content:
                # 説明パターン: 「用語(読み方: 説明)」
                explanation_pattern = (
                    rf"{re.escape(term)}[（(][^）)]*[）)]"
                )
                if not re.search(explanation_pattern, self.content):
                    issues.append(
                        f"⚠️  '{term}' が説明なしで使われている. "
                        f"初出時は '{term}({reading}: 説明)' 形式で説明"
                    )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_explanation_depth(self) -> Dict[str, any]:
        """説明の深さが十分か"""
        issues = []

        short_lines = len([line for line in self.content.split("\n") if len(line) < 10])

        has_why = "なぜ" in self.content or "理由" in self.content

        if not has_why:
            issues.append("❌ 「なぜ」の説明がない。各ステップで「なぜこれが必要か」を説明")

        has_polite = re.search(r"[です|ます|ました|ています]", self.content)
        if not has_polite:
            issues.append("❌ 文体がです・ます調でない。丁寧語で統一")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def check_sentence_length(self) -> Dict[str, any]:
        """文の長さが適切か"""
        issues = []

        sentences = re.split(r"[。\n]", self.content)
        long_sentences = [s for s in sentences if len(s) > 80]

        if len(long_sentences) > 5:
            issues.append(
                f"⚠️  長い文が多い（{len(long_sentences)}個）。40文字以内を目安に分割"
            )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
        }

    def generate_report(self) -> str:
        """検証レポートを生成"""
        all_checks = self.check_all()

        report = "\n"
        report += "╔════════════════════════════════════════════════════════════╗\n"
        report += "║          📋 教材品質自動検証レポート                          ║\n"
        report += "╚════════════════════════════════════════════════════════════╝\n\n"

        passed_count = 0
        for check_name, result in all_checks.items():
            if check_name == "is_passed":
                continue

            status = "✅" if result["passed"] else "❌"
            report += f"{status} {check_name}\n"

            if result.get("issues"):
                for issue in result["issues"]:
                    report += f"   {issue}\n"

                if not result["passed"]:
                    self.issues.extend(result["issues"])
            else:
                passed_count += 1

            report += "\n"

        report += f"\n{'='*60}\n"
        report += f"総合判定: {'✅ PASS' if all_checks['is_passed'] else '❌ FAIL'}\n"
        report += f"失敗項目: {len(all_checks) - passed_count - 1}\n"
        report += f"{'='*60}\n"

        return report


def validate_markdown_file(file_path: str) -> Tuple[bool, str]:
    """マークダウンファイルを検証"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    checker = TutorialQualityChecker(content)
    result = checker.check_all()
    report = checker.generate_report()

    return result["is_passed"], report


@tool
def validate_markdown_tool(markdown_file_path: str) -> str:
    """
    CrewAI Tool: Markdownファイルの品質を自動検証

    このツールはValidatorエージェントが使用するため、AIの「見た目」判断を
    機械的なチェックに置き換えます。

    Args:
        markdown_file_path: 検証するMarkdownファイルのパス

    Returns:
        JSON形式の検証結果レポート
    """
    try:
        if not Path(markdown_file_path).exists():
            return dumps({
                "passed": False,
                "error": f"ファイルが見つかりません: {markdown_file_path}",
                "report": ""
            }, ensure_ascii=False, indent=2)

        with open(markdown_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        checker = TutorialQualityChecker(content)
        all_checks = checker.check_all()
        report = checker.generate_report()

        # JSON形式で返す（AIが確実に読め、プログラムでも処理しやすい）
        result = {
            "passed": all_checks["is_passed"],
            "summary": {
                "markdown_format": all_checks["markdown_format"]["passed"],
                "required_sections": all_checks["required_sections"]["passed"],
                "emoji_usage": all_checks["emoji_usage"]["passed"],
                "code_blocks": all_checks["code_blocks"]["passed"],
                "tables": all_checks["tables"]["passed"],
                "step_by_step": all_checks["step_by_step"]["passed"],
                "error_handling": all_checks["error_handling"]["passed"],
                "technical_terms": all_checks["technical_terms"]["passed"],
                "explanation_depth": all_checks["explanation_depth"]["passed"],
                "sentence_length": all_checks["sentence_length"]["passed"],
            },
            "issues": {
                k: v.get("issues", [])
                for k, v in all_checks.items()
                if k != "is_passed" and isinstance(v, dict)
            },
            "report": report
        }

        return dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return dumps({
            "passed": False,
            "error": f"検証エラー: {str(e)}",
            "report": ""
        }, ensure_ascii=False, indent=2)


def get_quality_check_summary(markdown_file_path: str) -> Dict[str, any]:
    """
    品質チェック結果を辞書として取得（プログラムでの利用向け）

    Args:
        markdown_file_path: 検証するMarkdownファイルのパス

    Returns:
        {
            "passed": bool,
            "total_issues": int,
            "issues_by_category": {category: [issues]},
            "recommendations": [str]
        }
    """
    try:
        with open(markdown_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        checker = TutorialQualityChecker(content)
        all_checks = checker.check_all()

        recommendations = []
        issues_by_category = {}
        total_issues = 0

        for check_name, result in all_checks.items():
            if check_name == "is_passed":
                continue

            if not result["passed"] and result.get("issues"):
                issues_by_category[check_name] = result["issues"]
                total_issues += len(result["issues"])
                recommendations.extend(result["issues"])

        return {
            "passed": all_checks["is_passed"],
            "total_issues": total_issues,
            "issues_by_category": issues_by_category,
            "recommendations": recommendations[:5]  # 最初の5件の推奨
        }

    except Exception as e:
        return {
            "passed": False,
            "total_issues": 1,
            "issues_by_category": {"error": [str(e)]},
            "recommendations": [f"エラー発生: {str(e)}"]
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用法: python quality_checker.py <markdown_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    passed, report = validate_markdown_file(file_path)

    print(report)
    sys.exit(0 if passed else 1)
