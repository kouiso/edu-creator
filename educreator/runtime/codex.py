"""`codex exec` を子プロセスで呼ぶ口。

`codex exec --json` の JSONL（thread.started / item.started / item.completed / turn.completed / turn.failed / error）を
共通の Event に直す。2026-11-08 の時点でこの環境に codex CLI が無いため、出力の形は公開文書の記載に基づく
（tests/educreator/fixtures/codex_exec.jsonl）。実機で録画したら、そのカセットで置き換える。
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from educreator.runtime.base import AgentRequest, Event, json_lines


class CodexRuntime:
    provider = "chatgpt"

    def __init__(self, executable: str = "codex", schema_dir: Path | None = None) -> None:
        self.executable = executable
        self.schema_dir = schema_dir

    def build_command(self, req: AgentRequest) -> list[str]:
        cmd = [self.executable, "exec", "--json", "--cd", str(req.cwd)]
        # permission_mode の対応: 読むだけのレビューは read-only、書く作業は workspace-write
        sandbox = "read-only" if req.permission_mode in ("plan", "read-only") else "workspace-write"
        cmd += ["--sandbox", sandbox]
        if req.output_schema is not None:
            # --output-schema はファイルのパスを受け取る
            d = self.schema_dir or Path(tempfile.gettempdir())
            d.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", dir=d, delete=False, encoding="utf-8"
            ) as f:
                json.dump(req.output_schema, f, ensure_ascii=False)
            cmd += ["--output-schema", f.name]
        if req.model:
            cmd += ["--model", req.model]
        cmd.append(req.prompt)
        return cmd

    def parse(self, lines: Iterable[str]) -> Iterator[Event]:
        last_message = ""
        failed = False
        for obj in json_lines(lines):
            t = obj.get("type")
            if t == "__raw__":
                yield Event("error", {"message": obj["line"]})
            elif t in ("item.started", "item.completed"):
                item = obj.get("item", {})
                it = item.get("type")
                if it == "agent_message" and t == "item.completed":
                    last_message = item.get("text", "")
                    yield Event("text", {"text": last_message})
                elif it == "command_execution":
                    if t == "item.started":
                        yield Event(
                            "tool_call",
                            {
                                "id": item.get("id"),
                                "name": "shell",
                                "input": {"command": item.get("command")},
                            },
                        )
                    else:
                        yield Event(
                            "tool_result",
                            {
                                "id": item.get("id"),
                                "content": item.get("aggregated_output", ""),
                                "is_error": item.get("exit_code") not in (0, None),
                            },
                        )
                elif it == "file_change" and t == "item.completed":
                    yield Event(
                        "tool_call",
                        {
                            "id": item.get("id"),
                            "name": "file_change",
                            "input": {"changes": item.get("changes", [])},
                        },
                    )
                    yield Event(
                        "tool_result",
                        {
                            "id": item.get("id"),
                            "content": item.get("status"),
                            "is_error": item.get("status") == "failed",
                        },
                    )
            elif t in ("turn.failed", "error"):
                failed = True
                err = obj.get("error") or {}
                yield Event(
                    "error",
                    {
                        "message": err.get("message")
                        if isinstance(err, dict)
                        else obj.get("message")
                    },
                )
            elif t == "turn.completed":
                structured = None
                try:
                    structured = json.loads(last_message) if last_message else None
                except json.JSONDecodeError:
                    structured = None
                yield Event(
                    "result",
                    {
                        "ok": not failed,
                        "text": last_message,
                        "structured": structured,
                        "usage": obj.get("usage"),
                    },
                )
