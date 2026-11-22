"""skill の hook（関門・案内・印）の試験。hook をファイルとして子プロセスで打って、判定の 1〜5 を 1 つずつ確かめる。

標準の部品だけで動くので、どれも skip しない。
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = ROOT / "educreator" / "agent-skill" / "material-writing" / "hook"
GATE = HOOK_DIR / "material_writing_gate.py"
REMINDER = HOOK_DIR / "material_writing_reminder.py"
MARKER = HOOK_DIR / "material_writing_marker.py"


@pytest.fixture
def world(tmp_path):
    tree = tmp_path / "tree"
    guarded = tree / "material"
    guarded.mkdir(parents=True)
    (guarded / "day01_todo.md").write_text("# Day01\n", encoding="utf-8")
    marker_dir = tmp_path / "marker"
    target = tmp_path / "target.json"
    target.write_text(
        json.dumps({"guarded_dir": str(guarded), "marker_dir": str(marker_dir)}),
        encoding="utf-8",
    )
    return {
        "tree": tree,
        "guarded": guarded,
        "marker_dir": marker_dir,
        "target": target,
    }


def _fire(hook, target, payload, raw=None):
    stdin = raw if raw is not None else json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run(
        [sys.executable, str(hook), str(target)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    out = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, out, proc.stderr


def _bash(world, command, cwd=None, session="s1"):
    return {
        "session_id": session,
        "cwd": str(cwd or world["tree"]),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def _write(world, path, session="s1", tool="Write"):
    return {
        "session_id": session,
        "cwd": str(world["tree"]),
        "tool_name": tool,
        "tool_input": {"file_path": str(path)},
    }


def _is_deny(result):
    rc, out, _ = result
    assert rc == 0
    assert out is not None
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert spec["permissionDecision"] == "deny"
    assert spec["permissionDecisionReason"]
    return spec["permissionDecisionReason"]


def _is_pass(result):
    rc, out, _ = result
    assert rc == 0
    assert out is None


def _place_marker(world, session="s1"):
    world["marker_dir"].mkdir(parents=True, exist_ok=True)
    (world["marker_dir"] / session).write_text("", encoding="utf-8")


def test_gate_denies_write_to_guarded_md_without_marker(world):
    payload = _write(world, world["guarded"] / "day01_new.md")
    reason = _is_deny(_fire(GATE, world["target"], payload))
    assert "edu-creator:material-writing" in reason
    assert "同じ操作をやり直" in reason


@pytest.mark.parametrize("tool", ["Edit", "NotebookEdit"])
def test_gate_denies_other_write_tools(world, tool):
    payload = _write(world, world["guarded"] / "day01_todo.md", tool=tool)
    _is_deny(_fire(GATE, world["target"], payload))


def test_gate_passes_non_md_and_outside_paths(world):
    _is_pass(_fire(GATE, world["target"], _write(world, world["guarded"] / "memo.txt")))
    _is_pass(_fire(GATE, world["target"], _write(world, world["tree"] / "app" / "x.md")))
    _is_pass(_fire(GATE, world["target"], _write(world, world["tree"] / "app" / "todo.py")))


def test_gate_passes_with_marker(world):
    _place_marker(world)
    payload = _write(world, world["guarded"] / "day01_new.md")
    _is_pass(_fire(GATE, world["target"], payload))


def test_gate_marker_is_per_session(world):
    _place_marker(world, "other")
    _is_deny(_fire(GATE, world["target"], _write(world, world["guarded"] / "a.md")))


@pytest.mark.parametrize(
    "command",
    [
        "python3 x.py material/day01_todo.md",
        "printf x>>material/day01_todo.md",
        "python3 x.py --out=material/day01_todo.md",
        "git checkout -- material/day01_todo.md",
        "sort -o material/day01_todo.md material/day01_todo.md",
        "sort --output=material/day01_todo.md x",
        "uniq x material/day01_todo.md",
        "cat material/day01_todo.md | tee x",
        "cat material/day01_todo.md > copy.txt",
        'echo "abc material/day01_todo.md',
    ],
)
def test_gate_denies_bash_touching_guarded_without_marker(world, command):
    _is_deny(_fire(GATE, world["target"], _bash(world, command)))


def test_gate_denies_cd_into_guarded_and_find_delete(world):
    guarded = str(world["guarded"])
    _is_deny(_fire(GATE, world["target"], _bash(world, f"cd {guarded}")))
    _is_deny(_fire(GATE, world["target"], _bash(world, f"find {guarded} -delete")))


def test_gate_resolves_relative_paths_from_input_cwd(world):
    side = world["tree"] / "other"
    side.mkdir()
    payload = _bash(world, "echo x > ../material/day01_x.md", cwd=side)
    _is_deny(_fire(GATE, world["target"], payload))
    # cwd が守るフォルダの外で、相対のパスも外を指すなら通す
    _is_pass(_fire(GATE, world["target"], _bash(world, "echo x > notes.txt", cwd=side)))


def test_gate_passes_plain_read_only_cat(world):
    _is_pass(_fire(GATE, world["target"], _bash(world, "cat material/day01_todo.md")))
    _is_pass(_fire(GATE, world["target"], _bash(world, "grep Day material/day01_todo.md")))


def test_gate_passes_bash_not_touching_guarded(world):
    _is_pass(_fire(GATE, world["target"], _bash(world, "python3 app/todo.py")))
    _is_pass(_fire(GATE, world["target"], _bash(world, "ls app")))


def test_gate_passes_bash_touching_guarded_with_marker(world):
    _place_marker(world)
    _is_pass(_fire(GATE, world["target"], _bash(world, "python3 x.py material/day01_todo.md")))


def test_gate_ignores_other_tools(world):
    payload = {"session_id": "s1", "cwd": str(world["tree"]), "tool_name": "Read", "tool_input": {}}
    _is_pass(_fire(GATE, world["target"], payload))


def test_gate_symlinked_guarded_dir_gives_same_verdict(world, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(world["guarded"], target_is_directory=True)
    world["target"].write_text(
        json.dumps({"guarded_dir": str(link), "marker_dir": str(world["marker_dir"])}),
        encoding="utf-8",
    )
    _is_deny(_fire(GATE, world["target"], _write(world, world["guarded"] / "day01_new.md")))
    _is_deny(_fire(GATE, world["target"], _write(world, link / "day01_new.md")))
    _is_deny(_fire(GATE, world["target"], _bash(world, "python3 x.py material/day01_todo.md")))


def test_gate_denies_when_input_is_broken(world):
    _is_deny(_fire(GATE, world["target"], None, raw="{not json"))
    _is_deny(_fire(GATE, world["target"], None, raw=""))


def test_gate_denies_when_cwd_missing(world):
    payload = _write(world, world["guarded"] / "a.md")
    del payload["cwd"]
    reason = _is_deny(_fire(GATE, world["target"], payload))
    assert "入力を読めなかった" in reason


def test_gate_denies_when_target_json_unreadable(world, tmp_path):
    payload = _write(world, world["guarded"] / "a.md")
    _is_deny(_fire(GATE, tmp_path / "nope.json", payload))


def test_gate_denies_targeted_call_without_session_id(world):
    payload = _write(world, world["guarded"] / "a.md")
    del payload["session_id"]
    _is_deny(_fire(GATE, world["target"], payload))


def test_gate_rejects_unsafe_session_id(world):
    # 印のパスを組み立てる値なので、パスの区切りを含む番号は印があるものとして扱わない
    _place_marker(world, "x")
    payload = _write(world, world["guarded"] / "a.md", session="../marker/x")
    _is_deny(_fire(GATE, world["target"], payload))


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_safely_turns_any_exception_into_exit_2(capsys):
    gate = _load(GATE)

    def boom():
        raise ValueError("中で壊れた")

    assert gate.run_safely(boom) == 2
    err = capsys.readouterr().err
    assert "edu-creator の関門の hook が失敗したので止めた" in err
    assert "ValueError" in err
    assert "中で壊れた" in err
    assert gate.run_safely(lambda: 0) == 0


def test_run_safely_also_catches_base_exception(capsys):
    gate = _load(GATE)

    def interrupted():
        raise KeyboardInterrupt

    assert gate.run_safely(interrupted) == 2
    assert "KeyboardInterrupt" in capsys.readouterr().err


def test_gate_main_entry_goes_through_run_safely():
    text = GATE.read_text(encoding="utf-8")
    assert "sys.exit(run_safely(main))" in text


def test_marker_hook_creates_marker(world):
    payload = {
        "session_id": "s9",
        "cwd": str(world["tree"]),
        "tool_name": "Skill",
        "tool_input": {"skill": "edu-creator:material-writing"},
    }
    rc, out, _ = _fire(MARKER, world["target"], payload)
    assert rc == 0 and out is None
    assert (world["marker_dir"] / "s9").is_file()
    # 印ができたので、同じセッションの関門は通す
    _is_pass(_fire(GATE, world["target"], _write(world, world["guarded"] / "a.md", session="s9")))


def test_marker_hook_falls_back_to_command_and_ignores_other_skills(world):
    other = {
        "session_id": "s8",
        "cwd": str(world["tree"]),
        "tool_name": "Skill",
        "tool_input": {"skill": "edu-creator:course-mission"},
    }
    assert _fire(MARKER, world["target"], other)[0] == 0
    assert not (world["marker_dir"] / "s8").exists()
    via_command = {**other, "tool_input": {"command": "material-writing"}}
    assert _fire(MARKER, world["target"], via_command)[0] == 0
    assert (world["marker_dir"] / "s8").is_file()


def test_marker_hook_reports_when_it_cannot_write(world, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")
    world["target"].write_text(
        json.dumps({"guarded_dir": str(world["guarded"]), "marker_dir": str(blocker / "m")}),
        encoding="utf-8",
    )
    payload = {
        "session_id": "s7",
        "cwd": str(world["tree"]),
        "tool_name": "Skill",
        "tool_input": {"skill": "edu-creator:material-writing"},
    }
    rc, _, err = _fire(MARKER, world["target"], payload)
    assert rc == 0
    assert err.strip()


def test_reminder_fires_only_for_guarded_md(world):
    rc, out, _ = _fire(REMINDER, world["target"], _write(world, world["guarded"] / "a.md"))
    assert rc == 0 and out is not None
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert "edu-creator:material-writing" in spec["additionalContext"]
    assert "6" in spec["additionalContext"]
    _is_pass(_fire(REMINDER, world["target"], _write(world, world["tree"] / "app" / "a.md")))
    _is_pass(_fire(REMINDER, world["target"], _write(world, world["guarded"] / "a.txt")))


def test_reminder_never_blocks_on_broken_input(world):
    rc, out, _ = _fire(REMINDER, world["target"], None, raw="{not json")
    assert rc == 0 and out is None
