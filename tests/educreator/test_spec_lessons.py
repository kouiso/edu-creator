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
    # skill の本文（.md）も、どの教材にも同じ文であるべきなので同じ決まりで見る
    files = [
        *(ROOT / "educreator").rglob("*.py"),
        *(ROOT / "educreator" / "agent-skill").rglob("*.md"),
    ]
    for p in files:
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


def test_chapter_id_naming(tmp_path):
    mat = tmp_path / "curriculum"
    mat.mkdir()
    (mat / "README.md").write_text("# 置き場の説明\n", encoding="utf-8")
    (mat / "expo-first-screen.md").write_text("# はじめての画面をスマホに出す\n", encoding="utf-8")
    (mat / "orphan.md").write_text("# 表に無い章\n", encoding="utf-8")
    data = {
        **BASE,
        "stack_profile": "expo",
        "material_dir": "curriculum",
        "naming": "chapter-id",
        "chapters": [
            {
                "day": 10,
                "id": "expo-first-screen",
                "title": "はじめての画面",
                "file": "expo-first-screen.md",
            }
        ],
        "days": 31,
    }
    spec = CourseSpec.model_validate(data)
    assert check_chapters(spec, tmp_path) == ["orphan.md が chapters に無い"]
    with pytest.raises(ValidationError, match=r"<id>\.md"):
        CourseSpec.model_validate(
            {**data, "chapters": [{"day": 1, "id": "a", "title": "x", "file": "b.md"}]}
        )


def test_check_runs_on_chapter_id_material(tmp_path, capsys):
    mat = tmp_path / "curriculum"
    (mat / "screenshots").mkdir(parents=True)
    (mat / "README.md").write_text("# 置き場\n", encoding="utf-8")
    (mat / "expo-first-screen.md").write_text(
        "# はじめての画面\n\n**合計時間**: 約30分\n\n## Step 1: 開く\n\n本文\n", encoding="utf-8"
    )
    (mat / "live-reload.md").write_text(
        "# 書き換え\n\n**合計時間**: 約30分\n\n本文\n", encoding="utf-8"
    )
    data = {
        **BASE,
        "stack_profile": "expo",
        "material_dir": "curriculum",
        "naming": "chapter-id",
        "days": 31,
        "chapters": [
            {"day": 20, "id": "live-reload", "title": "書き換え", "file": "live-reload.md"},
            {
                "day": 10,
                "id": "expo-first-screen",
                "title": "はじめての画面",
                "file": "expo-first-screen.md",
            },
        ],
    }
    p = tmp_path / "course-spec.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    # 章IDの名前のままでも、検査が章を拾う（並び順で day01・day02 として見せる）
    assert main(["check", "--spec", str(p), "setext-heading", "budget", "-v"]) == 0
    out = capsys.readouterr().out
    assert "| 01 |" in out and "| 02 |" in out


def test_spec_skills_default_is_empty_and_names_are_kept_in_order():
    assert CourseSpec.model_validate(BASE).skills == []
    spec = CourseSpec.model_validate({**BASE, "skills": ["material-writing", "course-mission"]})
    assert spec.skills == ["material-writing", "course-mission"]


def test_spec_skills_unknown_name_and_duplicates_are_rejected():
    with pytest.raises(ValidationError, match="skill 'nope' は無い。使えるもの: course-mission"):
        CourseSpec.model_validate({**BASE, "skills": ["nope"]})
    with pytest.raises(
        ValidationError, match=r"skills に同じ名前が 2 回ある: \['material-writing'\]"
    ):
        CourseSpec.model_validate({**BASE, "skills": ["material-writing", "material-writing"]})


def test_spec_skills_cli_exit_codes(tmp_path, capsys):
    bad = {**BASE, "skills": ["nope"]}
    p = _spec_dir(tmp_path, bad)
    assert main(["spec", "check", str(p)]) == 1
    err = capsys.readouterr().err
    assert "スキーマに合わない" in err and "skill 'nope' は無い" in err
    assert main(["check", "--spec", str(p), "--list"]) == 0  # 一覧は spec を読まない
    assert main(["check", "--spec", str(p), "step-ref"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("エラー: ") and "skill 'nope' は無い" in err
    typo = tmp_path / "typo"
    typo.mkdir()
    p2 = _spec_dir(typo, {**BASE, "skill": ["material-writing"]})
    assert main(["spec", "check", str(p2)]) == 1
    assert "Extra inputs are not permitted" in capsys.readouterr().err


def test_agent_skill_folders_have_matching_frontmatter():
    base = ROOT / "educreator" / "agent-skill"
    assert sorted(p.name for p in base.iterdir() if (p / "SKILL.md").is_file()) == [
        "course-mission",
        "curriculum-quality-gate",
        "material-writing",
    ]
    expected = {
        "course-mission": (
            "教材づくりの目的・完了の定義・持ち主の決定・制約・次の一手の選び方の型。"
            "値は依頼文の「教材」と「学習者」の行から読む。Step を書く前に読む。"
        ),
        "material-writing": (
            "教材の本文（Step）を書く・書き直す前に必ず読む。AI らしい言い回し・翻訳調・手順書化を防ぐ "
            "6 つの手順と文体の仕様、合格の物差し（reference/voice-spec.md）。"
        ),
        "curriculum-quality-gate": (
            "教材の検査は edu-creator が Step の後に回す。この実行の中では検査の命令を打たず、"
            "検査の結果が依頼文にあれば、その指摘を直す。"
        ),
    }
    for name, description in expected.items():
        head = (base / name / "SKILL.md").read_text(encoding="utf-8").split("\n")[:4]
        assert head == ["---", f"name: {name}", f"description: {description}", "---"]


def test_agent_skill_files_carry_nothing_machine_or_tool_specific():
    base = ROOT / "educreator" / "agent-skill"
    # 元の教材の置き場・元に残る道具・目印の文字列は、どの教材にも同じ文であるべき skill に入れない
    banned = (
        "/Users/",
        "/home/",
        "textlint",
        "check_quality",
        "writing-lint",
        "CANARY",
        ".claude/skills",
    )
    hits = []
    for p in base.rglob("*"):
        if p.suffix not in (".md", ".py"):
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            hits += [f"{p.relative_to(ROOT)}:{n}: {w}" for w in banned if w in line]
    assert hits == []
