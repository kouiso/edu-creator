"""教材の検査（A3）。両教材で育った検査スクリプトを1つの版にまとめ、スタックの差は stack profile の qa で切り替える。

検査の本体は educreator/checks/qa/ にあり、どれも「教材のフォルダ（かファイル）を1つ受け取り、
問題があれば 0 以外で終わる」CLI。ここではそれを一覧にして、値を渡して起動する。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
)


def get(check_id: str) -> CheckDef:
    for c in CHECKS:
        if c.id == check_id:
            return c
    raise KeyError(f"検査 '{check_id}' は無い。使えるもの: {', '.join(c.id for c in CHECKS)}")


def qa_config(profile: str, overrides: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """stack profile の qa に、教材ごとの上書きを重ねる。上書きの値も同じ型で検める。"""
    base = load_profile(profile).qa.model_dump()
    merged = QaConfig.model_validate({**base, **overrides}).model_dump()
    merged["repo_root"] = str(repo_root.resolve())
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


def material_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted({p for g in MATERIAL_GLOBS for p in target.rglob(g)})


def run_check(
    check: CheckDef, target: Path, config: dict[str, Any], timeout: float = 300
) -> CheckResult:
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
