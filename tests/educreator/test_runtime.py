import json
from pathlib import Path

import pytest

from educreator.accounts import Account
from educreator.runtime import AgentRequest, ClaudeCodeRuntime, CodexRuntime, collect
from educreator.runtime.base import ProviderMismatchError, run

FIX = Path(__file__).parent / "fixtures"


def _acc(provider="claude", name="personal-1", d="/tmp/x"):
    return Account(provider, name, Path(d), 3 if provider == "claude" else 1)


def test_claude_command_has_explicit_flags(tmp_path):
    req = AgentRequest(
        prompt="書いて",
        cwd=tmp_path,
        output_schema={"type": "object"},
        allowed_tools=("Read", "Bash(pytest:*)"),
        permission_mode="acceptEdits",
        max_turns=12,
    )
    cmd = ClaudeCodeRuntime().build_command(req)
    assert cmd[:3] == ["claude", "-p", "書いて"]
    for flag, val in [
        ("--output-format", "stream-json"),
        ("--permission-mode", "acceptEdits"),
        ("--max-turns", "12"),
        ("--allowedTools", "Read,Bash(pytest:*)"),
        ("--json-schema", '{"type": "object"}'),
    ]:
        assert cmd[cmd.index(flag) + 1] == val
    # stream-json は --print では --verbose が無いと動かない（2.1.319 で実測）
    assert "--verbose" in cmd


def test_claude_stream_parsed_into_common_events():
    lines = (FIX / "claude_stream.jsonl").read_text().splitlines()
    res = collect(ClaudeCodeRuntime(), _acc(), lines)
    assert res.ok
    assert res.structured == {"ok": True}
    calls = [e for e in res.events if e.kind == "tool_call"]
    results = [e for e in res.events if e.kind == "tool_result"]
    # StructuredOutput は内部の道具なので数えない
    assert [c.data["name"] for c in calls] == ["Bash"]
    assert results[0].data == {"id": "toolu_1", "content": "hello-edu", "is_error": False}
    assert res.usage_windows["seven_day"]["utilization"] == 0.04


def test_claude_failure_result_is_not_ok():
    lines = ['{"type":"result","subtype":"error_max_turns","is_error":true,"result":""}']
    assert not collect(ClaudeCodeRuntime(), _acc(), lines).ok


def test_nonzero_exit_is_not_ok_even_if_result_success():
    lines = (FIX / "claude_stream.jsonl").read_text().splitlines()
    assert not collect(ClaudeCodeRuntime(), _acc(), lines, returncode=1).ok


def test_non_json_lines_become_error_events():
    res = collect(ClaudeCodeRuntime(), _acc(), ["warning: something", ""])
    assert [e.kind for e in res.events] == ["error"]
    assert not res.ok


def test_codex_command_and_schema_file(tmp_path):
    rt = CodexRuntime(schema_dir=tmp_path / "s")
    cmd = rt.build_command(
        AgentRequest(
            prompt="読んで", cwd=tmp_path, output_schema={"type": "object"}, permission_mode="plan"
        )
    )
    assert cmd[:3] == ["codex", "exec", "--json"]
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    schema_path = Path(cmd[cmd.index("--output-schema") + 1])
    assert json.loads(schema_path.read_text()) == {"type": "object"}
    assert cmd[-1] == "読んで"


def test_codex_stream_parsed_into_same_shape():
    lines = (FIX / "codex_exec.jsonl").read_text().splitlines()
    res = collect(CodexRuntime(), _acc("chatgpt"), lines)
    assert res.ok and res.structured == {"ok": True}
    assert [e.kind for e in res.events if e.kind in ("tool_call", "tool_result")] == [
        "tool_call",
        "tool_result",
    ]
    tr = next(e for e in res.events if e.kind == "tool_result")
    assert tr.data["content"] == "hello-edu\n" and tr.data["is_error"] is False


