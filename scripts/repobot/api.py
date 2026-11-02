# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF002, RUF003
"""GitHub REST API を標準ライブラリだけで呼ぶ窓口と、目印つきコメントの作成・更新。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class GitHubError(RuntimeError):
    """API が 2xx 以外を返した。"""

    def __init__(self, status: int, path: str, message: str):
        super().__init__(f"GitHub API {status} {path}: {message}")
        self.status = status


class GitHub:
    """workflow の GITHUB_TOKEN で動く最小の REST クライアント。"""

    def __init__(self, token: str, repo: str, base: str = "https://api.github.com"):
        self.token = token
        self.repo = repo
        self.base = base.rstrip("/")

    def request(self, method: str, path: str, body: Any = None) -> Any:
        url = path if path.startswith("http") else f"{self.base}{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read()
        except urllib.error.HTTPError as e:
            raise GitHubError(e.code, path, e.read().decode(errors="replace")[:300]) from e
        return json.loads(raw) if raw else None

    def paginate(self, path: str) -> list[Any]:
        sep = "&" if "?" in path else "?"
        items: list[Any] = []
        page = 1
        while True:
            chunk = self.request("GET", f"{path}{sep}per_page=100&page={page}") or []
            items.extend(chunk)
            if len(chunk) < 100:
                return items
            page += 1


def upsert_comment(
    client: Any, number: int, marker: str, body: str, create_if_missing: bool = True
) -> str:
    """目印 `marker` を含むコメントを1つだけ保つ。

    戻り値: "created" / "updated" / "unchanged" / "skipped"（無くて作らなかった）。
    """
    full = f"{marker}\n{body}"
    comments = client.paginate(f"/repos/{client.repo}/issues/{number}/comments")
    for c in comments:
        if marker in (c.get("body") or ""):
            if c.get("body") == full:
                return "unchanged"
            client.request(
                "PATCH", f"/repos/{client.repo}/issues/comments/{c['id']}", {"body": full}
            )
            return "updated"
    if not create_if_missing:
        return "skipped"
    client.request("POST", f"/repos/{client.repo}/issues/{number}/comments", {"body": full})
    return "created"


def is_bot(user: dict[str, Any] | None) -> bool:
    """ボットのアカウントか（GitHub App・Dependabot・github-actions など）。"""
    if not user:
        return False
    return user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]")


LABEL_COLOR = "ededed"


def ensure_labels(client: Any, names: list[str]) -> list[str]:
    """無いラベルだけ作る。作ったラベルの名前を返す。既にあるラベルには触らない。"""
    created = []
    for name in names:
        path = f"/repos/{client.repo}/labels/{urllib.parse.quote(name, safe='')}"
        try:
            client.request("GET", path)
        except GitHubError as e:
            if e.status != 404:
                raise
            client.request(
                "POST", f"/repos/{client.repo}/labels", {"name": name, "color": LABEL_COLOR}
            )
            created.append(name)
    return created
