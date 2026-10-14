"""
PM B (ChatGPT) - User-Friendliness Reviewer
読みやすさ・わかりやすさを重視したレビュー担当
"""

from openai import OpenAI
from typing import Optional
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from edu-creator/.env
load_dotenv(Path(__file__).parent.parent / '.env')


class PMChatGPT:
    """PM B: ChatGPT - 読みやすさ・わかりやすさをチェック"""

    def __init__(self, model: str = "gpt-5.2"):
        """
        Initialize ChatGPT PM

        Args:
            model: ChatGPT model name (default: gpt-5.2)
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.pm_name = "PM B (ChatGPT)"

    def review_draft(
        self,
        draft_content: str,
        chapter_id: str,
        quality_rules: str,
        target_audience: str = "初心者エンジニア"
    ) -> dict:
        """
        ドラフトをレビュー（読みやすさ・わかりやすさ重視）

        Args:
            draft_content: Claude Codeが生成したドラフト
            chapter_id: 章ID（例: day01）
            quality_rules: 品質ルール
            target_audience: 対象読者層

        Returns:
            {
                "approval": bool,  # True=承認, False=修正必要
                "review_comment": str,  # レビューコメント
                "issues": [
                    {
                        "severity": "critical" | "major" | "minor",
                        "category": str,  # 例: "わかりにくい", "冗長", "説明不足"
                        "description": str,
                        "suggestion": str
                    }
                ]
            }
        """
        prompt = f"""
You are PM B (ChatGPT) - a UX-focused reviewer who ensures tutorials are CLEAR, FRIENDLY, and EASY TO FOLLOW.

Review the following curriculum draft created by Claude Code for {chapter_id}.

QUALITY RULES:
{quality_rules}

TARGET AUDIENCE: {target_audience}

DRAFT CONTENT:
{draft_content}

YOUR REVIEW FOCUS (読みやすさ・わかりやすさ):
1. **Clarity**: Are explanations clear and easy to understand?
2. **Tone**: Is the writing friendly and encouraging?
3. **Structure**: Is information organized logically for learners?
4. **Examples**: Are examples helpful and relatable?
5. **Completeness**: Are there gaps that would confuse learners?
6. **Motivation**: Does it keep readers engaged and motivated?

OUTPUT FORMAT (JSON):
{{
    "approval": true/false,
    "review_comment": "全体的な評価コメント（日本語）",
    "issues": [
        {{
            "severity": "major",
            "category": "説明不足",
            "description": "問題の詳細説明",
            "suggestion": "具体的な修正案"
        }}
    ]
}}

SEVERITY GUIDELINES:
- **critical**: 初心者が完全に理解できない、手順が不明確
- **major**: わかりにくい説明、重要な情報の欠落
- **minor**: より良い表現の提案、小さな改善点

IMPORTANT:
- If approval=true, issues can be empty or contain only minor suggestions
- If approval=false, you MUST provide clear issues with suggestions
- Think from a LEARNER's perspective - what would confuse you?
- Be empathetic - we want tutorials that make people feel capable
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a UX-focused technical reviewer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # やや低めで一貫性を保つ
            )

            result_text = response.choices[0].message.content

            # JSONを抽出
            json_match = re.search(r'```json\n(.*?)\n```', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("JSON not found in ChatGPT response")

            return result

        except Exception as e:
            return {
                "approval": False,
                "review_comment": f"レビュー実行中にエラーが発生しました: {str(e)}",
                "issues": [
                    {
                        "severity": "critical",
                        "category": "システムエラー",
                        "description": f"ChatGPT API呼び出し失敗: {str(e)}",
                        "suggestion": "エラーを確認して再実行してください"
                    }
                ]
            }

    def __str__(self):
        return f"{self.pm_name} (読みやすさ・わかりやすさレビュー担当)"
