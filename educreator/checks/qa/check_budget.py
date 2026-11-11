#!/usr/bin/env python3
"""Day 予算の検査（G9・R-3）。本文から実測して、course-spec の budget を超えた Day を出す。

見積もりの表ではなく、本文そのものから数える。表から数えると、本文を直したのに表を直し忘れた Day が緑のまま残る。

数えるもの（Day ごと）:
- 写経の行（上限値）: 読者が実ファイルへ書き込むコードブロック（書き込み先が実ファイルの置き場で、言語が写経対象のもの）の、
  空行を除いた行の合計。書き込み先の目印の行、省略と置き場の目印の行（`{# ... #}`・`# ◆ ...` など）、
  検算用（`expect`）のブロックは数えない。打たないため。空行を数えないのは、Enter 1回で手間がほぼ無く、
  書式を守ったコードほど予算を食う数え方になるため。
  ただしブロックには「どこに足すか」を示す既にある周りの行も入るので、本文から数えた値は打つ行の上限値になる。
  実際に打つ行は Day ごとのタグの差分（リプレイ）でしか正しく数えられないので、この軸は警告だけにして合否に使わない。
- ファイル: 写経のブロックの書き込み先の種類の数
- 分: 本文の `**合計時間**` の値
- 概念: 本文からは数えられない（概念の台帳が要る）。台帳ができるまでは「未測定」と出す

上限を超えても、course-spec の qa.budget_approved に Day と軸と理由を書いたものは「了承済み」として通す。
qa.budget_report_only が true なら、超えても落とさず、表を出すだけにする（Day の数を変えない改訂で、上限を合否に使わない教材のため）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _config import CODE_LANGS, CONFIG  # noqa: E402
from curriculum_blocks import FILEPATH, REAL_PREFIXES, REAL_ROOT_FILES, _split_target, filepath_value  # noqa: E402
from fence_roles import apply_info_path, roles  # noqa: E402
from markdown_scan import fence_states, strip_fences  # noqa: E402

# 省略と置き場の目印の行（打たない）。`# ...`・`{# ... #}`・`// ...`・`<!-- ... -->` と、`◆` で始まる指示
ELISION = re.compile(
    r"^\s*(?:\{#\s*(?:\.\.\.|…|◆.*?)\s*#\}|#\s*(?:\.\.\.|…|◆.*)|//\s*(?:\.\.\.|…|◆.*)|<!--\s*(?:\.\.\.|…|◆.*?)\s*-->)\s*$"
)
# 合否に使う軸。写経の行は上限値なので警告だけにする（上の説明）
GATED = {"files", "minutes"}
TOTAL = re.compile(r"\*\*合計時間\*\*\s*(?:[:：]|は)\s*約?\s*(\d+)\s*分")
AXES = (("copy_lines", "写経の行"), ("files", "ファイル"), ("minutes", "分"))


def day_number(name: str) -> int | None:
    m = re.match(r"day(\d{2})", name)
    return int(m.group(1)) if m else None


def measure(text: str) -> dict:
    copy_lines = 0
    targets: set[str] = set()
    buf: list[str] = []
    value: str | None = None
    lang = ""
    role: frozenset = frozenset()
    info = ""
    for _i, line, state, fence in fence_states(text):
        if state == "open":
            buf, value = [], None
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
        # 書き込み先は本文の `# filepath:` の目印が先。無ければ `apply path=` の info から取る
        raw = value if value is not None else apply_info_path(info)
        if state == "close" and raw is not None:
            target, _note = _split_target(raw)
            real = target.startswith(REAL_PREFIXES) or target in REAL_ROOT_FILES
            if real and lang in CODE_LANGS and "expect" not in role:
                copy_lines += sum(1 for b in buf if b.strip() and not ELISION.match(b))
                targets.add(target)
    total = TOTAL.search(strip_fences(text))
    return {"copy_lines": copy_lines, "files": len(targets), "minutes": int(total.group(1)) if total else None}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("material/30days-curriculum")
    budget = CONFIG.get("budget")
    if not budget:
        print("❌ course-spec の budget が渡されていない", file=sys.stderr)
        return 2
    limits = {"copy_lines": budget["copy_lines"], "files": budget["files"], "minutes": budget["minutes"]}
    approved = {int(k): v for k, v in (CONFIG.get("budget_approved") or {}).items()}
    report_only = bool(CONFIG.get("budget_report_only"))
    files = sorted(root.glob("day[0-9][0-9]_*.md")) if root.is_dir() else [root]
    if not files:
        print(f"❌ Day のファイルがありません: {root}", file=sys.stderr)
        return 2

    over, warned, accepted = [], [], []
    print("| Day | 写経の行（上限値） | ファイル | 分 | 概念 |")
    print("|---|---|---|---|---|")
    for p in files:
        n = day_number(p.name)
        m = measure(p.read_text(encoding="utf-8"))
        cells = []
        for axis, _label in AXES:
            v = m[axis]
            mark = ""
            if v is not None and v > limits[axis]:
                reason = approved.get(n, {}).get(axis) if n is not None else None
                if reason:
                    accepted.append((n, axis, v, reason))
                    mark = " ✓"
                elif axis in GATED:
                    over.append((n, axis, v))
                    mark = " ❌"
                else:
                    warned.append((n, axis, v))
                    mark = " ⚠"
            cells.append(("—" if v is None else str(v)) + mark)
        print(f"| {n:02d} | " + " | ".join(cells) + " | 未測定 |")

    print()
    print(
        f"上限: 写経 {limits['copy_lines']} 行・ファイル {limits['files']}・{limits['minutes']} 分"
        "（✓ 了承済み、❌ 超過、⚠ 写経の上限値が超過。打つ行はリプレイの差分で確かめる）"
    )
    for n, axis, v, reason in accepted:
        print(f"  了承済み: Day{n:02d} の{dict(AXES)[axis]} {v}（{reason}）")
    for n, axis, v in warned:
        print(f"  ⚠ Day{n:02d} の{dict(AXES)[axis]}（上限値）{v} > {limits[axis]}")
    if over:
        label = "超過（報告だけ）" if report_only else "❌ 上限を超えた Day"
        print(f"{label}: {len(over)} 件")
        for n, axis, v in over:
            print(f"  Day{n:02d} の{dict(AXES)[axis]} {v} > {limits[axis]}")
        if not report_only:
            print("  Step を分けるか、Day を分けるか、了承を course-spec の qa.budget_approved に理由付きで書く。")
            return 1
    print(f"✅ Day 予算 OK（{len(files)} Day）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
