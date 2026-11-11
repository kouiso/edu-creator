"""実行の録画と再生（E-8）。

LLM の応答だけでなく、道具の呼び出しとその結果（Event の列）と、実行が終わった時の作業フォルダのファイルの状態を
1本の JSON に残す。再生ではエージェントを呼ばず、Event の列を返し、ファイルの状態を作業フォルダへ戻す。
録画は本人のサブスクで手元で作り、CI では再生だけを使う（CI にサブスクのログインを置かない。E-9）。

ファイルの状態は、実行の前後で変わった・増えたテキストファイルだけを持つ（消えたファイルは消した印を持つ）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from educreator.runtime.base import Event, RunResult

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "instance"}


def snapshot(root: Path) -> dict[str, str]:
    """root の下のテキストファイルの {相対パス: sha256}。"""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        # symlink はたどらない。作業ツリーの外の資格情報などへの symlink を、録画に読み込まないため
        if p.is_symlink() or not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def changes(root: Path, before: dict[str, str]) -> dict[str, str | None]:
    """before から変わったファイルの {相対パス: 中身}。消えたファイルは None。"""
    after = snapshot(root)
    out: dict[str, str | None] = {}
    for rel, digest in after.items():
        if before.get(rel) != digest:
            try:
                out[rel] = (root / rel).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    for rel in before:
        if rel not in after:
            out[rel] = None
    return out


TREE = "<tree>"


def save(
    path: Path,
    request: dict[str, Any],
    result: RunResult,
    files: dict[str, str | None],
    root: Path,
    before: dict[str, str] | None = None,
) -> None:
    """録画を書く。作業フォルダの絶対パスは <tree> に置き換える（機械ごとに違い、リポジトリに入れないため）。

    before（実行の前の snapshot）を渡すと、録画が触るファイルの開始時の sha256 を残す（無かったファイルは None）。
    再生はそれと今の作業ツリーを照合し、開始の状態が違えば止める。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "version": 1,
        "request": request,
        "result": asdict(result),
        "files": files,
    }
    if before is not None:
        data["start"] = {rel: before.get(rel) for rel in files}
    text = json.dumps(data, ensure_ascii=False, indent=1)
    # 相対の root（Path(".")）の文字列を全体から置換すると、prompt やファイル名のピリオドまで壊れる。絶対パスだけを置き換える
    text = text.replace(str(root.resolve()), TREE)
    path.write_text(text + "\n", encoding="utf-8")


class CassetteMismatch(Exception):
    pass


def play(path: Path, root: Path, request: dict[str, Any]) -> RunResult:
    """録画を再生する。依頼の中身が録画と違えば止める（古い録画で黙って通さないため）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["request"] != request:
        raise CassetteMismatch(
            f"{path.name} の依頼が今の依頼と違う。録り直す（edu-creator write --record）"
        )
    root = root.resolve()
    # 先に全部の行き先を確かめる。途中まで書いてから止まると、作業ツリーが半端な状態で残る
    for rel in data["files"]:
        if not (root / rel).resolve().is_relative_to(root):
            raise CassetteMismatch(f"{path.name} のファイル {rel!r} が作業ツリーの外を指している")
    start = data.get("start")
    if start is not None:
        for rel, want in start.items():
            have = root / rel
            got = (
                hashlib.sha256(have.read_bytes()).hexdigest()
                if have.is_file() and not have.is_symlink()
                else None
            )
            if got != want:
                raise CassetteMismatch(
                    f"{path.name} を録った時と {rel} の開始の状態が違う。録り直す（edu-creator write --record）"
                )
    for rel, content in data["files"].items():
        target = root / rel
        if content is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    r = data["result"]
    events = [Event(e["kind"], e["data"]) for e in r.pop("events")]
    return RunResult(events=events, **r)
