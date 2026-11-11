"""学び台帳 knowledge/lessons.yaml の検査（E-7）。

規則: 同じ category が2回以上出たら、その category の項目はすべて enforced_by が空であってはならない。
「気をつける」で終わる対策を台帳に残さないため。1回目の項目でも enforced_by の書式は検査する。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

_ENFORCED = re.compile(r"^(check:[\w.-]+|skill:[\w.-]+/[\w.-]+:[\w.-]+(#.+)?|ci:[\w./-]+:[\w.-]+)$")


class Lesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^LS-\d{3,}$")
    date: str
    source: str
    category: str
    symptom: str
    root_cause: str
    enforced_by: list[str] = Field(default_factory=list)
    test: str = ""


def load_lessons(path: Path) -> list[Lesson]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # 空ファイルや lessons の無い YAML を「問題なしの空の台帳」にしない
    if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
        raise ValueError(f"{path} は mapping で、list の `lessons` が要る")
    return [Lesson.model_validate(x) for x in data["lessons"]]


def check_lessons(lessons: list[Lesson]) -> list[str]:
    problems: list[str] = []
    ids = Counter(x.id for x in lessons)
    problems += [f"{i}: ID が重複している" for i, n in ids.items() if n > 1]
    counts = Counter(x.category for x in lessons)
    for x in lessons:
        for e in x.enforced_by:
            if not _ENFORCED.match(e):
                problems.append(f"{x.id}: enforced_by の書式が違う: {e!r}")
        if counts[x.category] >= 2 and not x.enforced_by:
            problems.append(
                f"{x.id}: 分類 '{x.category}' は {counts[x.category]} 回目なのに enforced_by が空（検査か skill の規則にする）"
            )
    return problems
