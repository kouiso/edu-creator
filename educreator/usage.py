"""アカウントごとの使用量の窓の記録。

Claude Code は stream-json の rate_limit_event に窓ごとの使用率（unifiedWindows）を出す。
それを実行のたびに追記し、auth status で最新の値を、U-12 の測定で時系列を見る。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from educreator.accounts import Account


def _path(state_dir: Path, account: Account) -> Path:
    return state_dir / "usage" / f"{account.provider}-{account.name}.jsonl"


def record_usage(
    state_dir: Path, account: Account, windows: dict[str, Any], now: float | None = None
) -> None:
    p = _path(state_dir, account)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps({"at": now or time.time(), "windows": windows}, ensure_ascii=False) + "\n"
        )


def latest_usage(state_dir: Path, account: Account) -> dict[str, Any] | None:
    p = _path(state_dir, account)
    if not p.is_file():
        return None
    last = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            # 追記の途中で切れた行は読み飛ばし、読めた最後の記録を使う。1本の壊れた行で全アカウントの一覧を止めない
            continue
        if isinstance(rec, dict):
            last = rec
    return last


def format_windows(entry: dict[str, Any] | None, now: float | None = None) -> str:
    if not entry:
        return "記録なし（このアカウントで1回動かすと出る）"
    now = now or time.time()
    parts = []
    for name, w in sorted(entry["windows"].items()):
        util = w.get("utilization")
        resets = w.get("resetsAt")
        s = f"{name}: {util * 100:.0f}% 使用" if isinstance(util, (int, float)) else f"{name}: ?"
        if isinstance(resets, (int, float)) and resets > now:
            s += f"（あと{(resets - now) / 3600:.1f}時間で戻る）"
        if w.get("status") and w.get("status") != "allowed":
            s += f" [{w['status']}]"
        parts.append(s)
    age = (now - entry.get("at", now)) / 60
    return " / ".join(parts) + f"（{age:.0f}分前の記録）"
