import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from educreator import skill
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


SKILLS = ("material-writing", "curriculum-quality-gate")


@pytest.fixture
def private_tmp(tmp_path, monkeypatch):
    # plugin と印の置き場（OS の一時フォルダの下）を、試験ごとの場所に向ける
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "os-tmp"))
    (tmp_path / "os-tmp").mkdir()
    return tmp_path


def _skill_req(tmp_path, skills=SKILLS):
    return AgentRequest(
        prompt="書いて",
        cwd=tmp_path,
        allowed_tools=("Read", "Skill"),
        permission_mode="acceptEdits",
        skills=skills,
        guarded_dir=tmp_path / "material",
    )


def _hook_entries(plugin):
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    found = {}
    for event, groups in hooks.items():
        for group in groups:
            for h in group["hooks"]:
                found[Path(h["args"][0]).name] = (event, group["matcher"], h)
    return found


def test_claude_command_with_skills(private_tmp):
    tmp_path = private_tmp
    cmd = ClaudeCodeRuntime(version_probe=lambda: "2.1.323").build_command(_skill_req(tmp_path))
    plugin = Path(cmd[cmd.index("--plugin-dir") + 1])
    assert plugin.name == "edu-creator"
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert "edu-creator:material-writing, edu-creator:curriculum-quality-gate" in prompt
    assert "Skill" in cmd[cmd.index("--allowedTools") + 1].split(",")
    assert cmd[cmd.index("--setting-sources") + 1] == "project,local"
    assert json.loads((plugin / ".claude-plugin" / "plugin.json").read_text()) == {
        "name": "edu-creator"
    }
    for name in SKILLS:
        assert (plugin / "skills" / name / "SKILL.md").is_file()
    assert (plugin / "skills" / "material-writing" / "reference" / "voice-spec.md").is_file()
    assert not (plugin / "skills" / "material-writing" / "hook").exists()
    assert (plugin.parent / "digest.txt").is_file()
    target = json.loads((plugin / "hooks" / "target.json").read_text(encoding="utf-8"))
    assert target["guarded_dir"] == os.path.realpath(tmp_path / "material")
    assert target["marker_dir"] == os.path.realpath(
        Path(tempfile.gettempdir()) / f"edu-creator-{os.getuid()}" / "marker"
    )
    entries = _hook_entries(plugin)
    assert set(entries) == {
        "material_writing_gate.py",
        "material_writing_reminder.py",
        "material_writing_marker.py",
    }
    for _event, _matcher, h in entries.values():
        assert h["type"] == "command"
        assert h["command"] == sys.executable
        assert len(h["args"]) == 2
        assert h["args"][0].startswith("${CLAUDE_PLUGIN_ROOT}/hooks/")
        assert h["args"][1] == "${CLAUDE_PLUGIN_ROOT}/hooks/target.json"
    ev, matcher, gate = entries["material_writing_gate.py"]
    assert (ev, matcher) == ("PreToolUse", "Write|Edit|NotebookEdit|Bash")
    assert gate["onFailure"] == "block"
    ev, matcher, rem = entries["material_writing_reminder.py"]
    assert (ev, matcher) == ("PreToolUse", "Write|Edit")
    ev, matcher, mark = entries["material_writing_marker.py"]
    assert (ev, matcher) == ("PostToolUse", "Skill")
    assert "onFailure" not in rem and "onFailure" not in mark


def test_claude_command_without_skills_only_adds_setting_sources(tmp_path):
    cmd = ClaudeCodeRuntime().build_command(AgentRequest(prompt="x", cwd=tmp_path))
    assert cmd == [
        "claude",
        "-p",
        "x",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "default",
        "--max-turns",
        "30",
        "--setting-sources",
        "project,local",
    ]


def test_claude_command_without_hook_skills_writes_no_hook_entries(private_tmp):
    req = _skill_req(private_tmp, skills=("course-mission",))
    cmd = ClaudeCodeRuntime(version_probe=lambda: "2.1.323").build_command(req)
    plugin = Path(cmd[cmd.index("--plugin-dir") + 1])
    assert (plugin / "skills" / "course-mission" / "SKILL.md").is_file()
    assert json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"] == {}


