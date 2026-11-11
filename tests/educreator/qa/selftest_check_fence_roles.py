#!/usr/bin/env python3
"""check_fence_roles.py の退行テスト。

通さないもの（path 無し expect・部分ファイル expect・apply 不在・危険パス）と、
通さなければならないもの（正しい apply/expect 対・従来の filepath フェンス）の
両方を置く。片方だけでは全部を止める検査か全部を通す検査か分からない。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "educreator" / "checks" / "qa"))

from check_fence_roles import check_text  # noqa: E402

APPLY = """```python apply path=app/routes/task.py
def page():
    return render_template("task/list.html")
```
"""

EXPECT = """```python expect path=app/routes/task.py
def page():
    return render_template("task/list.html")
```
"""

CASES: list[tuple[str, str, int]] = [
    (
        "apply + expect の正しい対は通す",
        APPLY + "\n" + EXPECT,
        0,
    ),
    (
        "従来の filepath フェンスだけは後方互換で通す",
        "```python\n# filepath: app/routes/task.py\ndef page(): ...\n```",
        0,
    ),
    (
        "expect に path= が無ければ止める",
        "```python expect\na = 1\n```",
        1,
    ),
    (
        "expect に対応する apply が無ければ止める",
        EXPECT,
        1,
    ),
    (
        "expect 本体に省略記号があれば止める",
        APPLY + "\n" + """```python expect path=app/routes/task.py
def page():
    # ...
    pass
```""",
        1,
    ),
    (
        "expect に危険なパスは止める",
        APPLY + "\n" + """```python expect path=../secret.py
a = 1
```""",
        1,
    ),
    (
        "apply path= に危険なパスは止める",
        "```python apply path=../../etc/passwd\nbody\n```",
        1,
    ),
    (
        "apply path= の途中 .. セグメントも止める",
        "```python apply path=app/../../outside.py\nbody\n```",
        1,
    ),
    (
        "expect は本文の # filepath: だけでは契約にならない",
        APPLY + "\n" + """```python expect
# filepath: app/routes/task.py
def page():
    return render_template("task/list.html")
```""",
        1,
    ),
    (
        "expect が同じ対象に重複していれば止める",
        APPLY + "\n" + EXPECT + "\n" + EXPECT,
        1,
    ),
    (
        "実コード中の日本語（既存の〜）はプレースホルダーにしない",
        APPLY + "\n" + """```python expect path=app/routes/task.py
message = "既存のタスクを表示"
def page():
    return render_template("task/list.html")
```""",
        0,
    ),
    (
        "従来の filepath フェンスが expect の apply 対象として数えられる",
        "```python\n# filepath: app/routes/task.py\na = 1\n```\n\n" + EXPECT,
        0,
    ),
    (
        "無タグの path= フェンスは対応 apply に数えない（実行時に止まるため）",
        "```python path=app/routes/task.py\na = 1\n```\n\n" + EXPECT,
        1,
    ),
    (
        "属性値の語（meta=expect）は役割にしない",
        APPLY + "\n" + """```python meta=expect path=app/routes/task.py
def page():
    return render_template("task/list.html")
```""",
        0,
    ),
    (
        "path= 値の中の expect 語は役割にしない",
        "```python apply path=app/utils/expect_utils.py\na = 1\n```",
        0,
    ),
    (
        "非コード言語の expect も検査する（yaml で apply 無し）",
        "```yaml expect path=app/routes/task.py\na: 1\n```",
        1,
    ),
    (
        "続き注記つき従来 filepath 注記も対応 apply に数える",
        "```python\n# filepath: app/routes/task.py（続き）\na = 1\n```\n\n" + EXPECT,
        0,
    ),
    (
        "省略せずの通常コメントはプレースホルダーにしない（移植元の実在コメント）",
        APPLY + "\n" + """```python expect path=app/routes/task.py
def page():
    # タイトル行: 長い名前も省略せず全文表示する
    return render_template("task/list.html")
```""",
        0,
    ),
    (
        "apply expect の併記は廃止した複合役割なので止める",
        """```python apply expect path=app/routes/task.py
def page():
    return render_template("task/list.html")
```""",
        1,
    ),
]


def main() -> int:
    failed = 0
    for label, text, want_errors in CASES:
        got = check_text(text, "dayXX_test.md")
        ok = (len(got) > 0) == bool(want_errors)
        if not ok:
            failed += 1
            print(f"❌ {label}: findings={len(got)} (期待={want_errors})")
            for f in got:
                print(f"   {f.lineno}: {f.message}")
        else:
            print(f"✅ {label}")
    if failed:
        print(f"❌ {failed} 件の退行")
        return 1
    print("✅ check_fence_roles 退行テスト全パス")
    return 0


if __name__ == "__main__":
    sys.exit(main())
