"""issue と PR の書き方チェック。見出しがあり、中身が書いてあるかを文字の規則だけで見る。"""

from __future__ import annotations

import re
from typing import Any

from repobot.api import is_bot

ISSUE_SECTIONS = ("背景", "今どこまで", "次にやること", "誰の判断待ち", "完了条件")

# PR は組織の既定テンプレート（関連 Issue / 概要・背景・妥協点 / やったこと）の見出しも受け付ける
PR_SECTIONS: dict[str, tuple[str, ...]] = {
    "概要": ("概要",),
    "変更内容": ("変更内容", "やったこと"),
    "関連Issue": ("関連issue",),
}

RELATION = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\b\s*:?\s*(?:[\w.-]+/[\w.-]+)?#\d+", re.IGNORECASE
)

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_NOTE = re.compile(r"[（(](?:必須|任意)[）)]")
# 中身として数えない行: 箇条書きの印だけ、空のチェックボックス、フォームが入れる「回答なし」
_EMPTY_LINE = re.compile(r"^(?:[-*+>]\s*)*(?:\[[ xX]?\]\s*)?(?:_No response_)?\s*$")

ALERT_LABEL = re.compile(r"alert|アラート", re.IGNORECASE)


def normalize(title: str) -> str:
    """見出しの比較用に、注記・空白・記号を落として小文字にする。"""
    t = _NOTE.sub("", title)
    t = re.sub(r"[\s　*_`:：]", "", t)
    return t.lower()


def sections(body: str | None) -> dict[str, str]:
    """見出し（正規化済み）→ その下の中身。中身は同じか浅い見出しの手前まで。コードブロック内は見出しにしない。"""
    lines = _COMMENT.sub("", body or "").splitlines()
    heads: list[tuple[int, int, str]] = []  # (行, 深さ, 見出し)
    fenced = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        m = None if fenced else _HEADING.match(line)
        if m:
            heads.append((i, len(m.group(1)), normalize(m.group(2))))
    out: dict[str, str] = {}
    for n, (i, depth, name) in enumerate(heads):
        end = len(lines)
        for j, d, _ in heads[n + 1 :]:
            if d <= depth:
                end = j
                break
        text = "\n".join(lines[i + 1 : end])
        out[name] = out.get(name, "") + text
    return out


def has_content(text: str | None) -> bool:
    return any(not _EMPTY_LINE.match(line) for line in (text or "").splitlines())


def _find(secs: dict[str, str], names: tuple[str, ...]) -> str | None:
    """見出しが名前と一致するか、名前で始まる（例: 概要・背景・妥協点）ものの中身を返す。"""
    keys = [normalize(n) for n in names]
    for head, text in secs.items():
        if any(head == k or head.startswith(k) for k in keys):
            return text
    return None


def check_issue(body: str | None) -> list[str]:
    """足りない項目の説明（無ければ空）。"""
    secs = sections(body)
    missing = []
    for name in ISSUE_SECTIONS:
        text = _find(secs, (name,))
        if text is None:
            missing.append(f"「{name}」の見出しがありません")
        elif not has_content(text):
            missing.append(f"「{name}」の中身が書かれていません")
    return missing


def check_pr(body: str | None) -> list[str]:
    secs = sections(body)
    missing = []
    for name, aliases in PR_SECTIONS.items():
        text = _find(secs, aliases)
        if text is None:
            missing.append(f"「{name}」の見出しがありません")
        elif not has_content(text):
            missing.append(f"「{name}」の中身が書かれていません")
        elif name == "関連Issue" and not RELATION.search(text):
            missing.append("「関連Issue」に `Closes #番号` か `Refs #番号` がありません")
    return missing


def skip_issue(issue: dict[str, Any]) -> str | None:
    """検査しない理由（検査するなら None）。"""
    if issue.get("pull_request"):
        return "PR は PR 側で検査する"
    if is_bot(issue.get("user")):
        return "ボットが作った issue"
    if any(ALERT_LABEL.search(lb.get("name", "")) for lb in issue.get("labels") or []):
        return "アラート系のラベル付き"
    if (issue.get("title") or "").lstrip().upper().startswith("[SBI]"):
        return "作業分解（SBI）の issue は本文が空でよい運用"
    return None


def skip_pr(pr: dict[str, Any]) -> str | None:
    if is_bot(pr.get("user")):
        return "ボットが作った PR"
    if pr.get("draft"):
        return "下書きの PR"
    return None


def report(kind: str, missing: list[str]) -> str:
    if not missing:
        return f"**書き方チェック: OK**\n\nこの{kind}の書き方はそろっています。"
    items = "\n".join(f"- {m}" for m in missing)
    need = "背景 / 今どこまで / 次にやること / 誰の判断待ち / 完了条件" if kind == "issue" else "概要 / 変更内容 / 関連Issue"
    return (
        f"**書き方チェック: 足りない所があります**\n\n{items}\n\n"
        f"必要な見出し: {need}。見出しだけ、または「-」やコメントだけの場合は未記入として扱います。"
        f"本文を直すと、このコメントが自動で更新されます。"
    )
