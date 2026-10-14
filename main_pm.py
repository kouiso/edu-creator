"""
=============================================================================
📚 Educational Material Generator with PM Architecture
=============================================================================
New Architecture:
  Claude Code (Worker) → PM A (Gemini) + PM B (ChatGPT) → PO (ChatGPT)

Flow:
  1. Claude Code: Investigate repo + Write draft
  2. PM A (Gemini): Technical/logical review
  3. PM B (ChatGPT): User-friendliness review
  4. PO (ChatGPT): Final decision (approve/revise)
  5. If revise: Claude Code implements changes → back to step 2

Usage:
  python edu-creator/main_pm.py --config edu-config.yaml --chapters 1-5
=============================================================================
"""

import argparse
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Import PM/PO agents
from agents.pm_gemini import PMGemini
from agents.pm_chatgpt import PMChatGPT
from agents.po_chatgpt import POChatGPT

# Import Claude Code wrapper
from tools.claude_code_wrapper import ClaudeCodeCLI

# Import config validation
from config_models import EduConfig, validate_config

# Import prompts
from prompt.task.quality_rules import QUALITY_RULES

# Load .env from project root (parent directory)
load_dotenv(Path(__file__).parent.parent / '.env')

# =============================================================================
# Configuration
# =============================================================================

MAX_REVISION_ROUNDS = 3  # 最大修正ラウンド数


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(log_level: str = "INFO"):
    """ロギング設定"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


# =============================================================================
# Main Workflow
# =============================================================================

class PMWorkflow:
    """PM体制ワークフロー管理"""

    def __init__(
        self,
        config: EduConfig,
        repo_path: Path,
        output_dir: Path,
        logger: logging.Logger
    ):
        self.config = config
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.logger = logger

        # Initialize agents
        self.logger.info("Initializing PM/PO agents...")

        # Get model names from environment variables
        import os
        claude_model = os.getenv("CLAUDE_CODE_MODEL", "claude-opus-4-5-20251101")
        gemini_model = os.getenv("GOOGLE_REVIEWER_MODEL", "gemini-3-pro-preview")
        chatgpt_model = os.getenv("OPENAI_MODEL", "gpt-5.2")

        self.claude_code = ClaudeCodeCLI(
            repo_path=str(repo_path),
            model=claude_model
        )
        self.pm_a = PMGemini(model=gemini_model)
        self.pm_b = PMChatGPT(model=chatgpt_model)
        self.po = POChatGPT(model=chatgpt_model)

        self.logger.info(f"✅ {self.pm_a}")
        self.logger.info(f"✅ {self.pm_b}")
        self.logger.info(f"✅ {self.po}")

    def generate_chapter(self, chapter_config: dict) -> bool:
        """
        1章分の教材を生成

        Args:
            chapter_config: 章の設定

        Returns:
            成功したかどうか
        """
        chapter_id = chapter_config["id"]
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"📖 Starting: {chapter_id} - {chapter_config['title']}")
        self.logger.info(f"{'='*80}\n")

        # Step 1: Claude Codeで初期ドラフト生成
        draft = self._generate_initial_draft(chapter_config)
        if not draft:
            self.logger.error(f"❌ Failed to generate initial draft for {chapter_id}")
            return False

        # Step 2-5: Review & Revision Loop
        for round_num in range(1, MAX_REVISION_ROUNDS + 1):
            self.logger.info(f"\n🔄 Review Round {round_num}/{MAX_REVISION_ROUNDS}")

            # PM A (Gemini) レビュー
            self.logger.info("📝 PM A (Gemini) reviewing...")
            pm_a_result = self.pm_a.review_draft(
                draft_content=draft,
                chapter_id=chapter_id,
                quality_rules=QUALITY_RULES,
                codebase_context=self._get_codebase_context(chapter_config)
            )
            self.logger.info(f"  └─ Approval: {pm_a_result['approval']}")

            # PM B (ChatGPT) レビュー
            self.logger.info("📝 PM B (ChatGPT) reviewing...")
            pm_b_result = self.pm_b.review_draft(
                draft_content=draft,
                chapter_id=chapter_id,
                quality_rules=QUALITY_RULES
            )
            self.logger.info(f"  └─ Approval: {pm_b_result['approval']}")

            # PO (ChatGPT) 最終判断
            self.logger.info("🎯 PO (ChatGPT) making final decision...")
            po_decision = self.po.make_final_decision(
                draft_content=draft,
                pm_a_review=pm_a_result,
                pm_b_review=pm_b_result,
                chapter_id=chapter_id,
                quality_rules=QUALITY_RULES
            )

            self.logger.info(f"  └─ Decision: {po_decision['final_decision'].upper()}")
            self.logger.info(f"  └─ Reason: {po_decision['decision_reason']}")

            # 承認されたら保存して終了
            if po_decision["final_decision"] == "approve":
                self._save_chapter(chapter_id, draft)
                self.logger.info(f"✅ {chapter_id} approved and saved!")
                return True

            # 修正が必要な場合
            if round_num < MAX_REVISION_ROUNDS:
                self.logger.info(f"🔧 Requesting Claude Code to revise...")
                draft = self._revise_draft(
                    chapter_config=chapter_config,
                    current_draft=draft,
                    revision_instructions=po_decision["revision_instructions"],
                    priority_issues=po_decision["priority_issues"]
                )
                if not draft:
                    self.logger.error(f"❌ Failed to revise draft")
                    return False
            else:
                self.logger.warning(f"⚠️ Max revision rounds reached, saving anyway...")
                self._save_chapter(chapter_id, draft)
                return True

        return False

    def _generate_initial_draft(self, chapter_config: dict) -> Optional[str]:
        """Claude Codeで初期ドラフトを生成"""
        chapter_id = chapter_config["id"]
        self.logger.info(f"🤖 Claude Code generating initial draft for {chapter_id}...")

        prompt = f"""
