# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF001, RUF002, RUF003
"""workflow からの入口: `PYTHONPATH=scripts python3 -m repobot <content|form|heading|triage>`。

GitHub が渡すイベント（GITHUB_EVENT_NAME / GITHUB_EVENT_PATH）を読む。
PR の外から来たコードは取り出さず、イベントの JSON と API だけを使う。
戻り値 1 = 検査を赤にする。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from repobot import content, form, heading, triage
from repobot.api import (
    BOT_LOGIN,
    GitHub,
    GitHubError,
    ensure_labels,
    is_bot,
    upsert_comment,
)

CONTENT_MARKER = "<!-- repobot:public-content:{key} -->"
FORM_MARKER = "<!-- repobot:format -->"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _target(
    event_name: str, event: dict[str, Any]
) -> tuple[int, str, str | None, str | None, str, dict[str, Any]] | None:
    """(issue/PR 番号, 目印の鍵, 題, 本文, 報告で使う呼び名, 書いた人) を返す。対象外なら None。"""
    if event_name == "issues":
        issue = event["issue"]
        return (
            issue["number"],
            "body",
            issue.get("title"),
            issue.get("body"),
            "この issue の題か本文",
            issue.get("user") or {},
        )
    if event_name in ("pull_request", "pull_request_target"):
        pr = event["pull_request"]
        return (
            pr["number"],
            "body",
            pr.get("title"),
            pr.get("body"),
            "この PR の題か本文",
            pr.get("user") or {},
        )
    if event_name == "issue_comment":
        c = event["comment"]
        return (
            event["issue"]["number"],
            f"comment-{c['id']}",
            None,
            c.get("body"),
            f"[このコメント]({c.get('html_url', '')})",
            c.get("user") or {},
        )
    if event_name == "pull_request_review_comment":
        c = event["comment"]
        return (
            event["pull_request"]["number"],
            f"review-comment-{c['id']}",
            None,
            c.get("body"),
            f"[このレビューコメント]({c.get('html_url', '')})",
            c.get("user") or {},
        )
    if event_name == "pull_request_review":
        r = event["review"]
        return (
            event["pull_request"]["number"],
            f"review-{r['id']}",
            None,
            r.get("body"),
            f"[このレビュー]({r.get('html_url', '')})",
            r.get("user") or {},
        )
    return None


def run_content(event_name: str, event: dict[str, Any], client: Any, env: dict[str, str]) -> int:
    target = _target(event_name, event)
    if target is None:
        _log(f"対象外のイベント: {event_name}")
        return 0
    number, key, title, body, name, author = target
    if author.get("login") == BOT_LOGIN:
        # この自動化自身の報告。中身は規則名と行番号だけなので検査しない
        _log("この自動化自身のコメントなので検査しない")
        return 0
    forbidden, broken = content.load_forbidden(env.get("REPOBOT_FORBIDDEN_PATTERNS"))
    if broken:
        _log(f"::warning::禁止語の一覧のうち {broken} 行が正規表現として読めず、使っていません")
    if not env.get("REPOBOT_FORBIDDEN_PATTERNS"):
        _log("::notice::禁止語の一覧（secret）が渡されていないため、汎用の規則だけで検査します")
    hits = content.scan(title, body, forbidden)
    marker = CONTENT_MARKER.format(key=key)
    try:
        # 当たりが無い時は新しく投稿しない。前に「要確認」を出していれば OK に書き換える
        action = upsert_comment(
            client, number, marker, content.report(name, hits), create_if_missing=bool(hits)
        )
        _log(f"コメント: {action}")
    except GitHubError as e:
        _log(f"::warning::コメントを書けませんでした（{e.status}）。検査結果は下の通り")
    for label, places, count in content.summarize(hits):
        _log(f"::error::公開内容チェック: {label} が {count} 件（場所: {', '.join(places)}）")
    return 1 if hits else 0


def run_form(event_name: str, event: dict[str, Any], client: Any, env: dict[str, str]) -> int:
    if event_name == "issues":
        item, kind = event["issue"], "issue"
        reason = form.skip_issue(item)
        missing = [] if reason else form.check_issue(item.get("body"))
    elif event_name in ("pull_request", "pull_request_target"):
        item, kind = event["pull_request"], "PR"
        reason = form.skip_pr(item)
        missing = [] if reason else form.check_pr(item.get("body"))
    else:
        _log(f"対象外のイベント: {event_name}")
        return 0
    if reason:
        _log(f"検査しない: {reason}")
        return 0
    try:
        action = upsert_comment(
            client, item["number"], FORM_MARKER, form.report(kind, missing), bool(missing)
        )
        _log(f"コメント: {action}")
    except GitHubError as e:
        _log(f"::warning::コメントを書けませんでした（{e.status}）")
    for m in missing:
        _log(f"::error::書き方チェック: {m}")
    return 1 if missing else 0


def run_heading(event_name: str, event: dict[str, Any], client: Any, env: dict[str, str]) -> int:
    if event_name != "issues":
        return 0
    issue = event["issue"]
    path = f"/repos/{client.repo}/issues/{issue['number']}"
    # 作られた直後に書き直された分を消さないよう、最新の本文を取り直してから直す
    latest = client.request("GET", path) or {}
    before = latest.get("body", issue.get("body")) or ""
    after = heading.fix(before)
    if after == before:
        _log("見出しの直しは不要")
        return 0
    client.request("PATCH", path, {"body": after})
    _log("見出しを1段浅くしました")
    return 0


def run_triage(event_name: str, event: dict[str, Any], client: Any, env: dict[str, str]) -> int:
    if event_name not in ("pull_request", "pull_request_target"):
        return 0
    pr = event["pull_request"]
    number = pr["number"]
    user = pr.get("user") or {}
    if event.get("action") in ("opened", "reopened") and not is_bot(user):
        try:
            client.request(
                "POST",
                f"/repos/{client.repo}/issues/{number}/assignees",
                {"assignees": [user["login"]]},
            )
            _log(f"担当者を {user['login']} にしました")
        except GitHubError as e:
            # 担当者の付け外しに失敗しても、ラベル付けは続ける
            _log(f"::warning::担当者を付けられませんでした（{e.status}）。ラベル付けは続けます")
    files = client.paginate(f"/repos/{client.repo}/pulls/{number}/files")
    labels = triage.labels_for((pr.get("head") or {}).get("ref"), [f["filename"] for f in files])
    if labels:
        made = ensure_labels(client, labels)
        if made:
            _log(f"無かったラベルを作りました: {', '.join(made)}")
        # 追加だけ。既にあるラベルは消さない
        client.request("POST", f"/repos/{client.repo}/issues/{number}/labels", {"labels": labels})
        _log(f"ラベル: {', '.join(labels)}")
    return 0


COMMANDS = {"content": run_content, "form": run_form, "heading": run_heading, "triage": run_triage}


def main(argv: list[str], env: dict[str, str] | None = None, client: Any = None) -> int:
    env = dict(os.environ) if env is None else env
    if len(argv) != 1 or argv[0] not in COMMANDS:
        _log(f"使い方: python3 -m repobot <{'|'.join(COMMANDS)}>")
        return 2
    with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        event = json.load(f)
    if client is None:
        client = GitHub(env.get("GITHUB_TOKEN", ""), env["GITHUB_REPOSITORY"])
    return COMMANDS[argv[0]](env.get("GITHUB_EVENT_NAME", ""), event, client, env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
