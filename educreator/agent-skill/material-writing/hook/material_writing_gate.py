"""PreToolUse の関門: 書き方の決まり（skill）を読まずに、教材のフォルダへ書くのを止める。

hook が見るのはファイルのパスの形だけで、文の意味は判定しない。
判定の材料は、印の hook（material_writing_marker.py）がセッションごとに置く印だけ。印が無ければ止める。
止める手は 2 つ。
- 判定して止める: 標準出力に permissionDecision: deny の JSON を書いて終了コード 0
- 判定の途中で例外が出た: run_safely が全部受けて、標準エラーに理由を書いて終了コード 2
  （この 1 か所を抜けて落ちても、plugin の設定の onFailure: block が止める）

使い方: python3 material_writing_gate.py <target.json>   標準入力に PreToolUse の JSON
target.json: {"guarded_dir": "<守る教材のフォルダ>", "marker_dir": "<印の置き場>"}
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
# 「読むだけ」の命令。ファイルを書き換える・消す・ほかの命令を動かす手を持つ物は入れない
READ_ONLY_COMMANDS = frozenset(
    {
        "cat",
        "head",
        "tail",
        "wc",
        "ls",
        "stat",
        "diff",
        "grep",
        "cut",
        "nl",
        "md5",
        "md5sum",
        "shasum",
        "sha256sum",
    }
)
# 1 つでも含めば、単純な 1 つの命令ではない
COMPOUND_MARKS = (";", "&", "|", "`", "$(", "\n", ">", "<")
SAFE_SESSION = re.compile(r"[A-Za-z0-9_.-]+")
# シェルが展開する変数・命令の置換。展開前の文字列は守るフォルダを指さないので、展開してから見る
_VAR_REF = re.compile(r"\$(?:\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_]*|\([^()]*\))|`[^`]*`")
# 語の中のパスの形をした断片（python -c 'open("material/x.md")' のような、文字列の中も拾う）
_TOKEN = re.compile(r"[A-Za-z0-9_.~${}/-]+")

REASON_UNREAD_INPUT = (
    "教材のフォルダへの書き込みを止めました。edu-creator の hook が入力を読めなかったため、"
    "安全の側に倒しています。同じ操作をやり直してください。"
)
REASON_NO_SKILL = (
    "教材のフォルダへの書き込みを止めました。このセッションは、書き方の決まり（skill）をまだ読んでいません。"
    "次の 1 手: Skill ツールで `edu-creator:material-writing` を読んでから、同じ操作をやり直してください。"
    "対象は教材のフォルダの .md だけです。シェル経由の書き込みも同じ扱いです。"
)


def deny(reason: str) -> int:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


def points_at(path_text: str, cwd: str, guarded: Path) -> bool:
    """パスが守るフォルダそのものか、その下を指すか。相対のパスは入力の cwd を起点にする。"""
    if not path_text:
        return False
    p = Path(path_text)
    if not p.is_absolute():
        p = Path(cwd) / p
    real = Path(os.path.realpath(p))
    return real == guarded or guarded in real.parents


def _expand_known(text: str, cwd: str) -> str:
    """分かる置換（$PWD・$HOME・~・$(pwd)）だけ先に展開する。分からない変数は残す。"""
    home = str(Path.home())
    out = text.replace("$(pwd)", cwd).replace("`pwd`", cwd)
    out = out.replace("${PWD}", cwd).replace("$PWD", cwd)
    out = out.replace("${HOME}", home).replace("$HOME", home)
    if out.startswith("~/") or out == "~":
        out = home + out[1:]
    out = out.replace("=~/", f"={home}/").replace(":~/", f":{home}/")
    return out


@cache
def _glob_prefix(pat: str, s: str, i: int = 0, j: int = 0) -> bool:
    """glob の pat（* のみのワイルドカード）が、s そのものか s を頭に持つ文字列に合いうるか。
    * は / を含む任意の並びに合う（シェルの変数展開が作るパスは深さが決まらないため）。"""
    if j == len(s):
        # s を使い切った。pat の残りは後ろに足すだけで必ず合う物が作れる
        return True
    if i == len(pat):
        # pat が尽きたのに s が残る。s の方が長いので pat の合う物は s の頭になれない
        return False
    if pat[i] == "*":
        return _glob_prefix(pat, s, i + 1, j) or _glob_prefix(pat, s, i, j + 1)
    if pat[i] != s[j]:
        return False
    return _glob_prefix(pat, s, i + 1, j + 1)


def _may_point(text: str, cwd: str, guarded: Path) -> bool:
    """1つの断片が守るフォルダを指しうるか。展開できない変数が残る時は、届きうる形なら対象にする。"""
    if not text:
        return False
    if _VAR_REF.search(text):
        pat = _VAR_REF.sub("*", text)
        p = Path(pat)
        if not p.is_absolute():
            p = Path(cwd) / p
        parts = str(p).split("/")
        if ".." in parts:
            # ワイルドカードに絡む .. は展開の結果が定まらない（*/../x は * 次第でどこへでも行く）
            return True
        return _glob_prefix(str(p), str(guarded))
    return points_at(text, cwd, guarded)


def _path_tokens(text: str) -> list[str]:
    """断片の中のパスの形をした連なり（/ か .md か $ か ~ を含む物だけ）。"""
    return [
        m.group(0)
        for m in _TOKEN.finditer(text)
        if "/" in m.group(0)
        or m.group(0).endswith(".md")
        or "$" in m.group(0)
        or m.group(0).startswith("~")
    ]


def _word_touched(word: str, cwd: str, guarded: Path) -> bool:
    expanded = _expand_known(word, cwd)
    # つながって書かれた書き込み先（x>>path・--out=path）も拾うため、> < = で切る。cd・pushd の次の語も 1 つの語として同じに見る
    pieces = [expanded, *re.split(r"[><=]", expanded)]
    if any(_may_point(piece, cwd, guarded) for piece in pieces):
        return True
    # インタプリタの -c / -e の文字列や引用符の中のパスの形も拾う（open("material/x.md") など）
    for piece in pieces:
        if any(_may_point(token, cwd, guarded) for token in _path_tokens(piece)):
            return True
    return False


def _bash_targets_guarded(command: str, cwd: str, guarded: Path) -> bool:
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        # 分けられない（閉じていない引用符など）なら、読むだけと言い切れないので対象にする
        return True
    touched = any(_word_touched(word, cwd, guarded) for word in words)
    if not touched:
        return False
    simple = not any(mark in command for mark in COMPOUND_MARKS)
    return not (simple and words and words[0] in READ_ONLY_COMMANDS)


def is_targeted(data: dict[str, Any], cwd: str, guarded: Path) -> bool:
    tool = data.get("tool_name")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    if tool in WRITE_TOOLS:
        # NotebookEdit は file_path ではなく notebook_path に書き先を入れる
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        return (
            isinstance(file_path, str)
            and file_path.endswith(".md")
            and points_at(file_path, cwd, guarded)
        )
    if tool == "Bash":
        command = tool_input.get("command")
        return isinstance(command, str) and _bash_targets_guarded(command, cwd, guarded)
    return False


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
        target = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        guarded = Path(os.path.realpath(target["guarded_dir"]))
        marker_dir = Path(target["marker_dir"])
        if not isinstance(data, dict):
            raise ValueError("入力が dict でない")
        cwd = data["cwd"]
        if not isinstance(cwd, str) or not cwd:
            raise ValueError("cwd が無い")
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return deny(REASON_UNREAD_INPUT)
    if not is_targeted(data, cwd, guarded):
        return 0
    session = data.get("session_id")
    if not isinstance(session, str) or not SAFE_SESSION.fullmatch(session):
        return deny(REASON_NO_SKILL)
    if not (marker_dir / session).is_file():
        return deny(REASON_NO_SKILL)
    return 0


def run_safely(fn: Callable[[], int]) -> int:
    """fn の中のどこで例外が出ても、止める側（終了コード 2）に倒す。"""
    try:
        return fn()
    except BaseException as e:
        sys.stderr.write(
            f"edu-creator の関門の hook が失敗したので止めた: {type(e).__name__}: {e}\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(run_safely(main))
