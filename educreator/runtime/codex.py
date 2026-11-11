"""`codex exec` を子プロセスで呼ぶ口。

`codex exec --json` の JSONL（thread.started / item.started / item.completed / turn.completed / turn.failed / error）を
共通の Event に直す。成功の流れ（tests/educreator/fixtures/codex_exec.jsonl）は公開文書の記載に基づく。
失敗の流れは codex-cli 0.167.1 の実機の出力を録画した（codex_exec_failed.jsonl）。
実機のログインが切れていて成功の流れは録画できていない。録画できたらそのカセットで置き換える。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from educreator.runtime.base import AgentRequest, Event, json_lines


def _private_schema_dir() -> Path:
    """既定のスキーマ置き場。共有の一時フォルダ直下ではなく、自分だけが入れるフォルダにする。"""
    d = Path(tempfile.gettempdir()) / f"edu-creator-{os.getuid()}"
    d.mkdir(mode=0o700, exist_ok=True)
    st = d.lstat()
    # 別のユーザーが先に作った物や symlink は使わない（同名のスキーマを仕込まれると、依頼と違う形を Codex に渡してしまう）
    if d.is_symlink() or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise PermissionError(
            f"{d} が自分専用でない（所有者か権限が違う）。schema_dir を指定してほしい"
        )
    return d


class CodexRuntime:
    """`codex exec` の口。

    AgentRequest のうち Codex の CLI が受けるのは permission_mode（--sandbox）と model（--model）だけ。
    allowed_tools と max_turns に当たる指定が `codex exec` に無いので、渡されても反映されない。
    書き込みの範囲はサンドボックスで縛り、道具の絞り込みと turn 数の上限は Claude の口でだけ効く。
    """

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
            if self.schema_dir is not None:
                d = self.schema_dir
                d.mkdir(parents=True, exist_ok=True)
            else:
                d = _private_schema_dir()
            # 名前を内容のハッシュにして使い回す。judge を Day の数だけ回してもファイルは増えない
            body = json.dumps(req.output_schema, ensure_ascii=False, sort_keys=True)
            path = d / f"schema-{hashlib.sha256(body.encode()).hexdigest()[:16]}.json"
            # 同名で中身が違う物（壊れた・書き換えられた）は使い回さず、書き直す
            if not path.is_file() or path.read_text(encoding="utf-8") != body:
                tmp = path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(body, encoding="utf-8")
                tmp.replace(path)
            cmd += ["--output-schema", str(path)]
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
                # turn.failed は error.message、トップレベルの error は message に入っている（実機で確認）
                err = obj.get("error")
                message = err.get("message") if isinstance(err, dict) else obj.get("message")
                yield Event("error", {"message": message or obj.get("message")})
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
