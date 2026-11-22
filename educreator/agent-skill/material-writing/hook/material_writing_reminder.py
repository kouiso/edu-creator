"""PreToolUse の案内: 守る教材のフォルダの .md を書く時に、書く前の 6 つの手順を文脈へ入れる。

止める hook ではない（止めるのは material_writing_gate.py）。入力が読めない時も、何も出さずに通す。
この案内はツールの結果の隣に届くので、書いた後の安全網である。書く前に効かせるのは関門の hook。

使い方: python3 material_writing_reminder.py <target.json>   標準入力に PreToolUse の JSON
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REMINDER = """[教材の書き方の決まり] 教材のファイルを編集しています。
まだ読んでいなければ、Skill ツールで `edu-creator:material-writing` を読んでください。

書く前・書き直す前の 6 つの手順:
1. 偏愛語を疑う（落ちる・壊れる・刺さる・設計・仕組み・本質・流れ）
2. 対象に実体があるか判定する（その名詞の指示対象を 1 文で説明できるか）
3. 実体が無ければ比喩に逃げず、具体の動作へ書き直す
4. 構文の癖を直す（過去形は現在形へ、1 文内の対比は 2 文に分ける）
5. 動詞・助詞・形容詞の選択ミスを正す（「課題を改善する」は「課題を解決する」）
6. 重言・翻訳調を消す（「することができます」は「できます」）

手順書化（「これを書く、確認する」の羅列）は禁止。コードの後に必ず「なぜこう動くか」を書く。
読者が次の似た手続きを自力で書ける見込みが無ければ、手順を増やさず理由を足す。

この案内は書き込みの後に届く（安全網）。次の編集から、6 つの手順を先に通してください。"""


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
        target = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        guarded = Path(os.path.realpath(target["guarded_dir"]))
        file_path = data["tool_input"]["file_path"]
        cwd = data["cwd"]
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return 0
    if not (isinstance(file_path, str) and isinstance(cwd, str) and file_path.endswith(".md")):
        return 0
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(cwd) / p
    real = Path(os.path.realpath(p))
    if real != guarded and guarded not in real.parents:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": REMINDER}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
