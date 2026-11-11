"""教材の検査（A3）。両教材で育った検査スクリプトを1つの版にまとめ、スタックの差は stack profile の qa で切り替える。

検査の本体は educreator/checks/qa/ にあり、どれも「教材のフォルダ（かファイル）を1つ受け取り、
問題があれば 0 以外で終わる」CLI。ここではそれを一覧にして、値を渡して起動する。
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from educreator.profiles import QaConfig, load_profile

QA_DIR = Path(__file__).parent / "qa"


@dataclass(frozen=True)
class CheckDef:
    id: str
    script: str
    summary: str
    # True ならファイルを1つずつ渡す（フォルダを渡すと落ちる検査）
    per_file: bool = False


# 取り込んだ順。統合のたびに足す（取り込み元・差分の扱いは docs/checks.md）
CHECKS: tuple[CheckDef, ...] = (
    CheckDef(
        "step-length", "check_step_length.py", "1つのコードブロックの行数の上限", per_file=True
    ),
    CheckDef("step-ref", "check_step_ref.py", "「Step N」への参照が実在する Step を指すか"),
    CheckDef("tone", "check_tone.py", "禁止の言い回し・AI 臭い文体", per_file=True),
    CheckDef("unused-image", "check_unused_image.py", "どこからも参照されない画像"),
    CheckDef("variants", "check_variants.py", "表記ゆれ"),
    CheckDef("setext-heading", "check_setext_heading.py", "下線式の見出し（意図しない見出し化）"),
    CheckDef("quiz", "check_quiz.py", "理解の確認の問答の書き方"),
    CheckDef("terms", "check_terms.py", "同じものを指す用語の割れ"),
    CheckDef(
        "fence-roles", "check_fence_roles.py", "コードブロックの役割（apply / expect）の書き方"
    ),
    CheckDef("crossref", "check_crossref.py", "「Day N で書いた」とファイルの対応"),
    CheckDef("no-skip", "check_no_skip.py", "Step に確認の手段と書き込み先があるか", per_file=True),
    CheckDef(
        "code-completeness",
        "check_code_completeness.py",
        "「省略」で切ったコードブロック",
        per_file=True,
    ),
    CheckDef("ja-latin-space", "check_ja_latin_space.py", "和文と英字の間の空白の有無の揃え"),
    CheckDef(
        "ja-line-break", "check_ja_line_break.py", "画面に出る日本語の文の、JSX の中での途中改行"
    ),
    CheckDef("step-time", "check_step_time.py", "所要時間の表の合計と本文の分数の一致"),
    CheckDef("why", "check_why.py", "写経のコードブロックの前に理由があるか"),
    CheckDef(
        "visualization", "check_visualization.py", "Step ごとの図・表・スクショ", per_file=True
    ),
    CheckDef(
        "comprehension",
        "check_comprehension.py",
        "専門用語の初出の注釈と確認ポイント",
        per_file=True,
    ),
    CheckDef(
        "tech-stack", "check_tech_stack.py", "技術の範囲（禁止のライブラリ・書き方）", per_file=True
    ),
    CheckDef(
        "anchor", "check_anchor.py", "コードブロックの書き込み先（続き・実在・読み比べ用の目印）"
    ),
    CheckDef("budget", "check_budget.py", "Day 予算（写経の行・ファイル・分）を本文から実測"),
    CheckDef(
        "forward-refs",
        "check_forward_refs.py",
        "後の Day で定義する名前を前の Day で使っていないか",
    ),
)


def get(check_id: str) -> CheckDef:
    for c in CHECKS:
        if c.id == check_id:
            return c
    raise KeyError(f"検査 '{check_id}' は無い。使えるもの: {', '.join(c.id for c in CHECKS)}")


def qa_config(
    profile: str,
    overrides: dict[str, Any],
    repo_root: Path,
    budget: dict[str, int] | None = None,
) -> dict[str, Any]:
    """stack profile の qa に、教材ごとの上書きを重ねる。上書きの値も同じ型で検める。

    budget は course-spec の budget（Day 予算の上限。check_budget が使う）。
    """
    base = load_profile(profile).qa.model_dump()
    merged = QaConfig.model_validate({**base, **overrides}).model_dump()
    merged["repo_root"] = str(repo_root.resolve())
    if budget is not None:
        merged["budget"] = budget
    return merged


@dataclass(frozen=True)
class CheckResult:
    check: CheckDef
    returncode: int
    output: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# 検査の対象にする教材のファイル（両教材の check_quality.sh と同じ規則）
MATERIAL_GLOBS = ("day[0-9][0-9]_*.md", "appendix_*.md")


@contextlib.contextmanager
def day_view(material: Path, chapters: list[tuple[int, str]]) -> Iterator[Path]:
    """章IDで名前を付けた教材を、検査が読める `dayNN_<章ID>.md` の並びに見せる一時フォルダ。

    取り込んだ検査は教材のファイルを `day[0-9][0-9]_*.md` で探す。検査の中身は取り込み元の形のまま変えず、
    章の並び順（course-spec の chapters）から名前を付けたシンボリックリンクを並べて渡す。
    画像などのフォルダもリンクで並べ、本文からの相対の参照が切れないようにする。
    """
    with tempfile.TemporaryDirectory(prefix="chapters-") as tmp:
        view = Path(tmp)
        for order, (_day, file) in enumerate(sorted(chapters), start=1):
            src = material / file
            if src.is_file():
                (view / f"day{order:02d}_{Path(file).stem}.md").symlink_to(src.resolve())
        for p in material.iterdir():
            if p.is_dir():
                (view / p.name).symlink_to(p.resolve(), target_is_directory=True)
        yield view


def material_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted({p for g in MATERIAL_GLOBS for p in target.rglob(g)})


def run_check(
    check: CheckDef, target: Path, config: dict[str, Any], timeout: float = 300
) -> CheckResult:
    # 子プロセスは cwd=repo_root で動く。相対のままの対象は、そこから見て別の場所を指してしまう
    target = target.resolve()
    env = dict(os.environ)
    env["EDU_CREATOR_QA_JSON"] = json.dumps(config, ensure_ascii=False)
    targets = material_files(target) if check.per_file else [target]
    if not targets:
        return CheckResult(check, 1, f"{target} に検査する教材のファイルが無い")
    rc, out = 0, []
    for t in targets:
        proc = subprocess.run(
            [sys.executable, str(QA_DIR / check.script), str(t)],
            cwd=config["repo_root"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rc = rc or proc.returncode
        text = (proc.stdout + proc.stderr).strip()
        if text:
            out.append(text)
    return CheckResult(check, rc, "\n".join(out))