You are creating a beginner-friendly programming tutorial.

Chapter: {chapter_id}
Title: {chapter_config['title']}
What You Will Make: {chapter_config.get('what_you_will_make', 'N/A')}
What You Will Learn: {chapter_config.get('what_you_will_learn', 'N/A')}
Topics: {', '.join(chapter_config.get('topics', []))}
Special Notes: {', '.join(chapter_config.get('special_notes', [])) if chapter_config.get('special_notes') else 'None'}

QUALITY RULES:
{QUALITY_RULES}

REPOSITORY CONTEXT:
- Repository path: {self.repo_path}
- This is a task management app built with Next.js 15, TypeScript, tRPC, Prisma
- Tech stack: Next.js App Router, shadcn/ui, Tailwind CSS v4, PostgreSQL

CURRICULUM APPROACH (CRITICAL - MUST FOLLOW):
- Tutorial must be COMPLETELY SELF-CONTAINED
- Students read the tutorial and type the code themselves - that's ALL they need
- NO external resources: NO git clone, NO ZIP download, NO starter template
- Day01 uses "npx create-next-app" to create project from scratch
- ALL code that students need to write MUST be included in the tutorial
- Students should be able to complete the tutorial WITHOUT looking at any existing codebase
- Reference the codebase to understand WHAT to teach, but write tutorials that stand alone

YOUR TASK:
1. **Investigate the codebase** to understand relevant files and implementation
2. **Write a complete tutorial** following the quality rules above

CRITICAL OUTPUT INSTRUCTIONS:
- DO NOT use Write tool or any file writing tools
- DO NOT save to files - output everything DIRECTLY in your response
- Your response must BE the complete tutorial in Markdown format
- Start your response with "# Day" (the tutorial heading)
- Include ALL content: headings, steps, code blocks, tables, everything
- です・ます調の日本語で記述

QUALITY REQUIREMENTS:
- 実際のコードベースからの正確な情報を使用
- 初心者が手順を追って実装できるように書く
- コード例は25行以内
- 段落は3文以内
- 禁止ワード: 「同様に」「以下略」「簡単です」

Your entire response should be the Markdown tutorial content, starting with # Day heading.
"""

        try:
            # コンテキストファイルを準備
            context_files = self._get_context_files(chapter_config)

            result = self.claude_code.run_task(
                prompt=prompt,
                context_files=context_files
            )

            # Markdownを抽出
            draft = self.claude_code.extract_markdown(result)
            return draft

        except Exception as e:
            self.logger.error(f"Error generating draft: {e}")
            return None

    def _revise_draft(
        self,
        chapter_config: dict,
        current_draft: str,
        revision_instructions: str,
        priority_issues: list
    ) -> Optional[str]:
        """Claude Codeでドラフトを修正"""
        chapter_id = chapter_config["id"]

        prompt = f"""
