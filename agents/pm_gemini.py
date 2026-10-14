"""
PM A (Gemini) - Logical/Technical Reviewer
論理性・技術的正確性を重視したレビュー担当
"""

import google.generativeai as genai
from typing import Optional
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from edu-creator/.env
load_dotenv(Path(__file__).parent.parent / '.env')


class PMGemini:
    """PM A: Gemini - 論理性・技術的正確性をチェック"""

    def __init__(self, model: str = "gemini-3-pro-preview"):
        """
        Initialize Gemini PM

        Args:
            model: Gemini model name (default: gemini-3-pro-preview)
        """
        # Use GOOGLE_REVIEWER_API_KEY for Gemini 3 Pro
        api_key = os.getenv("GOOGLE_REVIEWER_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_REVIEWER_API_KEY or GOOGLE_API_KEY not set")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.pm_name = "PM A (Gemini)"

    def review_draft(
        self,
        draft_content: str,
        chapter_id: str,
        quality_rules: str,
        codebase_context: Optional[str] = None
    ) -> dict:
        """
        ドラフトをレビュー（論理性・技術的正確性重視）

        Args:
            draft_content: Claude Codeが生成したドラフト
            chapter_id: 章ID（例: day01）
            quality_rules: 品質ルール
            codebase_context: コードベースのコンテキスト情報

        Returns:
            {
                "approval": bool,  # True=承認, False=修正必要
                "review_comment": str,  # レビューコメント
                "issues": [
                    {
                        "severity": "critical" | "major" | "minor",
                        "category": str,  # 例: "技術的誤り", "論理矛盾", "コード誤り"
                        "description": str,
                        "suggestion": str
                    }
                ]
            }
        """
        codebase_section = f"CODEBASE CONTEXT:\n{codebase_context}" if codebase_context else ""

        prompt = f"""
You are PM A (Gemini) - a technical reviewer focused on LOGICAL CORRECTNESS and TECHNICAL ACCURACY.

Review the following curriculum draft created by Claude Code for {chapter_id}.

QUALITY RULES:
{quality_rules}

DRAFT CONTENT:
{draft_content}

{codebase_section}

YOUR REVIEW FOCUS (論理性・技術的正確性):
1. **Code Correctness**: Do all code examples actually work?
2. **Technical Accuracy**: Are technical explanations factually correct?
3. **Logical Flow**: Does the tutorial flow make logical sense?
4. **Command Validity**: Are all shell commands correct and safe?
5. **Conceptual Consistency**: Are concepts explained consistently?

OUTPUT FORMAT (JSON):
{{
    "approval": true/false,
    "review_comment": "全体的な評価コメント（日本語）",
    "issues": [
        {{
            "severity": "critical",
            "category": "技術的誤り",
            "description": "問題の詳細説明",
            "suggestion": "具体的な修正案"
        }}
    ]
}}

SEVERITY GUIDELINES:
- **critical**: 技術的に完全に間違っている、動作しないコード
- **major**: 論理的な矛盾、重要な概念の説明ミス
- **minor**: より良い説明方法の提案、小さな改善点

IMPORTANT:
- If approval=true, issues can be empty or contain only minor suggestions
- If approval=false, you MUST provide clear issues with suggestions
- Focus on FACTS and LOGIC, not style or presentation
- Be strict but fair - we want high technical quality
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text

            # JSONを抽出
            import json
            import re

            # ```json ... ``` 形式
            json_match = re.search(r'```json\n(.*?)\n```', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # { ... } 形式
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("JSON not found in Gemini response")

            return result

        except Exception as e:
            # エラー時はcriticalとして扱う
            return {
                "approval": False,
                "review_comment": f"レビュー実行中にエラーが発生しました: {str(e)}",
                "issues": [
                    {
                        "severity": "critical",
                        "category": "システムエラー",
                        "description": f"Gemini API呼び出し失敗: {str(e)}",
                        "suggestion": "エラーを確認して再実行してください"
                    }
                ]
            }

    def __str__(self):
        return f"{self.pm_name} (論理性・技術的正確性レビュー担当)"
