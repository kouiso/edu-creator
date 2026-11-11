#!/usr/bin/env python3
"""写経対象のコードブロックを「書き込み先ファイル」ごとにまとめる共通処理。

移植元（姉妹教材）の点検では、「全日分のコードブロックを書き込み先ごとに連結し、
出来上がるファイルを見る」という同じ前処理を検査ごとに手でやっていた。手でやったので再現できず、
道具はそのまま捨てられた。連結の規則をここ1箇所へ置いて、検査はここを呼ぶ。

書き込み先の判定は filepath の目印（`# filepath:` / `{# filepath: #}` / `<!-- filepath: -->`）の値で行う。
教材の取り決めは次のとおり:
  - REAL_PREFIXES で始まる値、または REAL_ROOT_FILES の名前 = 読者が実際に書くファイル
  - 「読み比べ用サンプル」「ターミナル」など = 実ファイルを持たない
  - 値の後ろの `（続き）` `（import に追加）` は注記であって、書き込み先の一部ではない

`markdown_scan` のフェンス解釈をそのまま使う。ここで自前に数え直さない。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, NamedTuple

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent))

from markdown_scan import fence_states  # noqa: E402

__all__ = [
    "Block",
    "day_number",
    "iter_blocks",
    "concat_by_file",
    "has_confirmation_point",
    "heading_scan_view",
    "section_end",
]

# 読者が「次へ進んでよいか」を確かめる手段。教材は日によって書き方が違い、
# `**確認ポイント**` の日もあれば `### 期待する結果` の見出しで書く日もある。
# check_comprehension.py と check_no_skip.py が別々の定義を持っていた頃は、
# 片方が合格・片方が不合格という食い違いが起きていたので、定義はここ1箇所に置く。
CONFIRMATION_MARKERS = (
    re.compile(r"✅"),
    re.compile(r"- \[[ x]\]"),
    re.compile(r"確認[：:]"),
    re.compile(r"\*\*確認ポイント\*\*"),
)

CONFIRMATION_HEADING = re.compile(
    r"^#{2,4}\s+.*(確認|期待|チェック|成功|OK|見えたら|見ておき|見たい|見てほしい)"
)
# 「〜を確認する」で終わる見出しは、確かめる手段ではなく作業の指示である。
# 「README を開いて確認する」は何が出れば正しいのかを何も言っていないので、
# これを確認ポイントとして数えると、期待結果ゼロの節が緑のまま通る。
# 「ここで確認」「作成後に確認すること」は確認の提示なので残す。
ACTION_HEADING_TAIL = re.compile(r"確認(?:する|しよう|しましょう|してください|しておく)\s*$")


# ステップ節の終わりになる h2 見出し。`## まとめ` のような後続の節を節内に
# 取り込むと、そこに置かれた確認ポイントで手前のステップが合格してしまう。
# check_no_skip.py と check_comprehension.py で切り出し位置がずれると、
# 同じ教材に対して2つの検査が逆の判定を出すので、境界もここに1本化する。
SECTION_HEADING = re.compile(r"^## (?!#)", re.MULTILINE)


def heading_scan_view(content: str) -> str:
    """見出しを探すための、コードフェンスの中身を空白で潰した同じ長さの文字列。

    生の Markdown を見ると、コード例の中の `## main`（git status の出力）や
    README 例の `## 現在できること` が節の見出しに見える。そこでステップを
    切ると、以降の本文が検査されないまま通る。長さを変えずに潰すので、
    ここで得た位置はそのまま元の文字列の切り出しに使える。
    """
    return "\n".join(
        " " * len(line) if state != "outside" else line
        for _lineno, line, state, _fence in fence_states(content)
    )


def section_end(view: str, body_start: int, next_step_start: int) -> int:
    """ステップ節の終わりを返す。次のステップと次の h2 節の早いほうで切る。

    view には heading_scan_view の結果を渡す。元の文字列と長さが同じなので、
    返る位置はそのまま切り出しに使える。
    """
    following_section = SECTION_HEADING.search(view, body_start)
    if following_section and following_section.start() < next_step_start:
        return following_section.start()
    return next_step_start


def has_confirmation_point(section: str) -> bool:
    """節の本文に、読者が動作を確かめる手段が書かれているかを返す。

    見出し行そのものは呼び出し側で落としてから渡す。「〜を確認する」という
    ステップ名だけで合格させると、本文に検証手段が無いまま通ってしまう。
    """
    if any(marker.search(section) for marker in CONFIRMATION_MARKERS):
        return True
    return any(
        CONFIRMATION_HEADING.match(line) and not ACTION_HEADING_TAIL.search(line.strip())
        for line in section.split("\n")
    )

# 書き込み先の目印。`# filepath:`（Python・シェル・TOML・INI）、`{# filepath: ... #}`（テンプレート）、
# `<!-- filepath: ... -->`（素の HTML）、`// filepath:` と `{/* filepath: */}`（JS・JSX）を、スタックに依らず全部受ける。
# 受けないと、説明用の別言語の断片が「目印なし」と誤って数えられる。
# `#` の後ろに `}` が来るテンプレートの目印を `# filepath:` 側が先に食わないよう、テンプレートと HTML の形を前に置く。
FILEPATH = re.compile(
    r"^\s*(?:\{#\s*filepath:\s*(.+?)\s*#\}"
    r"|<!--\s*filepath:\s*(.+?)\s*-->"
    r"|\{/\*\s*filepath:\s*(.+?)\s*\*/\}"
    r"|(?://|#)\s*filepath:\s*(.+?))\s*$"
)


def filepath_value(match):
    # 4つの書き方を1つの正規表現で受けるため捕獲群が4本になる。どれが埋まるかは
    # 書き方で決まるので、呼び出し側に群番号を意識させず値だけを返す。
    return next(g for g in match.groups() if g is not None)


def first_filepath_match(code: str) -> "re.Match[str] | None":
    """ブロックの中で最初に見つかった目印の Match を返す。無ければ None。

    「目印があるか」と「その値は何か」を別々の判定で持つと、片方だけが
    書き方の追加に追従して割れる。実際に、有無は全行を見るのに値の取り出しは
    先頭行だけ、という食い違いが起きていた（#369）。両方をここから作る。
    """
    for line in code.split("\n"):
        m = FILEPATH.match(line)
        if m:
            return m
    return None


def has_filepath_marker(code: str) -> bool:
    # 「`{# filepath:` を含むか」で数えると、閉じの `#}` が無い壊れた目印まで
    # 有効として通る。そのまま貼ると構文エラーになるので、抽出側と同じ
    # FILEPATH で行ごとに判定して、検査と抽出の判定を1つに揃える。
    return first_filepath_match(code) is not None
# 値の末尾に付く注記1つ。入れ子は取らない（注記は `（続き）` 程度の平坦な語）。
TRAILING_NOTE = re.compile(r"^(.*?)\s*([（(][^（()）]*[）)])\s*$")
# 読者が実際に書くファイルの置き場・ルート直下のファイル・写経対象の言語は、スタックで決まるので
# stack profile の qa（と course-spec の qa の上書き）から受け取る。ルート直下のファイルは手書きの集合を
# 2か所に持たないよう、配布の区分の表（区分が「写経」のもの）からも足せる。
# bash は同じ `# filepath:` の書式を使うが、端末で打つコマンドなので写経対象の言語に入れない。
from _config import CODE_LANGS, REAL_PREFIXES, REAL_ROOT_FILES  # noqa: E402


class Block(NamedTuple):
    """1つのコードブロック。"""

    day: int
    source: str
    lineno: int
    target: str
    note: str
    lang: str
    lines: tuple[str, ...]

    @property
    def is_writing_target(self) -> bool:
        """読者が実ファイルへ書き込むブロックか。"""
        return self.target.startswith(REAL_PREFIXES) or self.target in REAL_ROOT_FILES


def day_number(name: str) -> int:
    m = re.match(r"day(\d{2})", name)
    return int(m.group(1)) if m else 0


def _split_target(value: str) -> tuple[str, str]:
    """`app/x.py（続き）` を ("app/x.py", "（続き）") に割る。

    注記は必ず値の末尾に付く。末尾の括弧だけを剥がし、途中の括弧はパスの一部として
    残す。最初の `(` で切る形だと、括弧を含むディレクトリ名（移植元では
    `(auth)` のようなルートグループ）が親ディレクトリへ潰れ、別のファイルのブロックと
    1つに連結されてしまう。
    """
    base = value.strip()
    notes: list[str] = []
    while True:
        m = TRAILING_NOTE.match(base)
        if not m:
            break
        head, note = m.group(1).strip(), m.group(2)
        # 括弧を剥がした残りがパスの途中で終わるなら、それは注記ではなく
        # パスの一部（`app/(group)` の形）。剥がさずに置く。
        # 半角の括弧の中に `/` があるときもパスの一部と見て剥がさない。全角の括弧はパスに
        # 出てこないので、中に `/` があっても注記として剥がす。剥がさないと
        # `（<h1> から「新規タスク」の </a> までを書き直す）` が注記ごと別の書き込み先になる。
        slash_in_path = "/" in note and not note.startswith("（")
        if slash_in_path or head.endswith("/") or not head:
            break
        base = head
        notes.insert(0, note)
    return base, "".join(notes)


def iter_blocks(text: str, source: str) -> Iterator[Block]:
    """filepath の目印を持つコードブロックを、現れた順に返す。

    filepath 行はブロックの1行目とは限らない（`{% extends %}` やエンコーディング宣言の下に置く日がある）ので、
    ブロックの中を最後まで見て最初に現れた1本だけを採る。filepath 行そのものは
    lines へ含めない。写経される中身ではないためである。
    """
    day = day_number(source)
    buf: list[str] = []
    value: str | None = None
    start = 0
    lang = ""
    for i, line, state, fence in fence_states(text):
        if state == "open":
            buf, value, start, lang = [], None, i, (fence.lang if fence else "")
            continue
        if state == "inside":
            m = FILEPATH.match(line)
            if m and value is None:
                value = filepath_value(m)
                continue
            buf.append(line)
            continue
        if state == "close" and value is not None:
            target, note = _split_target(value)
            yield Block(day, source, start, target, note, lang, tuple(buf))


def concat_by_file(paths: list[Path]) -> dict[str, list[Block]]:
    """書き込み先ファイルごとに、day 順のブロック列を返す。"""
    out: dict[str, list[Block]] = {}
    blocks: list[Block] = []
    for p in sorted(paths, key=lambda q: (day_number(q.name), q.name)):
        blocks.extend(iter_blocks(p.read_text(encoding="utf-8"), p.name))
    for b in blocks:
        if b.is_writing_target and b.lang in CODE_LANGS:
            out.setdefault(b.target, []).append(b)
    return out
