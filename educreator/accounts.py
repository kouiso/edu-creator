"""サブスクのアカウントと、その設定の置き場。

ログインそのものは各 CLI（`claude auth login`、`codex login`）に任せ、ここではアカウントごとに
設定の置き場を分けるだけにする。資格情報のファイルは読まない・写さない（E-9）。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

Provider = Literal["claude", "chatgpt"]

CONFIG_FILENAME = "edu-creator.toml"

# 2026-11-08 のユーザーの前提: Claude は個人3・チーム1、ChatGPT（Codex）は1つ。
# personal-1 は既定の置き場（~/.claude）を使う。手元の claude-team は ~/.claude-work を使っている。
DEFAULT_ACCOUNTS: dict[Provider, dict[str, str]] = {
    "claude": {
        "personal-1": "~/.claude",
        "personal-2": "~/.claude-p2",
        "personal-3": "~/.claude-p3",
        "team": "~/.claude-work",
    },
    "chatgpt": {
        "personal-1": "~/.codex",
    },
}

# 子プロセスに置き場を渡す環境変数
CONFIG_ENV: dict[Provider, str] = {"claude": "CLAUDE_CONFIG_DIR", "chatgpt": "CODEX_HOME"}


class AccountError(ValueError):
    pass


@dataclass(frozen=True)
class Account:
    provider: Provider
    name: str
    config_dir: Path
    max_parallel: int

    def env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        """このアカウントで CLI を動かすための環境変数。

        API キーの環境変数は外す。キーが残っていると CLI がサブスクではなくキーで課金するため。
        """
        env = dict(os.environ if base is None else base)
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            env.pop(key, None)
        env[CONFIG_ENV[self.provider]] = str(self.config_dir)
        return env


@dataclass(frozen=True)
class AccountsConfig:
    accounts: tuple[Account, ...]
    state_dir: Path

    def get(self, provider: Provider, name: str) -> Account:
        for a in self.accounts:
            if a.provider == provider and a.name == name:
                return a
        names = ", ".join(a.name for a in self.accounts if a.provider == provider) or "（無し）"
        raise AccountError(f"{provider} のアカウント '{name}' は設定に無い。使える名前: {names}")

    def of(self, provider: Provider) -> list[Account]:
        return [a for a in self.accounts if a.provider == provider]


def _default_max_parallel(provider: Provider) -> int:
    # Claude は5時間の窓と週の上限があるので1アカウント3まで（1週目に測って直す。U-12）。
    # Codex は1つの auth.json を並列のジョブで共有しないよう公式が求めているので1。
    return 3 if provider == "claude" else 1


def find_config(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        p = d / CONFIG_FILENAME
        if p.is_file():
            return p
    return None


def load_accounts(path: Path | None = None, home: Path | None = None) -> AccountsConfig:
    """edu-creator.toml を読む。無ければ既定のアカウントを使う。

    書式:
        [state]
        dir = "~/.local/state/edu-creator"

        [accounts.claude.personal-1]
        config_dir = "~/.claude"
        max_parallel = 3
    """
    home = home or Path.home()
    data: dict = {}
    if path is None:
        path = find_config()
    if path is not None:
        with path.open("rb") as f:
            data = tomllib.load(f)

    def expand(p: str) -> Path:
        return Path(p.replace("~", str(home), 1) if p.startswith("~") else p)

    raw = data.get("accounts")
    table: dict[str, dict[str, dict]] = {}
    if raw is None:
        for dprov, dnames in DEFAULT_ACCOUNTS.items():
            table[dprov] = {n: {"config_dir": d} for n, d in dnames.items()}
    else:
        table = raw

    accounts: list[Account] = []
    for prov, names in table.items():
        if prov not in CONFIG_ENV:
            raise AccountError(f"provider '{prov}' は使えない（claude か chatgpt）")
        if not isinstance(names, dict) or not names:
            raise AccountError(f"accounts.{prov} にアカウントが1つも無い")
        for name, conf in names.items():
            if "config_dir" not in conf:
                raise AccountError(f"accounts.{prov}.{name} に config_dir が無い")
            mp = int(conf.get("max_parallel", _default_max_parallel(cast(Provider, prov))))
            if mp < 1:
                raise AccountError(f"accounts.{prov}.{name}.max_parallel は1以上")
            if prov == "chatgpt" and mp > 1:
                raise AccountError(
                    "Codex は1つの auth.json を並列で共有できないので max_parallel は1"
                )
            accounts.append(Account(cast(Provider, prov), name, expand(conf["config_dir"]), mp))

    dirs = [a.config_dir for a in accounts]
    if len(set(dirs)) != len(dirs):
        raise AccountError(
            "同じ config_dir を2つのアカウントが使っている（ログインが互いに上書きされる）"
        )

    state = expand(data.get("state", {}).get("dir", "~/.local/state/edu-creator"))
    return AccountsConfig(tuple(accounts), state)
