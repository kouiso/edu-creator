#!/usr/bin/env python3
"""前方参照の検査（R-5・G6）。後の Day で初めて定義する識別子を、前の Day の写経のコードで使っていないかを見る。

読者は Day 順に写す。Day N のコードが Day N+3 で定義する関数を呼んでいると、Day N の終わりにアプリが動かない。
本文を Day ごとに書いていると、この食い違いに書き手は気づけない（前の Day を書いた時点で後の Day が無いため）。

やり方:
1. 写経のブロック（実ファイルへ書く、写経対象の言語。検算用の expect は除く）から、定義を拾う。
   定義の書き方は stack profile の qa.def_patterns（捕獲群1が名前の正規表現）で、トップレベルの定義だけを見る。
   import で入る名前（qa.import_patterns）も、その Day から使える名前として数える
2. 名前ごとに、初めて定義した Day を決める
3. 同じファイルに書く、それより前の Day の写経のブロックに、その名前が語として現れたら前方参照にする。
   名前の有効範囲をファイルごとに分けるのは、別のファイルの同名の別物（ローカルの `form` と別画面の `form` など）を取り違えないため
   （定義と同じ Day の中で、定義より前の行で使うのは、その Day の終わりには揃うので数えない）

名前が短すぎる（3文字以下）ものと、qa.forward_refs_ignore にあるものは外す。よくある語（id・name）や、
フレームワークが持つ同名の物と取り違えないため。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _config import CODE_LANGS, CONFIG  # noqa: E402
from curriculum_blocks import (  # noqa: E402
    FILEPATH,
    REAL_PREFIXES,
    REAL_ROOT_FILES,
    _split_target,
    filepath_value,
)
from fence_roles import apply_info_path, roles  # noqa: E402
from markdown_scan import fence_states  # noqa: E402

DEF_PATTERNS = [re.compile(p, re.M) for p in CONFIG.get("def_patterns", [])]
IMPORT_PATTERNS = [re.compile(p, re.M) for p in CONFIG.get("import_patterns", [])]
IGNORE = set(CONFIG.get("forward_refs_ignore", []))
# 了承した前方参照（course-spec の qa.forward_refs_approved）。{"ファイル: 名前": 理由}
APPROVED: dict[str, str] = dict(CONFIG.get("forward_refs_approved", {}))
MIN_LEN = 4


def day_number(name: str) -> int | None:
    m = re.match(r"day(\d{2})", name)
    return int(m.group(1)) if m else None


def writing_blocks(text: str) -> list[tuple[int, str, str]]:
    """(行番号, 書き込み先, コード) を、写経のブロックだけ返す。"""
    out: list[tuple[int, str, str]] = []
    buf: list[str] = []
    value: str | None = None
    lang = ""
    role: frozenset = frozenset()
    info = ""
    start = 0
    for i, line, state, fence in fence_states(text):
        if state == "open":
            buf, value, start = [], None, i
            lang = fence.lang if fence else ""
            info = fence.info if fence else ""
            role = roles(info)
            continue
        if state == "inside":
            m = FILEPATH.match(line)
            if m and value is None:
                value = filepath_value(m)
                continue
            buf.append(line)
            continue
        raw = value if value is not None else apply_info_path(info)
        if state == "close" and raw is not None:
            target, _ = _split_target(raw)
            real = target.startswith(REAL_PREFIXES) or target in REAL_ROOT_FILES
            if real and lang in CODE_LANGS and "expect" not in role:
                out.append((start, target, "\n".join(buf)))
    return out


def use_pattern(name: str) -> re.Pattern[str]:
    """名前を使っている所。属性やキーワード引数の名前（`name=` `name:`）は使用に数えない。

    JSX の `canManageMembers={false}` や Python の `can_edit=...` は、後で定義する同名の変数を参照していない。
    """
    return re.compile(rf"(?<![\w.]){re.escape(name)}\b(?!\s*=(?!=))(?!\s*:)")


def defines_locally(name: str, code: str) -> bool:
    """ブロックの中で同じ名前をローカルに作っているか（代入・引数・for・const/let/var）。

    作っていれば、そのブロックの同名はローカルの物で、後の Day の定義への参照ではない。
    """
    n = re.escape(name)
    return any(
        re.search(p, code, re.M)
        for p in (
            rf"^\s+{n}\s*(?::[^=\n]+)?=(?!=)",
            rf"^\s*for\s+[^\n]*\b{n}\b[^\n]*\bin\b",
            rf"\b(?:def|function)\s+\w+\s*\([^)]*\b{n}\b",
            rf"\b(?:const|let|var)\s+(?:\{{[^}}]*\b{n}\b[^}}]*\}}|\[[^\]]*\b{n}\b[^\]]*\]|{n}\b)",
        )
    )


def defined_names(code: str) -> set[str]:
    """ブロックで定義する名前と、import で入る名前（`a as b` なら b）。"""
    names: set[str] = set()
    for pat in DEF_PATTERNS:
        names.update(m.group(1) for m in pat.finditer(code))
    for pat in IMPORT_PATTERNS:
        for m in pat.finditer(code):
            for part in m.group(1).split(","):
                words = part.split()
                if words:
                    names.add(words[-1].split(".")[0])
    return {n for n in names if len(n) >= MIN_LEN and n not in IGNORE}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("material/30days-curriculum")
    if not DEF_PATTERNS:
        print("✅ このスタックには定義の書き方（qa.def_patterns）が無いので対象外")
        return 0
    files = sorted(root.glob("day[0-9][0-9]_*.md"))
    if not files:
        print(f"❌ Day のファイルがありません: {root}", file=sys.stderr)
        return 2
    # 名前の有効範囲は書き込み先のファイルごと。別のファイルの同名の物と取り違えないため
    blocks: list[tuple[int, str, int, str, str]] = []
    defined_at: dict[tuple[str, str], int] = {}
    for p in files:
        n = day_number(p.name)
        if n is None:
            continue
        for lineno, target, code in writing_blocks(p.read_text(encoding="utf-8")):
            blocks.append((n, p.name, lineno, target, code))
            for name in defined_names(code):
                key = (target, name)
                defined_at[key] = min(defined_at.get(key, n), n)

    by_target: dict[str, list[tuple[str, int]]] = {}
    for (target, name), first in defined_at.items():
        by_target.setdefault(target, []).append((name, first))
    hits: list[tuple[str, int, str, int, int]] = []
    for n, fname, lineno, target, code in sorted(blocks):
        for name, first in by_target.get(target, []):
            if first > n and use_pattern(name).search(code) and not defines_locally(name, code):
                hits.append((fname, lineno, f"{target}: {name}", n, first))

    accepted = [h for h in hits if h[2] in APPROVED]
    hits = [h for h in hits if h[2] not in APPROVED]
    for fname, lineno, key, n, first in accepted:
        print(f"  了承済み: {fname}:{lineno} `{key}`（Day{n:02d} で使い、定義は Day{first:02d}。{APPROVED[key]}）")
    if hits:
        print(f"❌ 前方参照 {len(hits)} 件（後の Day で定義する名前を、前の Day のコードで使っている）")
        for fname, lineno, name, n, first in hits:
            print(f"  {fname}:{lineno} `{name}`（Day{n:02d} で使い、定義は Day{first:02d}）")
        return 1
    print(f"✅ 前方参照 0 件（定義 {len(defined_at)} 個、写経のブロック {len(blocks)} 個）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
