import subprocess
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task


def validate_and_fix_quality(
    output_file: Path,
    scribe_agent: Agent,
    task_outline: Task,
    task_research: Task,
    chapter: dict[str, Any],
    repo_root: Path,
    max_attempts: int = 3,
) -> tuple[bool, int, str]:
    """
    Validate generated tutorial against quality rules and auto-fix if needed.

    Returns:
        tuple: (passed: bool, attempts: int, validation_log: str)
    """
    import subprocess

    log_messages = []

    # 品質チェックスクリプトの場所はプロジェクト構成によって異なる可能性があるため、
    # 複数候補から実在するものを探索する（見つからない場合は合格扱いにしない）。
    check_script_candidates = [
        repo_root / "edu-creator" / "script" / "check_quality.sh",
        # 旧パス互換（過去の表記揺れ対策）
        repo_root / "edu-creator" / "scripts" / "check_quality.sh",
        repo_root / "scripts" / "check_quality.sh",
    ]

    check_script: Path | None = next(
        (candidate for candidate in check_script_candidates if candidate.exists()),
        None,
    )

    if check_script is None:
        log_msg = (
            "⚠️  Quality check script not found. Tried:\n"
            + "\n".join(f"- {candidate}" for candidate in check_script_candidates)
        )
        print(log_msg)
        log_messages.append(log_msg)
        return False, 0, "\n".join(log_messages)

    for attempt in range(1, max_attempts + 1):
        log_msg = f"\n🔍 Quality Check (Attempt {attempt}/{max_attempts})..."
        print(log_msg)
        log_messages.append(log_msg)

        try:
            result = subprocess.run(
                ["bash", str(check_script), str(output_file)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=repo_root,
            )

            check_output = result.stdout + result.stderr
            log_messages.append(check_output)

            # Check if all tests passed
            if result.returncode == 0 and "PASS" in check_output and "FAIL" not in check_output:
                log_msg = f"✅ Quality check PASSED on attempt {attempt}!"
                print(log_msg)
                log_messages.append(log_msg)
                return True, attempt, "\n".join(log_messages)

            # If last attempt, return without fixing
            if attempt == max_attempts:
                log_msg = f"\n⚠️  Quality check still failing after {max_attempts} attempts."
                log_msg += f"\nPlease review manually:\n{check_output[:500]}"
                print(log_msg)
                log_messages.append(log_msg)
                return False, attempt, "\n".join(log_messages)

            # Parse failures and create fix prompt
            log_msg = f"\n🔧 Attempting to fix quality issues (attempt {attempt}/{max_attempts})..."
            print(log_msg)
            log_messages.append(log_msg)

            # Create fix prompt for Scribe
            fix_prompt = f"""
【品質チェック結果の修正】

以下の品質チェックスクリプトの出力から、問題を特定し、修正してください：

```
{check_output}
```

修正内容：
1. FAIL している各項目を特定する
2. その項目を修正する
3. 修正後、新しいMarkdownファイルを完全に再生成する

元のファイルはそのままに、同じファイルパスで新しいコンテンツを上書きしてください。

【重要】修正の際は、以下を必ず守ってください：
- 全ての品質ルール（禁止ワード、コード長、ビジュアル要素等）を満たす
- 日本語です・ます調を維持
- 技術的な正確性を失わない

再生成後、自動的に品質チェックが実行されます。
"""

            # Get current content
            current_content = output_file.read_text(encoding="utf-8")

            # Create a task to fix the issues
            fix_task = Task(
                description=fix_prompt,
                expected_output="修正されたMarkdownチュートリアル",
                agent=scribe_agent,
                context=[task_outline, task_research],
            )

            # Execute fix task
            crew = Crew(
                agents=[scribe_agent],
                tasks=[fix_task],
                process=Process.sequential,
                verbose=False,
            )

            fix_result = crew.kickoff()

            # Save fixed content
            fixed_content = str(fix_result)
            if fixed_content and len(fixed_content) > 100:
                output_file.write_text(fixed_content, encoding="utf-8")
                log_msg = f"✏️  Content updated. Re-checking quality..."
                print(log_msg)
                log_messages.append(log_msg)
            else:
                log_msg = f"⚠️  Fix attempt {attempt} produced invalid output"
                print(log_msg)
                log_messages.append(log_msg)

        except subprocess.TimeoutExpired:
            log_msg = "⚠️  Quality check timed out"
            print(log_msg)
            log_messages.append(log_msg)
            return False, attempt, "\n".join(log_messages)
        except Exception as e:
            log_msg = f"⚠️  Error during quality check: {e}"
            print(log_msg)
            log_messages.append(log_msg)
            return False, attempt, "\n".join(log_messages)

    return False, max_attempts, "\n".join(log_messages)
