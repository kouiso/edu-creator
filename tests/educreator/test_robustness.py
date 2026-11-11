"""壊れた入力や、1件の失敗で他を巻き込まないことの試験（レビューの指摘ごとに、直す前に落ちる形で書いた）。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from educreator import cassette
from educreator.accounts import Account, AccountError, load_accounts
from educreator.auth import status, status_report
from educreator.design import build
from educreator.judge import JudgeError, parse
from educreator.lessons import load_lessons
from educreator.runtime import AgentRequest, CodexRuntime
from educreator.runtime.base import RunResult
from educreator.spec import check_chapters, load_spec
from educreator.usage import latest_usage, record_usage

# ---- accounts / auth / usage ----


def _cfg(tmp_path: Path):
    p = tmp_path / "edu-creator.toml"
    p.write_text("", encoding="utf-8")
    return load_accounts(p, home=tmp_path)


def test_oauth_token_in_parent_env_is_not_shared_across_accounts(tmp_path):
    cfg = _cfg(tmp_path)
    base = {"CLAUDE_CODE_OAUTH_TOKEN": "shared-token", "PATH": "/bin"}
    p1, p2 = cfg.get("claude", "personal-1"), cfg.get("claude", "personal-2")
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in p1.env(base)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in p2.env(base)
    # アカウント専用の変数に入れた物だけが、そのアカウントの子プロセスに渡る
    own = {**base, p2.token_env(): "p2-token"}
    assert p2.env(own)["CLAUDE_CODE_OAUTH_TOKEN"] == "p2-token"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in p1.env(own)
    assert p2.token_env() == "EDU_CREATOR_TOKEN_CLAUDE_PERSONAL_2"


def test_config_dirs_pointing_to_same_place_are_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    body = f"""
[accounts.claude.a]
config_dir = "{real}"
[accounts.claude.b]
config_dir = "{tmp_path}/link"
"""
    p = tmp_path / "edu-creator.toml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(AccountError, match="同じ config_dir"):
        load_accounts(p, home=tmp_path)


def test_status_timeout_of_one_account_does_not_stop_the_report(tmp_path, monkeypatch):
    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: "/bin/" + exe)
    cfg = _cfg(tmp_path)
    for d in (".claude", ".claude-p2", ".claude-p3", ".claude-work", ".codex"):
        (tmp_path / d).mkdir()

    def runner(cmd, env, **kw):
        if env.get("CLAUDE_CONFIG_DIR", "").endswith(".claude-p2"):
            raise subprocess.TimeoutExpired(cmd, 30)
        return subprocess.CompletedProcess(cmd, 0, '{"loggedIn": true, "authMethod": "x"}', "")

    report = status_report(cfg, runner)
    assert "30秒以内に応答しなかった" in report
    assert "personal-3" in report and "team" in report


def test_status_nonzero_exit_is_not_logged_in_even_with_stale_json(tmp_path, monkeypatch):
    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: "/bin/" + exe)
    cfg = _cfg(tmp_path)
    (tmp_path / ".claude").mkdir()

    def runner(cmd, env, **kw):
        return subprocess.CompletedProcess(cmd, 1, '{"loggedIn": true, "authMethod": "x"}', "")

    assert status(cfg.get("claude", "personal-1"), runner).logged_in is False


def test_truncated_usage_line_is_skipped_and_last_good_record_is_used(tmp_path):
    a = Account("claude", "p", tmp_path / "c", 1)
    record_usage(tmp_path, a, {"five_hour": {"utilization": 0.4}}, now=1.0)
    usage_file = tmp_path / "usage" / "claude-p.jsonl"
    with usage_file.open("a", encoding="utf-8") as f:
        f.write('{"at": 2.0, "windows": {"five_h')
    assert latest_usage(tmp_path, a)["windows"]["five_hour"]["utilization"] == 0.4


# ---- lessons / spec ----


@pytest.mark.parametrize("body", ["", "lessons:\n", "- a\n", "other: 1\n"])
def test_lessons_ledger_must_have_a_lessons_list(tmp_path, body):
    p = tmp_path / "lessons.yaml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="lessons"):
        load_lessons(p)


def test_duplicate_yaml_keys_are_rejected(tmp_path):
    p = tmp_path / "course-spec.yaml"
    p.write_text("name: a\nname: b\ndays: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="重複"):
        load_spec(p)


def test_empty_chapters_still_report_unregistered_files(tmp_path):
    from educreator.spec import CourseSpec

    mat = tmp_path / "material"
    mat.mkdir()
    (mat / "day01_intro.md").write_text("# 題\n", encoding="utf-8")
    data = {
        "name": "s",
        "days": 1,
        "learner": {"description": "x", "prior_code_lines_max": 1, "os": ["macos"]},
        "budget": {
            "minutes": 1,
            "new_concepts": 1,
            "files": 1,
            "copy_lines": 1,
            "code_block_lines": 1,
        },
        "stack_profile": "flask",
        "app_repo": ".",
        "material_dir": "material",
        "distribution": {"formats": ["pdf"]},
        "chapters": [],
    }
    assert check_chapters(CourseSpec.model_validate(data), tmp_path) == [
        "day01_intro.md が chapters に無い"
    ]


# ---- judge ----


def _good_scores():
    from educreator.judge import DIMENSIONS

    return {k: {"score": 4, "evidence": "x"} for k, _ in DIMENSIONS}


@pytest.mark.parametrize("scores", [[], "x", None])
def test_parse_rejects_non_dict_scores_with_judge_error(scores):
    with pytest.raises(JudgeError):
        parse(1, "A", "p", {"scores": scores})


def test_parse_rejects_bool_score():
    s = _good_scores()
    s["clarity"]["score"] = True
    with pytest.raises(JudgeError):
        parse(1, "A", "p", {"scores": s})


def test_judge_day_wraps_timeout_and_missing_cli(tmp_path, monkeypatch):
    from educreator import judge as J

    md = tmp_path / "day01_x.md"
    md.write_text("# x\n", encoding="utf-8")
    acc = Account("claude", "p", tmp_path, 1)
    for exc in (subprocess.TimeoutExpired(["claude"], 900), FileNotFoundError("claude")):

        def boom(*a, _exc=exc, **k):
            raise _exc

        monkeypatch.setattr(J, "run", boom)
        with pytest.raises(JudgeError, match="Day01"):
            J.judge_day(md, 1, acc)


# ---- design ----


def test_malformed_design_access_is_a_value_error(tmp_path):
    for access in ({"routes": [{"roles": {}}]}, {"routes": [{"endpoint": "a", "roles": []}]}):
        with pytest.raises(ValueError, match=r"design\.access"):
            build([], access)


# ---- cassette / write ----


def test_snapshot_does_not_follow_symlink_out_of_the_tree(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    (tree / "link.txt").symlink_to(tmp_path / "secret.txt")
    (tree / "real.txt").write_text("ok", encoding="utf-8")
    assert list(cassette.snapshot(tree)) == ["real.txt"]
    assert cassette.changes(tree, {}) == {"real.txt": "ok"}


def test_save_with_relative_root_does_not_rewrite_every_period(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = RunResult(account="a", provider="claude", ok=True, text="ファイル a.b を直す。")
    out = tmp_path / "c.json"
    cassette.save(out, {"prompt": "x.y"}, res, {"a.b": "v1.2"}, Path("."))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["request"]["prompt"] == "x.y"
    assert "a.b" in data["files"] and data["files"]["a.b"] == "v1.2"
    assert data["result"]["text"] == "ファイル a.b を直す。"


def _recorded(tmp_path: Path, files: dict, before: dict | None = None) -> Path:
    res = RunResult(account="a", provider="claude", ok=True)
    p = tmp_path / "c.json"
    cassette.save(p, {"k": 1}, res, files, tmp_path / "tree", before)
    return p


def test_play_refuses_paths_that_escape_the_tree(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    p = _recorded(tmp_path, {"../outside.txt": "x"})
    with pytest.raises(cassette.CassetteMismatch, match="外"):
        cassette.play(p, tree, {"k": 1})
    assert not (tmp_path / "outside.txt").exists()


def test_play_refuses_when_the_start_state_differs(tmp_path):
    tree = tmp_path / "tree"
    (tree / "app").mkdir(parents=True)
    (tree / "app" / "a.py").write_text("old\n", encoding="utf-8")
    before = cassette.snapshot(tree)
    p = _recorded(tmp_path, {"app/a.py": "new\n"}, before)
    # 録った時と同じ開始なら再生できる
    cassette.play(p, tree, {"k": 1})
    assert (tree / "app" / "a.py").read_text(encoding="utf-8") == "new\n"
    # 開始のファイルが違うツリーには、古い録画を当てない
    (tree / "app" / "a.py").write_text("changed by someone\n", encoding="utf-8")
    with pytest.raises(cassette.CassetteMismatch, match="開始の状態"):
        cassette.play(p, tree, {"k": 1})


def test_request_key_includes_run_conditions(tmp_path):
    from educreator.write import _request_key

    base = AgentRequest(prompt="p", cwd=tmp_path)
    keys = [
        _request_key(base),
        _request_key(AgentRequest(prompt="p", cwd=tmp_path, permission_mode="plan")),
        _request_key(AgentRequest(prompt="p", cwd=tmp_path, max_turns=5)),
        _request_key(AgentRequest(prompt="p", cwd=tmp_path, model="m")),
    ]
    assert len({json.dumps(k, sort_keys=True) for k in keys}) == 4


# ---- codex schema ----


def test_codex_default_schema_dir_is_private_and_stale_file_is_rewritten(tmp_path, monkeypatch):
    import os

    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    req = AgentRequest(prompt="p", cwd=tmp_path, output_schema={"type": "object"})
    cmd = CodexRuntime().build_command(req)
    schema = Path(cmd[cmd.index("--output-schema") + 1])
    d = schema.parent
    assert d.name == f"edu-creator-{os.getuid()}" and (d.stat().st_mode & 0o077) == 0
    schema.write_text("tampered", encoding="utf-8")
    CodexRuntime().build_command(req)
    assert json.loads(schema.read_text(encoding="utf-8")) == {"type": "object"}


def test_codex_refuses_a_schema_dir_owned_by_someone_else_or_open(tmp_path, monkeypatch):
    import os

    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    d = tmp_path / f"edu-creator-{os.getuid()}"
    d.mkdir(mode=0o777)
    d.chmod(0o777)
    req = AgentRequest(prompt="p", cwd=tmp_path, output_schema={"type": "object"})
    with pytest.raises(PermissionError):
        CodexRuntime().build_command(req)


# ---- replay ----


def test_noisy_server_output_does_not_block_the_server(tmp_path):
    """出力を溜めたまま読まないと、パイプが満ちてサーバーが止まる。"""
    from educreator.profiles import QaConfig, StackProfile
    from educreator.replay import DaySource, replay_day

    server = (
        "import http.server, sys\n"
        "class H(http.server.BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        sys.stdout.write('x' * 300000 + '\\n'); sys.stdout.flush()\n"
        "        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')\n"
        "    def log_message(self, *a): pass\n"
        "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n"
    )
    day = tmp_path / "days" / "day01"
    day.mkdir(parents=True)
    (day / "server.py").write_text(server, encoding="utf-8")
    profile = StackProfile(
        name="t",
        language="python",
        filepath_comment={".py": "# filepath: {path}"},
        install=[sys.executable, "-c", "pass"],
        start=[sys.executable, "server.py", "{port}"],
        test=[],
        url="http://127.0.0.1:{port}",
        ready_path="/",
        qa=QaConfig(code_langs=["python"], real_prefixes=["app/"]),
    )
    r = replay_day(
        profile,
        DaySource("dirs", tmp_path / "days", "day{nn}"),
        1,
        paths={"/a": 200, "/b": 200, "/c": 200},
        ready_timeout=20,
    )
    assert r.ok, r.steps


def test_take_shots_turns_missing_node_into_failed_shots(tmp_path, monkeypatch):
    from educreator import replay

    def boom(*a, **k):
        raise FileNotFoundError("node")

    monkeypatch.setattr(replay.subprocess, "run", boom)
    r = replay.take_shots("http://x", [{"name": "a", "path": "/"}], None, tmp_path)
    assert r[0]["ok"] is False and "node" in r[0]["error"]
