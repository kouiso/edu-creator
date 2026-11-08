import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from educreator.cli import main
from educreator.lessons import Lesson, check_lessons, load_lessons
from educreator.profiles import available_profiles, load_profile
from educreator.spec import CourseSpec, check_chapters, load_spec

ROOT = Path(__file__).resolve().parents[2]

BASE = {
    "name": "sample",
    "days": 2,
    "learner": {"description": "未経験", "prior_code_lines_max": 100, "os": ["windows", "macos"]},
    "budget": {
        "minutes": 120,
        "new_concepts": 3,
        "files": 5,
        "copy_lines": 200,
        "code_block_lines": 25,
    },
    "stack_profile": "flask",
    "app_repo": ".",
    "material_dir": "material",
    "distribution": {"formats": ["pdf", "zip"]},
    "chapters": [
        {"day": 1, "title": "はじめての画面", "file": "day01_intro.md"},
        {"day": 2, "title": "ログイン", "file": "day02_login.md"},
    ],
}


def _spec_dir(tmp_path, data=BASE):
    (tmp_path / "material").mkdir()
    (tmp_path / "material" / "day01_intro.md").write_text(
        "# Day01 はじめての画面\n本文", encoding="utf-8"
    )
    (tmp_path / "material" / "day02_login.md").write_text("# Day02 ログイン\n", encoding="utf-8")
    p = tmp_path / "course-spec.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_profiles_all_load():
    assert {"flask", "nextjs", "expo"} <= available_profiles()
    for name in available_profiles():
        assert load_profile(name).name == name


def test_spec_ok_and_chapters_match(tmp_path):
    p = _spec_dir(tmp_path)
    spec = load_spec(p)
    assert check_chapters(spec, tmp_path) == []
    assert main(["spec", "check", str(p)]) == 0


def test_spec_detects_title_drift_and_unlisted_files(tmp_path):
    p = _spec_dir(tmp_path)
    (tmp_path / "material" / "day02_login.md").write_text("# Day02 認証\n", encoding="utf-8")
    (tmp_path / "material" / "day03_extra.md").write_text("# Day03\n", encoding="utf-8")
    problems = check_chapters(load_spec(p), tmp_path)
    assert any("タイトルが違う" in x and "Day02" in x for x in problems)
    assert any("day03_extra.md が chapters に無い" in x for x in problems)
    assert main(["spec", "check", str(p)]) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"unknown_key": 1},  # 知らないキーを黙って捨てない
        {"stack_profile": "rails"},
        {"chapters": [{"day": 3, "title": "x", "file": "x.md"}]},
        {
            "chapters": [
                {"day": 1, "title": "a", "file": "a.md"},
                {"day": 1, "title": "b", "file": "b.md"},
            ]
        },
    ],
)
def test_spec_rejects_bad_input(patch):
    with pytest.raises(ValidationError):
        CourseSpec.model_validate({**BASE, **patch})


def _lesson(i, cat, enforced=()):
    return Lesson(
        id=f"LS-{i:03d}",
        date="2026-11-08",
        source="s",
        category=cat,
        symptom="x",
        root_cause="y",
        enforced_by=list(enforced),
    )


def test_lessons_second_occurrence_without_enforcement_fails():
    assert check_lessons([_lesson(1, "a")]) == []  # 1回目は空でよい
    problems = check_lessons([_lesson(1, "a"), _lesson(2, "a", ["check:forward-refs"])])
    assert problems == [
        "LS-001: 分類 'a' は 2 回目なのに enforced_by が空（検査か skill の規則にする）"
    ]


def test_lessons_bad_enforced_format_and_dup_ids():
    problems = check_lessons([_lesson(1, "a", ["気をつける"]), _lesson(1, "b")])
    assert "LS-001: ID が重複している" in problems
    assert any("書式が違う" in p for p in problems)


def test_repo_ledger_passes():
    path = ROOT / "knowledge" / "lessons.yaml"
    lessons = load_lessons(path)
    assert {x.id for x in lessons} >= {"LS-001", "LS-002"}
    assert check_lessons(lessons) == []


# E-4: 特定のアプリや技術スタックの名前を、profiles/ の外のコードに直接書かない
_FORBIDDEN = re.compile(
    r"task-app|redmine|sns-app|Next\.?js|Flask|Expo\b|Prisma|Jinja", re.IGNORECASE
)


def test_no_hardcoded_stack_names_outside_profiles():
    hits = []
    for p in (ROOT / "educreator").rglob("*.py"):
        if "profiles" in p.relative_to(ROOT / "educreator").parts:
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if _FORBIDDEN.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()}")
    assert hits == []


def test_cli_check_runs_selected_checks_on_material(tmp_path, capsys):
    p = _spec_dir(tmp_path)
    assert main(["check", "--spec", str(p), "--list"]) == 0
    assert "no-skip" in capsys.readouterr().out
    # 書式の整った2日分は見出しと参照の検査を通る。スクショのフォルダが無ければ unused-image は落ちる
    assert main(["check", "--spec", str(p), "setext-heading", "step-ref"]) == 0
    assert main(["check", "--spec", str(p), "unused-image"]) == 1
    assert "画像がありません" in capsys.readouterr().out
    assert main(["check", "--spec", str(p), "nope"]) == 2


def test_spec_qa_overrides_are_validated():
    CourseSpec.model_validate({**BASE, "qa": {"gui_services": ["Render"]}})
    with pytest.raises(ValidationError, match="知らないキー"):
        CourseSpec.model_validate({**BASE, "qa": {"gui_service": ["typo"]}})


def test_license_is_all_rights_reserved_everywhere():
    # E-9 ③: LICENSE・pyproject・README の3か所が All Rights Reserved で一致する（U-17）
    import tomllib

    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "All rights reserved" in lic and "No permission is granted" in lic
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert meta["license"] == {"file": "LICENSE"}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## 📄 License", 1)[1]
    assert "All Rights Reserved" in section and "\nMIT\n" not in section
