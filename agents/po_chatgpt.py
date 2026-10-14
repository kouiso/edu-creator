"""
PO (Product Owner) - Final Decision Maker
2名のPMレビューを統合して最終判断を下す
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


class POChatGPT:
    """PO: ChatGPT - 最終意思決定者"""

    def __init__(self, model: str = "gpt-5.2"):
        """
        Initialize ChatGPT PO

        Args:
            model: ChatGPT model name (default: gpt-5.2)
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.po_name = "PO (ChatGPT)"

    def make_final_decision(
        self,
        draft_content: str,
        pm_a_review: dict,
        pm_b_review: dict,
        chapter_id: str,
        quality_rules: str
    ) -> dict:
        """
        2名のPMレビューを統合して最終判断

        Args:
            draft_content: Claude Codeが生成したドラフト
            pm_a_review: PM A (Gemini)のレビュー結果
            pm_b_review: PM B (ChatGPT)のレビュー結果
            chapter_id: 章ID
            quality_rules: 品質ルール

        Returns:
            {
                "final_decision": "approve" | "revise",
                "decision_reason": str,  # 判断理由
                "revision_instructions": str,  # 修正指示（reviseの場合）
                "priority_issues": [  # 優先度順の修正項目
                    {
                        "source": "PM A" | "PM B" | "PO",
                        "severity": str,
                        "category": str,
                        "description": str,
                        "suggestion": str
                    }
                ]
            }
        """
        prompt = f"""
You are the Product Owner (PO) - the final decision maker for curriculum quality.

You have received two independent reviews for {chapter_id}:

PM A (Gemini) - Technical/Logical Review:
{json.dumps(pm_a_review, ensure_ascii=False, indent=2)}

PM B (ChatGPT) - User-Friendliness Review:
{json.dumps(pm_b_review, ensure_ascii=False, indent=2)}

QUALITY RULES:
{quality_rules}

ORIGINAL DRAFT:
{draft_content}

YOUR TASK:
1. Analyze both PM reviews
2. Make a final decision: APPROVE or REVISE
3. If REVISE, consolidate feedback into clear, prioritized revision instructions

DECISION CRITERIA:
- If both PMs approve → APPROVE (even with minor issues)
- If one PM rejects with critical/major issues → REVISE
- If both PMs reject → REVISE (prioritize critical issues first)
- Balance technical correctness (PM A) with user experience (PM B)

OUTPUT FORMAT (JSON):
{{
    "final_decision": "approve" or "revise",
    "decision_reason": "判断の理由（日本語）",
    "revision_instructions": "Claude Codeへの具体的な修正指示（日本語、reviseの場合のみ）",
    "priority_issues": [
        {{
            "source": "PM A",
            "severity": "critical",
            "category": "技術的誤り",
            "description": "問題の説明",
            "suggestion": "修正案"
        }}
    ]
}}

IMPORTANT:
- If final_decision="approve", priority_issues can be empty or minor suggestions only
- If final_decision="revise", priority_issues MUST be sorted by severity (critical → major → minor)
- revision_instructions should be ACTIONABLE and SPECIFIC for Claude Code
- Consider BOTH perspectives - don't ignore either PM's concerns
- Be decisive - the team is waiting for your decision
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a decisive Product Owner who balances technical excellence with user experience."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # 低めで一貫した判断
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
                    raise ValueError("JSON not found in PO response")

            return result

        except Exception as e:
            # エラー時は安全側（revise）に倒す
            return {
                "final_decision": "revise",
                "decision_reason": f"POの意思決定中にエラーが発生しました: {str(e)}",
                "revision_instructions": "システムエラーが発生したため、再度レビューが必要です。",
                "priority_issues": [
                    {
                        "source": "PO",
                        "severity": "critical",
                        "category": "システムエラー",
                        "description": f"PO API呼び出し失敗: {str(e)}",
                        "suggestion": "エラーを確認して再実行してください"
                    }
                ]
            }

    def __str__(self):
        return f"{self.po_name} (最終意思決定者)"
