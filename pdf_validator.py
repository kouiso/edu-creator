#!/usr/bin/env python3
"""
PDF Visual Validator for edu-creator
=====================================

Validates PDF output for common issues:
1. Text truncation (especially in Mermaid diagrams)
2. Table rendering issues
3. Page break problems
4. Empty pages / excessive whitespace
5. Missing content

Usage:
    python edu-creator/pdf_validator.py material/pdf/day01_xxx.pdf

Returns exit code 0 if validation passes, 1 if issues found.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


class PDFValidator:
    """Validates PDF output for visual and structural issues."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.text_content: str = ""
        self.page_texts: list[str] = []
        self.issues: list[dict[str, Any]] = []

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

    def extract_text(self) -> bool:
        """Extract text from PDF using pdftotext or similar tool."""
        try:
            # Try pdftotext first (poppler-utils)
            result = subprocess.run(
                ["pdftotext", "-layout", str(self.pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.text_content = result.stdout
                # Split by form feed character (page break)
                self.page_texts = self.text_content.split("\f")
                return True
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            self.issues.append({
                "type": "error",
                "message": "PDF text extraction timed out",
                "severity": "high",
            })
            return False

        # Fallback: Try using Python library
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(self.pdf_path))
            self.page_texts = []
            for page in doc:
                self.page_texts.append(page.get_text())
            self.text_content = "\n\n".join(self.page_texts)
            doc.close()
            return True
        except ImportError:
            pass
        except Exception as e:
            self.issues.append({
                "type": "error",
                "message": f"PDF text extraction failed: {e}",
                "severity": "high",
            })
            return False

        self.issues.append({
            "type": "error",
            "message": "No PDF text extraction tool available (install poppler-utils or PyMuPDF)",
            "severity": "high",
        })
        return False

    def check_text_truncation(self) -> list[dict[str, Any]]:
        """Check for text truncation patterns (common in Mermaid diagrams)."""
        issues = []

        # Patterns indicating truncated text
        truncation_patterns = [
            # Single letter followed by space and another single letter (e.g., "N t j" for "Next.js")
            (r'\b[A-Z]\s+[a-z]\s+[a-z]\b', "Possible truncated word (single letters)"),
            # Incomplete words like "P t SQL" for "PostgreSQL"
            (r'\bP\s*t\s*SQL\b', "Truncated 'PostgreSQL'"),
            (r'\bN\s*t\s*j\b', "Truncated 'Next.js'"),
            (r'\bN\s*d\s*j\b', "Truncated 'Node.js'"),
            (r'\bD\s*k\s*[rC]\b', "Truncated 'Docker'"),
            # Very short isolated words that shouldn't be standalone
            (r'(?<!\w)[A-Z][a-z](?!\w)', "Possibly truncated single syllable"),
        ]

        for pattern, description in truncation_patterns:
            matches = list(re.finditer(pattern, self.text_content))
            if matches:
                for match in matches[:3]:  # Limit to first 3 matches
                    # Find page number
                    page_num = 0
                    char_count = 0
                    for i, page_text in enumerate(self.page_texts):
                        char_count += len(page_text) + 1
                        if char_count > match.start():
                            page_num = i + 1
                            break

                    issues.append({
                        "type": "truncation",
                        "message": f"{description}: '{match.group()}'",
                        "page": page_num,
                        "severity": "high",
                        "context": self.text_content[max(0, match.start()-30):match.end()+30],
                    })

        return issues

    def check_table_completeness(self) -> list[dict[str, Any]]:
        """Check for incomplete tables (header without data rows)."""
        issues = []

        # Look for table-like structures
        # Tables typically have headers separated by spaces and consistent alignment
        for i, page_text in enumerate(self.page_texts, 1):
            lines = page_text.split("\n")

            # Look for potential table headers (lines with multiple capitalized words)
            for j, line in enumerate(lines):
                # Check if this looks like a table header row
                if re.search(r'^\s*\w+\s{2,}\w+\s{2,}\w+', line):
                    # Check if next few lines have content
                    next_lines = lines[j+1:j+4] if j+1 < len(lines) else []
                    has_data = any(re.search(r'\S', l) for l in next_lines)

                    if not has_data:
                        issues.append({
                            "type": "incomplete_table",
                            "message": f"Possible incomplete table (header without data)",
                            "page": i,
                            "severity": "medium",
                            "context": line[:100],
                        })

        return issues

    def check_empty_pages(self) -> list[dict[str, Any]]:
        """Check for pages with very little content (possible layout issues)."""
        issues = []

        for i, page_text in enumerate(self.page_texts, 1):
            # Strip whitespace and count meaningful characters
            stripped = re.sub(r'\s+', '', page_text)

            if len(stripped) < 50:  # Very empty page
                issues.append({
                    "type": "empty_page",
                    "message": f"Page {i} has very little content ({len(stripped)} chars)",
                    "page": i,
                    "severity": "low",
                })
            elif len(stripped) < 200 and i > 1 and i < len(self.page_texts):
                # Middle page with little content (not first/last)
                issues.append({
                    "type": "sparse_page",
                    "message": f"Page {i} has sparse content ({len(stripped)} chars)",
                    "page": i,
                    "severity": "low",
                })

        return issues

    def check_mermaid_rendering(self) -> list[dict[str, Any]]:
        """Check for properly rendered Mermaid diagrams."""
        issues = []

        # Look for Mermaid diagram indicators
        # Well-rendered diagrams should have node labels visible together
        # Note: Arrows (→, -->) are typically rendered as SVG paths, not text
        mermaid_good_indicators = [
            r'User.*Next\.js',  # Flow visible in text
            r'Next\.js.*Node\.js',
            r'Node\.js.*PostgreSQL',
            r':3000.*Next\.js',  # Port + service
            r'API.*Node\.js',
            r'SQL.*PostgreSQL',
            r'compose.*Docker',
        ]

        # Check for multiple diagram elements appearing together (good sign)
        diagram_elements = []
        for elem in ['User', 'Next.js', 'Node.js', 'PostgreSQL', 'Docker', 'Taskfile']:
            if elem.lower() in self.text_content.lower():
                diagram_elements.append(elem)

        has_good_mermaid = any(
            re.search(pattern, self.text_content, re.IGNORECASE)
            for pattern in mermaid_good_indicators
        )

        # If we have multiple diagram elements, that's likely a good diagram
        if len(diagram_elements) >= 4:
            has_good_mermaid = True

        if not has_good_mermaid and len(diagram_elements) >= 2:
            # Only flag if we have diagram elements but they seem broken
            # Check for truncation patterns in diagram context
            truncation_near_diagram = re.search(
                r'\b[A-Z]\s+[a-z]\s+[a-z]\b.{0,50}(User|Docker|Next|Node|Post)',
                self.text_content,
                re.IGNORECASE
            )
            if truncation_near_diagram:
                issues.append({
                    "type": "mermaid_issue",
                    "message": "Mermaid diagram may have truncated text",
                    "severity": "high",
                    "context": f"Found elements: {', '.join(diagram_elements[:5])}",
                })

        return issues

    def check_code_blocks(self) -> list[dict[str, Any]]:
        """Check for properly formatted code blocks."""
        issues = []

        # Look for code-like content that might be broken
        # Well-formatted code should have consistent indentation
        code_patterns = [
            r'\$\s+\w+',  # Command prompts
            r'^\s{2,}\w+:',  # YAML-like indentation
            r'```',  # Markdown code fence (shouldn't appear in PDF)
        ]

        # If raw markdown fences appear, something went wrong
        if '```' in self.text_content:
            issues.append({
                "type": "raw_markdown",
                "message": "Raw markdown code fences found in PDF",
                "severity": "high",
            })

        return issues

    def check_long_lines(self) -> list[dict[str, Any]]:
        """Check for truncated long lines (code, URLs)."""
        issues = []

        for i, page_text in enumerate(self.page_texts, 1):
            lines = page_text.split("\n")

            for j, line in enumerate(lines):
                stripped = line.strip()

                # Check for truncated URLs (http:// without full domain)
                if re.search(r'http://local\s*$|https://local\s*$', stripped):
                    issues.append({
                        "type": "url_truncation",
                        "message": f"Truncated URL detected: '{stripped[:50]}...'",
                        "page": i,
                        "severity": "medium",
                        "context": stripped,
                    })

                # Check for lines ending abruptly (possible truncation)
                # Look for lines that end with incomplete words or code
                if len(stripped) > 60 and re.search(r'\w{2,}$', stripped):
                    # Check if it looks like code that was cut off
                    if re.search(r'[{(\[,;:]\s*\w+$', stripped):
                        issues.append({
                            "type": "line_truncation",
                            "message": f"Possibly truncated line on page {i}",
                            "page": i,
                            "severity": "low",
                            "context": stripped[-50:],
                        })

        return issues

    def check_orphan_headers(self) -> list[dict[str, Any]]:
        """Check for section headers appearing alone at page bottom."""
        issues = []

        for i, page_text in enumerate(self.page_texts, 1):
            lines = page_text.strip().split("\n")

            if not lines:
                continue

            # Check if last non-empty lines look like headers with no content after
            last_lines = [l for l in lines[-5:] if l.strip()]

            for line in last_lines:
                # Check for potential headers (lines with # or emoji + short text)
                if re.match(r'^#+ |^[🎯📊🛠️💡🔧📦🚀]', line.strip()):
                    # Header at end of page might be orphaned
                    issues.append({
                        "type": "orphan_header",
                        "message": f"Header may be orphaned at page {i} bottom: '{line.strip()[:40]}...'",
                        "page": i,
                        "severity": "low",
                        "context": line.strip(),
                    })

        return issues

    def check_screenshot_placeholders(self) -> list[dict[str, Any]]:
        """Check for unresolved screenshot placeholders."""
        issues = []

        # Pattern for screenshot placeholders
        placeholder_patterns = [
            r'【スクリーンショット[^】]*】',
            r'\[スクリーンショット[^\]]*\]',
            r'【screenshot[^】]*】',
            r'<!-- screenshot:.*?-->',
            r'\[画面キャプチャ[^\]]*\]',
        ]

        for pattern in placeholder_patterns:
            matches = list(re.finditer(pattern, self.text_content, re.IGNORECASE))
            for match in matches:
                page_num = self._find_page_for_position(match.start())
                issues.append({
                    "type": "screenshot_placeholder",
                    "message": "Unresolved screenshot placeholder",
                    "page": page_num,
                    "severity": "high",
                    "context": match.group()[:60],
                })

        return issues

    def _find_page_for_position(self, position: int) -> int:
        """Helper to find page number for a character position."""
        char_count = 0
        for i, page_text in enumerate(self.page_texts):
            char_count += len(page_text) + 1
            if char_count > position:
                return i + 1
        return len(self.page_texts)

    def validate(self) -> dict[str, Any]:
        """Run all validation checks and return results."""
        if not self.extract_text():
            return {
                "passed": False,
                "issues": self.issues,
                "page_count": 0,
            }

        # Run all checks
        all_issues = []
        all_issues.extend(self.check_text_truncation())
        all_issues.extend(self.check_table_completeness())
        all_issues.extend(self.check_empty_pages())
        all_issues.extend(self.check_mermaid_rendering())
        all_issues.extend(self.check_code_blocks())
        all_issues.extend(self.check_long_lines())
        all_issues.extend(self.check_orphan_headers())
        all_issues.extend(self.check_screenshot_placeholders())
        all_issues.extend(self.issues)

        # Determine pass/fail
        high_severity = [i for i in all_issues if i.get("severity") == "high"]

        return {
            "passed": len(high_severity) == 0,
            "issues": all_issues,
            "page_count": len(self.page_texts),
            "total_chars": len(self.text_content),
        }

    def generate_report(self) -> str:
        """Generate a human-readable validation report."""
        result = self.validate()

        report = []
        report.append("")
        report.append("=" * 60)
        report.append("    PDF Visual Validation Report")
        report.append("=" * 60)
        report.append("")
        report.append(f"File: {self.pdf_path.name}")
        report.append(f"Pages: {result['page_count']}")
        report.append(f"Total characters: {result.get('total_chars', 0):,}")
        report.append("")

        if result["passed"]:
            report.append("Status: PASS")
        else:
            report.append("Status: FAIL")

        report.append("")
        report.append("-" * 60)

        if not result["issues"]:
            report.append("No issues found!")
        else:
            # Group by severity
            high = [i for i in result["issues"] if i.get("severity") == "high"]
            medium = [i for i in result["issues"] if i.get("severity") == "medium"]
            low = [i for i in result["issues"] if i.get("severity") == "low"]

            if high:
                report.append("")
                report.append("HIGH SEVERITY:")
                for issue in high:
                    page_info = f" (p.{issue['page']})" if "page" in issue else ""
                    report.append(f"  {issue['message']}{page_info}")
                    if "context" in issue:
                        context = issue["context"][:80].replace("\n", " ")
                        report.append(f"    Context: ...{context}...")

            if medium:
                report.append("")
                report.append("MEDIUM SEVERITY:")
                for issue in medium:
                    page_info = f" (p.{issue['page']})" if "page" in issue else ""
                    report.append(f"  {issue['message']}{page_info}")

            if low:
                report.append("")
                report.append("LOW SEVERITY:")
                for issue in low:
                    page_info = f" (p.{issue['page']})" if "page" in issue else ""
                    report.append(f"  {issue['message']}{page_info}")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python pdf_validator.py <pdf_file>")
        print("       python pdf_validator.py material/pdf/day01_xxx.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        validator = PDFValidator(pdf_path)
        report = validator.generate_report()
        print(report)

        result = validator.validate()
        sys.exit(0 if result["passed"] else 1)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
