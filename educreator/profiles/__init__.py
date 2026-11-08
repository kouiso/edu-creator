"""stack profile。技術スタックごとの差分はここに閉じ込め、コードには固定の名前を書かない（E-4）。"""

from __future__ import annotations

from functools import cache
from typing import Any
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

_DIR = Path(__file__).parent


class QaConfig(BaseModel):
    """検査（educreator/checks/qa）に渡すスタックごとの値。教材ごとの上書きは course-spec の qa に書く。"""

    model_config = ConfigDict(extra="forbid")

    # 写経対象として扱うコードブロックの言語。端末で打つ bash は入れない
    code_langs: list[str] = Field(min_length=1)
    # 読者が実際に書くファイルの置き場の頭
    real_prefixes: list[str] = Field(min_length=1)
    # 読者が実際に書く、ルート直下のファイル
    real_root_files: list[str] = Field(default_factory=list)
    # ルート直下のファイルを、配布の区分の表（区分が「写経」のもの）からも足す。教材のリポジトリからの相対
    real_root_files_manifest: str | None = None
    # 文と文の対応づけ（check_crossref）で、どの Day の話でもない語として外すもの
    crossref_ignore: list[str] = Field(default_factory=list)
    # ブラウザで操作する手順だと分かる語に足す、公開先のサービス名（check_no_skip）
    gui_services: list[str] = Field(default_factory=list)
    # 要素の中の改行を空白に畳んで描画する JSX の言語（check_ja_line_break。無ければ何も見ない）
    jsx_langs: list[str] = Field(default_factory=list)
    # 初出で注釈を求める専門用語（check_comprehension）
    tech_terms: list[str] = Field(default_factory=list)
    # 技術の範囲（check_tech_stack）。forbidden: [[正規表現, 表示名]]、expect: [正規表現]、文面（msg_*）
    tech_stack: dict[str, Any] = Field(default_factory=dict)
    # 以下は教材で決まる値（course-spec の qa に書く）
    # 所要時間の表を持たない Day（check_step_time）
    no_table_days: list[int] = Field(default_factory=list)
    # スクショを免除する教材のファイル名と理由（check_visualization）
    screenshot_exempt: dict[str, str] = Field(default_factory=dict)
    # mermaid の図を必須にする Day（check_visualization）
    required_mermaid_days: list[int] = Field(default_factory=list)


class StackProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    language: str
    # コードブロックの1行目に置く書き込み先の書き方。拡張子ごと。{path} を置き換える
    filepath_comment: dict[str, str] = Field(min_length=1)
    install: list[str]
    start: list[str]
    test: list[str]
    url: str
    ready_path: str = "/"
    qa: QaConfig


@cache
def available_profiles() -> frozenset[str]:
    return frozenset(p.stem for p in _DIR.glob("*.yaml"))


def load_profile(name: str) -> StackProfile:
    p = _DIR / f"{name}.yaml"
    if not p.is_file():
        raise ValueError(
            f"stack profile '{name}' は無い。使えるもの: {', '.join(sorted(available_profiles()))}"
        )
    return StackProfile.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