def test_stage_plugin_reuse(private_tmp):
    guarded = private_tmp / "material"
    p1 = skill.stage_plugin(SKILLS, guarded)
    p2 = skill.stage_plugin(SKILLS, guarded)
    assert p1 == p2
    digest = (p1.parent / "digest.txt").read_text(encoding="utf-8")
    assert digest == skill.tree_hash(p1, skill.PLUGIN_GLOBS)
    assert p1.parent.name == f"plugin-{digest[:16]}"
    # hook が作る __pycache__ は数に入らず、使い回される
    (p1 / "hooks" / "__pycache__").mkdir()
    (p1 / "hooks" / "__pycache__" / "x.pyc").write_bytes(b"x")
    assert skill.stage_plugin(SKILLS, guarded) == p1
    # 違う守るフォルダなら別の plugin
    assert skill.stage_plugin(SKILLS, private_tmp / "other") != p1

    # digest.txt が無いフォルダは、消さず名前も変えず、別の名前で作り直す
    (p1.parent / "digest.txt").unlink()
    p3 = skill.stage_plugin(SKILLS, guarded)
    assert p3 != p1 and p1.is_dir()
    assert p3.parent.name.startswith(p1.parent.name + ".")
    assert (p3.parent / "digest.txt").is_file()

    # 中身が合わない digest.txt も同じ
    (p1.parent / "digest.txt").write_text("0" * 64, encoding="utf-8")
    p4 = skill.stage_plugin(SKILLS, guarded)
    assert p4 not in (p1, p3) and p1.is_dir()
    assert (p1.parent / "digest.txt").read_text(encoding="utf-8") == "0" * 64


