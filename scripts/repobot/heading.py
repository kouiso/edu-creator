# 日本語の全角記号（（）、：など）は意図した表記なので、紛らわしい文字の警告は外す
# ruff: noqa: RUF002, RUF003
"""issue 見出しの自動修正: フォームで作ると1段深くなる見出しを戻す（### → ##、#### → ###）。"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_DEEP = re.compile(r"^( {0,3})(#{3,4})(?=[ \t])")
_SHALLOW = re.compile(r"^ {0,3}#{1,2}(?=[ \t])")


def _outside_code(lines: list[str]) -> list[bool]:
    """各行がコードブロックの外か。閉じるのは開いた時と同じ記号で同じ長さ以上の区切りだけ。"""
    flags = []
    fence = ""
    for line in lines:
        m = _FENCE.match(line)
        if fence:
            flags.append(False)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = ""
        elif m:
            flags.append(False)
            fence = m.group(1)
        else:
            flags.append(True)
    return flags


def fix(body: str | None) -> str:
    """フォームで作った本文（いちばん浅い見出しが ###）だけ、行頭の ### と #### を1段浅くする。

    手で書いた本文に ## や # の見出しがあれば、見出しの階層をこわさないよう何も変えない。
    コードブロックの中は触らない。
    """
    lines = (body or "").splitlines(keepends=True)
    outside = _outside_code(lines)
    if any(o and _SHALLOW.match(line) for line, o in zip(lines, outside, strict=True)):
        return body or ""
    out = [
        _DEEP.sub(lambda m: m.group(1) + m.group(2)[1:], line, count=1) if o else line
        for line, o in zip(lines, outside, strict=True)
    ]
    return "".join(out)
