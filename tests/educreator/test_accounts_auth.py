import subprocess
from pathlib import Path

import pytest

from educreator.accounts import AccountError, load_accounts
from educreator.auth import status, status_report
from educreator.usage import format_windows, latest_usage, record_usage


def test_defaults_are_four_claude_and_one_chatgpt(tmp_path):
    cfg = load_accounts(path=_write(tmp_path, ""), home=tmp_path)
    claude = [a.name for a in cfg.of("claude")]
    assert claude == ["personal-1", "personal-2", "personal-3", "team"]
    assert [a.name for a in cfg.of("chatgpt")] == ["personal-1"]
    assert cfg.get("claude", "team").config_dir == tmp_path / ".claude-work"
    assert cfg.get("chatgpt", "personal-1").max_parallel == 1


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "edu-creator.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_custom_accounts_and_env(tmp_path):
    p = _write(
        tmp_path,
        """
[state]
dir = "~/st"
[accounts.claude.solo]
config_dir = "~/c1"
max_parallel = 2
[accounts.chatgpt.main]
config_dir = "~/cx"
""",
    )
    cfg = load_accounts(p, home=tmp_path)
    a = cfg.get("claude", "solo")
    assert a.max_parallel == 2 and cfg.state_dir == tmp_path / "st"
    env = a.env({"OPENAI_API_KEY": "k", "PATH": "/bin"})
    assert env == {"PATH": "/bin", "CLAUDE_CONFIG_DIR": str(tmp_path / "c1")}
    assert cfg.get("chatgpt", "main").env({})["CODEX_HOME"] == str(tmp_path / "cx")


@pytest.mark.parametrize(
    "body,msg",
    [
        (
            "[accounts.claude.a]\nconfig_dir='~/x'\n[accounts.claude.b]\nconfig_dir='~/x'\n",
            "同じ config_dir",
        ),
        ("[accounts.chatgpt.a]\nconfig_dir='~/x'\nmax_parallel=2\n", "max_parallel は1"),
        ("[accounts.gemini.a]\nconfig_dir='~/x'\n", "provider"),
        ("[accounts.claude.a]\nmax_parallel=1\n", "config_dir が無い"),
    ],
)
def test_invalid_configs_fail_loudly(tmp_path, body, msg):
    with pytest.raises(AccountError, match=msg):
        load_accounts(_write(tmp_path, body), home=tmp_path)


def test_unknown_account_lists_available(tmp_path):
    cfg = load_accounts(_write(tmp_path, ""), home=tmp_path)
    with pytest.raises(AccountError, match="personal-1, personal-2, personal-3, team"):
        cfg.get("claude", "personal-9")


def test_status_reads_cli_json_per_account(tmp_path, monkeypatch):
    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: "/bin/" + exe)
    cfg = load_accounts(_write(tmp_path, ""), home=tmp_path)
    (tmp_path / ".claude").mkdir()
    calls = []

    def runner(cmd, env, **kw):
        calls.append(env.get("CLAUDE_CONFIG_DIR"))
        return subprocess.CompletedProcess(
            cmd, 0, stdout='{"loggedIn": true, "authMethod": "claude.ai"}', stderr=""
        )

    s = status(cfg.get("claude", "personal-1"), runner)
    assert s.logged_in is True and s.method == "claude.ai"
    assert calls == [str(tmp_path / ".claude")]
    # 置き場が無いアカウントは CLI を呼ばずに未ログイン
    s2 = status(cfg.get("claude", "personal-2"), runner)
    assert s2.logged_in is False and len(calls) == 1


def test_status_warns_on_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: "/bin/" + exe)
    cfg = load_accounts(_write(tmp_path, ""), home=tmp_path)
    (tmp_path / ".claude").mkdir()

    def runner(cmd, env, **kw):
        return subprocess.CompletedProcess(
            cmd, 0, '{"loggedIn": true, "authMethod": "api_key"}', ""
        )

    assert "API キー" in status(cfg.get("claude", "personal-1"), runner).detail


def test_status_report_includes_usage(tmp_path, monkeypatch):
    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: None)
    cfg = load_accounts(_write(tmp_path, ""), home=tmp_path)
    a = cfg.get("claude", "team")
    record_usage(
        cfg.state_dir,
        a,
        {"five_hour": {"utilization": 0.5, "resetsAt": 2000.0 + 7200, "status": "allowed"}},
        now=2000.0,
    )
    assert latest_usage(cfg.state_dir, a)["windows"]["five_hour"]["utilization"] == 0.5
    assert format_windows(latest_usage(cfg.state_dir, a), now=2000.0).startswith(
        "five_hour: 50% 使用（あと2.0時間で戻る）"
    )
    report = status_report(cfg)
    assert "team" in report and "CLI が無い" in report and "50% 使用" in report


def test_cli_auth_login_unknown_account_exits_2(tmp_path, capsys):
    from educreator.cli import main

    p = _write(tmp_path, "")
    assert (
        main(["auth", "login", "--provider", "claude", "--account", "nope", "--config", str(p)])
        == 2
    )
    assert "personal-1, personal-2" in capsys.readouterr().err


def test_cli_auth_status_prints_every_account(tmp_path, capsys, monkeypatch):
    from educreator.cli import main

    monkeypatch.setattr("educreator.auth.shutil.which", lambda exe: None)
    assert main(["auth", "status", "--config", str(_write(tmp_path, ""))]) == 0
    out = capsys.readouterr().out
    assert all(n in out for n in ("personal-1", "personal-2", "personal-3", "team"))


def test_cli_auth_status_missing_config_exits_2(tmp_path, capsys):
    from educreator.cli import main

    assert main(["auth", "status", "--config", str(tmp_path / "nonexistent.toml")]) == 2
    assert "nonexistent.toml" in capsys.readouterr().err


@pytest.mark.parametrize("provider", ["claude", "chatgpt"])
def test_env_drops_api_keys_for_every_provider(tmp_path, monkeypatch, provider):
    """API キーの環境変数が親にあっても、どのアカウントの子プロセスにも渡さない（サブスクでなくキーで課金されるのを防ぐ）。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-a")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-o")
    empty = tmp_path / "edu-creator.toml"
    empty.write_text("", encoding="utf-8")
    cfg = load_accounts(empty, home=tmp_path)
    account = next(a for a in cfg.accounts if a.provider == provider)
    for env in (
        account.env(),
        account.env({"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k", "PATH": "/bin"}),
    ):
        assert "ANTHROPIC_API_KEY" not in env
        assert "OPENAI_API_KEY" not in env
