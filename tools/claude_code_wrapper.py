"""
Claude Code CLI Wrapper
月額課金範囲内でClaude Opus 4.5を使用
"""

import json
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Optional


class ClaudeCodeCLI:
    """Claude Code CLI wrapper - 全実作業を担当"""

    def __init__(self, repo_path: str, model: str = "claude-opus-4-5-20251101"):
        self.repo_path = Path(repo_path)
        self.model = model

    def run_task(self, prompt: str, context_files: Optional[list[Path]] = None) -> str:
        """
        Claude Code CLIを実行

        Args:
            prompt: タスクの指示
            context_files: コンテキストとして渡すファイル（未使用）

        Returns:
            Claude Codeの出力（クリーンなコンテンツ）
        """
        process = None
        try:
            cmd = [
                'claude',
                '--print',  # Non-interactive mode
                '--output-format', 'json',  # JSON形式で出力（result フィールドにコンテンツ）
                '--model', self.model,
                '--add-dir', str(self.repo_path),  # Allow access to repository
            ]

            # Popenで実行（プロセスグループを分離して、クリーンアップを安全に行う）
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.repo_path),
                start_new_session=True  # 新しいプロセスグループを作成
            )

            # プロンプトを送信して結果を取得
            stdout, stderr = process.communicate(input=prompt, timeout=1800)

            if process.returncode != 0:
                raise RuntimeError(f"Claude Code failed: {stderr}")

            # JSON形式から結果を抽出
            try:
                response = json.loads(stdout)
                # result フィールドに生成されたコンテンツが入る
                content = response.get("result", "")
                if content:
                    return content
                # result が空の場合、他のフィールドを試す
                if "content" in response:
                    return response["content"]
                # フォールバック: 全体を返す
                return stdout
            except json.JSONDecodeError:
                # JSONパース失敗時はテキストとして返す
                return stdout

        except subprocess.TimeoutExpired:
            # タイムアウト時もクリーンアップ
            if process:
                self._cleanup_process_group(process)
            raise RuntimeError("Claude Code execution timed out (30 minutes)")

        except Exception as e:
            raise RuntimeError(f"Claude Code execution error: {str(e)}")

        finally:
            # 実行完了後、プロセスグループ内の残存プロセスをクリーンアップ
            if process:
                self._cleanup_process_group(process)

    def _cleanup_process_group(self, process: subprocess.Popen) -> None:
        """
        プロセスグループ全体をクリーンアップ

        edu-creatorから起動したプロセスのみを終了し、
        他のClaude Codeセッションには影響しない。
        """
        try:
            pgid = os.getpgid(process.pid)

            # まずSIGTERMで優しく終了を要求
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                # プロセスグループが既に終了している場合は無視
                return

            # 最大5秒待機
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 終了しない場合はSIGKILLで強制終了
                try:
                    os.killpg(pgid, signal.SIGKILL)
                    process.wait(timeout=2)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    pass

        except (ProcessLookupError, OSError):
            # プロセスが既に終了している場合は無視
            pass

    def extract_json(self, text: str) -> dict:
        """テキストからJSON部分を抽出"""
        # ```json ... ``` 形式
        json_block = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if json_block:
            return json.loads(json_block.group(1))

        # { ... } 形式
        json_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if json_obj:
            return json.loads(json_obj.group())

        raise ValueError("JSON not found in Claude Code output")

    def extract_markdown(self, text: str) -> str:
        """テキストからMarkdown部分を抽出"""
        # 既に # で始まる場合（クリーンなMarkdown）
        if text.strip().startswith('#'):
            return text.strip()

        # ```markdown ... ``` 形式
        md_block = re.search(r'```markdown\n(.*?)\n```', text, re.DOTALL)
        if md_block:
            return md_block.group(1).strip()

        # 最初の # 見出しを探して抽出
        heading_match = re.search(r'^(# .+)$', text, re.MULTILINE)
        if heading_match:
            return text[heading_match.start():].strip()

        # マークダウンブロックがない場合はそのまま返す
        return text.strip()
