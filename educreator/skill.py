"""書き方の決まり（skill）を、Step を書く実行に渡す仕組み（docs/skill-integration.md の 2）。

skill の本文は `educreator/agent-skill/<名前>/` にある。Claude Code には plugin として実行の間だけ読み込ませ
（hook で「読まずに書く」を止める）、Codex には本文をプロンプトの頭に埋め込む。
作業フォルダ（学習者のツリー）には何も書かない。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from educreator.spec import CourseSpec

SKILL_DIR = Path(__file__).parent / "agent-skill"
# skill 1 つのフォルダの中で、数える・写すファイルの全部。これ以外（__pycache__・*.pyc・.DS_Store など）は無い物として扱う
SOURCE_GLOBS = ("SKILL.md", "reference/*.md", "hook/*.py")
# stage した plugin のフォルダ（edu-creator/）の中で数えるファイルの全部
PLUGIN_GLOBS = (
    ".claude-plugin/plugin.json",
    "skills/*/SKILL.md",
    "skills/*/reference/*.md",
    "hooks/*.py",
    "hooks/hooks.json",
    "hooks/target.json",
)
PLUGIN_NAME = "edu-creator"
# 関門の hook の onFailure が使える Claude Code の最低の版
MIN_CLAUDE_VERSION = (2, 1, 295)

_TARGET_ARG = "${CLAUDE_PLUGIN_ROOT}/hooks/target.json"
# (時機, matcher, hook のファイル名, onFailure)。onFailure は関門だけに付ける
HOOKS: tuple[tuple[str, str, str, str | None], ...] = (
    ("PreToolUse", "Write|Edit|NotebookEdit|Bash", "material_writing_gate.py", "block"),
    ("PreToolUse", "Write|Edit", "material_writing_reminder.py", None),
    ("PostToolUse", "Skill", "material_writing_marker.py", None),
)

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_VERSION = re.compile(r"\d+\.\d+\.\d+")


def available_skills() -> list[str]:
    """SKILL.md を持つ skill のフォルダ名を並べて返す。"""
    if not SKILL_DIR.is_dir():
        return []
    return sorted(p.name for p in SKILL_DIR.iterdir() if (p / "SKILL.md").is_file())


def _files(root: Path, globs: tuple[str, ...]) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_symlink() or not p.is_file():
                continue
            found[p.relative_to(root).as_posix()] = p
    return [found[k] for k in sorted(found)]


def tree_hash(root: Path, globs: tuple[str, ...]) -> str:
    """root の下で globs に当たるファイルの、パスと中身の sha256（16 進 64 桁）。"""
    h = hashlib.sha256()
    for p in _files(root, globs):
        body = p.read_bytes()
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0" + str(len(body)).encode("ascii") + b"\0")
        h.update(body)
    return h.hexdigest()


def source_digest(names: tuple[str, ...] | list[str]) -> str:
    """選んだ skill の中身の印。録画の照合だけに使う（skill を直したのに古い録画が通るのを防ぐ）。"""
    joined = "".join(f"{n}\0{tree_hash(SKILL_DIR / n, SOURCE_GLOBS)}" for n in names)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def course_facts(spec: CourseSpec) -> str:
    """教材に固有の値を、依頼文に入れる 2 行にする（skill の文はどの教材にも同じなので、値は実行の時に渡す）。"""
    formats = "、".join(spec.distribution.formats)
    return (
        f"- 教材: {spec.name}（全 {spec.days} 日。配布: {formats}。技術: {spec.stack_profile}）\n"
        f"- 学習者: {spec.learner.description}\n"
    )


def claude_version(executable: str) -> str:
    """`<executable> --version` の最初の `数字.数字.数字` を返す。分からなければ RuntimeError。"""
    try:
        proc = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"{executable} の版を読めなかった: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"{executable} --version が終了コード {proc.returncode} で終わった")
    m = _VERSION.search(proc.stdout)
    if m is None:
        raise RuntimeError(f"{executable} --version の出力に版が無い: {proc.stdout.strip()!r}")
    return m.group(0)


def version_tuple(version: str) -> tuple[int, ...]:
    m = _VERSION.search(version)
    if m is None:
        raise RuntimeError(f"版の形が違う: {version!r}")
    return tuple(int(x) for x in m.group(0).split("."))


def _skill_body(skill_md: Path) -> str:
    return _FRONTMATTER.sub("", skill_md.read_text(encoding="utf-8"), count=1)


def embed(names: tuple[str, ...] | list[str]) -> str:
    """Codex に渡す、skill の本文のかたまり（SKILL.md の frontmatter は除く。hook は入れない）。"""
    parts = ["以下は、この作業で守る書き方の決まり（skill）。作業の前に全部読む。\n"]
    for name in names:
        base = SKILL_DIR / name
        parts.append(f"===== skill: {name} =====\n")
        parts.append(_skill_body(base / "SKILL.md"))
        for ref in sorted((base / "reference").glob("*.md"), key=lambda p: p.name):
            if ref.is_symlink() or not ref.is_file():
                continue
            parts.append(f"\n----- {name}/reference/{ref.name} -----\n")
            parts.append(ref.read_text(encoding="utf-8"))
    parts.append("\n===== ここまで =====")
    return "".join(parts)


def _hooks_json(hook_files: set[str]) -> dict[str, Any]:
    hooks: dict[str, list[dict[str, Any]]] = {}
    for event, matcher, filename, on_failure in HOOKS:
        if filename not in hook_files:
            continue
        entry: dict[str, Any] = {
            "type": "command",
            "command": sys.executable,
            "args": [f"${{CLAUDE_PLUGIN_ROOT}}/hooks/{filename}", _TARGET_ARG],
        }
        if on_failure is not None:
            entry["onFailure"] = on_failure
        hooks.setdefault(event, []).append({"matcher": matcher, "hooks": [entry]})
    return {"hooks": hooks}


def _write_plugin(
    root: Path, names: tuple[str, ...] | list[str], guarded: Path, marker: Path
) -> None:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": PLUGIN_NAME}, ensure_ascii=False), encoding="utf-8"
    )
    hook_files: set[str] = set()
    (root / "hooks").mkdir()
    for name in names:
        src = SKILL_DIR / name
        for p in _files(src, ("SKILL.md", "reference/*.md")):
            dest = root / "skills" / name / p.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
        for p in _files(src, ("hook/*.py",)):
            shutil.copyfile(p, root / "hooks" / p.name)
            hook_files.add(p.name)
    (root / "hooks" / "hooks.json").write_text(
        json.dumps(_hooks_json(hook_files), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "hooks" / "target.json").write_text(
        json.dumps(
            {"guarded_dir": os.path.realpath(guarded), "marker_dir": os.path.realpath(marker)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _intact(folder: Path) -> bool:
    """plugin-<16 桁>/ が、digest.txt どおりの中身で名前とも合っているか。"""
    digest = folder / "digest.txt"
    plugin = folder / PLUGIN_NAME
    if not digest.is_file() or not plugin.is_dir():
        return False
    recorded = digest.read_text(encoding="utf-8").strip()
    return recorded == tree_hash(plugin, PLUGIN_GLOBS) and folder.name == f"plugin-{recorded[:16]}"


def stage_plugin(names: tuple[str, ...] | list[str], guarded_dir: Path) -> Path:
    """選んだ skill を、その実行の間だけ読み込ませる plugin のフォルダ（edu-creator/）にして返す。

    同じ中身なら作り直さず使い回す。途中で止まった・書き換えられた物は、ほかの実行の claude が
    使っている途中かもしれないので、消しも名前の変更もせず、別の名前で作り直す。
    """
    from educreator.runtime.base import private_dir

    base = private_dir()
    marker = base / "marker"
    marker.mkdir(mode=0o700, exist_ok=True)
    tmp = base / f"plugin-new.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    plugin = tmp / PLUGIN_NAME
    try:
        _write_plugin(plugin, names, guarded_dir, marker)
        digest = tree_hash(plugin, PLUGIN_GLOBS)
        (tmp / "digest.txt").write_text(digest, encoding="utf-8")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    final = base / f"plugin-{digest[:16]}"
    try:
        os.rename(tmp, final)
    except OSError:
        # 同じ名前が先にある（別の実行が先に作った）。確かめて使えれば使う
        if _intact(final):
            shutil.rmtree(tmp, ignore_errors=True)
            return final / PLUGIN_NAME
        alt = base / f"plugin-{digest[:16]}.{os.getpid()}.{secrets.token_hex(4)}"
        os.rename(tmp, alt)
        return alt / PLUGIN_NAME
    return final / PLUGIN_NAME