You are revising a tutorial based on PM feedback.

Chapter: {chapter_id}

CURRENT DRAFT:
{current_draft}

REVISION INSTRUCTIONS FROM PO:
{revision_instructions}

PRIORITY ISSUES TO FIX:
{json.dumps(priority_issues, ensure_ascii=False, indent=2)}

YOUR TASK:
1. **Address all priority issues** starting from highest severity
2. **Keep the overall structure** unless specifically requested to change
3. **Maintain quality rules** from the original requirements

CRITICAL OUTPUT INSTRUCTIONS:
- DO NOT use Write tool or any file writing tools
- DO NOT save to files - output everything DIRECTLY in your response
- Your response must BE the complete revised tutorial in Markdown format
- Start your response with "# Day" (the tutorial heading)
- Include ALL content of the revised tutorial
- です・ます調の日本語で記述

Your entire response should be the complete revised Markdown tutorial, starting with # Day heading.
"""

        try:
            result = self.claude_code.run_task(prompt=prompt)
            revised_draft = self.claude_code.extract_markdown(result)
            return revised_draft

        except Exception as e:
            self.logger.error(f"Error revising draft: {e}")
            return None

    def _get_context_files(self, chapter_config: dict) -> list[Path]:
        """章に関連するコンテキストファイルを取得"""
        # TODO: 章の内容に基づいて関連ファイルを動的に選択
        # 今は暫定でいくつかの重要ファイルを返す
        important_files = [
            self.repo_path / "CLAUDE.md",
            self.repo_path / "src" / "server" / "api" / "routers",
        ]

        return [f for f in important_files if f.exists()]

    def _get_codebase_context(self, chapter_config: dict) -> str:
        """コードベースのコンテキスト情報を取得"""
        return f"""
Repository: {self.repo_path}
Tech Stack: Next.js 15, TypeScript, tRPC, Prisma, PostgreSQL
UI: shadcn/ui, Tailwind CSS v4
Features: タスク管理、プロジェクト管理、ユーザー管理、コメント、検索、レポート
"""

    def _save_chapter(self, chapter_id: str, content: str):
        """章を保存"""
        output_file = self.output_dir / f"{chapter_id}.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"💾 Saved to: {output_file}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate educational materials with PM architecture"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to edu-config.yaml"
    )
    parser.add_argument(
        "--chapters",
        type=str,
        help="Chapters to generate (e.g., '1-5' or '1,3,5')"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level"
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.log_level)

    # シグナルハンドラを設定（Ctrl+Cでの安全な終了）
    def signal_handler(signum, frame):
        logger.info("\n⚠️ 中断シグナルを受信しました。クリーンアップ中...")
        logger.info("✅ プロセスクリーンアップはClaude Code wrapperで自動的に行われます")
        sys.exit(130)  # 128 + SIGINT(2)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load config
    logger.info(f"📖 Loading config from: {args.config}")
    with open(args.config, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    # Validate config
    success, config, error_msg = validate_config(config_dict)
    if not success or config is None:
        logger.error(f"❌ Config validation failed: {error_msg}")
        sys.exit(1)

    # Determine chapters to generate
    chapters_to_generate = []
    if args.chapters:
        # Parse章範囲
        if "-" in args.chapters:
            start, end = map(int, args.chapters.split("-"))
            chapter_indices = range(start - 1, end)
        else:
            chapter_indices = [int(c) - 1 for c in args.chapters.split(",")]

        chapters_to_generate = [config.chapters[i] for i in chapter_indices]
    else:
        chapters_to_generate = config.chapters

    logger.info(f"📚 Generating {len(chapters_to_generate)} chapters")

    # Setup paths
    repo_path = Path.cwd().parent  # edu-creatorの親 = task-app
    # YAMLから直接output_dirを取得
    output_dir = Path(config_dict.get("paths", {}).get("output_dir", "material/30days-curriculum"))

    # Initialize workflow
    workflow = PMWorkflow(
        config=config,
        repo_path=repo_path,
        output_dir=output_dir,
        logger=logger
    )

    # Generate chapters
    success_count = 0
    for chapter_config in chapters_to_generate:
        if workflow.generate_chapter(chapter_config.model_dump()):
            success_count += 1

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ Completed: {success_count}/{len(chapters_to_generate)} chapters")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
