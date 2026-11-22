"""`claude` CLI を子プロセスで呼ぶ口。

道具を使うエージェントのループは Claude Code 自身が持つ。ここではフラグを明示して呼び、
stream-json の出力を共通の Event に直すだけにする。出力の形は 2026-11-08 に Claude Code 2.1.319 で実測した
（tests/educreator/fixtures/claude_stream.jsonl）。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator

from educreator import skill
from educreator.runtime.base import AgentRequest, Event, json_lines

# StructuredOutput は --json-schema の答えを返すための内部の道具なので、道具の呼び出しとしては数えない
_INTERNAL_TOOLS = {"StructuredOutput"}


class ClaudeCodeRuntime:
    provider = "claude"

    def __init__(
        self, executable: str = "claude", version_probe: Callable[[], str] | None = None
    ) -> None:
        self.executable = executable
        # 版の文字列を返す関数。None なら、動かすのと同じ self.executable に `--version` を打つ
        self._version_probe = version_probe
        self._version_ok = False

    def _require_hook_support(self) -> None:
        """関門の hook の onFailure（2.1.295 から）が効く版だけ動かす。版が分からない時も動かさない。"""
        if self._version_ok:
            return
        probe = self._version_probe or (lambda: skill.claude_version(self.executable))
        version = probe()
        if skill.version_tuple(version) < skill.MIN_CLAUDE_VERSION:
            raise RuntimeError(
                "Claude Code 2.1.295 以降が要る（関門の hook の onFailure）。"
                f"{self.executable} は {version}"
            )
        self._version_ok = True

    def build_command(self, req: AgentRequest) -> list[str]:
        cmd = [
            self.executable,
            "-p",
            req.prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            req.permission_mode,
            "--max-turns",
            str(req.max_turns),
            # 使う人の設定のファイル（user）の hook と plugin を読ませない。
            # project と local は作業フォルダ（教材のリポジトリ）の持ち物なので残す
            "--setting-sources",
            "project,local",
        ]
        if req.skills:
            self._require_hook_support()
            plugin = skill.stage_plugin(req.skills, req.guarded_dir or req.cwd)
            names = ", ".join(f"{skill.PLUGIN_NAME}:{n}" for n in req.skills)
            cmd += [
                "--plugin-dir",
                str(plugin),
                "--append-system-prompt",
                f"教材のファイルに書く前に、Skill ツールで次の skill を順に読む: {names}",
            ]
        if req.allowed_tools:
            cmd += ["--allowedTools", ",".join(req.allowed_tools)]
        if req.output_schema is not None:
            cmd += ["--json-schema", json.dumps(req.output_schema, ensure_ascii=False)]
        if req.model:
            cmd += ["--model", req.model]
        return cmd

    def parse(self, lines: Iterable[str]) -> Iterator[Event]:
        internal_ids: set[str] = set()
        for obj in json_lines(lines):
            t = obj.get("type")
            if t == "__raw__":
                yield Event("error", {"message": obj["line"]})
            elif t == "system" and obj.get("subtype") == "init":
                # サブスクで動いているかの手がかり。API キーで動いていたら apiKeySource が none 以外になる
                yield Event(
                    "text",
                    {
                        "init": True,
                        "apiKeySource": obj.get("apiKeySource"),
                        "model": obj.get("model"),
                        "text": "",
                    },
                )
            elif t == "assistant":
                for c in obj.get("message", {}).get("content", []):
                    if c.get("type") == "text":
                        yield Event("text", {"text": c.get("text", "")})
                    elif c.get("type") == "tool_use":
                        if c.get("name") in _INTERNAL_TOOLS:
                            internal_ids.add(c.get("id", ""))
                            continue
                        yield Event(
                            "tool_call",
                            {"id": c.get("id"), "name": c.get("name"), "input": c.get("input", {})},
                        )
            elif t == "user":
                content = obj.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if (
                            c.get("type") == "tool_result"
                            and c.get("tool_use_id") not in internal_ids
                        ):
                            yield Event(
                                "tool_result",
                                {
                                    "id": c.get("tool_use_id"),
                                    "content": c.get("content"),
                                    "is_error": bool(c.get("is_error")),
                                },
                            )
            elif t == "rate_limit_event":
                info = obj.get("rate_limit_info", {})
                windows = info.get("unifiedWindows") or {}
                if windows:
                    yield Event("usage_window", windows)
            elif t == "result":
                yield Event(
                    "result",
                    {
                        "ok": obj.get("subtype") == "success" and not obj.get("is_error"),
                        "text": obj.get("result", ""),
                        "structured": obj.get("structured_output"),
                        "num_turns": obj.get("num_turns"),
                    },
                )
