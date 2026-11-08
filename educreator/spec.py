"""course-spec.yaml のスキーマ。

教材の仕様（学習者像・日数・1日の予算・stack profile・配布形式・章立て）の正本はこの1枚にする。
今の edu-config.yaml のように実ファイルとずれた設定を作らないため、章立ては実ファイルとの一致を検査する（G10）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from educreator.profiles import QaConfig, available_profiles


class Strict(BaseModel):
    # 知らないキーは黙って捨てずに落とす（今の edu-config.yaml は設定の一部が黙って捨てられていた）
    model_config = ConfigDict(extra="forbid")


class Learner(Strict):
    description: str
    prior_code_lines_max: int = Field(
        ge=0, description="これまでに書いたコードの行数の上限（試行者の参加条件にも使う）"
    )
    os: list[Literal["windows", "macos", "linux"]] = Field(min_length=1)


class DayBudget(Strict):
    minutes: int = Field(gt=0)
    new_concepts: int = Field(gt=0)
    files: int = Field(gt=0)
    copy_lines: int = Field(gt=0, description="写経する行数の上限")
    code_block_lines: int = Field(gt=0, description="1つのコードブロックの行数の上限")


class Chapter(Strict):
    day: int = Field(ge=0)
    title: str
    file: str


class Distribution(Strict):
    formats: list[Literal["pdf", "zip", "starter-per-day"]] = Field(min_length=1)
    manifest_product: str | None = None


class Shot(Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    path: str
    login: bool = False


class Login(Strict):
    path: str
    # {CSS セレクタ: 入れる値}
    fields: dict[str, str]
    submit: str


class Replay(Strict):
    """写経リプレイ（edu-creator replay）で Day のツリーを取り出す元と、Day ごとに確かめる道。"""

    kind: Literal["git", "dirs"]
    # git ならタグを持つリポジトリ、dirs なら Day ごとのフォルダの親。spec の置き場からの相対
    root: str
    # Day のツリーの名前。{nn} は2桁、{n} はそのままの Day 番号（例: day-{nn}-end、day{nn}）
    pattern: str
    install: bool = True
    # 入れた後、起動の前に打つコマンド（学習者が本文で打つもの。例: .env を作る、DB を作る）。Day に依らず同じ
    setup: list[list[str]] = Field(default_factory=list)
    # {Day: {道: 期待する状態コード}}。ready_path（profile）は全 Day で 200 を見る
    paths: dict[int, dict[str, int]] = Field(default_factory=dict)
    # 撮影（A7a）。{Day: [{name, path, login}]}。login が true の画面は先に login の手順でログインする
    shots: dict[int, list[Shot]] = Field(default_factory=dict)
    login: Login | None = None
    # スクショの置き場（spec の置き場からの相対）。Day ごとに dayNN/ を作る
    shots_dir: str = "build/shots"

    @field_validator("pattern")
    @classmethod
    def _has_day(cls, v: str) -> str:
        if "{nn}" not in v and "{n}" not in v:
            raise ValueError("pattern に {nn} か {n} が無い")
        return v


class CourseSpec(Strict):
    spec_version: Literal[1] = 1
    name: str
    days: int = Field(gt=0)
    learner: Learner
    budget: DayBudget
    stack_profile: str
    app_repo: str = Field(
        description="正解のコード（最終形のアプリ）のリポジトリのパス。spec の置き場からの相対"
    )
    material_dir: str
    distribution: Distribution
    chapters: list[Chapter] = Field(default_factory=list)
    replay: Replay | None = None
    # 検査に渡す値の、教材ごとの上書き（stack profile の qa を上書きする。公開先のサービス名など教材で決まるもの）
    qa: dict[str, Any] = Field(default_factory=dict)

    @field_validator("qa")
    @classmethod
    def _known_qa_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(v) - set(QaConfig.model_fields))
        if unknown:
            raise ValueError(f"qa に知らないキーがある: {unknown}")
        return v

    @field_validator("stack_profile")
    @classmethod
    def _known_profile(cls, v: str) -> str:
        names = available_profiles()
        if v not in names:
            raise ValueError(f"stack profile '{v}' は無い。使えるもの: {', '.join(sorted(names))}")
        return v

    @model_validator(mode="after")
    def _chapters_consistent(self) -> CourseSpec:
        days = [c.day for c in self.chapters]
        if len(set(days)) != len(days):
            raise ValueError("chapters の day が重複している")
        over = [d for d in days if d > self.days]
        if over:
            raise ValueError(f"chapters に days（{self.days}）を超える day がある: {over}")
        return self


def load_spec(path: Path) -> CourseSpec:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} の中身が mapping ではない")
    return CourseSpec.model_validate(data)


_HEADING = re.compile(r"^#\s+(.+?)\s*$")


def first_heading(md: Path) -> str | None:
    for line in md.read_text(encoding="utf-8").splitlines():
        m = _HEADING.match(line)
        if m:
            return m.group(1)
    return None


def check_chapters(spec: CourseSpec, base: Path) -> list[str]:
    """章立てと実ファイルの食い違いを返す（空なら一致）。タイトルは本文の最初の `# ` 見出しと比べる。"""
    problems: list[str] = []
    mdir = base / spec.material_dir
    for c in spec.chapters:
        p = mdir / c.file
        if not p.is_file():
            problems.append(f"Day{c.day:02d}: {p} が無い")
            continue
        h = first_heading(p)
        if h is None:
            problems.append(f"Day{c.day:02d}: {p} に `# ` 見出しが無い")
        elif c.title not in h:
            problems.append(f"Day{c.day:02d}: タイトルが違う（spec: {c.title!r} / 本文: {h!r}）")
    listed = {c.file for c in spec.chapters}
    if mdir.is_dir() and spec.chapters:
        for p in sorted(mdir.glob("day*.md")):
            if p.name not in listed:
                problems.append(f"{p.name} が chapters に無い")
    return problems
