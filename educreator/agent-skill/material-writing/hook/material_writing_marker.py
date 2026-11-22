"""PostToolUse の印: 書き方の決まり（skill）を Skill ツールで読んだセッションに印を置く。

Claude Code には「skill を読み込んだ」という出来事が無いので、Skill ツールの呼び出しを見て自分で記録する。
印は target.json の marker_dir の下の <セッション番号>。関門の hook（material_writing_gate.py）がこれだけを見る。
作れなかった時は標準エラーに理由を書いて終了コード 0 で終わる（関門が止めて、理由が見える）。

使い方: python3 material_writing_marker.py <target.json>   標準入力に PostToolUse の JSON
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SAFE_SESSION = re.compile(r"[A-Za-z0-9_.-]+")


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
        target = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        tool_input = data["tool_input"]
        skill = tool_input.get("skill") or tool_input.get("command") or ""
        session = data.get("session_id")
        marker_dir = Path(target["marker_dir"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
        sys.stderr.write(f"edu-creator の印の hook が入力を読めなかった: {type(e).__name__}: {e}\n")
        return 0
    if not isinstance(skill, str) or "material-writing" not in skill:
        return 0
    if not isinstance(session, str) or not SAFE_SESSION.fullmatch(session):
        sys.stderr.write(
            "edu-creator の印の hook: セッションの番号が無い（または使えない形）ので印を置けなかった\n"
        )
        return 0
    try:
        marker_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        (marker_dir / session).touch()
    except OSError as e:
        sys.stderr.write(f"edu-creator の印の hook が印を置けなかった: {e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