def test_stage_plugin_detects_tampered_files(private_tmp):
    guarded = private_tmp / "material"
    p1 = skill.stage_plugin(SKILLS, guarded)
    (p1 / "skills" / "material-writing" / "SKILL.md").write_text("TAMPERED-XYZ", encoding="utf-8")
    p2 = skill.stage_plugin(SKILLS, guarded)
    assert p2 != p1 and p1.is_dir()
    assert "TAMPERED-XYZ" not in (p2 / "skills" / "material-writing" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_claude_version_gate(private_tmp, tmp_path):
    req = _skill_req(private_tmp)
    old = ClaudeCodeRuntime(version_probe=lambda: "2.1.284", executable="my-claude")
    with pytest.raises(RuntimeError, match=r"2\.1\.284") as ei:
        old.build_command(req)
    assert "my-claude" in str(ei.value)
    assert "2.1.295" in str(ei.value)
    ClaudeCodeRuntime(version_probe=lambda: "2.1.295").build_command(req)
    ClaudeCodeRuntime(version_probe=lambda: "2.2.0").build_command(req)
    ClaudeCodeRuntime(version_probe=lambda: "3.0.1").build_command(req)

    def unknown():
        raise RuntimeError("版が分からない")

    with pytest.raises(RuntimeError, match="版が分からない"):
        ClaudeCodeRuntime(version_probe=unknown).build_command(req)

    calls = []

    def counting():
        calls.append(1)
        return "2.1.323"

    rt = ClaudeCodeRuntime(version_probe=counting)
    rt.build_command(AgentRequest(prompt="x", cwd=tmp_path))
    assert calls == []  # skill が空なら呼ばない
    rt.build_command(req)
    rt.build_command(req)
    assert calls == [1]  # 最初の 1 回だけ


def _fake_exe(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    p.chmod(0o755)
    return str(p)


def test_claude_version_parses_real_looking_output(tmp_path):
    ok = _fake_exe(tmp_path, "ok", 'echo "2.1.322 (Claude Code)"')
    assert skill.claude_version(ok) == "2.1.322"
    silent = _fake_exe(tmp_path, "silent", "true")
    with pytest.raises(RuntimeError):
        skill.claude_version(silent)
    failing = _fake_exe(tmp_path, "failing", 'echo "2.1.322"; exit 3')
    with pytest.raises(RuntimeError):
        skill.claude_version(failing)
    with pytest.raises(RuntimeError):
        skill.claude_version(str(tmp_path / "missing"))


def test_default_probe_uses_the_runtimes_own_executable(private_tmp):
    exe = _fake_exe(private_tmp, "old-claude", 'echo "2.1.200 (Claude Code)"')
    with pytest.raises(RuntimeError, match=r"2\.1\.200"):
        ClaudeCodeRuntime(executable=exe).build_command(_skill_req(private_tmp))


def test_source_digest_ignores_cache(tmp_path, monkeypatch):
    root = tmp_path / "sk"
    (root / "demo" / "hook").mkdir(parents=True)
    (root / "demo" / "reference").mkdir()
    (root / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n本文", encoding="utf-8")
    (root / "demo" / "hook" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "demo" / "reference" / "r.md").write_text("参照", encoding="utf-8")
    monkeypatch.setattr(skill, "SKILL_DIR", root)
    before = skill.source_digest(("demo",))
    (root / "demo" / "hook" / "__pycache__").mkdir()
    (root / "demo" / "hook" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0")
    (root / "demo" / ".DS_Store").write_bytes(b"\0")
    assert skill.source_digest(("demo",)) == before
    (root / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n本父", encoding="utf-8")
    assert skill.source_digest(("demo",)) != before


def test_source_digest_depends_on_order(tmp_path, monkeypatch):
    root = tmp_path / "sk"
    for n in ("a", "b"):
        (root / n).mkdir(parents=True)
        (root / n / "SKILL.md").write_text(n, encoding="utf-8")
    monkeypatch.setattr(skill, "SKILL_DIR", root)
    assert skill.source_digest(("a", "b")) != skill.source_digest(("b", "a"))


def test_tree_hash_ignores_symlinks_and_dirs(tmp_path):
    (tmp_path / "SKILL.md").write_text("x", encoding="utf-8")
    first = skill.tree_hash(tmp_path, ("SKILL.md", "reference/*.md"))
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "link.md").symlink_to(tmp_path / "SKILL.md")
    (tmp_path / "reference" / "dir.md").mkdir()
    assert skill.tree_hash(tmp_path, ("SKILL.md", "reference/*.md")) == first


def test_codex_prompt_embeds_skills(tmp_path):
    rt = CodexRuntime(schema_dir=tmp_path / "s")
    req = AgentRequest(prompt="元の依頼", cwd=tmp_path, skills=("material-writing",))
    cmd = rt.build_command(req)
    last = cmd[-1]
    assert last.startswith(
        "以下は、この作業で守る書き方の決まり（skill）。作業の前に全部読む。\n"
        "===== skill: material-writing =====\n"
    )
    assert last.endswith("\n===== ここまで =====\n\n元の依頼")
    assert last == skill.embed(("material-writing",)) + "\n\n元の依頼"
    assert "name: material-writing" not in last
    assert "----- material-writing/reference/voice-spec.md -----" in last
    assert "def main" not in last  # hook は埋め込まない
    assert "--ignore-user-config" in cmd
    plain = rt.build_command(AgentRequest(prompt="元の依頼", cwd=tmp_path))
    assert plain[-1] == "元の依頼"
    assert "--ignore-user-config" in plain


def test_embed_strips_frontmatter_and_lists_references_in_name_order(tmp_path, monkeypatch):
    root = tmp_path / "sk"
    (root / "demo" / "reference").mkdir(parents=True)
    (root / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\n本文1\n", encoding="utf-8"
    )
    (root / "demo" / "reference" / "b.md").write_text("B本文\n", encoding="utf-8")
    (root / "demo" / "reference" / "a.md").write_text("A本文\n", encoding="utf-8")
    monkeypatch.setattr(skill, "SKILL_DIR", root)
    text = skill.embed(("demo",))
    assert "description: d" not in text
    assert text.index("本文1") < text.index("A本文") < text.index("B本文")
    assert text.index("----- demo/reference/a.md -----") < text.index(
        "----- demo/reference/b.md -----"
    )


def test_private_dir_is_own_only_and_rejects_foreign_or_symlink(tmp_path, monkeypatch):
    from educreator.runtime.base import private_dir

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    d = private_dir()
    assert d == tmp_path / f"edu-creator-{os.getuid()}"
    assert d.stat().st_mode & 0o077 == 0
    shutil.rmtree(d)
    real = tmp_path / "real"
    real.mkdir()
    d.symlink_to(real, target_is_directory=True)
    with pytest.raises(PermissionError):
        private_dir()
    d.unlink()
    d.mkdir(mode=0o755)
    d.chmod(0o755)
    with pytest.raises(PermissionError):
        private_dir()
