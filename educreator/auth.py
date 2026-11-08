"""`edu-creator auth login|status`。

ログインは各 CLI のものを呼ぶだけにする（`claude auth login --claudeai`、`codex login`）。
置き場はアカウントごとに CLAUDE_CONFIG_DIR / CODEX_HOME で分ける。資格情報のファイルの中身は読まない（E-9）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass

from educreator.accounts import Account, AccountsConfig
from educreator.usage import format_windows, latest_usage

LOGIN_CMD = {"claude": ["claude", "auth", "login", "--claudeai"], "chatgpt": ["codex", "login"]}
STATUS_CMD = {
    "claude": ["claude", "auth", "status", "--json"],
    "chatgpt": ["codex", "login", "status"],
}
CLI_NAME = {"claude": "claude", "chatgpt": "codex"}


@dataclass(frozen=True)
class Status:
    account: Account
    cli_found: bool
    logged_in: bool | None
    method: str
    detail: str


def login(account: Account) -> int:
    """対話のログインを、そのアカウントの置き場で起動する（標準入出力はそのまま渡す）。"""
    if shutil.which(CLI_NAME[account.provider]) is None:
        print(
            f"{CLI_NAME[account.provider]} CLI が見つからない。先に入れてほしい。", file=sys.stderr
        )
        return 127
    account.config_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin" and account.provider == "claude":
        # macOS では OAuth のトークンがキーチェーンに置かれ、置き場を分けても上書きし合う報告がある（二次情報）。
        # その場合は `claude setup-token` のトークンをアカウントごとに CLAUDE_CODE_OAUTH_TOKEN で渡す（§3.4）。
        print(
            "注意: macOS ではログイン後に `edu-creator auth status` で他のアカウントが外れていないか確かめる。",
            file=sys.stderr,
        )
    return subprocess.run(LOGIN_CMD[account.provider], env=account.env(), check=False).returncode


def status(account: Account, runner=subprocess.run) -> Status:
    exe = CLI_NAME[account.provider]
    if shutil.which(exe) is None:
        return Status(account, False, None, "-", f"{exe} CLI が無い")
    if not account.config_dir.exists():
        return Status(
            account, True, False, "-", f"置き場 {account.config_dir} が無い（未ログイン）"
        )
    proc = runner(
        STATUS_CMD[account.provider],
        env=account.env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if account.provider == "claude":
        try:
            d = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return Status(account, True, None, "-", (proc.stderr or proc.stdout).strip()[:200])
        method = str(d.get("authMethod", "-"))
        logged = bool(d.get("loggedIn"))
        detail = ""
        # API キーで動いているならサブスクではない。キーの経路は持たない方針（U-2）なので知らせる
        if "api" in method.lower() and "key" in method.lower():
            detail = "API キーで動いている。サブスクでログインし直してほしい"
        return Status(account, True, logged, method, detail)
    out = (proc.stdout + proc.stderr).strip()
    return Status(
        account,
        True,
        proc.returncode == 0,
        "chatgpt" if proc.returncode == 0 else "-",
        out.splitlines()[0] if out else "",
    )


def status_report(cfg: AccountsConfig, runner=subprocess.run) -> str:
    lines = ["provider  account     login  method        置き場 / 使用量の窓"]
    for a in cfg.accounts:
        s = status(a, runner)
        mark = {True: "済", False: "未", None: "?"}[s.logged_in]
        lines.append(f"{a.provider:<9} {a.name:<11} {mark:<6} {s.method:<13} {a.config_dir}")
        if s.detail:
            lines.append(f"{'':<41}{s.detail}")
        lines.append(f"{'':<41}{format_windows(latest_usage(cfg.state_dir, a))}")
    return "\n".join(lines)
