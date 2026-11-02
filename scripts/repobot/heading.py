"""issue 見出しの自動修正: フォームで作ると1段深くなる見出しを戻す（### → ##、#### → ###）。"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_DEEP = re.compile(r"^( {0,3})(#{3,4})(?=[ \t])")


def fix(body: str | None) -> str:
    """コードブロックの外の行頭の ### と #### だけを1段浅くする。その他は1文字も変えない。"""
    text = body or ""
    out = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            line = _DEEP.sub(lambda m: m.group(1) + m.group(2)[1:], line, count=1)
        out.append(line)
    return "".join(out)
