#!/usr/bin/env python3
"""
PDF Issue Fixer for edu-creator
================================

Maps PDF validation issues to Markdown fixes.
Provides both automatic fixes (code-based) and LLM fix instructions.

Usage:
    from pdf_fixer import PDFFixer

    fixer = PDFFixer(markdown_path, pdf_issues)
    fixed_content = fixer.auto_fix_content()
    llm_instructions = fixer.generate_fix_instructions()
"""

import re
from pathlib import Path
from typing import Any


class PDFFixer:
    """Maps PDF issues to Markdown fixes and applies automatic corrections."""

    def __init__(self, markdown_path: Path, pdf_issues: list[dict[str, Any]]):
        """
        Initialize fixer with markdown file and PDF issues.

        Args:
            markdown_path: Path to the markdown file to fix
            pdf_issues: List of issues from PDFValidator.validate()
        """
        self.markdown_path = Path(markdown_path)
        self.pdf_issues = pdf_issues
        self.content = self.markdown_path.read_text(encoding="utf-8")
        self.applied_fixes: list[str] = []

    def generate_fix_instructions(self) -> list[str]:
        """
        Generate LLM-friendly fix instructions from PDF issues.

        Returns:
            List of human-readable fix instructions for LLM
        """
        instructions = []

        for issue in self.pdf_issues:
            fix = self._map_issue_to_fix(issue)
            if fix:
                instructions.append(fix)

        return instructions

    def _map_issue_to_fix(self, issue: dict[str, Any]) -> str | None:
        """Map a single PDF issue to a fix instruction."""
        issue_type = issue.get("type", "")
        message = issue.get("message", "")
        page = issue.get("page", 0)
        context = issue.get("context", "")

        # High-priority issues that need LLM attention
        if issue_type == "truncation":
            return (
                f"【ページ{page}】テキスト切れを検出: 「{context[:30]}...」\n"
                "  → 長い単語（特に技術用語）を短い英語に置き換えるか、改行を追加してください"
            )

        if issue_type == "empty_page":
            return (
                f"【ページ{page}】ほぼ空白のページを検出\n"
                "  → 前のセクションに内容を追加するか、次のセクションの内容をこのページに移動してください\n"
                "  → 不要な改ページ（<!-- pagebreak -->）があれば削除してください"
            )

        if issue_type == "incomplete_table":
            return (
                f"【ページ{page}】不完全なテーブルを検出: 「{context[:40]}...」\n"
                "  → テーブルにデータ行を追加してください（ヘッダーのみのテーブルは不完全です）"
            )

        if issue_type == "mermaid_issue":
            return (
                "【Mermaid図の問題】図のラベルが正しく表示されていない可能性\n"
                "  → ノードラベルを短い英語に変更してください（例: 'データベース' → 'DB'）\n"
                "  → 矢印のラベルは可能な限り短くしてください"
            )

        if issue_type == "raw_markdown":
            return (
                "【Markdown記法の問題】生のMarkdown記法（```）がPDFに表示されています\n"
                "  → コードフェンスが正しく閉じられているか確認してください"
            )

        if issue_type == "orphan_header":
            return (
                f"【ページ{page}】ページ末尾に孤立した見出しを検出: 「{context[:30]}...」\n"
                "  → 見出しの前に <!-- pagebreak --> を追加して次ページに移動させてください"
            )

        if issue_type == "url_truncation":
            return (
                f"【ページ{page}】URLが途中で切れています: 「{context[:40]}...」\n"
                "  → 長いURLはコードブロック内に記載するか、短縮URLを使用してください"
            )

        if issue_type == "screenshot_placeholder":
            return (
                f"【ページ{page}】未解決のスクリーンショットプレースホルダー: "
                f"「{context[:40]}...」\n"
                "  → 対応方法を選択:\n"
                "    A) 実際の画像を挿入（material/screenshots/に配置）\n"
                "    B) プレースホルダーを削除して説明文に置換\n"
                "    C) 「※画面イメージは実際に操作して確認してください」に統一\n"
                "  推奨: 初心者向け教材では実際の画像があると理解しやすい"
            )

        # Low priority issues - may not need LLM intervention
        if issue_type == "sparse_page":
            return None  # Often acceptable

        if issue_type == "line_truncation":
            return None  # Often false positive

        return None

    def auto_fix_content(self) -> str:
        """
        Apply automatic fixes that don't need LLM.

        Returns:
            Fixed markdown content
        """
        fixed = self.content

        # Fix 1: Wrap long code lines (>65 chars for PDF compatibility)
        fixed = self._wrap_long_code_lines(fixed, max_length=65)

        # Fix 2: Wrap long URLs in code blocks
        fixed = self._wrap_long_urls(fixed)

        # Fix 3: Normalize excessive blank lines
        fixed = self._normalize_blank_lines(fixed)

        # Fix 4: Ensure proper Mermaid diagram formatting
        fixed = self._fix_mermaid_formatting(fixed)

        # Fix 5: Optimize Mermaid for PDF (convert Japanese labels to English)
        fixed = self._optimize_mermaid_for_pdf(fixed)

        return fixed

    def _wrap_long_code_lines(self, content: str, max_length: int = 70) -> str:
        """Wrap long lines inside code blocks."""
        lines = content.split("\n")
        result = []
        in_code_block = False
        code_lang = ""

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    code_lang = line.strip()[3:].strip()
                result.append(line)
                continue

            if in_code_block and len(line) > max_length:
                # Wrap long lines in code blocks
                # Find a good break point (space, comma, etc.)
                wrapped = self._smart_wrap_line(line, max_length, code_lang)
                result.extend(wrapped)
                self.applied_fixes.append(f"Wrapped long code line ({len(line)} chars)")
            else:
                result.append(line)

        return "\n".join(result)

    def _smart_wrap_line(
        self, line: str, max_length: int, lang: str = ""
    ) -> list[str]:
        """Smart line wrapping for code."""
        if len(line) <= max_length:
            return [line]

        # Find indent level
        indent = len(line) - len(line.lstrip())
        indent_str = line[:indent]

        # For shell commands, wrap at && or |
        if lang in ("bash", "sh", "shell", ""):
            if " && " in line:
                parts = line.split(" && ")
                result = [parts[0] + " \\"]
                for part in parts[1:-1]:
                    result.append(indent_str + "  && " + part + " \\")
                result.append(indent_str + "  && " + parts[-1])
                return result

            if " | " in line:
                parts = line.split(" | ")
                result = [parts[0] + " \\"]
                for part in parts[1:-1]:
                    result.append(indent_str + "  | " + part + " \\")
                result.append(indent_str + "  | " + parts[-1])
                return result

        # For other code, wrap at commas or spaces
        if ", " in line[max_length // 2 :]:
            # Find comma near the max_length
            idx = line.rfind(", ", 0, max_length)
            if idx > max_length // 2:
                return [
                    line[: idx + 1],
                    indent_str + "  " + line[idx + 2 :].lstrip(),
                ]

        # Last resort: hard wrap
        return [line[:max_length], indent_str + "  " + line[max_length:]]

    def _wrap_long_urls(self, content: str) -> str:
        """Wrap long URLs that aren't in code blocks."""
        # Find URLs outside code blocks
        lines = content.split("\n")
        result = []
        in_code_block = False

        url_pattern = re.compile(
            r"(https?://[^\s\)>\]]+)"
        )

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                result.append(line)
                continue

            if in_code_block:
                result.append(line)
                continue

            # Check for long URLs in regular text
            match = url_pattern.search(line)
            if match and len(match.group(1)) > 50:
                url = match.group(1)
                # If URL is in markdown link format, leave it
                if f"]({url})" in line:
                    result.append(line)
                else:
                    # Wrap in code block
                    prefix = line[: match.start()]
                    suffix = line[match.end() :]
                    result.append(f"{prefix}`{url}`{suffix}")
                    self.applied_fixes.append(f"Wrapped long URL in code: {url[:30]}...")
            else:
                result.append(line)

        return "\n".join(result)

    def _normalize_blank_lines(self, content: str) -> str:
        """Remove excessive blank lines."""
        # Replace 4+ consecutive newlines with 3
        normalized = re.sub(r"\n{4,}", "\n\n\n", content)

        if normalized != content:
            self.applied_fixes.append("Normalized excessive blank lines")

        return normalized

    def _fix_mermaid_formatting(self, content: str) -> str:
        """Ensure Mermaid diagrams are properly formatted."""
        # Find Mermaid blocks
        mermaid_pattern = re.compile(
            r"```mermaid\s*\n(.*?)```",
            re.DOTALL,
        )

        def fix_mermaid(match: re.Match[str]) -> str:
            diagram = match.group(1)

            # Remove excessive whitespace
            lines = [l.rstrip() for l in diagram.split("\n")]
            # Remove empty lines at start/end
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()

            return "```mermaid\n" + "\n".join(lines) + "\n```"

        fixed = mermaid_pattern.sub(fix_mermaid, content)

        if fixed != content:
            self.applied_fixes.append("Fixed Mermaid diagram formatting")

        return fixed

    def _optimize_mermaid_for_pdf(self, content: str) -> str:
        """Mermaid図をPDF出力向けに最適化する。"""
        mermaid_pattern = re.compile(
            r"```mermaid\s*\n(.*?)```",
            re.DOTALL,
        )

        def optimize(match: re.Match[str]) -> str:
            diagram = match.group(1)

            # 日本語ラベルを短い英語に置換（PDFでの文字化け防止）
            replacements = {
                'データベース': 'DB',
                'ユーザー': 'User',
                'サーバー': 'Server',
                'ブラウザ': 'Browser',
                'リクエスト': 'Request',
                'レスポンス': 'Response',
                'コンポーネント': 'Component',
                'プロジェクト': 'Project',
                'タスク': 'Task',
                'クライアント': 'Client',
                'フロントエンド': 'Frontend',
                'バックエンド': 'Backend',
                'アプリケーション': 'App',
            }
            original = diagram
            for jp, en in replacements.items():
                diagram = diagram.replace(jp, en)

            if diagram != original:
                self.applied_fixes.append("Optimized Mermaid labels for PDF")

            return "```mermaid\n" + diagram + "```"

        return mermaid_pattern.sub(optimize, content)

    def get_fix_summary(self) -> str:
        """Get a summary of applied fixes."""
        if not self.applied_fixes:
            return "No automatic fixes applied"

        return "Applied fixes:\n" + "\n".join(f"  - {fix}" for fix in self.applied_fixes)


def create_pdf_fix_prompt(instructions: list[str]) -> str:
    """
    Create a prompt for LLM to fix PDF issues.

    Args:
        instructions: List of fix instructions from PDFFixer

    Returns:
        Formatted prompt for LLM
    """
    if not instructions:
        return ""

    prompt = """
【PDF視覚問題の修正指示】

PDF生成後の検証で以下の問題が検出されました。修正してください：

"""
    for i, instruction in enumerate(instructions, 1):
        prompt += f"{i}. {instruction}\n\n"

    prompt += """
修正ガイドライン：
- 既存の内容を削除せず、必要な修正のみを行う
- Mermaidのノードラベルは短い英語を使用（日本語は文字化けしやすい）
- テーブルは必ずヘッダー行 + セパレーター行 + データ行の完全な形式に
- 長いURLやコマンドはコードブロック内に配置
- 見出しがページ末尾に孤立しないよう改ページを調整

修正後のMarkdownファイル全体を出力してください。
"""
    return prompt


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_fixer.py <markdown_file> [pdf_issues_json]")
        sys.exit(1)

    md_path = Path(sys.argv[1])
    if not md_path.exists():
        print(f"Error: File not found: {md_path}")
        sys.exit(1)

    # Example issues for testing
    test_issues = [
        {"type": "empty_page", "page": 2, "message": "Page has very little content"},
        {"type": "truncation", "page": 5, "context": "PostgreSQL", "message": "Truncated text"},
        {"type": "mermaid_issue", "message": "Mermaid diagram may have truncated text"},
    ]

    fixer = PDFFixer(md_path, test_issues)

    print("=" * 60)
    print("PDF Fixer Test")
    print("=" * 60)
    print()
    print("LLM Fix Instructions:")
    print("-" * 40)
    for instr in fixer.generate_fix_instructions():
        print(instr)
        print()

    print("Auto-fix Summary:")
    print("-" * 40)
    fixed = fixer.auto_fix_content()
    print(fixer.get_fix_summary())
