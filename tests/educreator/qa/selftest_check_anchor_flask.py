#!/usr/bin/env python3
"""check_anchor.py の退行テスト。

素通ししてはいけないもの（指示語だけの値）と、止めてはいけないもの（実ファイル名、
実ファイルを持たない旨を書いたもの、コードブロックの外にある同じ文字列）の両方を置く。
片方だけでは、全部を止める検査でも全部を通す検査でも緑になってしまう。
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "educreator" / "checks" / "qa"))

from check_anchor import (  # noqa: E402
    find,
    find_missing,
    find_sample_with_real_path,
)

# Before/After の節にあるコードは写経の対象ではない。実ファイル名を名乗らせない。
SAMPLE_CASES: list[tuple[str, str, list[tuple[int, str]]]] = [
    (
        "読み比べ用の節で実ファイル名を名乗ったら拾う",
        "#### Before（改善前のコード）\n\n```python\n# filepath: app/routes/task.py\n```",
        [(4, "app/routes/task.py")],
    ),
    (
        "読み比べ用と書いてあれば通す",
        "#### After（プロが書くコード）\n\n```python\n# filepath: 読み比べ用サンプル（実ファイルには対応しません）\n```",
        [],
    ),
    (
        "写経の節なら実ファイル名でよい",
        "### Step 1: 書く\n\n```python\n# filepath: app/routes/task.py\n```",
        [],
    ),
    (
        "読み比べ用の節を抜けたら対象外に戻る",
        "#### Before（改善前のコード）\n\n### Step 2: 書く\n\n```python\n# filepath: app/routes/task.py\n```",
        [],
    ),
    (
        "Python の # filepath 行は見出しではないので節から抜けない",
        "#### Before（改善前のコード）\n\n```python\n# filepath: app/routes/task.py\nx = 1\n```",
        [(4, "app/routes/task.py")],
    ),
    (
        "Jinja の目印でも読み比べ用の節なら拾う",
        "#### Before（改善前のコード）\n\n```jinja\n{# filepath: app/templates/task/list.html #}\n```",
        [(4, "app/templates/task/list.html")],
    ),
    (
        "4連で開いたブロックは3連では閉じない",
        (
            "#### Before（改善前のコード）\n\n"
            "````md\n```\nx\n```\n# filepath: app/routes/task.py\n````\n"
        ),
        [(7, "app/routes/task.py")],
    ),
]

REPO = Path(json.loads(os.environ["EDU_CREATOR_QA_JSON"])["repo_root"])

# 実在するファイルは通し、実在しないファイルは止める。読み比べ用の断りは対象外にする。
MISSING_CASES: list[tuple[str, str, list[tuple[int, str]]]] = [
    (
        "完成版に無い app/ パスを名乗る Python ブロックは拾う（陽性フィクスチャ）",
        "```python\n# filepath: app/routes/graduation.py\n```",
        [(2, "app/routes/graduation.py")],
    ),
    (
        "完成版に無いテンプレートを名乗る Jinja ブロックも拾う",
        "```jinja\n{# filepath: app/templates/graduation/index.html #}\n```",
        [(2, "app/templates/graduation/index.html")],
    ),
    (
        "完成版に無い tests/ パスも拾う",
        "```python\n# filepath: tests/test_graduation.py\n```",
        [(2, "tests/test_graduation.py")],
    ),
    (
        "完成版に在るパスは通す",
        "```python\n# filepath: app/routes/task.py\n```",
        [],
    ),
    (
        "在るテンプレートは HTML コメントの目印でも通す",
        "```html\n<!-- filepath: app/templates/task/list.html -->\n```",
        [],
    ),
    (
        "在るパスに注記が付いていても通す",
        "```python\n# filepath: app/routes/task.py（同じファイルの続き）\n```",
        [],
    ),
    (
        "ルート直下の実ファイル（REAL_ROOT_FILES）も実在を見る",
        "```python\n# filepath: config.py\n```",
        [],
    ),
    (
        "読み比べ用の断りは対象外",
        "```python\n# filepath: 読み比べ用サンプル（実ファイルには対応しません）\n```",
        [],
    ),
]

CASES: list[tuple[str, str, list[tuple[int, str]]]] = [
    (
        "指示語だけの値は拾う",
        "```python\n# filepath: 続き\na = 1\n```",
        [(2, "続き")],
    ),
    (
        "実ファイル名なら通す",
        "```python\n# filepath: app/routes/task.py\na = 1\n```",
        [],
    ),
    (
        "実ファイル名に続きと添えても通す",
        "```python\n# filepath: app/routes/task.py（同じファイルの続き）\na = 1\n```",
        [],
    ),
    (
        "実ファイルを持たない旨を書けば通す",
        "```python\n# filepath: 読み比べ用サンプル（続き・実ファイルには対応しません）\na = 1\n```",
        [],
    ),
    (
        "同上も拾う",
        "```python\n# filepath: 同上\na = 1\n```",
        [(2, "同上")],
    ),
    (
        "コードブロックの外は対象外",
        "# filepath: 続き と書いた行の話をしています。\n",
        [],
    ),
    (
        "Jinja の目印で指示語だけの値も拾う",
        "```jinja\n{# filepath: 続き #}\n<p></p>\n```",
        [(2, "続き")],
    ),
    (
        "複数ブロックをまとめて拾う",
        "```python\n# filepath: 続き\n```\n\n```python\n# filepath: app/a.py\n```\n\n```python\n# filepath: 同上\n```",
        [(2, "続き"), (10, "同上")],
    ),
    (
        "同じ注記が2回ぶら下がったら拾う",
        "```python\n# filepath: app/a.py（同じファイルの続き）（同じファイルの続き）\n```",
        [(2, "app/a.py（同じファイルの続き）（同じファイルの続き）")],
    ),
    (
        "違う注記が2つ並ぶのは通す",
        "```python\n# filepath: app/a.py（Step 3 で作成）（同じファイルの続き）\n```",
        [],
    ),
    (
        "filepath の無いブロックは対象外",
        "```python\na = 1\n```",
        [],
    ),
]


def main() -> int:
    failed = 0
    for name, text, expected in CASES:
        got = find(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    for name, text, expected in SAMPLE_CASES:
        got = find_sample_with_real_path(text)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    for name, text, expected in MISSING_CASES:
        got = find_missing(text, REPO)
        if got != expected:
            failed += 1
            print(f"  ❌ {name}: 期待 {expected} / 実際 {got}")
    total = len(CASES) + len(MISSING_CASES) + len(SAMPLE_CASES)
    if failed:
        print(f"❌ check_anchor 自己テスト {failed}/{total} 失敗")
        return 1
    print(f"✅ check_anchor 自己テスト {total}/{total} 合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
