"""`edu-creator write`（Step を 1 つ書く命令）。録画の再生で、LLM を呼ばずに確かめる。"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from e2e_task import CASSETTE, FIXTURE, VERIFY

from educreator import cli, skill, write
from educreator.runtime import RunResult

SPEC = """\
spec_version: 1
name: sample-todo
days: 1
learner:
  description: プログラミングをしたことがない人
  prior_code_lines_max: 0
  os: [macos]
budget:
  minutes: 120
  new_concepts: 3
  files: 5
  copy_lines: 200
  code_block_lines: 25
stack_profile: flask
app_repo: .
material_dir: material
naming: day
distribution:
  formats: [zip]
chapters:
  - day: 1
    title: やることを覚える
    file: day01_todo.md
"""
GOAL = "足したやることを、番号付きの1行ずつの文字列で返す関数 list_items を app/todo.py に足す"
CONTEXT = "関数・リスト・f 文字列・for（Day01 の Step 1 まで）"


@pytest.fixture
def tree(tmp_path):
    t = tmp_path / "tree"
    shutil.copytree(FIXTURE, t)
    (t / "course-spec.yaml").write_text(SPEC, encoding="utf-8")
    return t


def _argv(tree, goal=GOAL, *extra):
    return [
        "write",
        "--spec",
        str(tree / "course-spec.yaml"),
        "--day",
        "1",
        "--goal",
        goal,
        "--verify",
        VERIFY,
        "--context",
        CONTEXT,
        *extra,
    ]


def test_write_replays_the_cassette_and_the_code_runs(tree, capsys):
    assert cli.main(_argv(tree, GOAL, "--cassette", str(CASSETTE))) == 0
    out = subprocess.run(
        VERIFY, shell=True, cwd=tree, capture_output=True, text=True, check=True
    ).stdout
    assert out == "1. 買い物\n2. 洗濯\n"
    assert "changed_files" in capsys.readouterr().out


def test_write_with_a_changed_goal_does_not_replay_a_stale_cassette(tree):
    assert cli.main(_argv(tree, GOAL + "。", "--cassette", str(CASSETTE))) != 0
    # 古い録画の中身を作業ツリーに書き込まない
    assert "list_items" not in (tree / "app" / "todo.py").read_text(encoding="utf-8")


def test_write_rejects_a_day_the_spec_does_not_have(tree):
    argv = _argv(tree, GOAL, "--cassette", str(CASSETTE))
    argv[argv.index("--day") + 1] = "2"
    assert cli.main(argv) == 2


def test_write_rejects_a_missing_spec(tree):
    argv = _argv(tree, GOAL, "--cassette", str(CASSETTE))
    argv[argv.index("--spec") + 1] = str(tree / "none.yaml")
    assert cli.main(argv) == 2


def test_write_record_needs_a_known_account(tree, tmp_path):
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text('[accounts.claude.only]\nconfig_dir = "~/.claude-none"\n', encoding="utf-8")
    argv = _argv(tree, GOAL, "--record", "--account", "missing", "--config", str(cfg))
    assert cli.main(argv) == 2


def test_write_passes_account_and_request_to_write_step(tree, tmp_path, monkeypatch):
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text('[accounts.claude.acct-b]\nconfig_dir = "~/.claude-acct-b"\n', encoding="utf-8")
    seen = {}

    def fake(req, account, cassette_path=None, record=False, state_dir=None):
        seen.update(req=req, account=account, cassette=cassette_path, record=record)
        return RunResult(account="acct-b", provider="claude", ok=True, structured={"x": 1})

    monkeypatch.setattr(write, "write_step", fake)
    out = tmp_path / "rec.json"
    argv = _argv(tree, GOAL, "--record", "--account", "acct-b", "--config", str(cfg))
    assert cli.main([*argv, "--cassette", str(out), "--max-files", "2"]) == 0
    assert seen["account"].name == "acct-b" and seen["record"] is True and seen["cassette"] == out
    req = seen["req"]
    assert req.cwd == tree
    assert "material/day01_todo.md" in req.prompt and "ファイルは 2 つまで" in req.prompt
    # skills の無い教材は依頼文も道具の一覧も今まで通り（録画の鍵が変わらない）
    assert req.skills == () and "Skill" not in req.allowed_tools
    assert "- 教材:" not in req.prompt


def test_write_gives_skills_and_course_facts_when_the_spec_names_skills(
    tree, tmp_path, monkeypatch
):
    (tree / "course-spec.yaml").write_text(SPEC + "skills: [material-writing]\n", encoding="utf-8")
    seen = {}

    def fake(req, account, cassette_path=None, record=False, state_dir=None):
        seen["req"] = req
        return RunResult(account="x", provider="claude", ok=False)

    monkeypatch.setattr(write, "write_step", fake)
    cassette = tmp_path / "c.json"
    assert cli.main(_argv(tree, GOAL, "--cassette", str(cassette))) == 1
    req = seen["req"]
    assert req.skills == ("material-writing",) and "Skill" in req.allowed_tools
    assert "- 教材: sample-todo（全 1 日。配布: zip。技術: flask）" in req.prompt


def test_write_reports_an_old_claude_as_one_error_line_and_exit_2(
    tree, tmp_path, monkeypatch, capsys
):
    # 偽の claude（古い版）を差し替える。skill を使う spec なので、build_command の
    # _require_hook_support が RuntimeError を投げ、本物の経路を通る
    (tree / "course-spec.yaml").write_text(SPEC + "skills: [material-writing]\n", encoding="utf-8")
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text('[accounts.claude.acct-b]\nconfig_dir = "~/.claude-acct-b"\n', encoding="utf-8")
    monkeypatch.setattr(skill, "claude_version", lambda executable: "2.1.100")
    argv = _argv(
        tree,
        GOAL,
        "--record",
        "--account",
        "acct-b",
        "--config",
        str(cfg),
        "--cassette",
        str(tmp_path / "rec.json"),
    )
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("エラー: ") and err.count("\n") == 1
    assert "2.1.295" in err and "2.1.100" in err and "Traceback" not in err


def test_write_reports_a_denied_write_as_one_error_line_and_exit_2(
    tree, tmp_path, monkeypatch, capsys
):
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text('[accounts.claude.acct-b]\nconfig_dir = "~/.claude-acct-b"\n', encoding="utf-8")

    def denied(req, account, cassette_path=None, record=False, state_dir=None):
        raise PermissionError("書き込めない")

    monkeypatch.setattr(write, "write_step", denied)
    argv = _argv(tree, GOAL, "--record", "--account", "acct-b", "--config", str(cfg))
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert err == "エラー: 書き込めない\n"


def test_write_rejects_an_unknown_skill_name(tree, capsys):
    (tree / "course-spec.yaml").write_text(SPEC + "skills: [no-such-skill]\n", encoding="utf-8")
    assert cli.main(_argv(tree, GOAL)) == 2
    err = capsys.readouterr().err
    assert err.startswith("エラー: ") and "no-such-skill" in err


def _ok_result():
    return RunResult(account="a", provider="claude", ok=True, structured={"x": 1})


def _record_cfg(tmp_path):
    cfg = tmp_path / "edu-creator.toml"
    cfg.write_text('[accounts.claude.a]\nconfig_dir = "~/.claude-a"\n', encoding="utf-8")
    return cfg


def _record_argv(tree, tmp_path, *extra):
    return _argv(
        tree,
        GOAL,
        "--record",
        "--account",
        "a",
        "--config",
        str(_record_cfg(tmp_path)),
        "--cassette",
        str(tmp_path / "rec.json"),
        *extra,
    )


def test_write_repairs_a_failed_step_check_once(tree, tmp_path, monkeypatch, capsys):
    from educreator import checks

    calls = []

    def fake_write(req, account, cassette_path=None, record=False, state_dir=None):
        calls.append(req)
        return _ok_result()

    # 1 回目だけ step-length を落とす。直しの依頼に検査 ID と出力が乗る
    results = iter([1] + [0] * 10)
    monkeypatch.setattr(write, "write_step", fake_write)
    monkeypatch.setattr(
        checks,
        "run_check",
        lambda c, target, config: checks.CheckResult(c, next(results), "NG の行"),
    )
    assert cli.main(_record_argv(tree, tmp_path)) == 0
    assert len(calls) == 2
    assert "今回は新しい Step を足さず" in calls[1].prompt
    assert "step-length" in calls[1].prompt and "NG の行" in calls[1].prompt
    assert "今から Step を1つだけ書きます" in calls[0].prompt


def test_write_stops_after_two_repairs_with_the_check_output(tree, tmp_path, monkeypatch, capsys):
    from educreator import checks

    calls = []
    monkeypatch.setattr(
        write, "write_step", lambda req, account, *a, **kw: calls.append(req) or _ok_result()
    )
    monkeypatch.setattr(
        checks,
        "run_check",
        lambda c, target, config: checks.CheckResult(c, 1, "ずっと NG"),
    )
    assert cli.main(_record_argv(tree, tmp_path)) == 1
    # 初回の 1 回 + 直し 2 回で止める
    assert len(calls) == 3
    assert "ずっと NG" in capsys.readouterr().err


def test_write_runs_five_step_checks_not_all(tree, tmp_path, monkeypatch):
    from educreator import checks

    seen = []
    monkeypatch.setattr(write, "write_step", lambda req, account, *a, **kw: _ok_result())
    monkeypatch.setattr(
        checks,
        "run_check",
        lambda c, target, config: seen.append(c.id) or checks.CheckResult(c, 0, ""),
    )
    assert cli.main(_record_argv(tree, tmp_path)) == 0
    assert sorted(seen) == sorted(
        ("step-length", "code-completeness", "anchor", "setext-heading", "forward-refs")
    )


def test_write_last_step_runs_all_checks(tree, tmp_path, monkeypatch):
    from educreator import checks

    seen = []
    monkeypatch.setattr(write, "write_step", lambda req, account, *a, **kw: _ok_result())
    monkeypatch.setattr(
        checks,
        "run_check",
        lambda c, target, config: seen.append(c.id) or checks.CheckResult(c, 0, ""),
    )
    assert cli.main(_record_argv(tree, tmp_path, "--last-step")) == 0
    assert len(seen) == len(checks.CHECKS) == 22


def test_write_replay_cannot_repair_and_reports_the_failure(tree, monkeypatch, capsys):
    from educreator import checks

    calls = []
    monkeypatch.setattr(
        write, "write_step", lambda req, account, *a, **kw: calls.append(req) or _ok_result()
    )
    monkeypatch.setattr(
        checks,
        "run_check",
        lambda c, target, config: checks.CheckResult(c, 1, "NG"),
    )
    # 録画の再生（account が無い）は直しを呼ばず、落ちた検査を出して 1 で終わる
    assert cli.main(_argv(tree, GOAL, "--cassette", str(CASSETTE))) == 1
    assert len(calls) == 1
    assert "NG" in capsys.readouterr().err
