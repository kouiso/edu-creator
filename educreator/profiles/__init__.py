"""stack profile。技術スタックごとの差分はここに閉じ込め、コードには固定の名前を書かない（E-4）。"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

_DIR = Path(__file__).parent


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
