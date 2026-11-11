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
    # 並び順。naming が day なら Day の番号
    day: int = Field(ge=0)
    title: str
    file: str
    # naming が chapter-id のときの章ID（ファイル名は <id>.md）
    id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")


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


class JudgeSpec(Strict):
    """Judge（A6）の設定。較正（E-6）が済んだ次元だけを合否に使う。"""

    # 結果の置き場（spec の置き場からの相対）
    out_dir: str = "reports/judge"
    # 較正が済んだ次元（clarity・accessibility・engagement・actionability・self_containment）
    calibrated: list[str] = Field(default_factory=list)


class DesignSpec(Strict):
    """design の段（A13）。役割の振る舞いの表（書式は educreator/design.py の cell）の置き場。spec の置き場からの相対"""

    access: str | None = None
    out: str = "docs/design/screen-matrix.md"


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
    # 章ファイルの命名。day は dayNN_*.md、chapter-id は <章ID>.md（連番を名前に入れない教材）
    naming: Literal["day", "chapter-id"] = "day"
    distribution: Distribution
    chapters: list[Chapter] = Field(default_factory=list)
    replay: Replay | None = None
    judge: JudgeSpec = Field(default_factory=JudgeSpec)
    design: DesignSpec = Field(default_factory=DesignSpec)
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
        if self.naming == "chapter-id":
            bad = [c.file for c in self.chapters if not c.id or c.file != f"{c.id}.md"]
            if bad:
                raise ValueError(
                    f"naming が chapter-id なのに、file が <id>.md でない章がある: {bad}"
                )
        return self


class _UniqueKeyLoader(yaml.SafeLoader):
    """同じキーが2回ある YAML を拒否する。safe_load は後の値を残すので、前の `chapters` や `qa` が検証の前に消える。"""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise ValueError(
                    f"キー {key!r} が重複している（{key_node.start_mark.line + 1} 行目）"
                )
            seen.add(key)
        return super().construct_mapping(node, deep)


def load_spec(path: Path) -> CourseSpec:
    with path.open(encoding="utf-8") as f:
        data = yaml.load(f, Loader=_UniqueKeyLoader)
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
    if mdir.is_dir():
        # chapter-id の命名では、章ファイルは直下の .md（README.md などの本文でない物は除く）
        pattern = "day*.md" if spec.naming == "day" else "*.md"
        for p in sorted(mdir.glob(pattern)):
            if spec.naming == "chapter-id" and p.name == "README.md":
                continue
            if p.name not in listed:
                problems.append(f"{p.name} が chapters に無い")
    return problems
