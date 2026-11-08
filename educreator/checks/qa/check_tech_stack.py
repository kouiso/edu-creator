#!/usr/bin/env python3
"""技術スタックの検査。教材のコードが、その教材の技術の範囲から外れていないかを見る。

両教材の同名の検査を1本にしたもの。考え方は共通で、
- 禁止パターン（別のフレームワーク・UI 部品ライブラリ・エラーを黙らせる書き方など）が1つでもあれば落とす
- そのスタックを使っていると分かるパターンが1つも無い日は、警告だけ出す（環境構築や言語入門の日は使わない）
禁止と使用のパターン・表示の文面は stack profile の qa.tech_stack に置く。

コードブロックの開き行は、言語名の後ろに属性（`apply path=...` など）が続く形も拾う。
言語名だけの形しか拾わないと、属性付きのブロックが検査をすり抜ける。
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import CONFIG  # noqa: E402

TS = CONFIG.get("tech_stack") or {}
# 検査しない言語。端末で打つコマンドと図は教材のコードではない。
SKIPPED_LANGS = tuple(TS.get("skipped_langs", ["mermaid", "bash", "shell", "sh", "text", "console"]))
FORBIDDEN = [(p, name) for p, name in TS.get("forbidden", [])]
FORBIDDEN_FLAGS = (re.IGNORECASE if TS.get("forbidden_ignorecase", False) else 0) | re.MULTILINE
EXPECT = list(TS.get("expect", []))
MSG_FORBIDDEN = TS.get("msg_forbidden", "❌ 技術の範囲外: {name}")
MSG_EXPECT_OK = TS.get("msg_expect_ok", "✅ スタックのパターン検出")
MSG_EXPECT_MISSING = TS.get("msg_expect_missing", "⚠️ スタックのパターンが検出されませんでした")


def check_tech_stack(filepath: str) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    code_blocks = re.findall(r"```(\w+)?[^\n]*\n(.*?)```", content, re.DOTALL)
    found = []
    expect_found = False
    for lang, code in code_blocks:
        if lang and lang.lower() in SKIPPED_LANGS:
            continue
        for pattern, name in FORBIDDEN:
            if re.search(pattern, code, FORBIDDEN_FLAGS):
                found.append(name)
        if not expect_found and any(re.search(p, code, re.MULTILINE) for p in EXPECT):
            expect_found = True

    errors = [MSG_FORBIDDEN.format(name=name) for name in sorted(set(found))]
    if not TS:
        print("✅ このスタックには技術の範囲の定義が無いので対象外")
        return True
    if expect_found:
        print(MSG_EXPECT_OK)
    elif code_blocks:
        print(MSG_EXPECT_MISSING)
    for error in errors:
        print(error)
    if errors:
        print("❌ 技術スタックチェックFAIL")
        return False
    print("✅ 技術スタックチェックPASS")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用法: python check_tech_stack.py <filepath>")
        sys.exit(1)
    sys.exit(0 if check_tech_stack(sys.argv[1]) else 1)