def test_codex_turn_failed_is_not_ok():
    lines = [
        '{"type":"turn.failed","error":{"message":"usage limit"}}',
        '{"type":"turn.completed"}',
    ]
    res = collect(CodexRuntime(), _acc("chatgpt"), lines)
    assert not res.ok
    assert any(e.kind == "error" and e.data["message"] == "usage limit" for e in res.events)


def test_run_rejects_wrong_provider(tmp_path):
    with pytest.raises(ProviderMismatchError):
        run(CodexRuntime(), _acc("claude"), AgentRequest(prompt="x", cwd=tmp_path))


def test_run_uses_account_env_and_records_usage(tmp_path, monkeypatch):
    seen = {}

    class P:
        returncode = 0
        stderr = ""
        stdout = (FIX / "claude_stream.jsonl").read_text()

    def fake_run(cmd, cwd, env, **kw):
        seen["env"] = env
        return P()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setattr("educreator.runtime.base.subprocess.run", fake_run)
    acc = _acc(d=str(tmp_path / "cfg"))
    res = run(
        ClaudeCodeRuntime(),
        acc,
        AgentRequest(prompt="x", cwd=tmp_path),
        state_dir=tmp_path / "state",
    )
    assert res.ok
    assert seen["env"]["CLAUDE_CONFIG_DIR"] == str(tmp_path / "cfg")
    # API キーが残るとサブスクではなくキーで課金されるので外す
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    rec = (tmp_path / "state" / "usage" / "claude-personal-1.jsonl").read_text()
    assert '"seven_day"' in rec


def test_codex_real_failed_stream_is_not_ok_and_keeps_message():
    # codex-cli 0.167.1 の実機の出力（モデル不許可で失敗）。警告の item(type=error) は失敗に数えず、
    # トップレベルの error は message が直下に入っている
    lines = (FIX / "codex_exec_failed.jsonl").read_text().splitlines()
    res = collect(CodexRuntime(), _acc("chatgpt"), lines, returncode=1)
    assert not res.ok
    messages = [e.data["message"] for e in res.events if e.kind == "error"]
    assert messages and all("not supported when using Codex" in m for m in messages)


def test_run_does_not_inherit_stdin(tmp_path, monkeypatch):
    import subprocess

    seen = {}

    class P:
        returncode = 0
        stderr = ""
        stdout = (FIX / "claude_stream.jsonl").read_text()

    def fake_run(cmd, cwd, env, **kw):
        seen.update(kw)
        return P()

    monkeypatch.setattr("educreator.runtime.base.subprocess.run", fake_run)
    run(ClaudeCodeRuntime(), _acc(d=str(tmp_path / "cfg")), AgentRequest(prompt="x", cwd=tmp_path))
    assert seen["stdin"] is subprocess.DEVNULL


def test_codex_warning_error_item_does_not_fail_a_completed_turn():
    # 警告の item(type=error) が混ざっていても、turn.completed で終わり returncode=0 なら成功
    warning = '{"type":"item.completed","item":{"id":"w","type":"error","message":"warn"}}'
    lines = (FIX / "codex_exec.jsonl").read_text().splitlines()
    res = collect(CodexRuntime(), _acc("chatgpt"), [lines[0], warning, *lines[1:]], returncode=0)
    assert res.ok


def test_codex_schema_file_is_reused_not_accumulated(tmp_path):
    rt = CodexRuntime(schema_dir=tmp_path / "s")
    req = AgentRequest(prompt="x", cwd=tmp_path, output_schema={"type": "object"})
    first = rt.build_command(req)
    second = rt.build_command(req)
    assert first[first.index("--output-schema") + 1] == second[second.index("--output-schema") + 1]
    assert len(list((tmp_path / "s").iterdir())) == 1
    other = rt.build_command(
        AgentRequest(prompt="x", cwd=tmp_path, output_schema={"type": "array"})
    )
    assert other[other.index("--output-schema") + 1] != first[first.index("--output-schema") + 1]
    assert len(list((tmp_path / "s").iterdir())) == 2
