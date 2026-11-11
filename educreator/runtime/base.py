"""実行の口の共通の形。

Claude Code と Codex は出力の形が違うが、stage・write・gate が口の違いを知らなくて済むように、
どちらも同じ Event の列と RunResult を返す。録画（カセット）もこの形で保存する（E-8）。
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from educreator.accounts import Account

EventKind = Literal["text", "tool_call", "tool_result", "usage_window", "result", "error"]


@dataclass(frozen=True)
class Event:
    kind: EventKind
    data: dict[str, Any]


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    cwd: Path
    output_schema: dict[str, Any] | None = None
    allowed_tools: tuple[str, ...] = ()
    permission_mode: str = "default"
    max_turns: int = 30
    model: str | None = None


@dataclass
class RunResult:
    account: str
    provider: str
    ok: bool
    text: str = ""
    structured: Any = None
    events: list[Event] = field(default_factory=list)
    usage_windows: dict[str, Any] = field(default_factory=dict)
    returncode: int = 0
    stderr: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False)


class Runtime(Protocol):
    provider: str

    def build_command(self, req: AgentRequest) -> list[str]: ...

    def parse(self, lines: Iterable[str]) -> Iterator[Event]: ...


class ProviderMismatchError(Exception):
    pass


def run(
    runtime: Runtime,
    account: Account,
    req: AgentRequest,
    timeout: float | None = None,
    state_dir: Path | None = None,
) -> RunResult:
    """CLI を子プロセスで1回動かし、共通の形にして返す。

    state_dir を渡すと、CLI が出した使用量の窓をアカウントごとに記録する（auth status で見る。U-12 の測定にも使う）。
    """
    if account.provider != runtime.provider:
        raise ProviderMismatchError(
            f"{runtime.provider} の口に {account.provider} のアカウントは使えない"
        )
    cmd = runtime.build_command(req)
    proc = subprocess.run(
        cmd,
        cwd=req.cwd,
        env=account.env(),
        # 標準入力を引き継ぐと codex exec が「追加入力」を待って止まりうる。プロンプトは引数で渡す
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    res = collect(runtime, account, proc.stdout.splitlines(), proc.returncode, proc.stderr)
    if state_dir is not None and res.usage_windows:
        from educreator.usage import record_usage

        record_usage(state_dir, account, res.usage_windows)
    return res


def collect(
    runtime: Runtime, account: Account, lines: Iterable[str], returncode: int = 0, stderr: str = ""
) -> RunResult:
    res = RunResult(
        account=account.name,
        provider=account.provider,
        ok=False,
        returncode=returncode,
        stderr=stderr,
    )
    for ev in runtime.parse(lines):
        res.events.append(ev)
        if ev.kind == "usage_window":
            res.usage_windows.update(ev.data)
        elif ev.kind == "result":
            res.ok = bool(ev.data.get("ok")) and returncode == 0
            res.text = ev.data.get("text", "")
            res.structured = ev.data.get("structured")
        elif ev.kind == "text" and not res.text:
            res.text = ev.data.get("text", "")
    return res


def json_lines(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """JSON でない行（CLI の警告など）は error の材料として残しつつ読み飛ばす。"""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            yield {"type": "__raw__", "line": line}
            continue
        if isinstance(obj, dict):
            yield obj
