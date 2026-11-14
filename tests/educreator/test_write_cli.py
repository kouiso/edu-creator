"""`edu-creator write`（Step を 1 つ書く命令）。録画の再生で、LLM を呼ばずに確かめる。"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from e2e_task import CASSETTE, FIXTURE, VERIFY

from educreator import cli, write
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
